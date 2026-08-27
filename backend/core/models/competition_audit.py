"""Append-only records required to defend competition outcomes."""
import hashlib
import json

from django.conf import settings
from django.db import models


def canonical_hash(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


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
        return super().save(*args, **kwargs)


class OperatorAuditEvent(models.Model):
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT)
    round = models.ForeignKey('core.Round', on_delete=models.PROTECT,
                              null=True, blank=True)
    user = models.ForeignKey('core.User', on_delete=models.PROTECT)
    action = models.CharField(max_length=64)
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
        return super().save(*args, **kwargs)


class ResolutionManifest(models.Model):
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT)
    round = models.OneToOneField('core.Round', on_delete=models.PROTECT,
                                 related_name='resolution_manifest')
    seed = models.CharField(max_length=64)
    input_manifest = models.JSONField(default=dict)
    input_sha256 = models.CharField(max_length=64)
    output_manifest = models.JSONField(default=dict)
    output_sha256 = models.CharField(max_length=64, blank=True, default='')
    code_revision = models.CharField(max_length=64, blank=True, default='')
    backup_path = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'competition_resolution_manifest'
