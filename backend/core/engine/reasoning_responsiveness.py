"""
Reasoning Dimension 2: Signal Responsiveness (deterministic).

For each active event/modifier in the round:
- Identify affected markets and domains
- Check if team filed a DecisionEventResponse
- Check if decisions in affected domains changed from previous round
- Score = weighted ratio of relevant adjustments to relevant signals

Pure function — no I/O, no database access.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EventSignal:
    """An event or modifier active in the current round."""
    event_name: str
    category: str  # e.g. 'GEOPOLITICAL', 'ECONOMIC', 'SUPPLY_CHAIN'
    affected_markets: List[str] = field(default_factory=list)
    severity: float = 0.5  # 0-1
    domains: List[str] = field(default_factory=list)
    # domains could be: pricing, marketing, sourcing, production, financing, etc.


@dataclass
class DecisionChange:
    """A detected change in a decision domain between rounds."""
    domain: str  # pricing, marketing, production, sourcing, financing, etc.
    market: str = ''
    description: str = ''
    magnitude: float = 0.0  # 0-1, how significant the change was


@dataclass
class ResponsivenessInput:
    events: List[EventSignal] = field(default_factory=list)
    has_event_response: bool = False  # Did team file a DecisionEventResponse?
    decision_changes: List[DecisionChange] = field(default_factory=list)
    active_market_names: List[str] = field(default_factory=list)


@dataclass
class EventDetail:
    event_name: str
    addressed: bool
    response_filed: bool
    relevant_changes: List[str]
    score: float


@dataclass
class ResponsivenessResult:
    score: float  # 0-100
    events_relevant: int
    events_addressed: int
    details: List[EventDetail] = field(default_factory=list)
    feedback: str = ''


# Domain mapping: event categories to expected decision domains
EVENT_DOMAIN_MAP = {
    'GEOPOLITICAL': ['sourcing', 'market_entry', 'financing'],
    'ECONOMIC': ['pricing', 'production', 'financing'],
    'SUPPLY_CHAIN': ['sourcing', 'production', 'logistics'],
    'REGULATORY': ['sourcing', 'compliance', 'market_entry'],
    'TECHNOLOGY': ['rd', 'platform', 'production'],
    'SOCIAL': ['marketing', 'esg', 'communications'],
    'ENVIRONMENTAL': ['sourcing', 'esg', 'logistics'],
    'SANCTIONS': ['sourcing', 'market_entry', 'financing'],
    'MARKET': ['pricing', 'marketing', 'production'],
    'NATURAL_DISASTER': ['sourcing', 'production', 'logistics'],
}


def calculate_responsiveness(inp: ResponsivenessInput) -> ResponsivenessResult:
    """
    Score how well a team responded to active events/modifiers.

    Checks:
    1. Did they file a DecisionEventResponse?
    2. Did they adjust decisions in domains affected by the event?
    3. Were adjustments in affected markets specifically?

    Returns ResponsivenessResult with score 0-100.
    """
    if not inp.events:
        return ResponsivenessResult(
            score=70.0,  # Neutral — no signals to respond to
            events_relevant=0,
            events_addressed=0,
            feedback='No active events requiring response this round.',
        )

    details = []
    total_weighted_score = 0.0
    total_weight = 0.0

    for event in inp.events:
        weight = max(event.severity, 0.1)
        total_weight += weight

        # Expected domains for this event category
        expected_domains = event.domains or EVENT_DOMAIN_MAP.get(
            event.category.upper(), ['sourcing', 'pricing']
        )

        # Find changes in relevant domains
        relevant_changes = []
        for change in inp.decision_changes:
            domain_match = change.domain in expected_domains
            market_match = (
                not event.affected_markets
                or not change.market
                or change.market in event.affected_markets
            )
            if domain_match and market_match:
                relevant_changes.append(change)

        # Score this event response
        event_score = 0.0

        # 40% for filing a response
        if inp.has_event_response:
            event_score += 40.0

        # 60% for actual decision changes
        if relevant_changes:
            change_ratio = min(len(relevant_changes) / max(len(expected_domains), 1), 1.0)
            avg_magnitude = sum(c.magnitude for c in relevant_changes) / len(relevant_changes)
            change_score = change_ratio * 0.6 + avg_magnitude * 0.4
            event_score += 60.0 * change_score
        elif not inp.has_event_response:
            # No response at all
            event_score = 10.0  # Minimal score for not ignoring entirely

        addressed = event_score >= 30.0
        total_weighted_score += event_score * weight

        details.append(EventDetail(
            event_name=event.event_name,
            addressed=addressed,
            response_filed=inp.has_event_response,
            relevant_changes=[c.description for c in relevant_changes],
            score=round(event_score, 2),
        ))

    if total_weight > 0:
        score = total_weighted_score / total_weight
    else:
        score = 70.0

    events_addressed = sum(1 for d in details if d.addressed)

    if score >= 70:
        feedback = 'Team demonstrated strong responsiveness to market signals.'
    elif score >= 40:
        feedback = 'Team showed partial awareness of events but could respond more decisively.'
    else:
        feedback = 'Team appears to have overlooked significant events requiring strategic adjustment.'

    return ResponsivenessResult(
        score=round(min(max(score, 0.0), 100.0), 2),
        events_relevant=len(inp.events),
        events_addressed=events_addressed,
        details=details,
        feedback=feedback,
    )
