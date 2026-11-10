"""RPG systems: character, story engine, save system, and combat anomalies."""
from .character import HackerCharacter
from .story_engine import StoryEngine, Quest, DialogueMessage
from .save_system import save_game, load_game
from .combat import (
    CompilationAnomaly,
    AnomalyManager,
    CpuOverheatAnomaly,
    LinkerErrorAnomaly,
    ContaminationWarningAnomaly,
)

__all__ = [
    "HackerCharacter",
    "StoryEngine",
    "Quest",
    "DialogueMessage",
    "save_game",
    "load_game",
    "CompilationAnomaly",
    "AnomalyManager",
    "CpuOverheatAnomaly",
    "LinkerErrorAnomaly",
    "ContaminationWarningAnomaly",
]
