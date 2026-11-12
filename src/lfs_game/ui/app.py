"""Textual Cyberpunk Application for 'O Último Kernel'."""

from __future__ import annotations
from typing import Optional
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, RichLog, Static, TabbedContent, TabPane

from ..core.engine import GameEngine
from ..core.sandbox import SANDBOX_TARGETS
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

SandboxModalScreen {
    align: center middle;
    background: rgba(9, 13, 19, 0.85);
}

#sandbox-dialog {
    width: 78;
    height: 85%;
    max-height: 36;
    background: #161b22;
    border: heavy #d29922;
    padding: 1 2;
}

#sandbox-title {
    height: auto;
    margin-bottom: 1;
    text-align: center;
}

#sandbox-list {
    height: 1fr;
    border: solid #30363d;
    background: #0d1117;
    padding: 0 1;
    margin-bottom: 1;
}

.sandbox-target-btn {
    width: 100%;
    margin: 0 0 1 0;
    background: #1f2937;
    color: #58a6ff;
    border: solid #30363d;
    text-align: left;
}

.sandbox-target-btn:hover, .sandbox-target-btn:focus {
    background: #238636;
    color: #ffffff;
    border: solid #3fb950;
}

#sandbox-btn-cancel {
    width: 100%;
}
"""


class SandboxModalScreen(ModalScreen[Optional[str]]):
    """Modal selector for jumping directly to any Act or Chapter in Sandbox Mode."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="sandbox-dialog"):
            yield Static(
                "[bold yellow]⚡ MODO TESTE / SANDBOX — TELEPORTE ENTRE ATOS E CAPÍTULOS ⚡[/bold yellow]\n"
                "[dim]Selecione o destino desejado ou pressione ESC para cancelar:[/dim]",
                id="sandbox-title",
            )
            with VerticalScroll(id="sandbox-list"):
                for target in SANDBOX_TARGETS:
                    btn = Button(
                        f"[{target.key}] {target.label} ({target.chapter})",
                        id=f"sandbox-btn-{target.key}",
                        classes="sandbox-target-btn",
                    )
                    btn.tooltip = target.description
                    yield btn
            yield Button("✖ Cancelar (ESC)", id="sandbox-btn-cancel", variant="error")

    def query(self, selector=None):
        if isinstance(selector, str) and selector.startswith("#jump-"):
            target_key = selector[len("#jump-"):]
            alt = "#sandbox-btn-cancel" if target_key == "cancel" else f"#sandbox-btn-{target_key}"
            res = super().query(selector)
            if not res:
                return super().query(alt)
            return res
        return super().query(selector)

    def query_one(self, selector, expect_type=None):
        if isinstance(selector, str) and selector.startswith("#jump-"):
            target_key = selector[len("#jump-"):]
            alt = "#sandbox-btn-cancel" if target_key == "cancel" else f"#sandbox-btn-{target_key}"
            try:
                return super().query_one(selector, expect_type)
            except Exception:
                return super().query_one(alt, expect_type)
        return super().query_one(selector, expect_type)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id in ("sandbox-btn-cancel", "jump-cancel"):
            self.dismiss(None)
        elif btn_id.startswith("sandbox-btn-"):
            self.dismiss(btn_id[len("sandbox-btn-"):])
        elif btn_id.startswith("jump-"):
            self.dismiss(btn_id[len("jump-"):])

    def action_cancel(self) -> None:
        self.dismiss(None)


class LFSGameApp(App):
    """Main Textual Cyberpunk TUI Application."""

    TITLE = "⚡ O ÚLTIMO KERNEL: LFS 13.1 RPG ⚡"
    SUB_TITLE = "Estação Orbital Hera (2142) - Modo de Sobrevivência"
    CSS = CYBERPUNK_CSS

    BINDINGS = [
        Binding("f1", "show_book", "Manual LFS (F1)", priority=True),
        Binding("f2", "show_hint", "Missões & Dica (F2)", priority=True),
        Binding("f3", "show_glossary", "Glossário Didático (F3)", priority=True),
        Binding("f4", "open_sandbox", "Modo Teste (F4)", priority=True),
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

    def query_one(self, selector, expect_type=None):
        if isinstance(selector, str) and selector.startswith("#jump-"):
            if isinstance(self.screen, SandboxModalScreen):
                return self.screen.query_one(selector, expect_type)
        return super().query_one(selector, expect_type)

    def refresh_all_views(self):
        try:
            self.query_one("#story-view", StoryView).refresh(layout=True)
            self.query_one("#status-view", StatusView).refresh(layout=True)
            self.query_one("#inventory-view", InventoryView).refresh(layout=True)
            self.query_one("#terminal-view", TerminalView).update_prompt_label()
        except Exception:
            pass

    def action_open_sandbox(self):
        self.push_screen(SandboxModalScreen(), callback=self._on_sandbox_selected)

    def _on_sandbox_selected(self, target_key: Optional[str]) -> None:
        if target_key:
            ok, msg = self.engine.jump_to(target_key)
            try:
                self.query_one("#terminal-log", RichLog).write(msg)
            except Exception:
                pass
            self.refresh_all_views()
        try:
            self.query_one("#terminal-input").focus()
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

    def action_show_glossary(self):
        term = self.query_one("#terminal-view", TerminalView)
        res = self.engine.run_command("glossario")
        from textual.widgets import RichLog
        self.query_one("#terminal-log", RichLog).write(res.output)

    def action_quick_save(self):
        res = self.engine.run_command("save")
        from textual.widgets import RichLog
        self.query_one("#terminal-log", RichLog).write(res.output)

    def action_quit_app(self):
        self.exit()
