"""
CC-32E: Agent Orchestrator Models — Logging and monitoring for agent cycles.
"""
from django.db import models


class AgentCycleLog(models.Model):
    """Records each agent processing cycle for debugging and analysis."""
    game = models.ForeignKey('Game', on_delete=models.CASCADE, related_name='agent_cycle_logs')
    round = models.ForeignKey('Round', on_delete=models.CASCADE, related_name='agent_cycle_logs')

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    convergence_iterations = models.IntegerField(default=0)
    total_actions = models.IntegerField(default=0)
    total_narratives = models.IntegerField(default=0)

    # Per-agent summary
    agent_summary = models.JSONField(
        default=dict,
        help_text='Per-agent stats: {agent_class: {actions_proposed, actions_revised, actions_applied}}'
    )

    # Full action log (for debugging — may be large)
    action_log = models.JSONField(null=True, blank=True)

    # Narrative items for briefing engine consumption
    narrative_items = models.JSONField(null=True, blank=True)

    # Errors
    errors = models.JSONField(default=list)

    class Meta:
        unique_together = ('game', 'round')

    def __str__(self):
        return f"AgentCycleLog Game={self.game_id} Round={self.round_id}"
