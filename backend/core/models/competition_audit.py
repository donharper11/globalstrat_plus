"""Append-only records required to defend competition outcomes."""
import hashlib
import json

from django.conf import settings
from django.db import models


def canonical_hash(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _schedule_seal():
    """Chain the new row once its transaction commits.

    Deliberately after commit, not inside the write: the seal takes a global
    advisory lock, and taking it underneath the operator lifecycle locks would
    invert a lock order that GSP-CRV2-02 certified. A rejected operator action
    rolls back its attempt but records its refusal in a later transaction, so
    both rows reach the chain by the same route.
    """
    from core.services.audit_chain import schedule_seal
    schedule_seal()


class DecisionAuditEvent(models.Model):
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT)
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT)
    round = models.ForeignKey('core.Round', on_delete=models.PROTECT)
    user = models.ForeignKey('core.User', on_delete=models.PROTECT,
                             null=True, blank=True)
    action = models.CharField(max_length=32)
    endpoint = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    request_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_decision_audit_event'
        ordering = ['id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('DecisionAuditEvent records are immutable.')
        if not self.payload_sha256:
            self.payload_sha256 = canonical_hash(self.payload)
        result = super().save(*args, **kwargs)
        _schedule_seal()
        return result


class OperatorAuditEvent(models.Model):
    """One row per operator attempt, committed or refused.

    A refused attempt is recorded with ``outcome='rejected'``, an empty
    ``after`` and the conflict that caused it. That keeps a race visible to
    whoever investigates later without implying the round moved: the pair of
    rows for two racing operators shows exactly one commit and one rejection.
    """
    OUTCOME_CHOICES = [('committed', 'Committed'), ('rejected', 'Rejected')]

    game = models.ForeignKey('core.Game', on_delete=models.PROTECT)
    round = models.ForeignKey('core.Round', on_delete=models.PROTECT,
                              null=True, blank=True)
    user = models.ForeignKey('core.User', on_delete=models.PROTECT)
    action = models.CharField(max_length=64)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES,
                               default='committed')
    conflict = models.JSONField(default=dict, blank=True)
    reason = models.TextField()
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    request_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_operator_audit_event'
        ordering = ['id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('OperatorAuditEvent records are immutable.')
        result = super().save(*args, **kwargs)
        _schedule_seal()
        return result


class ResolutionManifest(models.Model):
    """What one round was given and what it produced.

    ``schema_version`` is the envelope version. Version 1 stored decision-event
    metadata and three result tables; version 2 stores canonical snapshots of
    every table that carries competitive state (see
    ``core.services.resolution_manifest``). Old rows keep version 1 and are
    never reinterpreted as the wider envelope, so a v1 hash can never be
    mistaken for a v2 hash.
    """
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT)
    round = models.OneToOneField('core.Round', on_delete=models.PROTECT,
                                 related_name='resolution_manifest')
    schema_version = models.PositiveSmallIntegerField(default=1)
    seed = models.CharField(max_length=64)
    input_manifest = models.JSONField(default=dict)
    input_sha256 = models.CharField(max_length=64)
    input_section_digests = models.JSONField(default=dict)
    input_body_path = models.TextField(blank=True, default='')
    output_manifest = models.JSONField(default=dict)
    output_sha256 = models.CharField(max_length=64, blank=True, default='')
    output_section_digests = models.JSONField(default=dict)
    output_body_path = models.TextField(blank=True, default='')
    # Phase-2 prose is hashed separately: a narrative difference must be
    # visible without failing an otherwise identical competitive replay.
    narrative_manifest = models.JSONField(default=dict)
    narrative_sha256 = models.CharField(max_length=64, blank=True, default='')
    # Host configuration, deliberately outside every hash, so two matching
    # runs can be shown to have happened on differently configured machines.
    environment = models.JSONField(default=dict)
    decision_event_count = models.PositiveIntegerField(default=0)
    code_revision = models.CharField(max_length=64, blank=True, default='')
    # Content digest of the runtime source tree. A commit hash with a `-dirty`
    # suffix names the commit but not the modifications on top of it; this
    # names the exact code, tracked or not. Replay refuses a mismatch.
    source_tree_sha256 = models.CharField(max_length=64, blank=True, default='')
    backup_path = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'competition_resolution_manifest'
