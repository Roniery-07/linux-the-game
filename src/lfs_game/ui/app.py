"""Textual Cyberpunk Application for 'O Último Kernel'."""

from __future__ import annotations
from typing import Optional
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, TabbedContent, TabPane

from ..core.engine import GameEngine
from .inventory_view import InventoryView
from .status_view import StatusView
from .story_view import StoryView
from .terminal_view import TerminalView


CYBERPUNK_CSS = """
Screen {
    background: #0d1117;
    color: #e6edf3;
}

Header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
}

Footer {
    background: #161b22;
    color: #8b949e;
}

#main-container {
    width: 100%;
    height: 100%;
}

#left-panel {
    width: 62%;
    height: 100%;
    border-right: heavy #30363d;
    padding: 0 1;
}

#right-panel {
    width: 38%;
    height: 100%;
    padding: 0 1;
}

#terminal-log {
    height: 1fr;
    background: #090d13;
    border: solid #238636;
    padding: 1;
}

.prompt-label {
    height: 1;
    margin-top: 1;
}

#terminal-input {
    height: 3;
    border: solid #58a6ff;
    background: #161b22;
    color: #58a6ff;
}

TabbedContent {
    height: 100%;
}

TabPane {
    padding: 1 0;
}
"""


class LFSGameApp(App):
    """Main Textual Cyberpunk TUI Application."""

    TITLE = "⚡ O ÚLTIMO KERNEL: LFS 13.1 RPG ⚡"
    SUB_TITLE = "Estação Orbital Hera (2142) - Modo de Sobrevivência"
    CSS = CYBERPUNK_CSS

    BINDINGS = [
        Binding("f1", "show_book", "Manual LFS (F1)", priority=True),
        Binding("f2", "show_hint", "Missões & Dica (F2)", priority=True),
        Binding("f5", "quick_save", "Salvar Jogo (F5)", priority=True),
        Binding("f10", "quit_app", "Sair (F10)", priority=True),
    ]

    def __init__(self, engine: Optional[GameEngine] = None, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine or GameEngine()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield TerminalView(self.engine, id="terminal-view")
            with Vertical(id="right-panel"):
                with TabbedContent(initial="tab-story"):
                    with TabPane("📡 IA & Missões", id="tab-story"):
                        yield StoryView(self.engine, id="story-view")
                    with TabPane("⚡ Telemetria", id="tab-status"):
                        yield StatusView(self.engine, id="status-view")
                    with TabPane("💾 Hardware & $LFS", id="tab-inventory"):
                        yield InventoryView(self.engine, id="inventory-view")
        yield Footer()

    def on_mount(self):
        self.set_interval(1.0, self.on_telemetry_tick)

    def on_telemetry_tick(self):
        self.engine.tick(delta_seconds=1.0)
        self.refresh_all_views()

    def refresh_all_views(self):
        try:
            self.query_one("#story-view", StoryView).refresh()
            self.query_one("#status-view", StatusView).refresh()
            self.query_one("#inventory-view", InventoryView).refresh()
            self.query_one("#terminal-view", TerminalView).update_prompt_label()
        except Exception:
            pass

    def action_show_book(self):
        term = self.query_one("#terminal-view", TerminalView)
        res = self.engine.run_command("lfs-book 2")
        from textual.widgets import RichLog
        self.query_one("#terminal-log", RichLog).write(res.output)

    def action_show_hint(self):
        term = self.query_one("#terminal-view", TerminalView)
        res = self.engine.run_command("hint")
        from textual.widgets import RichLog
        self.query_one("#terminal-log", RichLog).write(res.output)

    def action_quick_save(self):
        res = self.engine.run_command("save")
        from textual.widgets import RichLog
        self.query_one("#terminal-log", RichLog).write(res.output)

    def action_quit_app(self):
        self.exit()
