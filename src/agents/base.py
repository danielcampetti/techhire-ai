"""Shared response model for all agents."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class AgentResponse(BaseModel):
    """Unified response envelope returned by every agent."""

    agent_name: str
    answer: str
    sources: list[str] = []
    data: Optional[dict] = None
    actions_taken: list[str] = []
    confidence: float = 0.0
