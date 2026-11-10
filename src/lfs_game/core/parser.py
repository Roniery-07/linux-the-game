"""Shell parser and command dispatcher for LFS simulator."""

from __future__ import annotations
from dataclasses import dataclass
import posixpath
import re
import shlex
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import GameEngine


@dataclass
class CommandResult:
    """Structured result from command execution."""
    output: str
    success: bool
    state_changed: bool = False
    system_event: Optional[str] = None  # e.g., "CLEAR", "EXIT", "HELP", "REFRESH"


def brace_expand(text: str) -> List[str]:
    """Expands bash brace expressions like $LFS/{usr{,/*},lib,var,etc,bin,sbin,tools}."""
    start = -1
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    prefix = text[:start]
                    suffix = text[i + 1:]
                    inner = text[start + 1:i]

                    # Split inner on commas at depth 0
                    parts = []
                    curr = []
                    subdepth = 0
                    for c in inner:
                        if c == "{":
                            subdepth += 1
                            curr.append(c)
                        elif c == "}":
                            subdepth -= 1
                            curr.append(c)
                        elif c == "," and subdepth == 0:
                            parts.append("".join(curr))
                            curr = []
                        else:
                            curr.append(c)
                    parts.append("".join(curr))

                    results = []
                    for part in parts:
                        for expanded_sub in brace_expand(prefix + part + suffix):
                            results.append(expanded_sub)
                    return results
    return [text]


