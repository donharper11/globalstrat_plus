"""
CC-32E: Agent Base Classes — Common interface for all agent types.

Every agent class implements evaluate(), resolve_dependencies(),
apply_actions(), and get_narrative().
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class AgentAction:
    """A proposed action from an agent. Not yet applied."""
    agent_class: str          # 'competitor', 'investor', 'alliance', 'government'
    agent_id: str             # Specific agent identifier
    action_type: str          # 'adjust_fit', 'trade_shares', 'update_satisfaction', etc.
    target_team: Optional[int] = None   # Team ID affected (None for market-wide)
    target_market: Optional[str] = None  # Market code affected
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5         # 1 = highest, 10 = lowest
    dependencies: List[str] = field(default_factory=list)


@dataclass
class StateSnapshot:
    """Immutable snapshot of game state at the start of agent processing."""
    round_number: int
    teams: Dict[int, Dict]        # team_id -> team data
    markets: Dict[str, Dict]      # market_code -> market data
    competitors: Dict[str, Dict]  # competitor_id -> competitor data
    investors: Dict[str, Dict]    # fund_id -> fund data
    alliances: Dict[str, Dict]    # alliance_key -> alliance data
    governments: Dict[str, Dict]  # market_code -> government data
    events_this_round: List[Dict] = field(default_factory=list)
    global_conditions: Dict = field(default_factory=dict)


class AgentBase(ABC):
    """Base class for all agent types."""

    agent_class: str = "base"

    @abstractmethod
    def evaluate(self, snapshot: StateSnapshot) -> List[AgentAction]:
        """
        Evaluate the current state and propose actions.
        Returns a list of AgentAction objects — NOT yet applied.
        Must be PURE — no side effects, no database writes.
        """
        pass

    @abstractmethod
    def resolve_dependencies(self, own_actions: List[AgentAction],
                              all_actions: List[AgentAction]) -> List[AgentAction]:
        """
        Revise proposed actions based on what other agents proposed.
        Called during convergence loop iterations.
        """
        pass

    @abstractmethod
    def apply_actions(self, actions: List[AgentAction], game, round_obj) -> None:
        """
        Apply finalized actions to the database.
        Called ONCE after convergence, inside a transaction.
        """
        pass

    @abstractmethod
    def get_narrative(self, actions: List[AgentAction]) -> List[Dict]:
        """
        Generate human-readable narrative items for briefing/ticker.
        """
        pass
