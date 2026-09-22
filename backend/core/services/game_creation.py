"""THE game builder: one implementation, every creation path calls it (V2-112).

There are two registered entry points that create a game in runtime code —
``POST /api/games/create/`` (``GameCreateView``) and ``manage.py
initialize_game`` (which ``setup_test_game``, ``load_demo``,
``run_deadline_rehearsal``, the ``run_*_test`` commands and the evidence
harnesses call). Each used to carry its own copy of the team-building loop, and
the copies had drifted:

  * the command read only the ``alpha`` platform block, created ONE platform
    and attached both starter products to it, so the ``beta`` block every
    shipped profile authors was loaded and never used;
  * the view built one platform per authored label, honoured
    ``FirmStarterProduct.platform_label``, and zero-filled every platform
    feature the profile does not author.

Round-zero adoption is apportioned on the best level across a team's platforms
(``bootstrap._round_zero_fit``), so the same scenario opened on different
published round-0 rows depending on which path built the heat. Two heats have
to be comparable, so there is now exactly one builder and it is this one.

WHICH COPY WON, AND WHY. The command's: ONE starting platform per team, built
from the ``alpha`` block, carrying both starter products. Not by preference --
by the engine's own rule. ``_run_phase_1`` refuses a round while
``rd_costs.duplicate_platform_state`` is non-empty ("a team develops one
platform per generation", V2-046 / V2-047), and the view's copy created an
``alpha`` AND a ``beta`` platform on the same starting generation for every
team. A heat created through the instructor route could therefore never have
resolved round 1. (It could not be created either: the route answered 500 to
every JWT-authenticated instructor. See ``GameCreateView``.) The command's
shape is the only one the engine scores, it is the shape every replay, balance
and playthrough record in this programme was measured on, and keeping it
byte-for-byte means none of that evidence is invalidated by this repair.

THE AUTHORED ``beta`` BLOCK IS STILL UNUSED, and that is now a statement about
the scenarios rather than about one path. Honouring it needs either a second
starting generation or a relaxation of one-platform-per-generation; both are
rules decisions for the competition owner and neither is taken here. What this
module guarantees is narrower and is what V2-112 asked for: there is no longer
a path on which the block means something different.

WHAT IS DELIBERATELY NOT IN HERE. Lifecycle. The view leaves a new game in
``setup`` for the instructor to activate after assigning students; the command
opens round 1 because its callers want a playable game. Both do that *after*
this function returns, on a field this function built. The section link
(``section_id`` and the ``SimulationInstance`` bridge) is here because it is
part of creating the game, and is simply absent when no section is given.

ORDERING (V2-111, same call sites). Profiles, platform configs and starter
products are read in primary-key order — the order ``load_scenario`` wrote
them, which is the order they are authored in. Which team receives which
profile therefore no longer rests on database return order.
"""
import json
import random

from django.db import transaction

from core.models.cc31_models import TeamMarketCompliance
from core.models.cc32b_models import (
    OrganizationalStructureType, TeamOrganizationalStructure,
)
from core.models.core import Game, Round, Team
from core.models.scenario import (
    EntryModeDefinition, FeatureDefinition, FirmStarterPlatformConfig,
    FirmStarterProduct, FirmStarterProfile, MarketDefinition,
    PlatformGenerationDefinition, ScenarioConfig,
)
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    RoundResultMarketRevenue, RoundResultProductMarket,
)
from core.models.team_state import (
    TeamMarketPresence, TeamPlatform, TeamPlatformFeatureLevel, TeamProduct,
    TeamProductMarket, TeamStrategyFeatureLevel,
)

# Default company names used when no scenario-specific names are configured.
DEFAULT_COMPANY_NAMES = [
    'Nexus Dynamics', 'Aether Industries', 'Solaris Corp',
    'Zenith Innovations', 'Orion Collective', 'Helios Ventures',
    'Vantage Systems', 'Prism Technologies', 'Astra Enterprises',
    'Vertex Global', 'Nova Synthetica', 'Quantum Forge',
    'Eclipse Digital', 'Cipher Networks', 'Parallax Labs',
    'Meridian Works', 'Stratos Group', 'Axiom Devices',
    'Pulse Robotics', 'Titan Microtech', 'Lumen Industries',
    'Catalyst Corp', 'Helix Foundry', 'Aegis Solutions',
    'Photon Systems', 'Nebula Dynamics', 'Tesseract Inc',
    'Arc Innovations', 'Cobalt Ventures', 'Apex Synergies',
]

