"""Interactive Terminal view with auto-complete and history."""

from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog, Static

if TYPE_CHECKING:
    from ..core.engine import GameEngine


COMMON_COMMANDS = [
    "help", "clear", "hint", "status", "coffee", "cafe", "lfs-book", "lfs-get-sources",
    "ls", "cd", "pwd", "mkdir", "rm", "touch", "cat", "echo", "export", "env",
    "whoami", "su", "exit", "useradd", "groupadd", "chown", "chmod",
    "fdisk", "cfdisk", "mkfs.ext4", "mkswap", "swapon", "swapoff", "mount", "umount",
    "df", "tar", "md5sum", "pushd", "popd", "save", "load",
]


class TerminalView(Vertical):
    """Terminal component holding output scrollback and input prompt."""

    def __init__(self, engine: GameEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.history: List[str] = []
        self.history_index: int = -1

    def compose(self) -> ComposeResult:
        yield RichLog(id="terminal-log", wrap=True, highlight=True, markup=True)
        yield Static(id="terminal-prompt-label", classes="prompt-label")
        yield Input(id="terminal-input", placeholder="Digite um comando Unix ou [1-4] para responder à IA...")

    def on_mount(self):
        log = self.query_one("#terminal-log", RichLog)
        banner = """[bold cyan]╔═══════════════════════════════════════════════════════════════════════╗
║     O ÚLTIMO KERNEL: LINUX FROM SCRATCH RPG (LFS 13.1 pt_BR)         ║
║         Terminal de Emergência - Estação Orbital Hera (2142)          ║
╚═══════════════════════════════════════════════════════════════════════╝[/bold cyan]
[dim]Digite '[bold green]help[/bold green]' para ver comandos ou '[bold yellow]hint[/bold yellow]' para orientações imediatas.[/dim]
"""
        log.write(banner)
        self.update_prompt_label()
        self.query_one("#terminal-input", Input).focus()

    def update_prompt_label(self):
        user = self.engine.fs.current_user
        cwd = self.engine.fs.pwd()
        is_root = user == "root"
        symbol = "#" if is_root else "$"
        color = "bold red" if is_root else "bold green"
        label_widget = self.query_one("#terminal-prompt-label", Static)
        label_widget.update(Text.assemble(
            (f"{user}@hera", color),
            (":", "white"),
            (cwd, "cyan"),
            (f"{symbol} ", "bold white")
        ))

    def on_input_submitted(self, event: Input.Submitted):
        cmd = event.value.strip()
        input_widget = self.query_one("#terminal-input", Input)
        input_widget.value = ""

        if not cmd:
            return

        # Add to history
        self.history.append(cmd)
        self.history_index = len(self.history)

        log = self.query_one("#terminal-log", RichLog)
        user = self.engine.fs.current_user
        cwd = self.engine.fs.pwd()
        symbol = "#" if user == "root" else "$"
        color = "red" if user == "root" else "green"

        log.write(f"[{color}]{user}@hera[/{color}]:[cyan]{cwd}[/cyan]{symbol} [bold white]{cmd}[/bold white]")

        # Execute
        result = self.engine.run_command(cmd)

        if result.system_event == "CLEAR":
            log.clear()
        elif result.output:
            log.write(result.output)

        if result.system_event == "EXIT":
            self.app.exit()

        self.update_prompt_label()
        self.app.call_after_refresh(self.app.refresh_all_views)

    def on_key(self, event: events.Key):
        input_widget = self.query_one("#terminal-input", Input)
        if not input_widget.has_focus:
            return

        if event.key == "up":
            if self.history and self.history_index > 0:
                self.history_index -= 1
                input_widget.value = self.history[self.history_index]
                input_widget.cursor_position = len(input_widget.value)
                event.prevent_default()
        elif event.key == "down":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                input_widget.value = self.history[self.history_index]
                input_widget.cursor_position = len(input_widget.value)
                event.prevent_default()
            elif self.history_index >= len(self.history) - 1:
                self.history_index = len(self.history)
                input_widget.value = ""
                event.prevent_default()
        elif event.key == "tab":
            self.handle_tab_completion(input_widget)
            event.prevent_default()

    def handle_tab_completion(self, input_widget: Input):
        val = input_widget.value
        if not val:
            return

        parts = val.split()
        if len(parts) == 1 and not val.endswith(" "):
            # Complete command
            token = parts[0]
            matches = [c for c in COMMON_COMMANDS if c.startswith(token)]
            if len(matches) == 1:
                input_widget.value = matches[0] + " "
                input_widget.cursor_position = len(input_widget.value)
            elif len(matches) > 1:
                log = self.query_one("#terminal-log", RichLog)
                log.write(f"[dim]Sugestões: {'  '.join(matches)}[/dim]")
        else:
            # Complete path or devices
            token = parts[-1] if not val.endswith(" ") else ""
            candidates = list(self.engine.fs.partitions.keys())
            node = self.engine.fs._resolve_node(self.engine.fs.cwd)
            if hasattr(node, "children"):
                candidates.extend(node.children.keys())
            if "$LFS" in token:
                token_clean = self.engine.fs.expand_vars(token)
            else:
                token_clean = token

            matches = [c for c in candidates if c.startswith(token_clean)]
            if len(matches) == 1:
                prefix = val[:val.rfind(token)] if token else val
                input_widget.value = prefix + matches[0] + " "
                input_widget.cursor_position = len(input_widget.value)
