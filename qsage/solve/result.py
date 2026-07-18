"""Solver result types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    SAT = "SAT"  # True / winning strategy exists
    UNSAT = "UNSAT"  # False / no winning strategy
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class SolveResult:
    status: Status
    backend: str
    seconds: float = 0.0
    message: str = ""
    raw: str = ""
