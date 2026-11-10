"""Status and Telemetry view for Station Hera."""

from __future__ import annotations
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import GameEngine


class StatusView(Static):
    """Renders real-time telemetry gauges and operator status."""

    def __init__(self, engine: GameEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine

    def render(self) -> Panel:
        telem = self.engine.telemetry
        char = self.engine.char

        # Gauge bar helper
        def make_bar(val: float, max_val: float = 100.0, width: int = 14) -> Text:
            ratio = max(0.0, min(1.0, val / max_val))
            filled = int(ratio * width)
            empty = width - filled
            color = "green" if ratio > 0.45 else ("yellow" if ratio > 0.25 else "red")
            bar_text = Text()
            bar_text.append("[" + "=" * filled, style=f"bold {color}")
            bar_text.append("-" * empty + "]", style="dim")
            bar_text.append(f" {val:>4.1f}%", style=color)
            return bar_text

        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold cyan", justify="right")
        table.add_column()

        # Telemetry
        table.add_row("Oxigênio Hera:", make_bar(telem.oxygen))
        table.add_row("Temp. Reator:", Text(f"{telem.temperature:.1f} °C", style="bold red" if telem.temperature > 70 else "yellow"))
        table.add_row("Carga CPU:", make_bar(telem.cpu_usage))
        table.add_row("Memória RAM:", Text(f"{telem.ram_mb} MB / 8192 MB", style="cyan"))

        table.add_row("", Text(""))  # spacer
        table.add_row("Operador:", Text(f"{char.name}", style="bold green"))
        table.add_row("Patente:", Text(f"{char.title} (Nv. {char.level})", style="yellow"))
        xp_needed = char.level * 100
        table.add_row("Experiência:", Text(f"{char.xp}/{xp_needed} XP", style="magenta"))
        table.add_row("Cafeína:", make_bar(char.caffeine))
        table.add_row("Paciência:", make_bar(char.patience))

        return Panel(
            table,
            title="[bold cyan]⚡ TELEMETRIA DA ESTAÇÃO HERA ⚡[/bold cyan]",
            border_style="cyan"
        )
