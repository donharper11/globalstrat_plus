"""The bounded adversarial tournament: 15 targeted candidates, then holdout.

Discovery: every candidate against the competent, diverse and incumbent
populations on one fixture identity. Selection: the strongest three by
performance across *all* populations, never by a win in one. Holdout: those
three against the same three populations on three previously unused fixture
identities, evaluation only.

Advantage is measured against what the same team scores playing the documented
baseline against the same opponents on the same identity. Opponents and
identities both change what a raw index means, so only that gap is comparable
across cells.
"""
import random
import statistics
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import fixture as F
import search_body as S
import targeted as T

DISCOVERY_SEED = 'crv2-06-tournament-discovery'
DIVERSE_SEED = 'crv2-06-tournament-diverse'
HOLDOUT_SEEDS = ('crv2-06-holdout-1', 'crv2-06-holdout-2', 'crv2-06-holdout-3')
POPULATIONS = ('competent', 'diverse', 'incumbent')
FINALISTS = 3


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('tournament', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import Game, Team

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    opponents = [t for t in teams if t.id != subject.id]

    # The diverse population is fixed across every cell. Holdout varies fixture
    # identity and nothing else, so a difference there is the fixture rather
    # than a different set of rivals.
    diverse_rng = random.Random(DIVERSE_SEED)
    diverse = {t.id: S.random_candidate(diverse_rng) for t in opponents}

    # Every payload must be legal under the final rules before anything is
    # measured. The first tournament's incumbent population played
    # `equity-raise`, which the adopted V2-024 rule rejects, so one of its
    # three populations could not legally exist.
    F.apply(game, DISCOVERY_SEED)
    game.refresh_from_db()
    from core.models import Round as _Round
    rnd_for_contract = _Round.objects.get(
        game=game, round_number=game.current_round)
    contract_payloads = {
        'baseline': lambda team: None,
        'diverse': lambda team: diverse.get(team.id),
    }
    for candidate in T.CANDIDATES:
        contract_payloads[f"candidate:{candidate['name']}"] = (
            lambda team, _g=candidate['genome']: _g)
    contract = S.check_payload_contract(
        game, rnd_for_contract, teams, contract_payloads)
    illegal = [label for label, r in contract.items() if not r['legal']]

    started = time.time()
    report = {
        'payload_contract': contract,
        'illegal_payloads': illegal,
        'discovery_seed': DISCOVERY_SEED,
        'diverse_seed': DIVERSE_SEED,
        'holdout_seeds': list(HOLDOUT_SEEDS),
        'discovery_identity': F.identity_for(DISCOVERY_SEED),
        'holdout_identities': {s: F.identity_for(s) for s in HOLDOUT_SEEDS},
        'rounds_per_candidate': S.ROUNDS_PER_CANDIDATE,
        'subject_team': subject.name,
        'field_size': len(teams),
        'candidates': [{'name': c['name'], 'family': c['family'],
                        'attacks': c['attacks'], 'genome': c['genome']}
                       for c in T.CANDIDATES],
        'evaluations': {'discovery_candidates': 0, 'discovery_baselines': 0,
                        'holdout_candidates': 0, 'holdout_baselines': 0},
    }

    def populations_for(incumbent):
        return {
            'competent': lambda team: None,
            'diverse': lambda team: diverse[team.id],
            'incumbent': lambda team: incumbent,
        }


    # ---- discovery -----------------------------------------------------
    F.apply(game, DISCOVERY_SEED)
    discovery = {}

    # A provisional incumbent is needed before the incumbent population can
    # exist. It is the strongest targeted candidate against competent
    # opponents, chosen in a first pass, exactly as the discovery batch did.
    competent_baseline = S.score(
        S.evaluate(game, subject, None, lambda t: None), subject.id)
    competent_repeat = S.score(
        S.evaluate(game, subject, None, lambda t: None), subject.id)
    report['evaluations']['discovery_baselines'] += 2
    report['discovery_baseline_repeatable'] = (
        competent_repeat == competent_baseline)

    first_pass = []
    for candidate in T.CANDIDATES:
        fitness = S.score(
            S.evaluate(game, subject, candidate['genome'], lambda t: None),
            subject.id, competent_baseline)
        first_pass.append({'name': candidate['name'], 'fitness': fitness})
        report['evaluations']['discovery_candidates'] += 1
        if verbose:
            print(f"  competent  {candidate['name']:<24} "
                  f"advantage {fitness['advantage']:>8.3f}", flush=True)

    leader = max(first_pass, key=lambda r: r['fitness']['advantage'])
    incumbent = next(c['genome'] for c in T.CANDIDATES
                     if c['name'] == leader['name'])
    # The incumbent becomes an opponent population, so it must be a legal
    # payload for every team, not only for the subject that played it.
    incumbent_contract = S.check_payload_contract(
        game, rnd_for_contract, teams,
        {'incumbent': lambda team, _g=incumbent: _g})
    report['incumbent_contract'] = incumbent_contract
    if not incumbent_contract['incumbent']['legal']:
        raise S.IllegalPayload(
            f"the leading candidate {leader['name']} is not a legal opponent "
            f"population: {incumbent_contract['incumbent']['problems']}")
    report['incumbent'] = {'name': leader['name'],
                           'advantage_vs_competent': leader['fitness']['advantage']}

    discovery['competent'] = {
        'baseline': competent_baseline,
        'baseline_is_repeatable': report['discovery_baseline_repeatable'],
        'rows': first_pass,
    }

    for label in ('diverse', 'incumbent'):
        opponent_for = populations_for(incumbent)[label]
        base = S.score(S.evaluate(game, subject, None, opponent_for), subject.id)
        repeat = S.score(S.evaluate(game, subject, None, opponent_for), subject.id)
        report['evaluations']['discovery_baselines'] += 2
        rows = []
        for candidate in T.CANDIDATES:
            fitness = S.score(
                S.evaluate(game, subject, candidate['genome'], opponent_for),
                subject.id, base)
            rows.append({'name': candidate['name'], 'fitness': fitness})
            report['evaluations']['discovery_candidates'] += 1
            if verbose:
                print(f"  {label:<10} {candidate['name']:<24} "
                      f"advantage {fitness['advantage']:>8.3f}", flush=True)
        discovery[label] = {'baseline': base,
                            'baseline_is_repeatable': repeat == base,
                            'rows': rows}

    report['discovery'] = discovery

    # ---- selection: across populations, never a win in one -------------
    by_name = {}
    for label in POPULATIONS:
        for row in discovery[label]['rows']:
            by_name.setdefault(row['name'], {})[label] = \
                row['fitness']['advantage']

    summary = []
    for name, per_population in by_name.items():
        values = [per_population[label] for label in POPULATIONS]
        summary.append({
            'name': name,
            'advantage_by_population': per_population,
            'worst_case': min(values),
            'median': statistics.median(values),
            'mean': round(statistics.fmean(values), 4),
            'wins_every_population': all(v > 0 for v in values),
        })
    # Worst-case first, median as the tie-break: a candidate that is strong
    # everywhere outranks one that is spectacular against a single population
    # and poor against the rest, which is the whole point of three populations.
    summary.sort(key=lambda r: (r['worst_case'], r['median']), reverse=True)
    report['discovery_summary'] = summary
    finalists = [row['name'] for row in summary[:FINALISTS]]
    report['finalists'] = finalists

    # ---- holdout: evaluation only, three unused identities -------------
    genome_of = {c['name']: c['genome'] for c in T.CANDIDATES}
    holdout = {}
    for seed in HOLDOUT_SEEDS:
        identity = F.apply(game, seed)
        per_identity = {}
        for label in POPULATIONS:
            opponent_for = populations_for(incumbent)[label]
            base = S.score(S.evaluate(game, subject, None, opponent_for),
                           subject.id)
            report['evaluations']['holdout_baselines'] += 1
            rows = []
            for name in finalists:
                fitness = S.score(
                    S.evaluate(game, subject, genome_of[name], opponent_for),
                    subject.id, base)
                rows.append({'name': name, 'fitness': fitness})
                report['evaluations']['holdout_candidates'] += 1
                if verbose:
                    print(f"  holdout {seed[-1]} {label:<10} {name:<24} "
                          f"advantage {fitness['advantage']:>8.3f}", flush=True)
            per_identity[label] = {'baseline': base, 'rows': rows}
        holdout[seed] = {'identity': identity, 'populations': per_identity}
    report['holdout'] = holdout

    # ---- the distribution the handoff asks for -------------------------
    final = []
    for name in finalists:
        cells = []
        for seed in HOLDOUT_SEEDS:
            for label in POPULATIONS:
                row = next(r for r in holdout[seed]['populations'][label]['rows']
                           if r['name'] == name)
                cells.append({'seed': seed, 'population': label,
                              'advantage': row['fitness']['advantage'],
                              'index': row['fitness']['index'],
                              'field_margin': row['fitness']['field_margin'],
                              'rank': row['fitness']['rank']})
        advantages = [c['advantage'] for c in cells]
        final.append({
            'name': name,
            'cells': cells,
            'distribution': sorted(advantages),
            'worst_case_population_margin': min(advantages),
            'median_margin': statistics.median(advantages),
            'mean_margin': round(statistics.fmean(advantages), 4),
            'best_case': max(advantages),
            'wins_every_cell': all(a > 0 for a in advantages),
            'cells_won': sum(1 for a in advantages if a > 0),
            'cells_total': len(advantages),
        })
    final.sort(key=lambda r: (r['worst_case_population_margin'],
                              r['median_margin']), reverse=True)
    report['holdout_summary'] = final
    report['any_candidate_wins_everywhere'] = any(
        row['wins_every_cell'] for row in final)
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
