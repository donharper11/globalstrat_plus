"""
CC-32E: Agent Registry — Singleton that manages all active agent classes.
"""
from typing import Dict, List, Optional

from .base import AgentBase


class AgentRegistry:
    """Singleton registry of all active agent classes."""

    _agents: Dict[str, AgentBase] = {}

    @classmethod
    def register(cls, agent: AgentBase):
        cls._agents[agent.agent_class] = agent

    @classmethod
    def get_all(cls) -> List[AgentBase]:
        return list(cls._agents.values())

    @classmethod
    def get(cls, agent_class: str) -> Optional[AgentBase]:
        return cls._agents.get(agent_class)

    @classmethod
    def clear(cls):
        """Clear all registered agents (for testing)."""
        cls._agents = {}
