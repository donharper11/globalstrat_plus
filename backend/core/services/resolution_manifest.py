import hashlib
import json
import os
import pathlib
import re
import subprocess

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from core.models import DecisionAuditEvent, ResolutionManifest
from core.models.competition_audit import canonical_hash


_UNRESOLVED_REVISIONS = {'', 'unknown', 'unset', 'none', 'null', 'dev', 'development'}


def resolve_code_revision():
    """Return an auditable build revision or fail before resolution starts."""
    configured = str(getattr(settings, 'GIT_REVISION', '') or
                     os.environ.get('GIT_REVISION', '')).strip()
    if configured:
        if (configured.lower() in _UNRESOLVED_REVISIONS or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+:/@-]{0,63}', configured)):
            raise RuntimeError('GIT_REVISION is not a valid release identifier.')
        return configured

    if getattr(settings, 'IS_PRODUCTION', False):
        raise RuntimeError(
            'Production resolution requires an explicit GIT_REVISION for the '
            'deployed immutable build.')

    repository = pathlib.Path(settings.BASE_DIR).resolve().parent
    try:
        revision = subprocess.run(
            ['git', '-C', str(repository), 'rev-parse', 'HEAD'], check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', '-C', str(repository), 'status', '--porcelain',
             '--untracked-files=no'], check=True, capture_output=True, text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            'Cannot determine the code revision. Set GIT_REVISION to the '
            'deployed commit or immutable build identifier.') from exc
    if not revision or len(revision) > 58:
        raise RuntimeError('Git returned an invalid code revision.')
    return f'{revision}-dirty' if dirty else revision


def prepare_manifest(game, round_obj, backup_path):
    code_revision = resolve_code_revision()
    events = list(DecisionAuditEvent.objects.filter(
        game=game, round=round_obj).values(
        'id', 'team_id', 'user_id', 'action', 'payload_sha256', 'created_at'))
    for event in events:
        event['created_at'] = event['created_at'].isoformat()
    payload = {
        'game_id': game.id, 'round_id': round_obj.id,
        'round_number': round_obj.round_number, 'decision_events': events,
        'team_ids': list(game.teams.filter(
            participation_status='active').order_by('id').values_list('id', flat=True)),
        'scenario_id': game.scenario_id,
    }
    seed = hashlib.sha256(
        f'{game.id}:{round_obj.round_number}:{game.scenario_id}'.encode()).hexdigest()
    return ResolutionManifest.objects.update_or_create(
        round=round_obj,
        defaults={'game': game, 'seed': seed, 'input_manifest': payload,
                  'input_sha256': canonical_hash(payload), 'backup_path': backup_path,
                  'code_revision': code_revision},
    )[0]


def complete_manifest(round_obj):
    from core.models.results_financials import (
        RoundResultFinancials, RoundResultMarketRevenue,
        RoundResultPerformanceIndex, RoundResultProductMarket,
        RoundResultCoherence, LeaderboardEntry)
    from core.models.results import RoundResultAdoption
    from core.models.cc26_models import SharePriceHistory
    from core.models.sc_state import ResilienceScoreHistory
    from core.models.core import Team

    common = {'game': round_obj.game, 'round_number': round_obj.round_number}
    payload = {
        'financials': list(RoundResultFinancials.objects.filter(
            **common).order_by('team_id').values()),
        'market_revenue': list(RoundResultMarketRevenue.objects.filter(
            **common).order_by('team_id', 'market_id').values()),
        'product_market': list(RoundResultProductMarket.objects.filter(
            **common).order_by('team_id', 'team_product_id', 'market_id').values()),
        'adoption': list(RoundResultAdoption.objects.filter(
            **common).order_by('team_id', 'market_id', 'segment_id').values()),
        'performance': list(RoundResultPerformanceIndex.objects.filter(
            **common).order_by('team_id').values()),
        'coherence': list(RoundResultCoherence.objects.filter(
            **common).order_by('team_id').values()),
        'resilience': list(ResilienceScoreHistory.objects.filter(
            round=round_obj).order_by('team_id').values()),
        'share_price': list(SharePriceHistory.objects.filter(
            **common).order_by('team_id').values()),
        'leaderboard': list(LeaderboardEntry.objects.filter(
            **common).order_by('rank', 'team_id').values()),
        # These fields are the directly carried, team-level competitive state
        # read by the next round. Lifecycle and audit timestamps are excluded.
        'carried_team_state': list(Team.objects.filter(
            game=round_obj.game).order_by('id').values(
                'id', 'performance_index', 'cash_on_hand', 'total_debt',
                'total_equity', 'shares_outstanding', 'share_price',
                'home_market_id', 'is_in_distress', 'participation_status')),
    }
    payload = json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
    for row in payload['carried_team_state']:
        row['team_id'] = row.pop('id')
    # Database surrogate keys depend on unrelated sequence activity and are not
    # part of a scoring result. Excluding them makes the manifest compare the
    # competition outputs themselves across isolated restore/replay.
    for rows in payload.values():
        for row in rows:
            row.pop('id', None)
    manifest = ResolutionManifest.objects.get(round=round_obj)
    manifest.output_manifest = payload
    manifest.output_sha256 = canonical_hash(payload)
    manifest.completed_at = timezone.now()
    manifest.save(update_fields=['output_manifest', 'output_sha256', 'completed_at'])
    return manifest
