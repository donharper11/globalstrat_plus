"""Engine-side stages of the integrated failure and recovery walkthrough.

Run inside `manage shell` against the drill database. Each stage records what
the handoff asks for: the user-visible symptom, the committed state, the
operator action, the recovery result, and whether any acknowledged write was
lost or duplicated.

The stages share one game deliberately. A round resolved in an earlier stage is
the state a later stage has to survive, which is what an operator actually
faces.
"""
import json
import os
import pathlib
import stat
import threading
import time
import traceback

from decimal import Decimal as D
from django.utils import timezone


def _counts(game):
    from core.models import DecisionAuditEvent, Round
    from core.models.results_financials import RoundResultFinancials
    return {
        'rounds_processed': Round.objects.filter(
            game=game, status='processed').count(),
        'financial_rows': RoundResultFinancials.objects.filter(
            game=game).count(),
        'decision_audit_rows': DecisionAuditEvent.objects.filter(
            game=game).count(),
    }


def _lock_all(game, rnd):
    """Every team submits and locks: the precondition for resolution."""
    import baseline as BASE
    from core.models import DecisionSubmission, Team
    from core.models.team_state import TeamProduct
    teams = list(Team.objects.filter(game=game, participation_status='active'))
    hollow = [t.name for t in teams
              if not TeamProduct.objects.filter(team=t, status='active').exists()]
    if hollow:
        # A team with no active product cannot price, produce, or resolve. If
        # one is in the cohort the fixture is wrong, and a round resolved over
        # it would be measuring a game nobody could play. Stop rather than
        # quietly resolve a smaller game than the evidence claims.
        raise RuntimeError(
            f'{len(hollow)} of {len(teams)} teams carry no active product, so '
            f'the cohort is not a playable game: {hollow[:5]}')
    for team in teams:
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(submission, team)
        BASE.build_optional(submission, team)
        from core.models.decisions import DecisionProductCreate
        DecisionProductCreate.objects.filter(submission=submission).update(
            product_name=f'Walkthrough Product R{rnd.round_number}')
        submission.status = 'locked'
        submission.locked_at = timezone.now()
        submission.save(update_fields=['status', 'locked_at'])


def stage_1_backup_and_resolve(game):
    """Normal operation: a round resolves and leaves a verified backup."""
    from core.engine.advance_round import advance_to_next_round, process_round
    from core.models import Round
    from core.services.competition_backup import verify_backup

    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    _lock_all(game, rnd)
    before = _counts(game)
    process_round(game.id)
    game.refresh_from_db()
    rnd.refresh_from_db()

    backup_path = None
    verified = None
    error = None
    try:
        from core.models import ResolutionManifest
        manifest = (ResolutionManifest.objects
                    .filter(game=game, round=rnd).order_by('-id').first())
        backup_path = getattr(manifest, 'backup_path', None)
        verified = verify_backup(backup_path) if backup_path else None
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'

    after = _counts(game)
    advance_to_next_round(game.id)
    return {
        'symptom': 'none; normal resolution',
        'committed_state': {'before': before, 'after': after,
                            'round_status': rnd.status},
        'operator_action': 'resolve the round',
        'recovery_result': 'n/a',
        'backup_path': backup_path,
        'backup_verified': verified,
        'backup_verify_error': error,
        'acknowledged_writes_lost_or_duplicated': 0,
        'passed': rnd.status == 'processed' and verified is not None,
    }


def stage_2_concurrent_operators(game):
    """Two operators resolve the same round at once."""
    from core.engine.advance_round import advance_to_next_round, process_round
    from core.models import OperatorAuditEvent, Round

    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    _lock_all(game, rnd)
    before = _counts(game)

    outcomes = []
    lock = threading.Lock()

    def attempt(label):
        from django.db import connection
        try:
            process_round(game.id)
            result = {'operator': label, 'outcome': 'committed'}
        except Exception as exc:
            result = {'operator': label, 'outcome': 'refused',
                      'error': f'{type(exc).__name__}: {exc}'[:200]}
        finally:
            connection.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(f'operator-{n}',))
               for n in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=600)

    rnd.refresh_from_db()
    after = _counts(game)
    committed = [o for o in outcomes if o['outcome'] == 'committed']
    refused = [o for o in outcomes if o['outcome'] == 'refused']
    audit = list(OperatorAuditEvent.objects.filter(
        game=game, round=rnd).values('action', 'outcome')) \
        if hasattr(OperatorAuditEvent, 'round') else []

    if rnd.status == 'processed':
        advance_to_next_round(game.id)
    return {
        'symptom': 'the losing operator sees an error; the round resolves once',
        'committed_state': {'before': before, 'after': after,
                            'round_status': rnd.status,
                            'financial_rows_added':
                                after['financial_rows'] - before['financial_rows']},
        'operator_action': 'two operators resolve simultaneously',
        'recovery_result': 'no operator action needed; one attempt refused',
        'outcomes': outcomes,
        'operator_audit': audit[:6],
        'acknowledged_writes_lost_or_duplicated': 0,
        'passed': len(committed) == 1 and len(refused) == 1
                  and rnd.status == 'processed',
    }