# The authored block a team's single starting platform is built from.
STARTING_PLATFORM_LABEL = 'alpha'


class GameCreationError(ValueError):
    """The scenario cannot produce a game; the message says what is missing.

    The message is English: the management command prints it. `key` and
    `values` name the same sentence in `core.utils.operator_messages`, so the
    console route can say it in the instructor's language.
    """

    def __init__(self, message, *, key=None, **values):
        super().__init__(message)
        self.key = key
        self.values = values


def get_company_names(scenario):
    """Return a shuffled list of company names for team creation."""
    cfg = ScenarioConfig.objects.filter(
        scenario=scenario, config_key='company_names',
    ).first()
    if cfg:
        try:
            names = json.loads(cfg.config_value)
            if isinstance(names, list) and names:
                random.shuffle(names)
                return names
        except (json.JSONDecodeError, TypeError):
            pass
    names = list(DEFAULT_COMPANY_NAMES)
    random.shuffle(names)
    return names


def resolve_home_markets(scenario, codes):
    """Market codes -> ``MarketDefinition`` rows, or refuse naming the bad one."""
    markets = []
    for code in codes or []:
        market = MarketDefinition.objects.filter(
            scenario=scenario, code__iexact=str(code).strip()).first()
        if not market:
            raise GameCreationError(
                f"Market code '{code}' not found in scenario '{scenario.name}'.",
                key='game_creation_market_unknown', code=str(code),
                scenario=scenario.name)
        markets.append(market)
    return markets


def create_game(scenario, num_teams, *, name, created_by,
                home_market_overrides=None, section_id=None):
    """Build a game, its teams, their starting state and round 0.

    Returns ``(game, teams)`` where ``teams`` is a list of dicts carrying the
    ``team``, its ``profile`` and its ``home_market``, in creation order. The
    game is left in ``setup`` with round 0 processed and every later round
    pending; activating it is the caller's decision.
    """
    profiles = list(
        FirmStarterProfile.objects.filter(scenario=scenario).order_by('id'))
    if not profiles:
        raise GameCreationError(
            f"No starter profiles found for scenario '{scenario.name}'.",
            key='game_creation_no_starter_profiles', scenario=scenario.name)

    starting_gen = PlatformGenerationDefinition.objects.filter(
        scenario=scenario, is_starting_platform=True).order_by('id').first()
    if not starting_gen:
        raise GameCreationError(
            f"No starting platform generation found for scenario "
            f"'{scenario.name}'.",
            key='game_creation_no_starting_platform', scenario=scenario.name)

    default_entry_mode = EntryModeDefinition.objects.filter(
        scenario=scenario).order_by('capital_requirement', 'id').first()
    strategy_features = list(FeatureDefinition.objects.filter(
        scenario=scenario, layer='strategy').order_by('id'))
    default_org = OrganizationalStructureType.objects.filter(
        scenario=scenario, code='centralized').first()
    home_market_overrides = list(home_market_overrides or [])

    with transaction.atomic():
        game = Game.objects.create(
            scenario=scenario, name=name, current_round=0, status='setup',
            created_by=created_by, section_id=section_id)

        teams = []
        company_names = get_company_names(scenario)

        for i in range(num_teams):
            profile = profiles[i % len(profiles)]
            starting_cash = (profile.starting_cash if profile.starting_cash
                             else scenario.starting_cash)
            starting_debt = profile.starting_debt

            if home_market_overrides:
                home_market = home_market_overrides[
                    i % len(home_market_overrides)]
            else:
                home_market = profile.home_market

            team = Team.objects.create(
                game=game,
                name=(company_names[i] if i < len(company_names)
                      else f"Team {i + 1}"),
                firm_starter_profile=profile,
                home_market=home_market,
                performance_index=scenario.performance_index_base,
                cash_on_hand=starting_cash,
                total_debt=starting_debt,
                total_equity=starting_cash - starting_debt,
            )

            # ONE starting platform, from the profile's `alpha` block. One
            # per generation is an engine precondition, not a convention.
            team_platform = TeamPlatform.objects.create(
                team=team,
                platform_generation=starting_gen,
                name=f"{team.name} Base Platform",
                status='active',
                activated_round=0,
            )
            # Only the authored features get a row. Further features are
            # acquired in play, under the scenario's max_platform_features.
            for config in FirmStarterPlatformConfig.objects.filter(
                    firm_starter_profile=profile,
                    platform_label=STARTING_PLATFORM_LABEL).order_by('id'):
                TeamPlatformFeatureLevel.objects.get_or_create(
                    team_platform=team_platform,
                    feature=config.feature,
                    defaults={'current_level': config.starting_level},
                )

            for sp in FirmStarterProduct.objects.filter(
                    firm_starter_profile=profile).order_by('id'):
                product = TeamProduct.objects.create(
                    team=team,
                    team_platform=team_platform,
                    name=sp.product_name,
                    positioning=(sp.positioning_label.lower()
                                 .replace('-', '_').replace(' ', '_')),
                    created_round=0,
                )
                TeamProductMarket.objects.create(
                    team_product=product,
                    market=home_market if home_market else sp.market,
                    first_offered_round=0,
                )

            if default_entry_mode:
                TeamMarketPresence.objects.create(
                    team=team, market=home_market,
                    entry_mode=default_entry_mode, established_round=0,
                    initial_investment=0, status='active')

            TeamMarketCompliance.objects.create(
                game=game, team=team, market=home_market,
                cumulative_investment=0, compliance_level=0,
                current_trust_multiplier=1.0,
                effective_rd_multiplier=1.0,
                effective_commercial_multiplier=1.0,
                effective_operations_multiplier=1.0,
                rounds_present=1,
            )

            for feature in strategy_features:
                TeamStrategyFeatureLevel.objects.create(
                    team=team, feature=feature, market=None,
                    current_level=feature.default_value, round_number=0)

            if default_org:
                TeamOrganizationalStructure.objects.create(
                    game=game, team=team, current_structure=default_org,
                    adopted_round=0)

            teams.append({'team': team, 'profile': profile,
                          'home_market': home_market})

        Round.objects.create(game=game, round_number=0, status='processed')
        for round_number in range(1, scenario.num_rounds + 1):
            Round.objects.create(
                game=game, round_number=round_number, status='pending')

        from core.engine.bootstrap import bootstrap_round_zero
        bootstrap_round_zero(game)

        # Bridge Section -> Game for student auth.
        if section_id:
            from core.models.course import SimulationInstance
            SimulationInstance.objects.update_or_create(
                section_id=section_id,
                defaults={
                    'game_id': game.id,
                    'current_round': 0,
                    'total_rounds': scenario.num_rounds,
                    'status': 'setup',
                },
            )

    return game, teams


