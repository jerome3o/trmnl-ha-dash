"""Data models for Home Assistant entities and goals."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GoalConfig:
    """Configuration parsed from HA label."""
    label_id: str
    weekly_target: int
    emoji: Optional[str] = None
    sound: Optional[str] = None


@dataclass
class Goal:
    """A habit/goal to track."""
    entity_id: str
    friendly_name: str
    label_id: str
    config: GoalConfig

    # Progress data (filled in later)
    current_count: int = 0
    target_by_now: float = 0.0
    status: str = "unknown"  # "ahead", "on_track", "behind"
    days_left: int = 0
