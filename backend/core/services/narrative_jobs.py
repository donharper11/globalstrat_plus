"""Enqueue, claim and run Phase-2 narrative work durably.

The contract, in one place:

* **Enqueued in the Phase-1 transaction.** If the numbers committed, the work
  exists. There is no window in which a round is resolved and nothing records
  that its narratives are outstanding.
* **Claimed as a lease, not a lock.** A worker takes a job with
  `SELECT … FOR UPDATE SKIP LOCKED` and stamps an expiry on it. A worker that
  dies mid-call leaves a lease that runs out, and the next worker reclaims the
  job. Nothing needs to notice the death.
* **Bounded.** Each attempt increments `attempts`; at `max_attempts` the job is
  `failed`, which is terminal and visible. An operator retries it explicitly;
  scoring is never re-run to fix a narrative.
* **Idempotent.** Every producer writes through `update_or_create` on a natural
  key, so re-running a job overwrites its own row rather than adding a second.
"""
import hashlib
import logging
import os
import re
import socket
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models.narrative_jobs import NarrativeJob

logger = logging.getLogger('narrative_jobs')

# How long a worker may hold a job before another may reclaim it. Longer than
# the LLM batch timeout, so a slow call is not stolen from a live worker.
CLAIM_LEASE_SECONDS = 300

# The types enqueued for every resolved round, in the order a worker runs them.
ENQUEUED_TYPES = ('briefing', 'coherence_rag', 'coaching', 'outlook',
                  'sc_event', 'compliance')

TEMPLATE_VERSION = 1

# Anything that looks like a credential, stripped before an error is stored.
_SECRET_PATTERN = re.compile(
    r'(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+|api[_-]?key["\'\s:=]+\S+)',
    re.IGNORECASE)


def sanitize_error(error, limit=500):
    """An operator-readable error with any credential removed.

    Provider errors quote the request, and the request carries an
    Authorization header. Storing one verbatim would put a key in a table
    instructors can read.
    """
    text = str(error)
    text = _SECRET_PATTERN.sub('[redacted]', text)
    return text[:limit]


def worker_identity():
    return f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}'


def enqueue_round(game, round_obj, types=ENQUEUED_TYPES,
                  template_version=TEMPLATE_VERSION):
    """Record the round's outstanding narrative work.

    Called inside the Phase-1 transaction. `get_or_create` rather than
    `create`: re-resolving a round after a recovery must not raise on jobs that
    already exist, and must not duplicate them.
    """
    jobs = []
    for narrative_type in types:
        job, created = NarrativeJob.objects.get_or_create(
            round=round_obj, narrative_type=narrative_type,
            template_version=template_version,
            defaults={'game': game, 'state': NarrativeJob.PENDING},
        )
        if not created and job.state == NarrativeJob.FAILED:
            # A re-resolution is a fresh chance for work that had given up.
            job.state = NarrativeJob.PENDING
            job.attempts = 0
            job.last_error = ''
            job.save(update_fields=['state', 'attempts', 'last_error'])
        jobs.append(job)
    return jobs


def claim_next(worker=None, lease_seconds=CLAIM_LEASE_SECONDS, game_id=None):
    """Take one claimable job, or return None.

    `SKIP LOCKED` is what lets several workers run without coordinating: each
    takes a different row rather than queueing behind the same one.
    """
    worker = worker or worker_identity()
    now = timezone.now()
    with transaction.atomic():
        queryset = NarrativeJob.objects.select_for_update(skip_locked=True).filter(
            state__in=[NarrativeJob.PENDING, NarrativeJob.CLAIMED])
        if game_id is not None:
            queryset = queryset.filter(game_id=game_id)
        for job in queryset.order_by('round_id', 'narrative_type'):
            if not job.is_claimable:
                continue
            if job.state == NarrativeJob.CLAIMED:
                logger.warning(
                    'Reclaiming %s from %s: lease expired at %s',
                    job, job.claimed_by, job.claim_expires_at)
            job.state = NarrativeJob.CLAIMED
            job.claimed_by = worker
            job.claimed_at = now
            job.claim_expires_at = now + timezone.timedelta(seconds=lease_seconds)
            job.save(update_fields=['state', 'claimed_by', 'claimed_at',
                                    'claim_expires_at'])
            return job
    return None