def rehome_team(team, market):
    """Move a team's starting state to ``market`` (W-CE-21).

    The console's Team Configuration panel sets a team's home market after
    the game exists.  ``Team.home_market`` alone used to change: the round-0
    presence, the starter products' market rows, the compliance row and every
    round-0 result had already been built by ``create_game`` against the
    profile's authored market, and ``bootstrap_round_zero`` reads the home
    market from the presence row.  The student then saw the chosen market as
    *Not Entered* and the authored one as a foreign market at VERY_HIGH
    cultural distance -- both fields reported faithfully, disagreeing.

    This moves exactly the rows ``create_game`` wrote against the home market
    and rebuilds round 0, so a team re-homed here starts byte-for-byte as one
    created with ``home_market_overrides=[market]`` (the Create Game form's
    own path).  It is for a game no team has played yet: the route refuses
    once a round-1 submission exists, and nothing later than round 0 is
    touched.  A game whose home markets are never changed is not touched at
    all -- ``create_game`` and ``bootstrap_round_zero`` are as they were.
    """
    if team.home_market_id == market.id:
        return
    game = team.game
    with transaction.atomic():
        team.home_market = market
        team.save(update_fields=['home_market'])

        # The starting rows `create_game` keys on the home market.  Each team
        # has exactly one presence, one compliance row and one market row per
        # starter product at round 0, so these are the rows and only these.
        TeamMarketPresence.objects.filter(
            team=team, established_round=0).update(market=market)
        TeamProductMarket.objects.filter(
            team_product__team=team, first_offered_round=0,
        ).update(market=market)
        TeamMarketCompliance.objects.filter(team=team).update(market=market)

        # Round-0 results carry the market in their key, so a rebuild would
        # leave the old market's rows beside the new ones: clear the team's
        # market-keyed round-0 rows, then rebuild round 0 the one way it is
        # ever built.  Everything else bootstrap writes is keyed without a
        # market and is overwritten in place with the same values.
        for model in (RoundResultProductMarket, RoundResultAdoption,
                      RoundResultMarketRevenue):
            model.objects.filter(game=game, round_number=0, team=team).delete()

        from core.engine.bootstrap import bootstrap_round_zero
        bootstrap_round_zero(game)