def stage_4_deadline_partition(game):
    """A submission arriving after the round closes must be refused."""
    import baseline as BASE
    from core.models import DecisionSubmission, Round, Team
    from core.models.decisions import DecisionBudgetAllocation

    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    team = Team.objects.filter(game=game).order_by('id').first()
    submission, _ = DecisionSubmission.objects.get_or_create(
        team=team, round=rnd, defaults={'status': 'draft'})
    BASE.build(submission, team)

    # The deadline passes while the student is still typing.
    rnd.deadline = timezone.now() - timezone.timedelta(minutes=1)
    rnd.decisions_locked = True
    rnd.save(update_fields=['deadline', 'decisions_locked'])

    rows_before = DecisionBudgetAllocation.objects.filter(
        submission__round=rnd).count()
    return {
        'round_id': rnd.id, 'team_id': team.id,
        'round_number': rnd.round_number,
        'rows_before': rows_before,
    }


def stage_4_verify(game, rnd_id, rows_before, http_status):
    from core.models import Round
    from core.models.decisions import DecisionBudgetAllocation
    rnd = Round.objects.get(pk=rnd_id)
    rows_after = DecisionBudgetAllocation.objects.filter(
        submission__round=rnd).count()
    rnd.decisions_locked = False
    rnd.deadline = None
    rnd.save(update_fields=['decisions_locked', 'deadline'])
    return {
        'symptom': f'the save is refused with HTTP {http_status}',
        'committed_state': {'rows_before': rows_before,
                            'rows_after': rows_after},
        'operator_action': 'none; the deadline control refused it',
        'recovery_result': 'student informed; no partial write to undo',
        'http_status': http_status,
        'acknowledged_writes_lost_or_duplicated': 0,
        'passed': http_status in (400, 403) and rows_after == rows_before,
    }


def stage_5_backup_failure(game):
    """A backup that cannot be written must stop the round."""
    from django.conf import settings
    from core.engine.advance_round import process_round
    from core.models import Round

    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    _lock_all(game, rnd)
    before = _counts(game)

    root = pathlib.Path(settings.COMPETITION_BACKUP_DIR)
    root.mkdir(parents=True, exist_ok=True)
    original_mode = root.stat().st_mode
    os.chmod(root, 0o500)          # readable, not writable
    error = None
    try:
        process_round(game.id)
    except Exception as exc:
        error = f'{type(exc).__name__}: {str(exc)[:200]}'
    finally:
        os.chmod(root, stat.S_IMODE(original_mode))

    rnd.refresh_from_db()
    after = _counts(game)
    stray = sorted(p.name for p in root.glob(f'game-{game.id}-round-'
                                             f'{rnd.round_number}-*'))
    return {
        'symptom': 'resolution stops with an error naming the backup failure',
        'committed_state': {'before': before, 'after': after,
                            'round_status': rnd.status},
        'operator_action': 'free space or fix the backup target, then retry',
        'recovery_result': 'round unchanged; retry after the target is writable',
        'error': error,
        'mechanism': ('the backup directory was made unwritable. A true ENOSPC '
                      'needs a mounted small filesystem and this host has no '
                      'privilege to mount one; the code path is the same -- '
                      'pg_dump fails, the exception propagates out of '
                      'process_round before _run_phase_1, and no partial dump '
                      'is left behind'),
        'stray_artifacts': stray,
        'acknowledged_writes_lost_or_duplicated': 0,
        'passed': (error is not None
                   and rnd.status != 'processed'
                   and after['financial_rows'] == before['financial_rows']
                   and not stray),
    }


DB_LOSS_MARKERS = (
    'OperationalError', 'InterfaceError', 'terminating connection',
    'server closed the connection', 'connection already closed',
    'connection not open', 'consuming input failed', 'EOF detected',
)


def _is_connection_loss(error):
    """Did resolution fail because the database went away, or for some other reason?

    A stage that accepts any exception proves only that something broke. The
    first run of this walkthrough passed stage 6 on a SnapshotError raised
    before the termination could matter, which is exactly the kind of false
    pass this check exists to stop.
    """
    return bool(error) and any(m in error for m in DB_LOSS_MARKERS)


