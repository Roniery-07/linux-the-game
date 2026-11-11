"""Entry point for 'O Último Kernel: Linux From Scratch RPG'."""

from __future__ import annotations
import argparse
import sys
from rich.console import Console
from rich.prompt import Prompt

from .core.engine import GameEngine
from .rpg.save_system import load_game


def run_headless_shell(engine: GameEngine):
    """Fallback interactive CLI shell when TUI cannot be allocated."""
    console = Console()
    console.print("[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold yellow]⚡ O ÚLTIMO KERNEL: LINUX FROM SCRATCH RPG (LFS 13.1 pt_BR) ⚡[/bold yellow]")
    console.print("[bold cyan]   Modo Shell Interativo - Estação Orbital Hera (2142)[/bold cyan]")
    console.print("[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[dim]Digite 'help' para comandos, 'hint' para objetivos, ou 'exit' para sair.[/dim]\n")

    # Show initial transmission
    if engine.story_engine.current_dialogue:
        d = engine.story_engine.current_dialogue
        console.print(f"[bold magenta]TRANSMISSÃO DA IA ({d.speaker}):[/bold magenta]\n{d.text}\n")
        if d.choices:
            for c in d.choices:
                console.print(f"  [bold green][{c['key']}][/bold green] {c['label']}")

    while True:
        user = engine.fs.current_user
        cwd = engine.fs.pwd()
        is_root = user == "root"
        symbol = "#" if is_root else "$"
        color = "red" if is_root else "green"

        if engine.fs.in_chroot:
            prompt_str = f"[yellow](lfs chroot)[/yellow] [{color}]{user}[/{color}]:[cyan]{cwd}[/cyan]{symbol} "
        else:
            prompt_str = f"[{color}]{user}@hera[/{color}]:[cyan]{cwd}[/cyan]{symbol} "

        try:
            cmd = Prompt.ask(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Conexão encerrada pelo operador.[/yellow]")
            break

        if not cmd:
            continue

        result = engine.run_command(cmd)

        if result.system_event == "EXIT":
            console.print(result.output or "Sessão finalizada.")
            break
        elif result.system_event == "CLEAR":
            console.clear()
        elif result.output:
            console.print(result.output)


def main():
    """Main CLI launcher."""
    parser = argparse.ArgumentParser(description="O Último Kernel: Linux From Scratch RPG")
    parser.add_argument("--headless", action="store_true", help="Executa no modo shell puro (sem interface TUI completa)")
    parser.add_argument("--load", type=str, default=None, help="Caminho do arquivo de save para carregar")
    args = parser.parse_args()

    engine = GameEngine()
    if args.load:
        ok, msg = load_game(engine, args.load)
        print(msg)

    # Check if stdout/stdin is interactive TTY
    if args.headless or not sys.stdin.isatty():
        run_headless_shell(engine)
    else:
        try:
            from .ui.app import LFSGameApp
            app = LFSGameApp(engine=engine)
            app.run()
        except Exception as e:
            print(f"[Aviso] Interface TUI não pôde ser iniciada ({e}). Alternando para Shell Interativo...", file=sys.stderr)
            run_headless_shell(engine)


if __name__ == "__main__":
    main()
