"""
CC-32E: Agent module — registers all agent classes with the orchestrator.

Import this module to register agents. The orchestrator will pick them up
via AgentRegistry.get_all().
"""
from .registry import AgentRegistry
from .competitors import CompetitorAgent
from .investors import InvestorAgent
from .alliances import AllianceAgent
from .governments import GovernmentAgent

AgentRegistry.register(CompetitorAgent())
AgentRegistry.register(InvestorAgent())
AgentRegistry.register(AllianceAgent())
AgentRegistry.register(GovernmentAgent())