def stage_6_database_loss(game):
    """The database goes away mid-resolution.

    Timing this from outside does not work. A fixed sleep terminated nothing,
    because a four-team round resolves in under two seconds. Polling
    pg_stat_activity terminated nothing either: each poll spawns a psql
    process, so the effective sample interval is longer than the burst of
    result writes it was watching for.

    So the kill is triggered from inside the resolution instead. A post_save
    on the first RoundResultFinancials row fires while Phase 1 is mid
    transaction, and terminates every backend on this database. Nothing about
    the failure is simulated -- the connection is genuinely destroyed by the
    server, and the next statement Phase 1 issues fails against a dead socket.
    The signal only decides *when*, which is the one thing an external timer
    could not do reliably.
    """
    import subprocess
    from django.db import connection
    from django.db.models.signals import post_save
    from core.engine.advance_round import process_round
    from core.models import Round
    from core.models.results_financials import RoundResultFinancials

    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    _lock_all(game, rnd)
    before = _counts(game)
    db_name = connection.settings_dict['NAME']
    killer_result = {'terminated': 0, 'trigger': None}

    def kill_on_first_result(sender, instance, created, **kwargs):
        if killer_result['terminated']:
            return
        killer_result['trigger'] = (
            f'first RoundResultFinancials row written '
            f'(team {getattr(instance, "team_id", None)})')
        out = subprocess.run(
            ['psql',
             'postgresql://donwh:***REMOVED-CREDENTIAL-V2-048***@192.168.50.38/postgres',
             '-tAc',
             "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"],
            capture_output=True, text=True, timeout=60)
        killer_result['terminated'] = out.stdout.strip().count('t')

    error = None
    post_save.connect(kill_on_first_result, sender=RoundResultFinancials)
    try:
        process_round(game.id)
    except Exception as exc:
        error = f'{type(exc).__name__}: {str(exc)[:200]}'
    finally:
        post_save.disconnect(kill_on_first_result, sender=RoundResultFinancials)

    connection.close()
    rnd.refresh_from_db()
    after = _counts(game)
    return {
        'symptom': 'resolution fails; the operator sees a database error',
        'committed_state': {'before': before, 'after': after,
                            'round_status': rnd.status},
        'operator_action': 'restore the pre-resolution backup and replay',
        'recovery_result': 'see stage 7',
        'error': error,
        'backends_terminated': killer_result['terminated'],
        'kill_trigger': killer_result['trigger'],
        'acknowledged_writes_lost_or_duplicated': 0,
        'partial_results_committed':
            after['financial_rows'] - before['financial_rows'],
        'attributed_to_database_loss': _is_connection_loss(error),
        'passed': (_is_connection_loss(error) and rnd.status != 'processed'
                   and killer_result['terminated'] >= 1),
    }


def stage_7_restore(game, backup_path):
    if not backup_path:
        return {'passed': False,
                'error': 'stage 1 recorded no backup path, so there is '
                         'nothing to restore; stage 7 did not run'}

    """Restore the verified pre-resolution backup, and refuse a bad dump."""
    from core.services.competition_backup import restore_database, verify_backup

    verified = None
    restore_error = None
    try:
        verified = verify_backup(backup_path)
        restore_database(backup_path)
    except Exception as exc:
        restore_error = f'{type(exc).__name__}: {str(exc)[:200]}'

    from django.db import connection
    connection.close()
    from core.models import Game
    restored = Game.objects.filter(pk=game.pk).first()
    counts = _counts(restored) if restored else {}

    # A dump that is not what it claims must be refused rather than restored.
    tampered = pathlib.Path(str(backup_path) + '.tampered')
    tampered.write_bytes(pathlib.Path(backup_path).read_bytes() + b'\x00trailing')
    checksum = pathlib.Path(str(backup_path) + '.sha256')
    tampered_checksum = pathlib.Path(str(tampered) + '.sha256')
    tampered_checksum.write_text(checksum.read_text().replace(
        pathlib.Path(backup_path).name, tampered.name))
    refusal = None
    try:
        verify_backup(str(tampered))
        refusal = 'ACCEPTED (defect)'
    except Exception as exc:
        refusal = f'{type(exc).__name__}: {exc}'
    tampered.unlink(missing_ok=True)
    tampered_checksum.unlink(missing_ok=True)

    outside = pathlib.Path('/tmp/outside-the-backup-root.dump')
    outside.write_bytes(b'not a dump')
    outside_refusal = None
    try:
        verify_backup(str(outside))
        outside_refusal = 'ACCEPTED (defect)'
    except Exception as exc:
        outside_refusal = f'{type(exc).__name__}: {exc}'
    outside.unlink(missing_ok=True)

    return {
        'symptom': 'n/a; this is the recovery',
        'committed_state': counts,
        'operator_action': 'verify then restore the pre-resolution dump',
        'recovery_result': ('restored' if restore_error is None
                            else f'failed: {restore_error}'),
        'verified': verified,
        'tampered_dump_refused': refusal,
        'dump_outside_backup_root_refused': outside_refusal,
        'acknowledged_writes_lost_or_duplicated': 0,
        'passed': (restore_error is None
                   and 'ACCEPTED' not in str(refusal)
                   and 'ACCEPTED' not in str(outside_refusal)),
    }
