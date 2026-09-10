from __future__ import annotations

from typing import Literal

from src.graph.state import TriageState


def route_after_evaluate(state: TriageState) -> Literal["finalize_normal", "finalize_risky"]:
    return "finalize_risky" if state.get("requires_approval") else "finalize_normal"
