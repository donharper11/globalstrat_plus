"""
Event Engine: Fire events, shift preferences, generate newsfeeds.

Orchestrates the event lifecycle per round:
1. Query event_triggers for the current round_number + game_id
2. For each triggered event, create triggered_events for ALL teams
3. Apply event_impacts: shift stakeholder preferences
4. Generate newsfeeds entries
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from core.models.events import (
    TriggeredEvent,
)
from core.models import Team, Round
# TODO: GlobalStrat — update to use new scenario models (CC-3)
# Removed: Event, EventTrigger, EventImpact, SegmentPreference


def fire_events(round_number, game_id):
    """
    Main entry point: fire all events scheduled for this round and game.
    """
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Event, EventTrigger, EventImpact models removed — stub returning empty result
    return {
        'round_number': round_number,
        'game_id': game_id,
        'events_triggered': 0,
        'event_ids': [],
        'triggered_event_records': 0,
        'newsfeeds_created': 0,
        'preferences_shifted': 0,
    }


def shift_preferences(event_id):
    """
    Shift stakeholder preferences based on event impacts.
    """
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # EventImpact, SegmentPreference models removed — stub returning 0
    return 0


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# Newsfeeds model deleted — generate_newsfeeds is a no-op stub
# def generate_newsfeeds(round_id, game_id, event_ids):
#     """
#     For each triggered event, create a newsfeeds entry with:
#     - round_id, team_id=None (broadcast to all teams), category='Event'
#     - title = event.event_name, body = event.description
#     """
#     if not event_ids:
#         return 0
#
#     created_count = 0
#
#     for eid in event_ids:
#         event = Event.objects.filter(event_id=eid).first()
#         if not event:
#             continue
#
#         if round_id is None:
#             continue
#
#         Newsfeeds.objects.create(
#             round_id=round_id,
#             team_id=None,
#             category='Event',
#             title=event.event_name,
#             body=event.description,
#             created_at=timezone.now(),
#         )
#         created_count += 1
#
#     return created_count


def generate_newsfeeds(round_id, game_id, event_ids):
    """Stub — Newsfeeds model deleted."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return 0
