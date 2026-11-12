"""Story and K.E.R.N.E.L. transmission view."""

from __future__ import annotations
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import GameEngine


class StoryView(Static):
    """Renders latest K.E.R.N.E.L. transmission and active mission goals."""

    def __init__(self, engine: GameEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine

    def refresh(self, *args, **kwargs):
        """Force layout recalculation so quest/dialogue updates render cleanly."""
        kwargs.setdefault("layout", True)
        return super().refresh(*args, **kwargs)

    def render(self) -> Panel:
        story = self.engine.story_engine
        dlg = story.current_dialogue
        quest = story.current_quest

        content = Table.grid(padding=(0, 1))
        content.add_column()

        # Transmission header
        mood_styles = {
            "alert": "bold red",
            "triumph": "bold green",
            "encouraging": "bold cyan",
            "sarcastic": "bold yellow",
            "normal": "cyan",
        }
        mood_style = mood_styles.get(dlg.mood if dlg else "normal", "cyan")

        speaker_label = f"◆ TRANSMISSÃO DA IA: {dlg.speaker if dlg else 'K.E.R.N.E.L.'} [{dlg.mood.upper() if dlg else 'ONLINE'}] ◆"
        content.add_row(Text(speaker_label, style=mood_style))
        content.add_row(Text(dlg.text if dlg else "Aguardando sinal...", style="white"))

        # Choices if available
        if dlg and dlg.choices:
            content.add_row(Text("\n[Respostas Neurais Disponíveis - Digite o número ou comando]:", style="bold yellow"))
            for c in dlg.choices:
                choice_text = Text(f"  [{c['key']}] ", style="bold green")
                choice_text.append(c["label"], style="italic white")
                content.add_row(choice_text)

        content.add_row(Text("\n" + "─" * 45, style="dim cyan"))

        # Quest header
        content.add_row(Text(f"★ MISSÃO ATUAL: {quest.title} ★", style="bold magenta"))
        content.add_row(Text(quest.description, style="dim white"))
        content.add_row(Text("\nObjetivos Operacionais:", style="bold cyan"))

        for obj in quest.objectives:
            # Simple check mark based on quest completion
            status_box = "[✔] " if quest.completed else "[ ] "
            status_style = "bold green" if quest.completed else "yellow"
            content.add_row(Text(status_box + obj, style=status_style))

        return Panel(
            content,
            title="[bold magenta]📡 K.E.R.N.E.L. COMMLINK & MISSÕES 📡[/bold magenta]",
            border_style="magenta"
        )
