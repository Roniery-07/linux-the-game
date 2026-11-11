"""Main Game Engine coordinating filesystem, character, telemetry, and story."""

from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Any, Dict, List, Optional
from .virtual_fs import VirtualFS
from .parser import ShellParser, CommandResult
from ..rpg.character import HackerCharacter
from ..rpg.story_engine import StoryEngine, DialogueMessage
from ..rpg.combat import AnomalyManager


@dataclass
class Telemetry:
    """Station life-support and hardware sensors."""
    oxygen: float = 42.0       # Atmospheric percentage
    temperature: float = 48.0  # Station core temp in Celsius
    cpu_usage: float = 14.5    # Station CPU %
    ram_mb: int = 1450         # Allocated memory in MB

    def to_dict(self) -> dict:
        return {
            "oxygen": self.oxygen,
            "temperature": self.temperature,
            "cpu_usage": self.cpu_usage,
            "ram_mb": self.ram_mb,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Telemetry:
        return cls(**data)


class GameEngine:
    """Core Game Engine for 'O Último Kernel'."""

    def __init__(self):
        self.fs = VirtualFS()
        self.char = HackerCharacter()
        self.story_engine = StoryEngine()
        self.anomaly_manager = AnomalyManager()
        self.parser = ShellParser(self)
        self.telemetry = Telemetry()
        self.command_history: List[str] = []

    def tick(self, delta_seconds: float = 1.0):
        """Simulation tick for telemetry and life support."""
        if delta_seconds <= 0:
            return

        # Oxygen slowly decreases if Act 1 is not completed, stabilized if completed
        if self.story_engine.flags.get("act1_celebrated"):
            # Stabilized at safe reserve
            self.telemetry.oxygen = max(0.0, min(75.0, self.telemetry.oxygen + 0.1 * delta_seconds))
        else:
            self.telemetry.oxygen = max(0.0, self.telemetry.oxygen - (0.015 * delta_seconds))

        # CPU jitter
        base_cpu = 15.0 if self.fs.current_user == "root" else 22.0
        self.telemetry.cpu_usage = max(0.0, min(100.0, base_cpu + random.uniform(-4.0, 4.0)))

        # Temperature jitter
        self.telemetry.temperature = max(38.0, min(85.0, 48.0 + (self.telemetry.cpu_usage * 0.15) + random.uniform(-1.0, 1.0)))

        # Caffeine slow decay
        if random.random() < 0.1 * delta_seconds:
            self.char.modify_caffeine(-1)

    def run_command(self, cmd_line: str) -> CommandResult:
        """Executes a command and checks story progression triggers."""
        cmd_clean = cmd_line.strip()
        if cmd_clean:
            self.command_history.append(cmd_clean)

        res = self.parser.execute(cmd_clean)

        # Check story engine milestones
        story_broadcasts = self.story_engine.check_progress(self.fs, self.char)
        if story_broadcasts:
            broadcast_texts = [f"\n[bold magenta]TRANSMISSÃO DA IA ({m.speaker}):[/bold magenta]\n{m.text}" for m in story_broadcasts]
            res.output = (res.output + "\n" if res.output else "") + "\n".join(broadcast_texts)
            res.state_changed = True

        return res

    def get_prompt(self) -> str:
        """Returns standard shell prompt string."""
        user = self.fs.current_user
        cwd = self.fs.pwd()
        symbol = "#" if user == "root" else "$"
        if self.fs.in_chroot:
            return f"(lfs chroot) {user}:{cwd}{symbol} "
        return f"{user}@hera:{cwd}{symbol} "

    def to_dict(self) -> dict:
        return {
            "fs": self.fs.to_dict(),
            "char": self.char.to_dict(),
            "story_engine": self.story_engine.to_dict(),
            "telemetry": self.telemetry.to_dict(),
            "command_history": list(self.command_history),
            "anomaly_manager": self.anomaly_manager.to_dict(),
            "didactic_enabled": getattr(self.parser, "didactic_enabled", True),
        }

    def from_dict(self, data: dict):
        # Atomic deserialization: construct components first to prevent partial corruption
        new_fs = VirtualFS.from_dict(data["fs"])
        new_char = HackerCharacter.from_dict(data["char"])
        new_story_engine = StoryEngine.from_dict(data["story_engine"])
        new_telemetry = Telemetry.from_dict(data["telemetry"])
        new_history = list(data.get("command_history", []))
        new_anomaly_manager = AnomalyManager.from_dict(data.get("anomaly_manager", {}))

        self.fs = new_fs
        self.char = new_char
        self.story_engine = new_story_engine
        self.telemetry = new_telemetry
        self.command_history = new_history
        self.anomaly_manager = new_anomaly_manager
        self.parser = ShellParser(self)
        if "didactic_enabled" in data:
            self.parser.didactic_enabled = bool(data["didactic_enabled"])
