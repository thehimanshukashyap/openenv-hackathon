"""Scenario generators for Incident Response Triage Environment."""

from .task_easy import generate_easy_scenario
from .task_medium import generate_medium_scenario
from .task_hard import generate_hard_scenario

__all__ = [
    "generate_easy_scenario",
    "generate_medium_scenario",
    "generate_hard_scenario",
]
