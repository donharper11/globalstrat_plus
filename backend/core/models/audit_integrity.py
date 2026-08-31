"""Tamper evidence for the audit tables, and evidence of who read what.

Two separate problems share this module because they answer the same class of
question after a competition dispute.

`AuditChainEntry` is a forward hash chain over the append-only audit tables.
Database triggers refuse `UPDATE` and `DELETE` on those tables, which stops the
application — but the application connects as the tables' owner, and an owner
can drop a trigger. The chain is what survives that: each entry commits to the
one before it, and the head is exported outside the database
(`core.services.audit_anchor`), so a privileged change made with the triggers
disabled still breaks verification against the anchor.

`SensitiveReadEvent` records reads of raw team decisions and audit payloads, so
"who accessed Team X's Round Y decisions?" has an answer that does not depend on
web-server logs. It deliberately stores no payload: the disclosure claim is
about who looked, and copying the decisions into a second table would widen the
exposure it exists to investigate.
"""
from django.db import models


GENESIS_SHA256 = '0' * 64


class AuditChainEntry(models.Model):
    """One sealed audit row's position in the forward hash chain."""
    seq = models.BigIntegerField(unique=True)
    source_table = models.CharField(max_length=64)
    source_id = models.BigIntegerField()
    # Digest of the row's immutable projection, taken with the same canonical
    # JSON rules the resolution manifests use, so a chain digest and a manifest
    # digest cannot disagree about how a Decimal or a timestamp is spelled.
    row_sha256 = models.CharField(max_length=64)
    prev_sha256 = models.CharField(max_length=64)
    entry_sha256 = models.CharField(max_length=64)
    sealed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_audit_chain'
        ordering = ['seq']
        constraints = [
            # One entry per audit row. Excluded for the recovery-audit file,
            # which is chained by its content digest and legitimately produces
            # a new entry whenever the file changes — including a change that
            # leaves the line count where it was.
            models.UniqueConstraint(
                fields=['source_table', 'source_id'],
                condition=~models.Q(source_table='recovery_audit_file'),
                name='audit_chain_one_entry_per_row'),
        ]
        indexes = [models.Index(fields=['source_table', 'source_id'])]

    def __str__(self):
        return f'#{self.seq} {self.source_table}:{self.source_id}'


class SensitiveReadEvent(models.Model):
    """One read of a team's raw decisions or of an audit payload.

    `outcome` records refusals as well as disclosures. A denied cross-team read
    is the more interesting row of the two when a team alleges that a rival saw
    their decisions: it shows the attempt and shows that it failed.
    """
    OUTCOME_CHOICES = [
        ('allowed', 'Allowed'),
        ('denied', 'Denied'),
        ('error', 'Error'),
    ]
    CATEGORY_CHOICES = [
        ('decisions', 'Raw team decisions'),
        ('audit', 'Audit payload'),
    ]

    # The actor is a plain integer plus a snapshot of the username, not a
    # foreign key. `on_delete` is the problem: every rule Django offers either
    # removes the audit row with the account or rewrites it, and the database
    # triggers refuse both. An id that outlives its user is the point.
    actor_user_id = models.IntegerField(null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, default='')

    # Subject identifiers are stored as integers, not foreign keys: a read of a
    # team that does not exist, or of another game's team, is precisely the
    # attempt worth recording, and a foreign key could not hold it.
    game_id_read = models.IntegerField(null=True, blank=True)
    team_id_read = models.IntegerField(null=True, blank=True)
    round_number_read = models.IntegerField(null=True, blank=True)

    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES)
    route = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=8)
    status_code = models.PositiveSmallIntegerField()
    outcome = models.CharField(max_length=8, choices=OUTCOME_CHOICES)
    request_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_sensitive_read_event'
        ordering = ['id']
        indexes = [
            models.Index(fields=['game_id_read', 'team_id_read',
                                 'round_number_read']),
            models.Index(fields=['actor_user_id', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('SensitiveReadEvent records are immutable.')
        return super().save(*args, **kwargs)

    def __str__(self):
        who = self.username or 'anonymous'
        return (f'{who} {self.outcome} {self.method} {self.endpoint} '
                f'({self.category})')


class AuthorizationRefusalEvent(models.Model):
    """One refused attempt to act on a game the caller does not own.

    CRV2-02 made operator refusals auditable: a race leaves one committed row
    and one rejected row, and the rejected one is what shows the attempt. Moving
    authorization to `GameScopeGuardMiddleware` refused cross-cohort lifecycle
    attempts *before* the view, which is correct, and left them invisible --
    thirty-seven refused writes with no record anywhere (V2-034).

    Deliberately not an `OperatorAuditEvent`: that model describes a lifecycle
    action with a before and an after, and this attempt never reached one. It
    is not a `SensitiveReadEvent` either, because a refused POST is not a read.
    A separate narrow row says exactly what happened -- someone tried to act on
    a cohort that is not theirs, and was refused -- and claims nothing else.

    No request body, header or credential is stored. What the caller was trying
    to send is not needed to investigate that they were refused, and copying it
    here would put another cohort's payload in a table created to protect it.
    """
    # An id that outlives its user, as elsewhere in this module: every
    # `on_delete` rule either removes the audit row with the account or
    # rewrites it, and the database triggers refuse both.
    actor_user_id = models.IntegerField(null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, default='')

    # Plain integer: an attempt against a game the caller cannot see, or one
    # that does not exist, is precisely the attempt worth recording.
    game_id_attempted = models.IntegerField(null=True, blank=True)

    method = models.CharField(max_length=8)
    route = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=255)
    outcome = models.CharField(max_length=16, default='rejected')
    reason = models.CharField(max_length=255)
    request_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_authorization_refusal_event'
        ordering = ['id']
        indexes = [
            models.Index(fields=['game_id_attempted', 'created_at']),
            models.Index(fields=['actor_user_id', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('AuthorizationRefusalEvent records are immutable.')
        result = super().save(*args, **kwargs)
        # Chain the row once its transaction commits, the same route every
        # other audit row takes. Listing the table in `audit_chain.SEAL_ORDER`
        # only makes it eligible for a pass that something else triggers: a
        # final refusal could otherwise sit unsealed indefinitely, which is not
        # what "chained and tamper-evident" means. After commit, never inside
        # the write -- the seal takes a global advisory lock.
        from core.models.competition_audit import _schedule_seal
        _schedule_seal()
        return result

    def __str__(self):
        who = self.username or 'anonymous'
        return (f'{who} refused {self.method} {self.endpoint} '
                f'(game {self.game_id_attempted})')
