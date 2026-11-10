"""Inventory and System Hardware view for Station Hera."""

from __future__ import annotations
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import GameEngine


class InventoryView(Static):
    """Renders mounted storage partitions, $LFS status, and source inventory."""

    def __init__(self, engine: GameEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine

    def render(self) -> Panel:
        fs = self.engine.fs
        lfs_var = fs.env.get("LFS", "[não definido]")

        table = Table(title="Partições e Montagens ($LFS)", border_style="green", expand=True)
        table.add_column("Dispositivo", style="bold green")
        table.add_column("Tamanho", style="cyan")
        table.add_column("Sistema Arq.", style="yellow")
        table.add_column("Ponto de Montagem", style="bold white")
        table.add_column("Status", style="magenta")

        for dev, part in fs.partitions.items():
            mp = part.mount_point or "-"
            if part.is_swap_active:
                status = "SWAP ATIVO"
            elif part.mount_point:
                status = "MONTADO"
            elif part.filesystem:
                status = "FORMATADO"
            else:
                status = "NÃO FORMATADO"

            table.add_row(
                dev,
                part.size_human,
                part.filesystem or part.part_type,
                mp,
                status
            )

        # Sources info
        sources_path = f"{fs.env.get('LFS', '/mnt/lfs')}/sources"
        has_sources = fs.is_dir(sources_path)
        has_md5 = fs.is_file(f"{sources_path}/md5sums")

        sources_summary = Table.grid(padding=(0, 1))
        sources_summary.add_column(style="bold yellow", justify="right")
        sources_summary.add_column()

        sources_summary.add_row("$LFS Atual:", Text(lfs_var, style="bold cyan"))
        sources_summary.add_row("$LFS_TGT:", Text(fs.env.get("LFS_TGT", "[não definido]"), style="bold green"))
        sources_summary.add_row("Diretório $LFS/sources:", Text("EXISTE" if has_sources else "NÃO CRIADO", style="green" if has_sources else "red"))
        sources_summary.add_row("Somas MD5 Oficiais:", Text("VALIDADAS (98/98)" if self.engine.story_engine.flags.get("md5_checked") else ("ARQUIVO PRESENTE" if has_md5 else "NÃO BAIXADO"), style="bold green" if self.engine.story_engine.flags.get("md5_checked") else "yellow"))

        wrapper = Table.grid()
        wrapper.add_column()
        wrapper.add_row(table)
        wrapper.add_row(Text("\nAmbiente e Fontes:", style="bold cyan"))
        wrapper.add_row(sources_summary)

        return Panel(
            wrapper,
            title="[bold green]💾 HARDWARE & INVENTÁRIO DO LFS 💾[/bold green]",
            border_style="green"
        )
