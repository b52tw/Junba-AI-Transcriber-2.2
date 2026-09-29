from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


@dataclass
class TranscriptResult:
    text: str
    segments: list[Segment] = field(default_factory=list)
    language: Optional[str] = None
    engine: str = ''
