"""
CC-7: RAG-related models.
"""
from django.db import models


class ResearchQueryLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='research_queries',
    )
    round_number = models.IntegerField()
    query_text = models.TextField()
    response_text = models.TextField()
    source_tags_used = models.CharField(max_length=500, null=True, blank=True)
    queried_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'research_query_log'

    def __str__(self):
        return f"Team {self.team_id} R{self.round_number}: {self.query_text[:50]}"
