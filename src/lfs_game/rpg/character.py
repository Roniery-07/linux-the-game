"""RPG Character system: attributes, levels, inventory, and stats."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class HackerCharacter:
    """Player character in the cyberpunk station."""
    name: str = "Operador 0x7F"
    title: str = "Aprendiz de Sucata"
    level: int = 1
    xp: int = 0
    patience: int = 100    # 0 to 100: drops with syntax errors, restored with coffee
    insight: int = 15      # 0 to 100: system comprehension
    caffeine: int = 85     # 0 to 100: operational focus
    inventory: List[str] = field(default_factory=list)
    unlocked_titles: List[str] = field(default_factory=lambda: ["Aprendiz de Sucata"])

    def add_xp(self, amount: int) -> bool:
        """Adds XP and returns True if leveled up."""
        self.xp += amount
        needed = self.level * 100
        leveled = False
        while self.xp >= needed:
            self.xp -= needed
            self.level += 1
            self.patience = 100
            self.caffeine = min(100, self.caffeine + 30)
            self.insight = min(100, self.insight + 10)
            leveled = True
            needed = self.level * 100
            self._check_title_unlocks()
        return leveled

    def _check_title_unlocks(self):
        titles_table = [
            (2, "Engenheiro de Partições"),
            (3, "Guardião dos Somas MD5"),
            (4, "Arquiteto da Toolchain"),
            (5, "Compilador do Vácuo"),
            (8, "Mestre da Toolchain Cruzada"),
        ]
        for lvl, title in titles_table:
            if self.level >= lvl and title not in self.unlocked_titles:
                self.unlocked_titles.append(title)
                self.title = title

    def modify_patience(self, delta: int):
        self.patience = max(0, min(100, self.patience + delta))

    def modify_caffeine(self, delta: int):
        self.caffeine = max(0, min(100, self.caffeine + delta))

    def drink_coffee(self) -> str:
        if self.caffeine >= 95:
            return "☕ Seus receptores neurais já estão saturados de cafeína!"
        self.caffeine = min(100, self.caffeine + 25)
        self.patience = min(100, self.patience + 15)
        return "☕ Você toma um gole de café sintético forte. Foco restaurado (+25 Cafeína, +15 Paciência)."

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "level": self.level,
            "xp": self.xp,
            "patience": self.patience,
            "insight": self.insight,
            "caffeine": self.caffeine,
            "inventory": list(self.inventory),
            "unlocked_titles": list(self.unlocked_titles),
        }

    @classmethod
    def from_dict(cls, data: dict) -> HackerCharacter:
        return cls(**data)