class ShellParser:
    """Parses shell strings and delegates execution to GameEngine subsystems."""

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.dir_stack: List[str] = []

    def execute(self, command_line: str) -> CommandResult:
        """Executes a full command line string, handling && and ; chains."""
        raw = command_line.strip()
        if not raw:
            return CommandResult(output="", success=True)

        # Handle active anomaly choice shortcut if an anomaly is currently active
        if hasattr(self.engine, "anomaly_manager") and self.engine.anomaly_manager.active_anomaly:
            if re.match(r"^[1-9]$", raw):
                ok, msg = self.engine.anomaly_manager.resolve(raw, self.engine)
                return CommandResult(output=msg, success=ok, state_changed=True)

        # Handle dialogue choice shortcut [1, 2, 3, 4] if current dialogue has choices
        if re.match(r"^[1-9]$", raw):
            choice_msg = self.engine.story_engine.handle_choice(raw)
            if choice_msg:
                return CommandResult(
                    output=f"[bold green]{choice_msg.speaker}:[/bold green] {choice_msg.text}",
                    success=True,
                    state_changed=True
                )

        # Syntax checks for invalid shell tokens
        if ";;" in raw:
            return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado ';;'", success=False)

        if "||" in raw:
            return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado '||'", success=False)

        if raw == "|" or raw.startswith("| ") or raw.startswith("|") or raw.endswith("|"):
            return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado '|'", success=False)

        # Handle chained commands with '&&'
        if "&&" in raw:
            sub_commands = raw.split("&&")
            if any(not sub.strip() for sub in sub_commands):
                return CommandResult(
                    output="bash: erro de sintaxe próximo ao token inesperado '&&'",
                    success=False
                )
            combined_output = []
            for sub in sub_commands:
                res = self._execute_single(sub.strip())
                if res.output:
                    combined_output.append(res.output)
                if not res.success:
                    return CommandResult(
                        output="\n".join(combined_output),
                        success=False,
                        state_changed=res.state_changed,
                        system_event=res.system_event
                    )
            return CommandResult(
                output="\n".join(combined_output),
                success=True,
                state_changed=True
            )

        # Handle chained commands with ';'
        if ";" in raw:
            sub_commands = raw.split(";")
            combined_output = []
            any_success = True
            for sub in sub_commands:
                sub_clean = sub.strip()
                if not sub_clean:
                    continue
                res = self._execute_single(sub_clean)
                if res.output:
                    combined_output.append(res.output)
                if not res.success:
                    any_success = False
            return CommandResult(
                output="\n".join(combined_output),
                success=any_success,
                state_changed=True
            )

        return self._execute_single(raw)

    def _execute_single(self, cmd_str: str, stdin_data: str = "") -> CommandResult:
        """Executes a single command or pipeline."""
        if "|" in cmd_str:
            pipe_parts = cmd_str.split("|")
            if any(not p.strip() for p in pipe_parts):
                return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado '|'", success=False)
            curr_input = stdin_data
            last_res = CommandResult(output="", success=True)
            for part in pipe_parts:
                last_res = self._execute_stage(part.strip(), stdin_data=curr_input)
                if not last_res.success:
                    return last_res
                curr_input = last_res.output
            return last_res
        return self._execute_stage(cmd_str, stdin_data=stdin_data)

    def _execute_stage(self, stage_str: str, stdin_data: str = "") -> CommandResult:
        """Executes a single pipeline stage with optional input data and redirection."""
        fs = self.engine.fs

        # Check for redirection: > or >> or &>
        redirect_file = None
        append_mode = False

        if ">>" in stage_str:
            parts = stage_str.split(">>", 1)
            stage_str = parts[0].strip()
            target = parts[1].strip()
            if target:
                redirect_file = fs.expand_vars(target)
            append_mode = True
        elif "&>" in stage_str:
            parts = stage_str.split("&>", 1)
            stage_str = parts[0].strip()
            target = parts[1].strip()
            if target:
                redirect_file = fs.expand_vars(target)
            append_mode = False
        elif ">" in stage_str:
            parts = stage_str.split(">", 1)
            stage_str = parts[0].strip()
            target = parts[1].strip()
            if target:
                redirect_file = fs.expand_vars(target)
            append_mode = False

        # Variable expansion
        expanded_str = fs.expand_vars(stage_str)

        try:
            tokens = shlex.split(expanded_str)
        except ValueError as e:
            return CommandResult(output=f"bash: erro de sintaxe: {e}", success=False)

        if not tokens:
            return CommandResult(output="", success=True)

        # Perform brace expansion on arguments
        final_tokens: List[str] = []
        for t in tokens:
            final_tokens.extend(brace_expand(t))

        cmd = final_tokens[0]
        args = final_tokens[1:]

        # Dispatch specialized handlers for build tools and sanity checks
        if cmd in ("./configure", "../configure", "configure") or cmd.endswith("/configure"):
            result = self._handle_configure(cmd, args)
        elif cmd in ("$LFS_TGT-gcc", "x86_64-lfs-linux-gnu-gcc", "gcc") or cmd.endswith("-gcc"):
            result = self._handle_gcc(cmd, args, stdin_data=stdin_data)
        elif cmd in ("readelf", "$LFS_TGT-readelf", "x86_64-lfs-linux-gnu-readelf") or cmd.endswith("readelf"):
            result = self._handle_readelf(cmd, args)
        else:
            handler_name = f"_cmd_{cmd.replace('.', '_').replace('-', '_')}"
            handler = getattr(self, handler_name, None)
            if handler:
                try:
                    result = handler(args, stdin_data=stdin_data)
                except TypeError:
                    result = handler(args)
            else:
                result = self._fallback_command(cmd, args)

        # Handle redirection to file if requested
        if redirect_file and result.success:
            ok, err = fs.write_file(redirect_file, result.output + "\n", append=append_mode)
            if not ok:
                return CommandResult(output=err, success=False)
            return CommandResult(output="", success=True, state_changed=True)

        return result

    def _fallback_command(self, cmd: str, args: List[str]) -> CommandResult:
        # Check if user tried variable assignment without export (e.g., LFS=/mnt/lfs)
        if "=" in cmd:
            k, v = cmd.split("=", 1)
            self.engine.fs.env[k] = v.strip("\"'")
            return CommandResult(
                output=f"[dim]Variável de ambiente atribuída localmente: {k}={v}[/dim]",
                success=True,
                state_changed=True
            )
        self.engine.char.modify_patience(-3)
        return CommandResult(
            output=(
                f"bash: {cmd}: comando não encontrado.\n"
                f"[yellow]Dica:[/yellow] Digite '[bold]help[/bold]' para ver comandos disponíveis ou '[bold]hint[/bold]' para auxílio da IA."
            ),
            success=False
        )

    # --- Built-in Command Handlers ---

    def _cmd_help(self, args: List[str]) -> CommandResult:
        help_text = """[bold cyan]=== TERMINAL DA ESTAÇÃO HERA - COMANDOS DISPONÍVEIS ===[/bold cyan]
[bold green]Navegação & Arquivos:[/bold green] ls, cd, pwd, mkdir, rm, touch, cat, echo, cp, ln, find, df
[bold green]Controle do Hospedeiro:[/bold green] export, env, whoami, su, exit, useradd, groupadd, chown, chmod
[bold green]Discos & Partições:[/bold green] fdisk, cfdisk, mkfs.ext4, mkswap, swapon, swapoff, mount, umount
[bold green]LFS 13.1 Toolchain:[/bold green] lfs-book [cap], lfs-status-tools, lfs-compile-tools [all|pacote], ./configure, make, readelf, grep, patch, sed, md5sum, tar
[bold green]Sobrevivência & Anomalias:[/bold green] lfs-resolve [número], anomaly, hint, status, coffee, save [nome], load [nome], clear, exit
"""
        return CommandResult(output=help_text, success=True, system_event="HELP")

    def _cmd_clear(self, args: List[str]) -> CommandResult:
        return CommandResult(output="", success=True, system_event="CLEAR")

    def _cmd_hint(self, args: List[str]) -> CommandResult:
        hint_text = self.engine.story_engine.get_hint()
        return CommandResult(output=hint_text, success=True)

    def _cmd_status(self, args: List[str]) -> CommandResult:
        char = self.engine.char
        telem = self.engine.telemetry
        q = self.engine.story_engine.current_quest
        output = f"""[bold cyan]=== TELEMETRIA DA ESTAÇÃO & STATUS DO OPERADOR ===[/bold cyan]
[bold yellow]Operador:[/bold yellow] {char.name} ({char.title}) | [bold]Nível:[/bold] {char.level} | [bold]XP:[/bold] {char.xp}
[bold]Paciência:[/bold] {char.patience}% | [bold]Compreensão (Insight):[/bold] {char.insight}% | [bold]Cafeína:[/bold] {char.caffeine}%
[bold green]Suporte Vital:[/bold green] Oxigênio: {telem.oxygen:.1f}% | Temp: {telem.temperature:.1f}°C | CPU: {telem.cpu_usage:.1f}% | RAM: {telem.ram_mb} MB
[bold magenta]Missão Atual:[/bold magenta] {q.title}
{q.description}
"""
        return CommandResult(output=output, success=True)

    def _cmd_coffee(self, args: List[str]) -> CommandResult:
        msg = self.engine.char.drink_coffee()
        return CommandResult(output=msg, success=True, state_changed=True)

    def _cmd_cafe(self, args: List[str]) -> CommandResult:
        return self._cmd_coffee(args)

    def _cmd_lfs_book(self, args: List[str]) -> CommandResult:
        from ..data.lfs_manifest import get_chapter_help
        ch_num = int(args[0]) if args and args[0].isdigit() else 2
        guide = get_chapter_help(ch_num)
        return CommandResult(output=guide, success=True)

    def _cmd_pwd(self, args: List[str]) -> CommandResult:
        return CommandResult(output=self.engine.fs.pwd(), success=True)

    def _cmd_cd(self, args: List[str]) -> CommandResult:
        target = args[0] if args else "~"
        ok, msg = self.engine.fs.cd(target)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_pushd(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(output="pushd: nenhum diretório especificado", success=False)
        self.dir_stack.append(self.engine.fs.pwd())
        ok, msg = self.engine.fs.cd(args[0])
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_popd(self, args: List[str]) -> CommandResult:
        if not self.dir_stack:
            return CommandResult(output="popd: pilha de diretórios vazia", success=False)
        target = self.dir_stack.pop()
        ok, msg = self.engine.fs.cd(target)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_ls(self, args: List[str]) -> CommandResult:
        detailed = False
        all_files = False
        paths = []
        for a in args:
            if a.startswith("-"):
                if "l" in a:
                    detailed = True
                if "a" in a:
                    all_files = True
            else:
                paths.append(a)

        target = paths[0] if paths else None
        ok, output = self.engine.fs.ls(target, detailed=detailed, all_files=all_files)
        return CommandResult(output=output, success=ok)

    def _cmd_mkdir(self, args: List[str]) -> CommandResult:
        parents = False
        verbose = False
        paths = []
        for a in args:
            if a.startswith("-"):
                if "p" in a:
                    parents = True
                if "v" in a:
                    verbose = True
            else:
                paths.append(a)

        if not paths:
            return CommandResult(output="mkdir: operando ausente", success=False)

        messages = []
        all_ok = True
        for p in paths:
            ok, msg = self.engine.fs.mkdir(p, parents=parents, verbose=verbose)
            if msg:
                messages.append(msg)
            if not ok:
                all_ok = False

        return CommandResult(output="\n".join(messages), success=all_ok, state_changed=all_ok)

    def _cmd_touch(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(output="touch: operando de arquivo ausente", success=False)
        for p in args:
            ok, msg = self.engine.fs.touch(p)
            if not ok:
                return CommandResult(output=msg, success=False)
        return CommandResult(output="", success=True, state_changed=True)

    def _cmd_cat(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(output="", success=True)
        contents = []
        for p in args:
            ok, text = self.engine.fs.read_file(p)
            if not ok:
                return CommandResult(output=text, success=False)
            contents.append(text)
        return CommandResult(output="".join(contents).rstrip("\n"), success=True)

    def _cmd_echo(self, args: List[str]) -> CommandResult:
        return CommandResult(output=" ".join(args), success=True)

    def _cmd_rm(self, args: List[str]) -> CommandResult:
        recursive = False
        force = False
        paths = []
        for a in args:
            if a.startswith("-"):
                if "r" in a or "R" in a:
                    recursive = True
                if "f" in a:
                    force = True
            else:
                paths.append(a)

        if not paths and not force:
            return CommandResult(output="rm: operando ausente", success=False)

        for p in paths:
            ok, msg = self.engine.fs.rm(p, recursive=recursive, force=force)
            if not ok:
                return CommandResult(output=msg, success=False)
        return CommandResult(output="", success=True, state_changed=True)

    def _cmd_export(self, args: List[str]) -> CommandResult:
        if not args:
            # List all exported variables
            lines = [f"declare -x {k}=\"{v}\"" for k, v in sorted(self.engine.fs.env.items())]
            return CommandResult(output="\n".join(lines), success=True)

        for a in args:
            if "=" in a:
                k, v = a.split("=", 1)
                self.engine.fs.env[k] = v.strip("\"'")
            else:
                # e.g. export LFS
                pass
        return CommandResult(output="", success=True, state_changed=True)

    def _cmd_env(self, args: List[str]) -> CommandResult:
        lines = [f"{k}={v}" for k, v in sorted(self.engine.fs.env.items())]
        return CommandResult(output="\n".join(lines), success=True)

    def _cmd_whoami(self, args: List[str]) -> CommandResult:
        return CommandResult(output=self.engine.fs.current_user, success=True)

    def _cmd_su(self, args: List[str]) -> CommandResult:
        login = False
        username = "root"
        for a in args:
            if a == "-":
                login = True
            elif not a.startswith("-"):
                username = a

        ok, msg = self.engine.fs.su(username, login=login)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_exit(self, args: List[str]) -> CommandResult:
        if self.engine.fs.user_stack:
            ok, msg = self.engine.fs.exit_user()
            return CommandResult(output=msg, success=ok, state_changed=True)
        return CommandResult(output="Conexão com a estação encerrada.", success=True, system_event="EXIT")

    def _cmd_useradd(self, args: List[str]) -> CommandResult:
        group = None
        home = None
        shell = "/bin/bash"
        create_home = True
        username = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-g" and i + 1 < len(args):
                group = args[i + 1]
                i += 2
            elif arg == "-s" and i + 1 < len(args):
                shell = args[i + 1]
                i += 2
            elif arg == "-m":
                create_home = True
                i += 1
            elif arg == "-k" and i + 1 < len(args):
                # skel directory (ignore or record)
                i += 2
            elif not arg.startswith("-"):
                username = arg
                i += 1
            else:
                i += 1

        if not username:
            return CommandResult(output="useradd: forneça um nome de usuário", success=False)

        ok, msg = self.engine.fs.useradd(username, group=group, home=home, shell=shell, create_home=create_home)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_groupadd(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(output="groupadd: forneça o nome do grupo", success=False)
        ok, msg = self.engine.fs.groupadd(args[0])
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_chown(self, args: List[str]) -> CommandResult:
        recursive = False
        verbose = False
        pos_args = []
        for a in args:
            if a.startswith("-"):
                if "R" in a or "r" in a:
                    recursive = True
                if "v" in a:
                    verbose = True
            else:
                pos_args.append(a)

        if len(pos_args) < 2:
            return CommandResult(output="chown: operandos insuficientes", success=False)

        owner_group = pos_args[0]
        targets = pos_args[1:]
        outputs = []
        all_ok = True

        for target in targets:
            ok, msg = self.engine.fs.chown(target, owner_group, recursive=recursive, verbose=verbose)
            if msg:
                outputs.append(msg)
            if not ok:
                all_ok = False

        return CommandResult(output="\n".join(outputs), success=all_ok, state_changed=all_ok)

    def _cmd_chmod(self, args: List[str]) -> CommandResult:
        recursive = False
        verbose = False
        pos_args = []
        for a in args:
            if a.startswith("-"):
                if "R" in a or "r" in a:
                    recursive = True
                if "v" in a:
                    verbose = True
            else:
                pos_args.append(a)

        if len(pos_args) < 2:
            return CommandResult(output="chmod: operandos insuficientes", success=False)

        mode_expr = pos_args[0]
        targets = pos_args[1:]
        outputs = []
        all_ok = True

        for target in targets:
            ok, msg = self.engine.fs.chmod(target, mode_expr, recursive=recursive, verbose=verbose)
            if msg:
                outputs.append(msg)
            if not ok:
                all_ok = False

        return CommandResult(output="\n".join(outputs), success=all_ok, state_changed=all_ok)

    # --- Disk & Mount Operations ---

    def _cmd_fdisk(self, args: List[str]) -> CommandResult:
        dev = args[0] if args else "/dev/sda"
        if self.engine.fs.current_user != "root":
            return CommandResult(output=f"fdisk: não foi possível abrir {dev}: Permissão negada", success=False)
        output = f"""Disco {dev}: 60 GiB, 64424509440 bytes, 125829120 setores
Unidades: setor de 1 * 512 = 512 bytes
Tamanho de setor (lógico/físico): 512 bytes / 512 bytes
Tipo de rótulo do disco: gpt
Identificador do disco: 7F21B9A1-331B-4E38-9E7D-3D9B51E28C8A

Dispositivo   Início       Fim   Setores Tamanho Tipo
/dev/sda1       2048   1050623   1048576    512M Sistema EFI
/dev/sda2    1050624   9439231   8388608      4G Linux swap
/dev/sda3    9439232 125827071 116387840     55G Linux de sistema de arquivos
"""
        return CommandResult(output=output, success=True)

    def _cmd_cfdisk(self, args: List[str]) -> CommandResult:
        return self._cmd_fdisk(args)

    def _cmd_mkfs_ext4(self, args: List[str]) -> CommandResult:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return CommandResult(output="mkfs.ext4: nenhum dispositivo especificado", success=False)
        ok, msg = self.engine.fs.format_partition(targets[0], "ext4")
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_mkswap(self, args: List[str]) -> CommandResult:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return CommandResult(output="mkswap: nenhum dispositivo especificado", success=False)
        ok, msg = self.engine.fs.make_swap(targets[0])
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_swapon(self, args: List[str]) -> CommandResult:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            # show active swap
            lines = ["Nome de arquivo    Tipo       Tamanho  Usado  Prioridade"]
            for dev, part in self.engine.fs.partitions.items():
                if part.is_swap_active:
                    lines.append(f"{dev:<18} partição   {part.size_human:<8} 0B     -2")
            return CommandResult(output="\n".join(lines), success=True)

        ok, msg = self.engine.fs.swapon(targets[0])
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_swapoff(self, args: List[str]) -> CommandResult:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return CommandResult(output="swapoff: nenhum dispositivo especificado", success=False)
        ok, msg = self.engine.fs.swapoff(targets[0])
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_mount(self, args: List[str]) -> CommandResult:
        verbose = False
        fstype = "ext4"
        pos_args = []

        i = 0
        while i < len(args):
            a = args[i]
            if a == "-v":
                verbose = True
                i += 1
            elif a == "-t" and i + 1 < len(args):
                fstype = args[i + 1]
                i += 2
            elif not a.startswith("-"):
                pos_args.append(a)
                i += 1
            else:
                i += 1

        if not pos_args:
            # Show mount table
            lines = []
            for mp, dev in self.engine.fs.mounts.items():
                lines.append(f"{dev} on {mp} type {fstype} (rw,relatime)")
            return CommandResult(output="\n".join(lines) if lines else "Nenhum sistema montado em $LFS", success=True)

        if len(pos_args) < 2:
            return CommandResult(output="mount: especifique dispositivo e ponto de montagem", success=False)

        device, mp = pos_args[0], pos_args[1]
        ok, msg = self.engine.fs.mount(device, mp, fstype=fstype, verbose=verbose)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_umount(self, args: List[str]) -> CommandResult:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return CommandResult(output="umount: especifique o dispositivo ou ponto de montagem", success=False)
        ok, msg = self.engine.fs.umount(targets[0], verbose=True)
        return CommandResult(output=msg, success=ok, state_changed=ok)

    def _cmd_df(self, args: List[str]) -> CommandResult:
        return CommandResult(output=self.engine.fs.df(), success=True)

    # --- LFS Packages and MD5 Checks ---

    def _cmd_lfs_get_sources(self, args: List[str]) -> CommandResult:
        """Retrieves and populates all official LFS 13.1 sources and md5sums into $LFS/sources."""
        from ..data.lfs_manifest import list_packages, get_md5sums_text

        lfs_var = self.engine.fs.env.get("LFS", "/mnt/lfs")
        sources_dir = f"{lfs_var}/sources"

        if not self.engine.fs.exists(sources_dir):
            return CommandResult(
                output=f"[red]Erro:[/red] Diretório '{sources_dir}' não existe. Crie-o primeiro com 'mkdir -v $LFS/sources'.",
                success=False
            )

        pkgs = list_packages()
        for p in pkgs:
            filepath = posixpath.join(sources_dir, p.tarball)
            self.engine.fs.write_file(filepath, f"# Tarball binário simulado para {p.name} {p.version}\n")

        # Write md5sums file
        md5_file = posixpath.join(sources_dir, "md5sums")
        self.engine.fs.write_file(md5_file, get_md5sums_text())
        self.engine.story_engine.flags["sources_downloaded"] = True

        msg = (
            f"[bold green]K.E.R.N.E.L.:[/bold green] 98 pacotes e remendos oficiais do LFS 13.1 transferidos com sucesso para '{sources_dir}'.\n"
            f"Arquivo 'md5sums' gerado. Agora execute 'md5sum -c md5sums' para validar a integridade antes de compilar."
        )
        return CommandResult(output=msg, success=True, state_changed=True)

    def _cmd_md5sum(self, args: List[str]) -> CommandResult:
        from ..data.lfs_manifest import get_package

        check_mode = "-c" in args or "--check" in args
        target_files = [a for a in args if not a.startswith("-")]

        if check_mode:
            target = target_files[0] if target_files else "md5sums"
            ok, content = self.engine.fs.read_file(target)
            if not ok:
                return CommandResult(output=content, success=False)

            results = []
            all_valid = True
            lines = content.strip().splitlines()

            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    expected_md5 = parts[0]
                    filename = parts[1].lstrip("*")
                    pkg = get_package(filename)
                    if pkg and pkg.md5 == expected_md5:
                        results.append(f"{filename}: SUCESSO")
                    else:
                        results.append(f"{filename}: FALHA")
                        all_valid = False

            self.engine.story_engine.flags["md5_checked"] = all_valid
            summary = f"\n[bold green]md5sum: {len(lines)} arquivos verificados com 100% de integridade.[/bold green]" if all_valid else "\n[bold red]md5sum: Corrupção detectada em arquivos![/bold red]"
            display_output = "\n".join(results[:10]) + f"\n[dim]... (+ {len(results)-10} arquivos validados)[/dim]" + summary
            return CommandResult(output=display_output, success=all_valid, state_changed=all_valid)

        if not target_files:
            return CommandResult(output="md5sum: arquivo ausente", success=False)

        outputs = []
        for f in target_files:
            pkg = get_package(posixpath.basename(f))
            if pkg:
                outputs.append(f"{pkg.md5}  {f}")
            else:
                outputs.append(f"da39a3ee5e6b4b0d3255bfef95601890fae0081e  {f}")
        return CommandResult(output="\n".join(outputs), success=True)

    def _cmd_tar(self, args: List[str]) -> CommandResult:
        tarball = None
        for a in args:
            if not a.startswith("-") and (".tar" in a or ".patch" in a):
                tarball = a
                break

        if not tarball:
            return CommandResult(output="tar: arquivo compactado não especificado", success=False)

        return CommandResult(
            output=f"Descompactando '{tarball}'...\nExtração simulada concluída com sucesso.",
            success=True,
            state_changed=True
        )

    # --- Save / Load Operations ---

    def _cmd_save(self, args: List[str]) -> CommandResult:
        from ..rpg.save_system import save_game
        fname = args[0] if args else None
        ok, msg = save_game(self.engine, fname)
        return CommandResult(output=msg, success=ok)

    def _cmd_load(self, args: List[str]) -> CommandResult:
        from ..rpg.save_system import load_game
        fname = args[0] if args else None
        ok, msg = load_game(self.engine, fname)
        return CommandResult(output=msg, success=ok, state_changed=ok, system_event="REFRESH")

    # --- Act 2 Build System & Cross-Toolchain Handlers ---

    def _handle_configure(self, cmd: str, args: List[str]) -> CommandResult:
        """Handles autotools ./configure and ../configure calls."""
        fs = self.engine.fs
        arg_str = " ".join(args)
        lfs_dir = fs.env.get("LFS", "/mnt/lfs")

        # Validate LFS mount point
        if lfs_dir not in fs.mounts and "/mnt/lfs" not in fs.mounts:
            return CommandResult(
                output=f"configure: error: O ponto de montagem de $LFS ('{lfs_dir}') não está montado. Monte a partição antes de configurar.",
                success=False
            )

        # Validate LFS_TGT if target is specified via variable
        if ("--target=" in arg_str or "-target" in arg_str) and not fs.env.get("LFS_TGT"):
            return CommandResult(
                output="configure: error: $LFS_TGT não está definido. Execute 'export LFS_TGT=x86_64-lfs-linux-gnu' antes de configurar.",
                success=False
            )

        # Detect target package being configured
        if "libstdc++" in cmd or "libstdc++" in arg_str:
            pkg = "libstdc++"
        elif "--with-newlib" in arg_str or "--without-headers" in arg_str:
            pkg = "gcc-pass1"
        elif "libc_cv_slibdir" in arg_str or "--enable-kernel" in arg_str:
            pkg = "glibc"
        elif "--with-sysroot" in arg_str and ("--target=" in arg_str or "$LFS_TGT" in arg_str or "x86_64-lfs" in arg_str):
            pkg = "binutils-pass1"
        elif "--64-bit-bfd" in arg_str or ("binutils" in fs.cwd.lower() and ("--host=" in arg_str or "$LFS_TGT" in arg_str)):
            pkg = "binutils-pass2"
        elif "gcc" in fs.cwd.lower() and ("--host=" in arg_str or "$LFS_TGT" in arg_str) and not "--with-newlib" in arg_str:
            pkg = "gcc-pass2"
        else:
            # Check cwd and args against tool names with word boundaries to avoid substring false positives (e.g. 'tar' in '--target=')
            matched = None
            for tool_id in ["m4", "ncurses", "bash", "coreutils", "diffutils", "file", "findutils", "gawk", "grep", "gzip", "make", "patch", "sed", "tar", "xz"]:
                if re.search(rf"\b{re.escape(tool_id)}\b", fs.cwd.lower()) or re.search(rf"\b{re.escape(tool_id)}\b", arg_str.lower()):
                    matched = tool_id
                    break
            if matched:
                pkg = matched
            else:
                # Sequential fallback based on uncompiled Chapter 5 packages
                if not fs.is_package_compiled("binutils-pass1"):
                    pkg = "binutils-pass1"
                elif not fs.is_package_compiled("gcc-pass1"):
                    pkg = "gcc-pass1"
                elif not fs.is_package_compiled("glibc"):
                    pkg = "glibc"
                elif not fs.is_package_compiled("libstdc++"):
                    pkg = "libstdc++"
                else:
                    pkg = "binutils-pass2"

        # Record configured state
        fs.configured_packages[pkg] = {"args": args, "cwd": fs.cwd}
        fs.configured_packages["_current"] = pkg

        # Create Makefile in current directory
        fs.write_file(posixpath.join(fs.cwd, "Makefile"), f"# Autogenerated Makefile for {pkg}\nall:\n\t@echo 'Build {pkg}'\n")

        # Telemetry CPU jitter
        self.engine.telemetry.cpu_usage = min(95.0, self.engine.telemetry.cpu_usage + 10.0)

        output = (
            f"checking build system type... x86_64-pc-linux-gnu\n"
            f"checking host system type... x86_64-lfs-linux-gnu\n"
            f"checking target system type... x86_64-lfs-linux-gnu\n"
            f"checking for a BSD-compatible install... /usr/bin/install -c\n"
            f"checking whether build environment is sane... yes\n"
            f"checking for C compiler... x86_64-lfs-linux-gnu-gcc\n"
            f"checking whether the C compiler works... yes\n"
            f"config.status: creating Makefile\n"
            f"config.status: executing default commands\n"
            f"[bold green]✔ Configuração de '{pkg}' concluída com sucesso.[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=True)

    def _handle_gcc(self, cmd: str, args: List[str], stdin_data: str = "") -> CommandResult:
        """Simulates $LFS_TGT-gcc and compiler sanity check."""
        fs = self.engine.fs
        lfs_dir = fs.env.get("LFS", "/mnt/lfs")
        tgt = fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu")

        # Validate LFS_TGT variable if executing -gcc command
        if (cmd == "-gcc" or "$LFS_TGT" in cmd) and not fs.env.get("LFS_TGT"):
            return CommandResult(
                output="bash: $LFS_TGT: variável de ambiente não definida. Execute 'export LFS_TGT=x86_64-lfs-linux-gnu'.",
                success=False
            )

        # Verify GCC Pass 1 is installed
        gcc_bin_path = f"{lfs_dir}/tools/bin/{tgt}-gcc"
        if not (fs.is_package_compiled("gcc-pass1") or fs.exists(gcc_bin_path) or "x86_64-lfs-linux-gnu-gcc" in fs.installed_tools or "$LFS_TGT-gcc" in fs.installed_tools):
            return CommandResult(
                output=f"bash: {cmd}: comando não encontrado. Compile e instale o GCC Passagem 1 primeiro.",
                success=False
            )

        # Handle -print-file-name=include
        for a in args:
            if "-print-file-name=include" in a:
                inc_dir = f"{lfs_dir}/tools/lib/gcc/{tgt}/16.2.0/include"
                fs.mkdir(inc_dir, parents=True)
                return CommandResult(output=inc_dir, success=True)

        # Detect output file name
        out_name = "a.out"
        for i, a in enumerate(args):
            if a == "-o" and i + 1 < len(args):
                out_name = args[i + 1]
                break

        out_path = posixpath.join(fs.cwd, out_name)
        # Create virtual ELF binary
        fs.write_file(out_path, "\x7fELF (x86_64 LFS 13.1 Sanity Check Binary)\n")
        node = fs._resolve_node(out_path)
        if node:
            node.mode = 0o755

        # Check if verbose output requested (-v or -Wl,--verbose)
        arg_str = " ".join(args)
        if "-v" in args or "--verbose" in arg_str:
            verbose_output = (
                f"Using built-in specs.\n"
                f"COLLECT_GCC={tgt}-gcc\n"
                f"Target: {tgt}\n"
                f"Configured with: ../configure --target={tgt} --prefix={lfs_dir}/tools --with-glibc-version=2.44 --with-sysroot={lfs_dir}\n"
                f"Thread model: posix\n"
                f"gcc version 16.2.0 (GCC)\n"
                f"#include \"...\" search starts here:\n"
                f"#include <...> search starts here:\n"
                f" {lfs_dir}/usr/include\n"
                f"End of search list.\n"
                f"attempt to open {lfs_dir}/lib/crt1.o succeeded\n"
                f"attempt to open {lfs_dir}/lib/crti.o succeeded\n"
                f"attempt to open {lfs_dir}/lib/crtn.o succeeded\n"
                f"SEARCH_DIR(\"{lfs_dir}/tools/{tgt}/lib\"); SEARCH_DIR(\"{lfs_dir}/usr/lib\"); SEARCH_DIR(\"{lfs_dir}/lib\");\n"
                f"attempt to open {lfs_dir}/lib/libc.so.6 succeeded\n"
                f"found {lfs_dir}/lib/libc.so.6 at {lfs_dir}/lib/libc.so.6"
            )
            return CommandResult(output=verbose_output, success=True, state_changed=True)

        return CommandResult(output="", success=True, state_changed=True)

    def _handle_readelf(self, cmd: str, args: List[str]) -> CommandResult:
        """Simulates readelf / $LFS_TGT-readelf program header inspection."""
        fs = self.engine.fs

        # Target file
        target = "a.out"
        for a in args:
            if not a.startswith("-"):
                target = a
                break

        abs_p = fs.resolve_path(target)
        if not fs.exists(abs_p):
            return CommandResult(output=f"readelf: Error: '{target}': No such file", success=False)

        if fs.is_dir(abs_p):
            return CommandResult(output=f"readelf: Error: '{target}': is not an ordinary file", success=False)

        elf_output = fs.inspect_elf(abs_p)
        if not elf_output:
            return CommandResult(
                output=f"readelf: Error: '{target}': Not an ELF file - it has the wrong magic bytes at the start",
                success=False
            )

        # Mark sanity check passed
        self.engine.story_engine.flags["sanity_check_passed"] = True

        return CommandResult(output=elf_output, success=True, state_changed=True)

    def _cmd_make(self, args: List[str]) -> CommandResult:
        """Handles make targets: mrproper, headers, install, and standard build."""
        fs = self.engine.fs
        lfs_dir = fs.env.get("LFS", "/mnt/lfs")
        tgt = fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu")

        # Target: make mrproper
        if "mrproper" in args:
            return CommandResult(output="make: mrproper concluído para a árvore do Linux 6.14.7.", success=True, state_changed=True)

        # Target: make headers
        if "headers" in args:
            fs.mkdir(f"{lfs_dir}/usr/include/linux", parents=True)
            fs.mkdir("usr/include/linux", parents=True)
            fs.write_file(f"{lfs_dir}/usr/include/linux/version.h", "#define LINUX_VERSION_CODE 396807\n")
            fs.write_file("usr/include/linux/version.h", "#define LINUX_VERSION_CODE 396807\n")
            fs.record_package_compiled("linux-headers")
            self.engine.char.add_xp(100)
            output = (
                "make[1]: Entering directory 'usr/include'\n"
                "  HDRINST usr/include/asm-generic/errno.h\n"
                "  HDRINST usr/include/linux/version.h\n"
                "  HDRINST usr/include/linux/types.h\n"
                "[bold green]✔ Cabeçalhos da API do Linux 6.14.7 gerados com sucesso.[/bold green]"
            )
            return CommandResult(output=output, success=True, state_changed=True)

        # Target: make install or make DESTDIR=$LFS install
        is_install = any("install" in a for a in args)
        if is_install:
            curr_pkg = fs.configured_packages.get("_current")
            if not curr_pkg:
                for candidate in ["gcc-pass1", "binutils-pass1", "glibc", "libstdc++", "gcc-pass2", "binutils-pass2", "m4", "ncurses", "bash", "coreutils", "diffutils", "file", "findutils", "gawk", "grep", "gzip", "make", "patch", "sed", "tar", "xz"]:
                    if candidate in fs.cwd.lower():
                        curr_pkg = candidate
                        break
            if not curr_pkg:
                curr_pkg = "binutils-pass1" if not fs.is_package_compiled("binutils-pass1") else "gcc-pass1"

            if curr_pkg == "binutils-pass1":
                fs.install_tool(f"{tgt}-ld", f"{lfs_dir}/tools/bin/{tgt}-ld")
                fs.install_tool(f"{tgt}-as", f"{lfs_dir}/tools/bin/{tgt}-as")
                fs.install_tool(f"{tgt}-ar", f"{lfs_dir}/tools/bin/{tgt}-ar")
                fs.install_tool(f"{tgt}-readelf", f"{lfs_dir}/tools/bin/{tgt}-readelf")
                fs.record_package_compiled("binutils-pass1")
                self.engine.char.add_xp(150)
                return CommandResult(
                    output=f"make[1]: Entering directory 'binutils'\n  INSTALL  {lfs_dir}/tools/bin/{tgt}-ld\n  INSTALL  {lfs_dir}/tools/bin/{tgt}-as\n[bold green]✔ Binutils Passagem 1 instalado em $LFS/tools.[/bold green]",
                    success=True,
                    state_changed=True
                )

            elif curr_pkg == "gcc-pass1":
                fs.install_tool(f"{tgt}-gcc", f"{lfs_dir}/tools/bin/{tgt}-gcc")
                fs.install_tool(f"{tgt}-g++", f"{lfs_dir}/tools/bin/{tgt}-g++")
                fs.install_tool(f"{tgt}-cpp", f"{lfs_dir}/tools/bin/{tgt}-cpp")
                fs.record_package_compiled("gcc-pass1")
                self.engine.char.add_xp(200)
                return CommandResult(
                    output=f"make[1]: Entering directory 'gcc'\n  INSTALL  {lfs_dir}/tools/bin/{tgt}-gcc\n  INSTALL  {lfs_dir}/tools/bin/{tgt}-g++\n[bold green]✔ GCC Passagem 1 instalado em $LFS/tools.[/bold green]",
                    success=True,
                    state_changed=True
                )

            elif curr_pkg == "glibc":
                fs.mkdir(f"{lfs_dir}/lib64", parents=True)
                fs.mkdir(f"{lfs_dir}/lib", parents=True)
                fs.mkdir(f"{lfs_dir}/usr/lib", parents=True)
                fs.mkdir(f"{lfs_dir}/usr/bin", parents=True)
                fs.install_tool("ld-linux-x86-64.so.2", f"{lfs_dir}/lib64/ld-linux-x86-64.so.2")
                fs.install_tool("ld-linux.so.2", f"{lfs_dir}/lib/ld-linux-x86-64.so.2")
                fs.install_tool("libc.so.6", f"{lfs_dir}/usr/lib/libc.so.6")
                fs.install_tool("ldd", f"{lfs_dir}/usr/bin/ldd")
                fs.record_package_compiled("glibc")
                self.engine.char.add_xp(200)
                return CommandResult(
                    output=f"make[1]: Entering directory 'glibc'\n  INSTALL  {lfs_dir}/lib64/ld-linux-x86-64.so.2\n  INSTALL  {lfs_dir}/usr/lib/libc.so.6\n[bold green]✔ Glibc 2.44 instalada em $LFS.[/bold green]",
                    success=True,
                    state_changed=True
                )

            elif curr_pkg == "libstdc++":
                fs.install_tool("libstdc++.so", f"{lfs_dir}/usr/lib/libstdc++.so")
                fs.install_tool("libstdc++.so.6", f"{lfs_dir}/usr/lib/libstdc++.so.6")
                fs.record_package_compiled("libstdc++")
                self.engine.char.add_xp(150)
                return CommandResult(
                    output=f"make[1]: Entering directory 'libstdc++-v3'\n  INSTALL  {lfs_dir}/usr/lib/libstdc++.so\n[bold green]✔ Libstdc++ Passagem 1 instalada em $LFS/usr/lib.[/bold green]",
                    success=True,
                    state_changed=True
                )

            elif curr_pkg == "binutils-pass2":
                fs.install_tool("ld", f"{lfs_dir}/usr/bin/ld")
                fs.install_tool("as", f"{lfs_dir}/usr/bin/as")
                fs.install_tool("readelf", f"{lfs_dir}/usr/bin/readelf")
                fs.record_package_compiled("binutils-pass2")
                self.engine.char.add_xp(200)
                return CommandResult(
                    output=f"make[1]: Entering directory 'binutils'\n  INSTALL  {lfs_dir}/usr/bin/ld\n  INSTALL  {lfs_dir}/usr/bin/as\n[bold green]✔ Binutils Passagem 2 instalado em $LFS/usr/bin.[/bold green]",
                    success=True,
                    state_changed=True
                )

            elif curr_pkg == "gcc-pass2":
                fs.install_tool("gcc", f"{lfs_dir}/usr/bin/gcc")
                fs.install_tool("g++", f"{lfs_dir}/usr/bin/g++")
                fs.install_tool("cc", f"{lfs_dir}/usr/bin/cc")
                fs.record_package_compiled("gcc-pass2")
                self.engine.char.add_xp(350)
                return CommandResult(
                    output=f"make[1]: Entering directory 'gcc'\n  INSTALL  {lfs_dir}/usr/bin/gcc\n  INSTALL  {lfs_dir}/usr/bin/g++\n[bold green]✔ GCC Passagem 2 instalado em $LFS/usr/bin.[/bold green]",
                    success=True,
                    state_changed=True
                )

            else:
                fs.install_tool(curr_pkg, f"{lfs_dir}/usr/bin/{curr_pkg}")
                fs.record_package_compiled(curr_pkg)
                self.engine.char.add_xp(75)
                return CommandResult(
                    output=f"[bold green]✔ {curr_pkg} instalado em {lfs_dir}/usr/bin/{curr_pkg}.[/bold green]",
                    success=True,
                    state_changed=True
                )

        # Standard make / make -jX compilation
        curr_pkg = fs.configured_packages.get("_current", "pacote")
        self.engine.telemetry.cpu_usage = min(99.0, self.engine.telemetry.cpu_usage + 32.0)
        self.engine.telemetry.temperature = min(86.0, self.engine.telemetry.temperature + 8.0)

        # Boss encounter during GCC Pass 2
        if curr_pkg == "gcc-pass2" and hasattr(self.engine, "anomaly_manager"):
            if "CPU_OVERHEAT" not in self.engine.anomaly_manager.resolved_history:
                self.engine.anomaly_manager.trigger_anomaly("CPU_OVERHEAT")
                prompt = self.engine.anomaly_manager.format_active_prompt()
                return CommandResult(
                    output=f"[make] Compilando GCC Passagem 2 (Boss Fight do Ato 2)...\n\n{prompt}",
                    success=True,
                    state_changed=True
                )

        output = (
            f"[CC]  Compilando submódulos de {curr_pkg}...\n"
            f"[LD]  Vinculando objetos e bibliotecas compartilhadas...\n"
            f"[bold green]Compilação de '{curr_pkg}' concluída.[/bold green] Execute 'make install' para instalar."
        )
        return CommandResult(output=output, success=True, state_changed=True)

    def _cmd_grep(self, args: List[str], stdin_data: str = "") -> CommandResult:
        """Searches for patterns in files or piped input."""
        if not args and not stdin_data:
            return CommandResult(output="Uso: grep [OPÇÕES] PADRÃO [ARQUIVO...]", success=False)

        invert = False
        ignore_case = False
        only_matching = False
        files: List[str] = []
        pattern = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-v":
                invert = True
            elif arg == "-i":
                ignore_case = True
            elif arg == "-o":
                only_matching = True
            elif arg.startswith("-E") or arg.startswith("-o") or arg.startswith("-B") or arg.startswith("-A"):
                if arg == "-E":
                    pass
                elif arg.startswith("-B") or arg.startswith("-A"):
                    if len(arg) == 2 and i + 1 < len(args) and args[i+1].isdigit():
                        i += 1
            elif pattern is None and not arg.startswith("-"):
                pattern = arg
            elif pattern is not None and not arg.startswith("-"):
                files.append(arg)
            i += 1

        if not pattern:
            return CommandResult(output="", success=True)

        lines_to_search: List[str] = []
        if files:
            for f in files:
                ok, content = self.engine.fs.read_file(f)
                if ok:
                    lines_to_search.extend(content.splitlines())
                else:
                    return CommandResult(output=f"grep: {f}: Arquivo ou diretório inexistente", success=False)
        else:
            lines_to_search = stdin_data.splitlines()

        matched_lines: List[str] = []
        flags = re.IGNORECASE if ignore_case else 0

        try:
            regex = re.compile(pattern, flags)
        except re.error:
            regex = re.compile(re.escape(pattern), flags)

        for line in lines_to_search:
            m = regex.search(line)
            if (m and not invert) or (not m and invert):
                if only_matching and m and not invert:
                    matched_lines.append(m.group(0))
                else:
                    matched_lines.append(line)

        return CommandResult(output="\n".join(matched_lines), success=True)

    def _cmd_sed(self, args: List[str], stdin_data: str = "") -> CommandResult:
        """Stream editor for filtering and transforming text."""
        if not args and not stdin_data:
            return CommandResult(output="Uso: sed [OPÇÃO]... {script} [arquivo...]", success=False)

        in_place = False
        script = ""
        files: List[str] = []

        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("-i"):
                in_place = True
            elif a in ("-e", "--expression"):
                if i + 1 < len(args):
                    i += 1
                    script = args[i]
            elif not a.startswith("-") and not script:
                script = a
            elif not a.startswith("-") and script:
                files.append(a)
            i += 1

        def transform(text: str) -> str:
            if not script:
                return text
            if script.startswith("s"):
                delim = script[1]
                parts = script.split(delim)
                if len(parts) >= 3:
                    pat = parts[1]
                    repl = parts[2]
                    is_global = "g" in parts[3] if len(parts) > 3 else False
                    count = 0 if is_global else 1
                    try:
                        return re.sub(pat, repl, text, count=count)
                    except Exception:
                        return text.replace(pat, repl)
            return text

        if files:
            for f in files:
                ok, content = self.engine.fs.read_file(f)
                if ok:
                    new_content = "\n".join(transform(line) for line in content.splitlines())
                    if in_place:
                        self.engine.fs.write_file(f, new_content + "\n")
                    else:
                        return CommandResult(output=new_content, success=True, state_changed=in_place)
                else:
                    return CommandResult(output=f"sed: {f}: Arquivo não encontrado", success=False)
            return CommandResult(output="", success=True, state_changed=True)
        else:
            new_lines = [transform(line) for line in stdin_data.splitlines()]
            return CommandResult(output="\n".join(new_lines), success=True)

    def _cmd_patch(self, args: List[str]) -> CommandResult:
        """Applies diff patches in the virtual filesystem."""
        patch_file = ""
        for i, a in enumerate(args):
            if a == "-i" and i + 1 < len(args):
                patch_file = args[i + 1]
            elif a.startswith("-i"):
                patch_file = a[2:]
            elif not a.startswith("-"):
                patch_file = a

        target_name = patch_file.split("/")[-1] if patch_file else "patch"
        return CommandResult(
            output=f"patching file Makefile...\nHunk #1 succeeded at 1.\nPatch '{target_name}' aplicado com sucesso.",
            success=True,
            state_changed=True
        )

    def _cmd_cp(self, args: List[str]) -> CommandResult:
        """Copies files and directories in virtual FS."""
        clean_args = [a for a in args if not a.startswith("-")]
        if len(clean_args) < 2:
            return CommandResult(output="cp: operandos ausentes", success=False)
        src = clean_args[0]
        dst = clean_args[1]

        # Handle header copying (usr/include to $LFS/usr)
        if "include" in src:
            from .virtual_fs import VirtualDirectory
            target_inc = posixpath.join(dst, "include") if not dst.endswith("include") else dst
            parts = [p for p in target_inc.split("/") if p]
            curr = self.engine.fs.root
            for part in parts:
                if part not in curr.children:
                    new_dir = VirtualDirectory(
                        name=part,
                        is_directory=True,
                        owner=self.engine.fs.current_user,
                        group=self.engine.fs.users.get(self.engine.fs.current_user, {}).get("group", "root"),
                        mode=0o755
                    )
                    curr.children[part] = new_dir
                    curr = new_dir
                else:
                    curr = curr.children[part]

            self.engine.fs.write_file(posixpath.join(target_inc, "stdio.h"), "/* ISO C Standard IO */\n")
            self.engine.fs.write_file(posixpath.join(target_inc, "stdlib.h"), "/* ISO C Standard Lib */\n")
            linux_inc = posixpath.join(target_inc, "linux")
            if not self.engine.fs.exists(linux_inc):
                curr.children["linux"] = VirtualDirectory(name="linux", is_directory=True, owner=self.engine.fs.current_user, group="root", mode=0o755)
            self.engine.fs.write_file(posixpath.join(linux_inc, "version.h"), "#define LINUX_VERSION_CODE 396807\n")
            return CommandResult(output=f"'{src}' -> '{dst}'", success=True, state_changed=True)

        ok, content = self.engine.fs.read_file(src)
        if ok:
            dest_file = posixpath.join(dst, posixpath.basename(src)) if self.engine.fs.is_dir(dst) else dst
            self.engine.fs.write_file(dest_file, content)
            return CommandResult(output=f"'{src}' -> '{dst}'", success=True, state_changed=True)
        return CommandResult(output=f"cp: não foi possível obter estado de '{src}': Arquivo ou diretório inexistente", success=False)

    def _cmd_find(self, args: List[str]) -> CommandResult:
        """Finds files and directories in virtual FS."""
        target_dir = args[0] if args and not args[0].startswith("-") else "."
        if "-delete" in args:
            return CommandResult(output=f"[find] Arquivos desnecessários removidos de '{target_dir}'.", success=True, state_changed=True)
        return CommandResult(output=target_dir, success=True)

    def _cmd_ln(self, args: List[str]) -> CommandResult:
        """Creates hard or symbolic links in virtual FS."""
        clean_args = [a for a in args if not a.startswith("-")]
        if len(clean_args) < 2:
            return CommandResult(output="ln: operandos ausentes", success=False)
        src = clean_args[0]
        dst = clean_args[1]

        target_path = posixpath.join(dst, posixpath.basename(src)) if self.engine.fs.is_dir(dst) else dst
        parent_dir = posixpath.dirname(target_path)
        if not self.engine.fs.exists(parent_dir):
            self.engine.fs.mkdir(parent_dir, parents=True)

        self.engine.fs.write_file(target_path, f"# Symlink to {src}\n")
        return CommandResult(output=f"'{target_path}' -> '{src}'", success=True, state_changed=True)

    def _cmd_lfs_compile_tools(self, args: List[str]) -> CommandResult:
        """Compiles Chapter 6 temporary tools (individual or batch)."""
        from ..data.lfs_manifest import TOOLCHAIN_CATALOG, get_toolchain_package

        target = args[0].strip().lower() if args else "all"
        lfs_dir = self.engine.fs.env.get("LFS", "/mnt/lfs")

        if lfs_dir not in self.engine.fs.mounts and "/mnt/lfs" not in self.engine.fs.mounts:
            return CommandResult(
                output=f"lfs-compile-tools: ERRO: O ponto de montagem de $LFS ('{lfs_dir}') não está montado. Monte a partição antes de compilar.",
                success=False
            )

        if target == "all":
            ch6_order = [
                "m4", "ncurses", "bash", "coreutils", "diffutils",
                "file", "findutils", "gawk", "grep", "gzip",
                "make", "patch", "sed", "tar", "xz"
            ]
            lines = [
                "[bold cyan]╔══════════════════════════════════════════════════════════════════╗[/bold cyan]",
                "[bold cyan]║ FORJA DAS FERRAMENTAS TEMPORÁRIAS DO CAPÍTULO 6 (LFS 13.1)       ║[/bold cyan]",
                "[bold cyan]╚══════════════════════════════════════════════════════════════════╝[/bold cyan]",
            ]
            total_xp = 0
            new_compiled_count = 0
            for idx, tool_id in enumerate(ch6_order, 1):
                pkg = TOOLCHAIN_CATALOG.get(tool_id)
                name = pkg.name if pkg else tool_id.upper()
                sbu = pkg.sbu_label if pkg else "0,1 UPC"
                if not self.engine.fs.is_package_compiled(tool_id):
                    new_compiled_count += 1
                    total_xp += 50
                self.engine.fs.record_package_compiled(tool_id)
                self.engine.fs.install_tool(tool_id, f"{lfs_dir}/usr/bin/{tool_id}")
                if pkg and pkg.binaries:
                    for b in pkg.binaries:
                        b_clean = b.replace("$LFS_TGT", self.engine.fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu"))
                        self.engine.fs.install_tool(b_clean, f"{lfs_dir}/usr/bin/{b_clean}")
                        self.engine.fs.record_package_compiled(b_clean)
                lines.append(f"  [cyan][{idx:02d}/15][/cyan] {name:16} ({sbu:12}) ... [bold green][OK][/bold green]")

            if new_compiled_count > 0:
                self.engine.char.add_xp(total_xp)
            self.engine.story_engine.flags["temp_tools_compiled"] = True
            if new_compiled_count == 0:
                lines.append(f"\n[yellow]ℹ Todas as 15 ferramentas temporárias já estavam previamente compiladas em $LFS/usr/bin! (+0 XP)[/yellow]")
            else:
                lines.append(f"\n[bold green]★ Todas as 15 ferramentas temporárias foram instaladas com sucesso em $LFS/usr/bin! (+{total_xp} XP)[/bold green]")
            return CommandResult(output="\n".join(lines), success=True, state_changed=new_compiled_count > 0)

        pkg = get_toolchain_package(target)
        if not pkg:
            return CommandResult(
                output=f"lfs-compile-tools: pacote '{target}' não encontrado no catálogo. Use 'lfs-status-tools' para ver pacotes válidos.",
                success=False
            )

        already_compiled = self.engine.fs.is_package_compiled(pkg.id)
        self.engine.fs.record_package_compiled(pkg.id)
        for b in pkg.binaries:
            b_clean = b.replace("$LFS_TGT", self.engine.fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu"))
            base_dir = f"{pkg.install_path}/bin" if pkg.install_path.endswith("/tools") else pkg.install_path
            target_path = f"{base_dir}/{b_clean}".replace("$LFS", lfs_dir)
            self.engine.fs.install_tool(b_clean, target_path)

        if not pkg.binaries:
            self.engine.fs.mkdir(f"{lfs_dir}/usr/include", parents=True)

        if already_compiled:
            return CommandResult(
                output=f"[yellow]ℹ {pkg.name} já se encontra compilado e atualizado em {pkg.install_path}. (+0 XP)[/yellow]",
                success=True,
                state_changed=False
            )

        xp = int(pkg.sbu * 100) + 50
        self.engine.char.add_xp(xp)
        return CommandResult(
            output=f"[bold green]✔ {pkg.name} ({pkg.sbu_label}) compilado e instalado com sucesso em {pkg.install_path}! (+{xp} XP)[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_lfs_status_tools(self, args: List[str]) -> CommandResult:
        """Displays status checklist of Chapter 5 and Chapter 6 toolchain packages."""
        from ..data.lfs_manifest import get_toolchain_packages

        pkgs = get_toolchain_packages()
        lines = [
            "[bold cyan]╔════════════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ CHECKLIST DA TOOLCHAIN & FERRAMENTAS TEMPORÁRIAS (CAPÍTULOS 5 E 6)                 ║[/bold cyan]",
            "[bold cyan]╚════════════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            f"{'PACOTE':<28} {'CAP':<5} {'UPC (SBU)':<14} {'STATUS':<15} {'DESTINO'}",
            "─" * 84,
        ]

        total_sbu = 0.0
        compiled_sbu = 0.0
        installed_count = 0

        for p in pkgs:
            total_sbu += p.sbu
            is_done = self.engine.fs.is_package_compiled(p.id)
            if is_done:
                compiled_sbu += p.sbu
                installed_count += 1
                status = "[bold green]✔ INSTALADO[/bold green]"
            else:
                status = "[dim yellow]⏳ PENDENTE [/dim yellow]"

            lines.append(f"{p.name:<28} {p.chapter:<5} {p.sbu_label:<14} {status:<24} {p.install_path}")

        lines.append("─" * 84)
        pct = (installed_count / len(pkgs)) * 100 if pkgs else 0
        lines.append(
            f"[bold white]Progresso:[/bold white] {installed_count}/{len(pkgs)} pacotes ({pct:.1f}%) | "
            f"[bold white]SBU Concluído:[/bold white] {compiled_sbu:.1f}/{total_sbu:.1f} UPC"
        )
        return CommandResult(output="\n".join(lines), success=True)

    def _cmd_lfs_resolve(self, args: List[str]) -> CommandResult:
        """Resolves active compilation anomaly."""
        if not args:
            return CommandResult(output="Uso: lfs-resolve <número_da_opção>", success=False)
        ok, msg = self.engine.anomaly_manager.resolve(args[0], self.engine)
        return CommandResult(output=msg, success=ok, state_changed=True)

    def _cmd_anomaly(self, args: List[str]) -> CommandResult:
        """Inspects, triggers, or resolves compilation anomalies."""
        if args and args[0] in ("trigger", "novo"):
            a_type = args[1] if len(args) > 1 else None
            anomaly = self.engine.anomaly_manager.trigger_anomaly(a_type)
            prompt = self.engine.anomaly_manager.format_active_prompt()
            return CommandResult(output=prompt, success=True, state_changed=True)
        if args and args[0] in ("resolve", "resolver"):
            choice = args[1] if len(args) > 1 else "1"
            return self._cmd_lfs_resolve([choice])
        if self.engine.anomaly_manager.active_anomaly:
            return CommandResult(output=self.engine.anomaly_manager.format_active_prompt(), success=True)
        return CommandResult(output="Nenhuma anomalia ativa no momento. Todos os parâmetros estáveis.", success=True)
