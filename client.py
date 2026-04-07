"""
Simple HTTP client for the Incident Response Triage Environment.
For inference use, prefer using requests directly (as in inference.py).
This client is a convenience wrapper.
"""

import requests
from typing import Optional


class IncidentResponseClient:
    """
    Lightweight HTTP client wrapping the environment's REST API.

    Usage:
        client = IncidentResponseClient("http://localhost:8000")
        obs = client.reset("easy")
        obs = client.step({"action_type": "query_alerts", "task_name": "easy"})
        state = client.state("easy")
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def reset(self, task_name: str = "easy") -> dict:
        r = requests.post(
            f"{self.base_url}/reset",
            params={"task_name": task_name},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def step(self, action: dict) -> dict:
        r = requests.post(
            f"{self.base_url}/step",
            json=action,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def state(self, task_name: str = "easy") -> dict:
        r = requests.get(
            f"{self.base_url}/state",
            params={"task_name": task_name},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def health(self) -> dict:
        r = requests.get(f"{self.base_url}/health", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def schema(self) -> dict:
        r = requests.get(f"{self.base_url}/schema", timeout=self.timeout)
        r.raise_for_status()
        return r.json()