def _model_provenance():
    return {
        'model_name': str(getattr(settings, 'DASHSCOPE_MODEL', '') or '')[:128],
        'model_endpoint': str(
            getattr(settings, 'DASHSCOPE_COMPATIBLE_URL', '') or '')[:255],
    }


def run_job(job):
    """Execute one job and record what happened. Never raises.

    A raising worker is a worker that stops draining the queue, so every
    outcome — success, retryable failure, terminal failure — comes back as a
    state on the row.
    """
    from core.engine import narratives

    provenance = _model_provenance()
    job.attempts += 1
    job.model_name = provenance['model_name']
    job.model_endpoint = provenance['model_endpoint']
    try:
        produced = narratives.run_narrative_type(
            job.game, job.round, job.narrative_type)
    except Exception as error:                       # noqa: BLE001 - see docstring
        job.last_error = sanitize_error(error)
        if job.attempts >= job.max_attempts:
            job.state = NarrativeJob.FAILED
            job.completed_at = timezone.now()
            logger.error('%s failed terminally after %s attempts: %s',
                         job, job.attempts, job.last_error)
        else:
            job.state = NarrativeJob.PENDING
            logger.warning('%s failed on attempt %s/%s, will retry: %s',
                           job, job.attempts, job.max_attempts, job.last_error)
        job.claimed_by = ''
        job.claim_expires_at = None
        job.save(update_fields=['state', 'attempts', 'last_error', 'claimed_by',
                                'claim_expires_at', 'completed_at',
                                'model_name', 'model_endpoint'])
        return job

    job.state = NarrativeJob.SUCCEEDED
    job.completed_at = timezone.now()
    job.claimed_by = ''
    job.claim_expires_at = None
    job.degraded = bool(produced.get('degraded'))
    # Succeeded on fallbacks is still worth saying out loud: without this an
    # operator sees `succeeded` and no sign the provider never answered.
    if job.degraded:
        detail = '; '.join(produced.get('errors') or []) or 'no response'
        job.last_error = sanitize_error(
            f"{produced.get('calls_failed')}/{produced.get('calls')} calls fell "
            f"back to templates: {detail}")
        logger.warning('%s completed degraded: %s', job, job.last_error)
    else:
        job.last_error = ''
    job.result_sha256 = hashlib.sha256(
        repr(sorted(produced.items())).encode('utf-8')).hexdigest()
    job.save(update_fields=['state', 'attempts', 'completed_at', 'last_error',
                            'claimed_by', 'claim_expires_at', 'result_sha256',
                            'degraded', 'model_name', 'model_endpoint'])
    return job


def drain(limit=None, worker=None, game_id=None, lease_seconds=CLAIM_LEASE_SECONDS):
    """Run claimable jobs until there are none left, or `limit` is reached."""
    worker = worker or worker_identity()
    processed = []
    while limit is None or len(processed) < limit:
        job = claim_next(worker=worker, lease_seconds=lease_seconds,
                         game_id=game_id)
        if job is None:
            break
        processed.append(run_job(job))
    return processed


def backlog(game_id=None):
    """What is outstanding, for an operator or an alert."""
    queryset = NarrativeJob.objects.all()
    if game_id is not None:
        queryset = queryset.filter(game_id=game_id)
    now = timezone.now()
    return {
        'pending': queryset.filter(state=NarrativeJob.PENDING).count(),
        'claimed': queryset.filter(state=NarrativeJob.CLAIMED).count(),
        'stale_claims': queryset.filter(
            state=NarrativeJob.CLAIMED, claim_expires_at__lte=now).count(),
        'succeeded': queryset.filter(state=NarrativeJob.SUCCEEDED).count(),
        'failed': queryset.filter(state=NarrativeJob.FAILED).count(),
        'degraded': queryset.filter(state=NarrativeJob.SUCCEEDED,
                                    degraded=True).count(),
    }
