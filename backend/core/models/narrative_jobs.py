"""Durable record of Phase-2 narrative work.

The defect this closes (V2-006): Phase 2 ran in a daemon thread with no record
of its own. A worker restart between dispatch and completion abandoned the work
silently — an abrupt process death cannot even set `narrative_error`, so an
operator saw a round that looked finished and a briefing that never arrived.

A job row is written in the *same transaction that commits Phase 1*, so the
work exists the moment the numbers do. Everything after that — claiming,
retrying, timing out, failing terminally — moves this row, and a worker
starting up asks the database what is outstanding rather than trusting anything
in memory.
"""
from django.db import models
from django.utils import timezone


class NarrativeJob(models.Model):
    """One unit of Phase-2 work for one round.

    Identity is `(round, narrative_type, template_version)`. A retry re-runs the
    same row; it cannot create a second one, which is what stops a restart
    duplicating a team's briefing.
    """

    PENDING, CLAIMED, SUCCEEDED, FAILED = 'pending', 'claimed', 'succeeded', 'failed'
    STATE_CHOICES = [
        (PENDING, 'Pending'),
        (CLAIMED, 'Claimed by a worker'),
        (SUCCEEDED, 'Succeeded'),
        (FAILED, 'Failed — terminal, needs an operator retry'),
    ]

    # Kept in step with core.engine.narratives; the inventory in
    # handoff_readiness_v2/NARRATIVE_JOB_INVENTORY.md is the reviewed list.
    TYPE_CHOICES = [
        ('briefing', 'Strategic briefings'),
        ('coherence_rag', 'Coherence RAG evaluation'),
        ('coaching', 'Instructor coaching alerts'),
        ('outlook', 'Market outlooks'),
        ('sc_event', 'Supply-chain event narratives'),
        ('compliance', 'Compliance enforcement narratives'),
    ]

    game = models.ForeignKey('core.Game', on_delete=models.PROTECT,
                             related_name='narrative_jobs')
    round = models.ForeignKey('core.Round', on_delete=models.PROTECT,
                              related_name='narrative_jobs')
    narrative_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    # Bump when a prompt or storage shape changes: a new version is a new job,
    # so old content is never silently reinterpreted as the new kind.
    template_version = models.PositiveSmallIntegerField(default=1)

    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)

    # A claim is a lease, not a lock: a worker that dies leaves the lease to
    # expire, and the next worker reclaims the job instead of it being lost.
    claimed_by = models.CharField(max_length=128, blank=True, default='')
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)

    # Provenance an instructor can read. Never a key or a token: `model_name`
    # and `model_endpoint` are configuration, and last_error is sanitised.
    model_name = models.CharField(max_length=128, blank=True, default='')
    model_endpoint = models.CharField(max_length=255, blank=True, default='')
    last_error = models.TextField(blank=True, default='')
    result_sha256 = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'narrative_job'
        unique_together = [('round', 'narrative_type', 'template_version')]
        indexes = [
            models.Index(fields=['state', 'claim_expires_at'],
                         name='narrative_job_claimable'),
        ]
        ordering = ['round_id', 'narrative_type']

    def __str__(self):
        return (f'{self.narrative_type} v{self.template_version} for round '
                f'{self.round_id} ({self.state})')

    @property
    def is_claimable(self):
        """Pending, or claimed by a worker whose lease has run out."""
        if self.state == self.PENDING:
            return True
        return (self.state == self.CLAIMED and self.claim_expires_at is not None
                and self.claim_expires_at <= timezone.now())

    @property
    def attempts_remaining(self):
        return max(self.max_attempts - self.attempts, 0)
