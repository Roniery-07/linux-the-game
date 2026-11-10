"""Game save and load serialization system."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import GameEngine


DEFAULT_SAVE_FILE = Path("savegame.json")


def get_save_path(custom_name: Optional[str] = None) -> Path:
    if custom_name:
        p = Path(custom_name)
        if not p.suffix:
            p = p.with_suffix(".json")
        return p
    return DEFAULT_SAVE_FILE


def save_game(engine: GameEngine, filename: Optional[str] = None) -> Tuple[bool, str]:
    """Serializes the complete GameEngine state into a JSON file."""
    try:
        path = get_save_path(filename)
        data = engine.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True, f"Jogo salvo com sucesso em '{path.resolve()}'."
    except Exception as e:
        return False, f"Falha ao salvar jogo: {e}"


def load_game(engine: GameEngine, filename: Optional[str] = None) -> Tuple[bool, str]:
    """Loads game state from JSON file and restores GameEngine."""
    try:
        path = get_save_path(filename)
        if not path.exists():
            return False, f"Arquivo de save não encontrado: '{path}'."

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return False, "Falha ao carregar jogo: formato de save inválido (esperado dicionário JSON)."

        engine.from_dict(data)
        return True, f"Jogo carregado com sucesso de '{path.resolve()}'."
    except Exception as e:
        return False, f"Falha ao carregar jogo: {e}"
