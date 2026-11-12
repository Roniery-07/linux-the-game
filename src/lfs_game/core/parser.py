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
        self.didactic_enabled: bool = True

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

        # Handle bash case statement (e.g. case $(uname -m) in x86_64) ... ;; esac)
        case_res = self._try_execute_case_statement(raw)
        if case_res is not None:
            return case_res

        # Handle multiline heredoc (e.g. cat > /etc/fstab << "EOF" ... EOF)
        heredoc_res = self._try_execute_heredoc(command_line)
        if heredoc_res is not None:
            return heredoc_res

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

    def _try_execute_case_statement(self, raw: str) -> Optional[CommandResult]:
        """Parses and executes a bash 'case $(uname -m) in x86_64) ... ;; esac' block."""
        clean = raw.strip()
        if not (clean.startswith("case ") or re.match(r"^case\s+", clean)):
            return None

        m = re.match(r"^case\s+(.+?)\s+in\s+(.+?)\s+esac\s*$", clean, re.DOTALL)
        if not m:
            return None

        test_expr = m.group(1).strip()
        branches_block = m.group(2).strip()

        fs = self.engine.fs
        test_val = fs.expand_vars(test_expr)
        test_val = test_val.replace("$(uname -m)", "x86_64").replace("`uname -m`", "x86_64").strip()
        if not test_val:
            test_val = "x86_64"

        branches = branches_block.split(";;")
        for branch in branches:
            branch = branch.strip()
            if not branch or ")" not in branch:
                continue
            pattern, cmds = branch.split(")", 1)
            pattern = pattern.strip()
            cmds = cmds.strip()

            patterns = [p.strip() for p in pattern.split("|")]
            matched = False
            for p in patterns:
                if p in ("*", test_val) or (test_val == "x86_64" and "64" in p):
                    matched = True
                    break

            if matched and cmds:
                return self.execute(cmds)

        return CommandResult(output="", success=True)

    def _try_execute_heredoc(self, raw_cmd: str) -> Optional[CommandResult]:
        """Parses and executes bash multiline heredocs (<< EOF, << \"EOF\", << 'EOF', <<- EOF)."""
        if "<<" not in raw_cmd:
            return None

        lines = raw_cmd.splitlines()
        if not lines:
            return None

        first_line = lines[0]
        m = re.search(r"(<<-?)\s*(['\"]?)([A-Za-z0-9_]+)\2", first_line)
        if not m:
            return None

        strip_tabs = m.group(1) == "<<-"
        is_quoted = bool(m.group(2))
        delimiter = m.group(3)

        closing_idx: Optional[int] = None
        for idx, line in enumerate(lines[1:], start=1):
            candidate = line.strip() if strip_tabs else line.rstrip("\r")
            if candidate == delimiter:
                closing_idx = idx
                break

        if closing_idx is None:
            return CommandResult(
                output=f"bash: erro de sintaxe: here-document delimitado por fim-de-arquivo (esperado '{delimiter}')",
                success=False,
            )

        body_lines = lines[1:closing_idx]
        if strip_tabs:
            body_lines = [ln.lstrip("\t") for ln in body_lines]
        body = "\n".join(body_lines)
        if not is_quoted:
            body = self.engine.fs.expand_vars(body)
        stdin_payload = body + ("\n" if body else "")

        header_cmd = (first_line[:m.start()] + first_line[m.end():]).strip()
        if not header_cmd:
            return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado '<<'", success=False)

        outputs: List[str] = []
        state_changed = False

        if "&&" in header_cmd:
            parts = [p.strip() for p in header_cmd.split("&&")]
            if any(not p for p in parts):
                return CommandResult(output="bash: erro de sintaxe próximo ao token inesperado '&&'", success=False)
            for p in parts[:-1]:
                pre_res = self.execute(p)
                if pre_res.output:
                    outputs.append(pre_res.output)
                state_changed = state_changed or pre_res.state_changed
                if not pre_res.success:
                    return CommandResult(output="\n".join(outputs), success=False, state_changed=state_changed)
            main_res = self._execute_single(parts[-1], stdin_data=stdin_payload)
        else:
            main_res = self._execute_single(header_cmd, stdin_data=stdin_payload)

        if main_res.output:
            outputs.append(main_res.output)
        state_changed = state_changed or main_res.state_changed

        if not main_res.success:
            return CommandResult(output="\n".join(outputs), success=False, state_changed=state_changed)

        remaining = "\n".join(lines[closing_idx + 1:]).strip()
        if remaining:
            rem_res = self.execute(remaining)
            if rem_res.output:
                outputs.append(rem_res.output)
            state_changed = state_changed or rem_res.state_changed
            return CommandResult(
                output="\n".join(outputs),
                success=rem_res.success,
                state_changed=state_changed,
                system_event=rem_res.system_event,
            )

        return CommandResult(
            output="\n".join(outputs),
            success=True,
            state_changed=state_changed,
            system_event=main_res.system_event,
        )

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
            if self.didactic_enabled and last_res.success:
                insight = self._get_didactic_insight(cmd_str)
                if insight:
                    last_res.output = (last_res.output + "\n" if last_res.output else "") + insight
            return last_res

        res = self._execute_stage(cmd_str, stdin_data=stdin_data)
        if self.didactic_enabled and res.success:
            insight = self._get_didactic_insight(cmd_str)
            if insight:
                res.output = (res.output + "\n" if res.output else "") + insight
        return res

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
            if not handler and cmd.lower() in (
                "explain", "explicar", "oquee",
                "glossario", "glossary",
                "didactic", "didatico",
                "lfs-jump", "jump", "test-act", "goto-act",
                "help", "hint", "status", "save", "load", "clear", "exit"
            ):
                handler = getattr(self, f"_cmd_{cmd.lower().replace('.', '_').replace('-', '_')}", None)
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
[bold green]LFS 13.1 Toolchain:[/bold green] lfs-book [cap], lfs-status-tools, lfs-compile-tools [all|pacote], lfs-status-chroot, lfs-compile-chroot, ./configure, make, readelf, grep, patch, sed, md5sum, tar
[bold green]LFS 13.1 Sistema (Ato 4):[/bold green] lfs-status-system, lfs-compile-system [tier1..4|all|pacote], make check, localedef, pwconv, grpconv, passwd, exec, udev-hwdb, lfs-strip
[bold green]LFS 13.1 Kernel & Boot (Ato 5):[/bold green] lfs-install-bootscripts, lfs-config-network, lfs-config-system, lfs-check-config, make menuconfig, lfs-kernel-config, lfs-compile-kernel, make modules_install, grub-install, grub-mkconfig, lfs-config-grub
[bold green]Glossário Didático:[/bold green] glossario [termo|cat], explain <termo>, didactic [on|off]
[bold green]Modo Teste / Sandbox:[/bold green] lfs-jump [alvo] (aliases: jump, test-act, goto-act) | F4 na TUI
[bold green]Sobrevivência & Anomalias:[/bold green] lfs-resolve [número], anomaly, hint, status, coffee, save [nome], load [nome], clear, exit
"""
        return CommandResult(output=help_text, success=True, system_event="HELP")

    def _cmd_glossario(self, args: List[str]) -> CommandResult:
        from ..data.glossary import glossary_manager
        if args:
            query = " ".join(args).strip()
            if not query:
                return CommandResult(output=glossary_manager.format_index(), success=True)
            # 1. Try direct entry lookup
            entry = glossary_manager.get(query)
            if entry:
                return CommandResult(output=glossary_manager.format_entry(entry), success=True)
            # 2. Try category filter
            cats = glossary_manager.list_by_category()
            clean_query = glossary_manager._strip_accents(query.lower())
            for cat in cats:
                clean_cat = glossary_manager._strip_accents(cat.lower())
                if clean_query in clean_cat or query.lower() in cat.lower():
                    return CommandResult(output=glossary_manager.format_index(category_filter=cat), success=True)
            # 3. Try search
            matches = glossary_manager.search(query)
            if matches:
                if len(matches) == 1:
                    return CommandResult(output=glossary_manager.format_entry(matches[0]), success=True)
                match_names = ", ".join(f"'{m.term}'" for m in matches[:8])
                return CommandResult(
                    output=f"[yellow]Termo '{query}' não encontrado diretamente.[/yellow]\nCorrespondências: {match_names}\nUse '[bold green]explain <termo>[/bold green]' para ler a explicação detalhada.",
                    success=True,
                )
            return CommandResult(
                output=f"[red]Nenhum termo ou categoria correspondente a '{query}' no glossário.[/red]\nDigite '[bold cyan]glossario[/bold cyan]' para ver todos os termos catalogados.",
                success=False,
            )
        return CommandResult(output=glossary_manager.format_index(), success=True)

    def _cmd_glossary(self, args: List[str]) -> CommandResult:
        return self._cmd_glossario(args)

    def _cmd_explain(self, args: List[str]) -> CommandResult:
        from ..data.glossary import glossary_manager
        query = " ".join(args).strip() if args else ""
        if not query:
            msg = (
                "[bold yellow]Uso:[/bold yellow] explain <termo>\n"
                "Exemplos: 'explain export', 'explain $LFS', 'explain sysroot', 'explain readelf'\n"
                "Digite '[bold cyan]glossario[/bold cyan]' para ver o índice completo de termos."
            )
            return CommandResult(output=msg, success=True)
        entry = glossary_manager.get(query)
        if entry:
            return CommandResult(output=glossary_manager.format_entry(entry), success=True)
        matches = glossary_manager.search(query)
        if matches:
            if len(matches) == 1:
                return CommandResult(output=glossary_manager.format_entry(matches[0]), success=True)
            match_names = ", ".join(f"'{m.term}'" for m in matches[:8])
            return CommandResult(
                output=f"[yellow]Termo '{query}' não encontrado diretamente.[/yellow]\nVocê quis dizer: {match_names}?\nUse '[bold green]explain <termo>[/bold green]' para ler a explicação didática.",
                success=True,
            )
        return CommandResult(
            output=f"[red]Termo '{query}' não encontrado no glossário.[/red]\nDigite '[bold cyan]glossario[/bold cyan]' para ver todos os termos catalogados.",
            success=False,
        )

    def _cmd_explicar(self, args: List[str]) -> CommandResult:
        return self._cmd_explain(args)

    def _cmd_oquee(self, args: List[str]) -> CommandResult:
        return self._cmd_explain(args)

    def _cmd_didactic(self, args: List[str]) -> CommandResult:
        if not args:
            status = "[bold green]ATIVADO (ON)[/bold green]" if self.didactic_enabled else "[bold yellow]DESATIVADO (OFF)[/bold yellow]"
            msg = (
                f"[bold cyan]Modo Didático LFS:[/bold cyan] {status}\n"
                "Quando ativado, exibe insights pedagógicos automáticos após comandos arquiteturais vitais.\n"
                "Use '[bold green]didactic on[/bold green]' para ativar ou '[bold green]didactic off[/bold green]' para desativar."
            )
            return CommandResult(output=msg, success=True)
        opt = args[0].lower().strip()
        if opt in ("on", "1", "true", "ativar", "ligar"):
            self.didactic_enabled = True
            return CommandResult(
                output="[bold green]✓ Modo Didático ATIVADO![/bold green] Dicas educacionais de arquitetura LFS serão exibidas após comandos vitais.",
                success=True,
                state_changed=True,
            )
        if opt in ("off", "0", "false", "desativar", "desligar"):
            self.didactic_enabled = False
            return CommandResult(
                output="[bold yellow]✓ Modo Didático DESATIVADO.[/bold yellow] Dicas automáticas foram silenciadas. Use 'didactic on' para reativar a qualquer momento.",
                success=True,
                state_changed=True,
            )
        return CommandResult(output="Uso: didactic [on|off]", success=False)

    def _cmd_didatico(self, args: List[str]) -> CommandResult:
        return self._cmd_didactic(args)

    def _get_didactic_insight(self, cmd_str: str) -> Optional[str]:
        """Returns a didactic insight string if the command executed an architectural milestone."""
        c = cmd_str.strip()
        if not c:
            return None

        # Ignore non-architectural commands
        tokens = c.split()
        first = tokens[0] if tokens else ""
        if first in (
            "help", "glossario", "glossary", "explain", "explicar", "oquee",
            "didactic", "didatico", "status", "hint", "coffee", "cafe",
            "save", "load", "clear", "exit", "pwd", "ls", "echo"
        ):
            return None

        # 1. $LFS export or assignment
        if re.search(r"\bexport\s+LFS\s*=", c) or (c.startswith("LFS=") and "/mnt" in c):
            return "💡 [bold cyan]Insight LFS ($LFS):[/bold cyan] Definir $LFS é o alicerce do projeto. Sem essa variável apontando para a partição montada, comandos subsequentes poderiam tentar escrever na raiz do sistema hospedeiro!"

        # 2. $LFS_TGT export or assignment
        if re.search(r"\bexport\s+LFS_TGT\s*=", c) or c.startswith("LFS_TGT="):
            return "💡 [bold cyan]Insight LFS ($LFS_TGT):[/bold cyan] A tupla de arquitetura com sufixo customizado '-lfs-' assegura que a toolchain do GNU reconheça o cross-compiler e não use bibliotecas do hospedeiro."

        # 3. $PATH export with tools/bin
        if ("PATH=" in c or "export PATH" in c) and "tools/bin" in c:
            return "💡 [bold cyan]Insight LFS ($PATH):[/bold cyan] Adicionar $LFS/tools/bin no início do PATH garante que os novos utilitários compilados tenham prioridade imediata sobre os programas do hospedeiro."

        # 4. LC_ALL=POSIX
        if "LC_ALL=POSIX" in c:
            return "💡 [bold cyan]Insight LFS (LC_ALL=POSIX):[/bold cyan] A localidade POSIX padroniza a ordenação de caracteres em ASCII puro, evitando que regras regionais de idiomas quebrem expressões regulares e Makefiles."

        # 5. mount command (especially on LFS)
        if re.search(r"\bmount\b", c) and ("$LFS" in c or "/mnt/lfs" in c):
            return "💡 [bold cyan]Insight LFS (mount):[/bold cyan] A partição foi acoplada ao sistema de arquivos! Todos os arquivos gravados sob o ponto de montagem agora vão diretamente para o disco permanente do LFS."

        # 6. su - lfs
        if re.search(r"\bsu\s+-\s+lfs\b", c):
            return "💡 [bold cyan]Insight LFS (su - lfs):[/bold cyan] O '-' (hífen) inicia um login shell limpo, descartando variáveis do root que poderiam contaminar a compilação do LFS."

        # 7. useradd lfs
        if re.search(r"\buseradd\b.*lfs\b", c):
            return "💡 [bold cyan]Insight LFS (useradd lfs):[/bold cyan] Compilar como um usuário sem privilégios protege seu sistema principal contra falhas catastróficas ou erros destrutivos em Makefiles."

        # 8. mkfs.ext4
        if "mkfs.ext4" in c or "mkfs -t ext4" in c:
            return "💡 [bold cyan]Insight LFS (mkfs.ext4):[/bold cyan] A partição foi formatada em EXT4 com journaling e suporte a metadados POSIX, pronta para receber a árvore de diretórios do novo sistema operacional."

        # 9. mkswap or swapon
        if re.search(r"\b(mkswap|swapon)\b", c):
            return "💡 [bold cyan]Insight LFS (swap):[/bold cyan] A memória swap fornece paginação em disco, impedindo que o compilador GCC seja abortado por falta de memória RAM durante compilações pesadas."

        # 10. configure script
        if re.search(r"(^|\s)(\./|\.\./|/)configure\b", c):
            return "💡 [bold cyan]Insight LFS (configure):[/bold cyan] O script inspeciona os recursos do hardware e monta os Makefiles. Compilar em um diretório 'build' separado mantém o código-fonte imaculado."

        # 11. make with DESTDIR
        if "DESTDIR=" in c:
            return "💡 [bold cyan]Insight LFS (DESTDIR):[/bold cyan] DESTDIR redireciona a raiz física de instalação para $LFS sem modificar os caminhos lógicos internos fixados pelo --prefix nos binários."

        # 12. readelf sanity check
        if re.search(r"\breadelf\b", c):
            return "💡 [bold cyan]Insight LFS (readelf):[/bold cyan] O teste de sanidade no cabeçalho ELF verifica o interpretador de programas (/tools/lib64/ld-linux...), atestando o isolamento da toolchain."

        # 13. chroot
        if re.search(r"\bchroot\b", c):
            return "💡 [bold cyan]Insight LFS (chroot):[/bold cyan] O diretório raiz agora é $LFS! A partir deste ponto, o sistema hospedeiro está totalmente isolado e você opera no novo Linux."

        # 14. Act 4: make check / make -k check
        if re.search(r"\bmake\b.*\bcheck\b", c):
            return "💡 [bold cyan]Insight LFS (make check):[/bold cyan] As suítes de testes da Glibc, Binutils e GCC no Capítulo 8 validam a integridade da ABI e do vinculador antes de prosseguir com o sistema final."

        # 15. Act 4: localedef
        if re.search(r"\blocaledef\b", c):
            return "💡 [bold cyan]Insight LFS (localedef):[/bold cyan] Os arquivos compilados em /usr/lib/locale/locale-archive garantem suporte completo a UTF-8 e internacionalização para programas modernos."

        # 16. Act 4: pwconv / passwd
        if re.search(r"\b(pwconv|grpconv|passwd)\b", c):
            return "💡 [bold cyan]Insight LFS (Shadow):[/bold cyan] Separar os hashes secretos em /etc/shadow (modo 0600) impede que usuários comuns leiam as credenciais em /etc/passwd."

        # 17. Act 4: exec bash
        if re.search(r"\bexec\b.*\bbash\b", c):
            return "💡 [bold cyan]Insight LFS (exec bash):[/bold cyan] 'exec' substitui o processo do shell temporário em memória pelo novo Bash definitivo compilado com Readline e Ncurses nativos."

        # 18. Act 4: udev-hwdb
        if re.search(r"\budev-hwdb\b", c):
            return "💡 [bold cyan]Insight LFS (udev-hwdb):[/bold cyan] O banco binário /etc/udev/hwdb.bin permite ao udev identificar dispositivos PCI/USB instantaneamente durante o boot."

        # 19. Act 4: lfs-strip / strip
        if re.search(r"\b(lfs-strip|strip)\b", c):
            return "💡 [bold cyan]Insight LFS (strip):[/bold cyan] Remover símbolos de depuração DWARF com --strip-debug/--strip-unneeded libera gigabytes de disco mantendo os binários 100% funcionais."

        # 20. Act 5: Bootscripts & Network/System Config
        if re.search(r"\b(lfs-install-bootscripts|lfs-config-network|lfs-config-system)\b", c):
            return "💡 [bold cyan]Insight LFS (Cap. 9):[/bold cyan] Os scripts em /etc/rc.d/ e arquivos de rede/SysVinit (/etc/inittab, /etc/hosts, /etc/profile) estruturam os runlevels e a identidade do sistema no boot."

        # 21. Act 5: Kernel configuration (menuconfig / defconfig / lfs-kernel-config)
        if re.search(r"\b(menuconfig|defconfig|lfs-kernel-config)\b", c):
            return "💡 [bold cyan]Insight LFS (Kernel Config):[/bold cyan] Sem initramfs, drivers vitais como EXT4, SATA_AHCI, DEVTMPFS e BINFMT_ELF precisam ser compilados built-in [y] no núcleo, nunca como módulos [m]."

        # 22. Act 5: GRUB installation & grub.cfg
        if re.search(r"\b(grub-install|grub-mkconfig|lfs-config-grub)\b", c):
            return "💡 [bold cyan]Insight LFS (GRUB):[/bold cyan] O grub-install grava o código de estágio inicial no MBR de /dev/sda, enquanto /boot/grub/grub.cfg aponta ao núcleo vmlinuz-7.1.8-lfs-13.1 e root=/dev/sda3."

        return None

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

    def _cmd_cat(self, args: List[str], stdin_data: str = "") -> CommandResult:
        if not args:
            return CommandResult(output=stdin_data.rstrip("\n"), success=True)
        contents = []
        for p in args:
            if p == "-":
                contents.append(stdin_data)
                continue
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
        if self.engine.fs.in_chroot:
            ok, msg = self.engine.fs.exit_chroot()
            return CommandResult(output=msg, success=ok, state_changed=True)
        return CommandResult(output="Conexão com a estação encerrada.", success=True, system_event="EXIT")

    def _cmd_chroot(self, args: List[str]) -> CommandResult:
        """Enters chroot environment at target directory."""
        if not args:
            return CommandResult(output="chroot: operando ausente", success=False)

        target = args[0]
        ok, msg = self.engine.fs.enter_chroot(target)
        if not ok:
            return CommandResult(output=msg, success=False)

        # Parse any environment overrides passed (e.g. HOME=/root TERM=xterm PATH=/usr/bin:/usr/sbin)
        i = 1
        while i < len(args):
            arg = args[i]
            if "=" in arg and not arg.startswith("-"):
                k, v = arg.split("=", 1)
                self.engine.fs.env[k] = v
            i += 1

        return CommandResult(output=msg, success=True, state_changed=True)

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
        from_owner = None
        pos_args = []
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("--from="):
                from_owner = a.split("=", 1)[1]
            elif a == "--from" and i + 1 < len(args):
                from_owner = args[i + 1]
                i += 1
            elif a.startswith("-"):
                if "R" in a or "r" in a:
                    recursive = True
                if "v" in a:
                    verbose = True
            else:
                pos_args.append(a)
            i += 1

        if len(pos_args) < 2:
            return CommandResult(output="chown: operandos insuficientes", success=False)

        owner_group = pos_args[0]
        targets = pos_args[1:]
        outputs = []
        all_ok = True

        for target in targets:
            ok, msg = self.engine.fs.chown(target, owner_group, recursive=recursive, verbose=verbose, from_owner=from_owner)
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
        is_bind = False
        fstype = "ext4"
        options = ""
        pos_args = []

        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-v", "--verbose"):
                verbose = True
                i += 1
            elif a in ("--bind", "-B"):
                is_bind = True
                i += 1
            elif a == "-vt" and i + 1 < len(args):
                verbose = True
                fstype = args[i + 1]
                i += 2
            elif a.startswith("-vt") and len(a) > 3:
                verbose = True
                fstype = a[3:]
                i += 1
            elif a == "-t" and i + 1 < len(args):
                fstype = args[i + 1]
                i += 2
            elif a.startswith("-t") and len(a) > 2:
                fstype = a[2:]
                i += 1
            elif a == "-o" and i + 1 < len(args):
                options = args[i + 1]
                i += 2
            elif a.startswith("-o") and len(a) > 2:
                options = a[2:]
                i += 1
            elif not a.startswith("-"):
                pos_args.append(a)
                i += 1
            else:
                if "bind" in a:
                    is_bind = True
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
        ok, msg = self.engine.fs.mount(device, mp, fstype=fstype, verbose=verbose, is_bind=is_bind, options=options)
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

        base = posixpath.basename(tarball)
        extracted_dir = re.sub(r"\.tar(?:\.(?:xz|gz|bz2|zst))?$", "", base)
        if extracted_dir and extracted_dir != base:
            self.engine.fs.mkdir(extracted_dir, parents=True)

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
            if fs.in_chroot:
                return self._kernel_mrproper()
            return CommandResult(output="make: mrproper concluído para a árvore do Linux 6.14.7.", success=True, state_changed=True)

        # Target: make defconfig / menuconfig / modules_install (Act 5 Kernel 7.1.8)
        if "defconfig" in args:
            return self._kernel_defconfig()
        if "menuconfig" in args:
            return self._kernel_menuconfig()
        if "modules_install" in args:
            return self._kernel_modules_install()

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

        # Target: make check / make -k check (Act 4 test suites)
        if "check" in args:
            return self._handle_make_check(args)

        # Target: make install or make DESTDIR=$LFS install
        is_install = any("install" in a for a in args)
        if is_install:
            if fs.in_chroot and (
                "bootscripts" in fs.cwd.lower()
                or fs.configured_packages.get("_current") == "lfs-bootscripts"
            ):
                return self._cmd_lfs_install_bootscripts([])

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
        if fs.in_chroot and (
            "linux" in fs.cwd.lower()
            or fs.configured_packages.get("_current") == "linux-kernel"
        ):
            return self._compile_linux_kernel(args)

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
            ok_w, err_w = self.engine.fs.write_file(dest_file, content)
            if not ok_w:
                return CommandResult(output=err_w, success=False)
            return CommandResult(output=f"'{src}' -> '{dest_file}'", success=True, state_changed=True)
        return CommandResult(output=f"cp: não foi possível obter estado de '{src}': Arquivo ou diretório inexistente", success=False)

    def _cmd_find(self, args: List[str]) -> CommandResult:
        """Finds files and directories in virtual FS."""
        target_dir = args[0] if args and not args[0].startswith("-") else "."
        if "-delete" in args:
            return CommandResult(output=f"[find] Arquivos desnecessários removidos de '{target_dir}'.", success=True, state_changed=True)
        return CommandResult(output=target_dir, success=True)

    def _cmd_install(self, args: List[str]) -> CommandResult:
        """Handles Unix 'install' utility (e.g. install -dv -m 0750 /root)."""
        verbose = False
        dir_mode = False
        mode: Optional[int] = None
        targets = []

        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("-"):
                if "d" in a:
                    dir_mode = True
                if "v" in a:
                    verbose = True
                if "m" in a:
                    if a.endswith("m") and i + 1 < len(args):
                        mode_str = args[i + 1]
                        i += 1
                    else:
                        m_idx = a.index("m")
                        mode_str = a[m_idx + 1:]
                    try:
                        mode = int(mode_str, 8)
                    except ValueError:
                        pass
            else:
                targets.append(a)
            i += 1

        if not targets:
            return CommandResult(output="install: operando de arquivo ausente", success=False)

        ok, msg = self.engine.fs.install(targets, dir_mode=dir_mode, mode=mode, verbose=verbose)
        return CommandResult(output=msg, success=ok, state_changed=ok)

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

        pkgs = [p for p in get_toolchain_packages() if p.chapter in (5, 6, 7)]
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

    def _cmd_lfs_compile_chroot(self, args: List[str]) -> CommandResult:
        """Compiles Chapter 7 additional chroot tools (individual or batch)."""
        from ..data.lfs_manifest import TOOLCHAIN_CATALOG, get_toolchain_package

        if not self.engine.fs.in_chroot:
            return CommandResult(
                output="lfs-compile-chroot: ERRO: O comando só pode ser executado dentro do ambiente chroot ($LFS).",
                success=False
            )

        if not self.engine.fs.exists("/dev/null"):
            return CommandResult(
                output="lfs-compile-chroot: ERRO: /dev/null não encontrado no chroot. Monte /dev via bind mount antes de compilar.",
                success=False
            )

        if not self.engine.fs.exists("/proc/cpuinfo") and not self.engine.fs.exists("/proc"):
            return CommandResult(
                output="lfs-compile-chroot: ERRO: /proc não está montado no chroot. Monte o sistema de arquivos proc antes de compilar.",
                success=False
            )

        target = args[0].strip().lower() if args else "all"

        ch7_order = ["gettext", "bison", "perl", "python", "texinfo", "util-linux"]

        if target == "all":
            lines = [
                "[bold cyan]╔════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
                "[bold cyan]║ FORJA DAS FERRAMENTAS ADICIONAIS DO CHROOT - CAPÍTULO 7 (LFS 13.1)     ║[/bold cyan]",
                "[bold cyan]╚════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            ]
            total_xp = 0
            new_compiled_count = 0
            for idx, tool_id in enumerate(ch7_order, 1):
                pkg = TOOLCHAIN_CATALOG.get(tool_id)
                name = pkg.name if pkg else tool_id.upper()
                sbu = pkg.sbu_label if pkg else "0,2 UPC"
                if not self.engine.fs.is_package_compiled(tool_id):
                    new_compiled_count += 1
                    total_xp += 75
                self.engine.fs.record_package_compiled(tool_id)
                self.engine.fs.install_tool(tool_id, f"/usr/bin/{tool_id}")
                if pkg and pkg.binaries:
                    for b in pkg.binaries:
                        self.engine.fs.install_tool(b, f"/usr/bin/{b}")
                        self.engine.fs.record_package_compiled(b)
                lines.append(f"  [cyan][{idx:02d}/06][/cyan] {name:16} ({sbu:12}) ... [bold green][OK][/bold green]")

            if new_compiled_count > 0:
                self.engine.char.add_xp(total_xp)
            self.engine.story_engine.flags["chroot_tools_compiled"] = True
            if new_compiled_count == 0:
                lines.append(f"\n[yellow]ℹ Todas as 6 ferramentas do chroot já estavam compiladas! (+0 XP)[/yellow]")
            else:
                lines.append(f"\n[bold green]★ Todas as 6 ferramentas temporárias do chroot instaladas com sucesso! (+{total_xp} XP)[/bold green]")
            return CommandResult(output="\n".join(lines), success=True, state_changed=new_compiled_count > 0)

        # Single package
        pkg = get_toolchain_package(target)
        if not pkg:
            return CommandResult(
                output=f"lfs-compile-chroot: pacote '{target}' não encontrado no catálogo. Pacotes válidos: {', '.join(ch7_order)}.",
                success=False
            )

        already_compiled = self.engine.fs.is_package_compiled(pkg.id)
        self.engine.fs.record_package_compiled(pkg.id)
        for b in pkg.binaries:
            self.engine.fs.install_tool(b, f"/usr/bin/{b}")
            self.engine.fs.record_package_compiled(b)

        if already_compiled:
            return CommandResult(
                output=f"[yellow]ℹ {pkg.name} já se encontra compilado e atualizado em {pkg.install_path}. (+0 XP)[/yellow]",
                success=True,
                state_changed=False
            )

        xp_earned = int(pkg.sbu * 100)
        self.engine.char.add_xp(xp_earned)
        return CommandResult(
            output=f"[bold green]✔ {pkg.name} compilado e instalado com sucesso em {pkg.install_path}! (+{xp_earned} XP)[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_lfs_status_chroot(self, args: List[str]) -> CommandResult:
        """Displays status checklist of Chapter 7 tools."""
        from ..data.lfs_manifest import get_toolchain_packages
        pkgs = get_toolchain_packages(chapter=7)

        lines = [
            "[bold cyan]╔══════════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ STATUS DAS FERRAMENTAS DO CHROOT - CAPÍTULO 7 (LFS 13.1)                         ║[/bold cyan]",
            "[bold cyan]╚══════════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            f"{'PACOTE':<24} {'VERSÃO':<10} {'UPC (SBU)':<14} {'STATUS':<20} {'DESTINO'}",
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

            lines.append(f"{p.name:<24} {p.version:<10} {p.sbu_label:<14} {status:<24} {p.install_path}")

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

    # --- Act 4: Chapter 8 Basic System Software Handlers ---

    def _require_chroot(self, cmd_name: str) -> Optional[CommandResult]:
        """Guards Act 4 commands so they can only run inside the chroot jail."""
        if not self.engine.fs.in_chroot:
            return CommandResult(
                output=f"{cmd_name}: ERRO: Este comando do Capítulo 8 só pode ser executado dentro do ambiente chroot ($LFS).",
                success=False
            )
        return None

    def _install_system_package(self, pkg) -> bool:
        """Installs a Chapter 8 package into virtual /usr/{bin,sbin,lib} and returns True if newly compiled."""
        fs = self.engine.fs
        already_compiled = fs.is_package_compiled(pkg.id)
        fs.record_package_compiled(pkg.id)

        for d in ("/usr/bin", "/usr/sbin", "/usr/lib", "/etc"):
            if not fs.exists(d):
                fs.mkdir(d, parents=True)

        if pkg.binaries:
            for b in pkg.binaries:
                if b.startswith("lib") or ".so" in b or b.endswith(".a"):
                    dest_dir = "/usr/lib"
                elif pkg.install_path in ("/usr/sbin", "/sbin"):
                    dest_dir = "/usr/sbin"
                else:
                    dest_dir = "/usr/bin"
                fs.install_tool(b, f"{dest_dir}/{b}")
        elif pkg.install_path == "/etc":
            fs.write_file("/etc/services", "# IANA network services\nssh\t22/tcp\nhttps\t443/tcp\n")
            fs.write_file("/etc/protocols", "# IANA internet protocols\ntcp\t6\tTCP\nudp\t17\tUDP\n")

        return not already_compiled

    def _handle_make_check(self, args: List[str]) -> CommandResult:
        """Executes simulated LFS Chapter 8 test suites (glibc, binutils, gcc) idempotently."""
        guard = self._require_chroot("make check")
        if guard:
            return guard

        fs = self.engine.fs
        keep_going = "-k" in args
        explicit = None
        non_flags = [a for a in args if not a.startswith("-") and a.lower() != "check"]
        if non_flags:
            target_candidate = non_flags[0].lower()
            if target_candidate in ("glibc", "binutils", "gcc", "all"):
                explicit = target_candidate
            else:
                return CommandResult(
                    output=f"make check: alvo de teste '{non_flags[0]}' desconhecido. Alvos válidos: glibc, binutils, gcc, all.",
                    success=False
                )

        suites_meta = {
            "glibc": {
                "pkg_id": "glibc-final",
                "title": "Glibc 2.44 Test Suite",
                "summary": "PASS: 5891 | XFAIL: 16 | FAIL: 0 (conformidade POSIX/ABI 100%)",
                "xp": 150,
            },
            "binutils": {
                "pkg_id": "binutils-final",
                "title": "Binutils 2.47 Test Suite (ld, gas, binutils)",
                "summary": "PASS: 2841 | XFAIL: 4 | UNEXPECTED FAIL: 0",
                "xp": 120,
            },
            "gcc": {
                "pkg_id": "gcc-final",
                "title": "GCC 16.2.0 Test Suite (gcc, g++, libstdc++)",
                "summary": "PASS: 198420 | XFAIL: 1412 | FAIL: 0 (test_summary validado)",
                "xp": 200,
            },
        }

        if explicit == "all":
            targets = [k for k, m in suites_meta.items() if fs.is_package_compiled(m["pkg_id"])]
            if not targets:
                return CommandResult(
                    output="make check: ERRO: Nenhum dos pacotes com suíte (glibc-final, binutils-final, gcc-final) foi compilado ainda.",
                    success=False
                )
        elif explicit:
            if not fs.is_package_compiled(suites_meta[explicit]["pkg_id"]):
                return CommandResult(
                    output=f"make check: ERRO: Compile '{suites_meta[explicit]['pkg_id']}' primeiro com 'lfs-compile-system {suites_meta[explicit]['pkg_id']}'.",
                    success=False
                )
            targets = [explicit]
        else:
            cwd_l = fs.cwd.lower()
            curr_pkg = fs.configured_packages.get("_current", "").lower()
            chosen = None
            for k in ("glibc", "binutils", "gcc"):
                if k in cwd_l or k in curr_pkg:
                    if fs.is_package_compiled(suites_meta[k]["pkg_id"]):
                        chosen = k
                        break
            if not chosen:
                if keep_going and fs.is_package_compiled("gcc-final") and "gcc" not in fs.system_checks_passed:
                    chosen = "gcc"
                elif fs.is_package_compiled("glibc-final") and "glibc" not in fs.system_checks_passed:
                    chosen = "glibc"
                elif fs.is_package_compiled("binutils-final") and "binutils" not in fs.system_checks_passed:
                    chosen = "binutils"
                elif fs.is_package_compiled("gcc-final") and "gcc" not in fs.system_checks_passed:
                    chosen = "gcc"
                else:
                    for k in ("glibc", "binutils", "gcc"):
                        if fs.is_package_compiled(suites_meta[k]["pkg_id"]):
                            chosen = k
                            break
            if not chosen:
                return CommandResult(
                    output="make check: ERRO: Compile glibc-final, binutils-final ou gcc-final antes de executar as suítes de testes.",
                    success=False
                )
            targets = [chosen]

        lines = [
            "[bold cyan]╔══════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ SUÍTE DE TESTES AUTOMATIZADOS LFS 13.1 (CAPÍTULO 8)                  ║[/bold cyan]",
            "[bold cyan]╚══════════════════════════════════════════════════════════════════════╝[/bold cyan]",
        ]
        total_xp = 0
        any_new = False
        for t in targets:
            meta = suites_meta[t]
            is_new = t not in fs.system_checks_passed
            fs.system_checks_passed.add(t)
            if is_new:
                any_new = True
                total_xp += meta["xp"]
            xp_tag = f"+{meta['xp']} XP" if is_new else "+0 XP (já verificado)"
            lines.append(f"[bold green]✔ {meta['title']}[/bold green] ({xp_tag})")
            lines.append(f"  [dim]{meta['summary']}[/dim]")

        if total_xp > 0:
            self.engine.char.add_xp(total_xp)

        return CommandResult(output="\n".join(lines), success=True, state_changed=any_new)

    def _cmd_lfs_status_system(self, args: List[str]) -> CommandResult:
        """Displays Chapter 8 system build progress across Tiers 1-4, test suites, and Act 4 milestones."""
        from ..data.lfs_manifest import SYSTEM_TIERS, get_system_packages, get_system_package

        fs = self.engine.fs
        filter_tier: Optional[int] = None
        if args:
            a0 = args[0].strip().lower().replace("tier", "")
            if a0.isdigit() and int(a0) in (1, 2, 3, 4):
                filter_tier = int(a0)
            else:
                target_pkg = get_system_package(args[0])
                if target_pkg:
                    is_done = fs.is_package_compiled(target_pkg.id)
                    st = "[bold green]✔ INSTALADO[/bold green]" if is_done else "[dim yellow]⏳ PENDENTE[/dim yellow]"
                    lines = [
                        f"[bold cyan]=== DETALHES DO PACOTE: {target_pkg.name} ({target_pkg.id}) ===[/bold cyan]",
                        f"  • Versão:      {target_pkg.version}",
                        f"  • Capítulo:    {target_pkg.chapter} (Tier {target_pkg.tier})",
                        f"  • Carga SBU:   {target_pkg.sbu_label} ({target_pkg.sbu} UPC)",
                        f"  • Destino:     {target_pkg.install_path}",
                        f"  • Status:      {st}",
                    ]
                    if target_pkg.binaries:
                        lines.append(f"  • Binários:    {', '.join(target_pkg.binaries)}")
                    return CommandResult(output="\n".join(lines), success=True)
                return CommandResult(
                    output=(
                        f"lfs-status-system: tier ou pacote '{args[0]}' não encontrado no Capítulo 8.\n"
                        f"Use: lfs-status-system [tier1|tier2|tier3|tier4|<pacote>] ou execute sem argumentos para o panorama geral."
                    ),
                    success=False
                )

        if filter_tier is not None:
            pkgs = get_system_packages(tier=filter_tier)
            tinfo = SYSTEM_TIERS[filter_tier]
            lines = [
                f"[bold cyan]=== {tinfo['name']} ({tinfo['sections']}) ===[/bold cyan]",
                f"{'PACOTE':<26} {'VERSÃO':<12} {'UPC':<12} {'STATUS'}",
                "─" * 68,
            ]
            done = 0
            for p in pkgs:
                is_done = fs.is_package_compiled(p.id)
                if is_done:
                    done += 1
                st = "[bold green]✔ INSTALADO[/bold green]" if is_done else "[dim yellow]⏳ PENDENTE[/dim yellow]"
                lines.append(f"{p.name:<26} {p.version:<12} {p.sbu_label:<12} {st}")
            lines.append("─" * 68)
            lines.append(f"[bold white]Tier {filter_tier}:[/bold white] {done}/{len(pkgs)} pacotes compilados.")
            return CommandResult(output="\n".join(lines), success=True)

        all_pkgs = get_system_packages()
        total_done = sum(1 for p in all_pkgs if fs.is_package_compiled(p.id))
        total_sbu = sum(p.sbu for p in all_pkgs)
        done_sbu = sum(p.sbu for p in all_pkgs if fs.is_package_compiled(p.id))

        lines = [
            "[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ TELEMETRIA DO SISTEMA DEFINITIVO - CAPÍTULO 8 (LFS 13.1 ATO 4)               ║[/bold cyan]",
            "[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
        ]

        for tier_num in (1, 2, 3, 4):
            t_pkgs = get_system_packages(tier=tier_num)
            t_done = sum(1 for p in t_pkgs if fs.is_package_compiled(p.id))
            t_info = SYSTEM_TIERS[tier_num]
            t_pct = (t_done / len(t_pkgs)) * 100 if t_pkgs else 0.0
            badge = "[bold green]✔[/bold green]" if t_done == len(t_pkgs) else "[yellow]⏳[/yellow]"
            lines.append(
                f"{badge} [bold white]Tier {tier_num} ({t_info['sections']}):[/bold white] {t_done:02d}/{len(t_pkgs):02d} ({t_pct:5.1f}%) - {t_info['name']}"
            )

        pct = (total_done / len(all_pkgs)) * 100 if all_pkgs else 0.0
        lines.extend([
            "─" * 78,
            f"[bold white]Progresso Total:[/bold white] {total_done}/{len(all_pkgs)} pacotes ({pct:.1f}%) | [bold white]SBU:[/bold white] {done_sbu:.1f}/{total_sbu:.1f} UPC",
            "",
            "[bold yellow]Suítes de Testes (make check):[/bold yellow]",
            f"  • Glibc (make check):      {'[bold green]✔ PASSOU[/bold green]' if 'glibc' in fs.system_checks_passed else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Binutils (make check):   {'[bold green]✔ PASSOU[/bold green]' if 'binutils' in fs.system_checks_passed else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • GCC (make -k check):     {'[bold green]✔ PASSOU[/bold green]' if 'gcc' in fs.system_checks_passed else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            "",
            "[bold yellow]Marcos Especiais de Configuração (Cap. 8):[/bold yellow]",
            f"  • Localidades UTF-8 (localedef):       {'[bold green]✔ OK[/bold green]' if fs.locales_configured else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Senhas Ocultas Shadow (pwconv):      {'[bold green]✔ OK[/bold green]' if fs.shadow_configured else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Senha de Root (passwd root):         {'[bold green]✔ OK[/bold green]' if fs.root_password_set else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Shell Nativo (exec bash --login):    {'[bold green]✔ OK[/bold green]' if fs.bash_restarted else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Banco de Hardware (udev-hwdb):       {'[bold green]✔ OK[/bold green]' if fs.udev_updated else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
            f"  • Stripping de Depuração (lfs-strip):  {'[bold green]✔ OK[/bold green]' if fs.debug_stripped else '[dim yellow]⏳ PENDENTE[/dim yellow]'}",
        ])
        return CommandResult(output="\n".join(lines), success=True)

    def _cmd_lfs_compile_system(self, args: List[str]) -> CommandResult:
        """Compiles Chapter 8 system packages inside chroot by tier, all, or individual package."""
        from ..data.lfs_manifest import SYSTEM_TIERS, get_system_packages, get_system_package

        guard = self._require_chroot("lfs-compile-system")
        if guard:
            return guard

        target = args[0].strip().lower() if args else "all"

        if target in ("tier1", "tier2", "tier3", "tier4", "1", "2", "3", "4", "all"):
            if target == "all":
                tiers_to_build = [1, 2, 3, 4]
                header_title = "FORJA DO SISTEMA DEFINITIVO - TODOS OS TIERS (81 PACOTES)"
            else:
                t_num = int(target.replace("tier", ""))
                tiers_to_build = [t_num]
                header_title = SYSTEM_TIERS[t_num]["name"].upper()

            lines = [
                "[bold cyan]╔════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
                f"[bold cyan]║ {header_title:<70} ║[/bold cyan]",
                "[bold cyan]╚════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            ]

            new_count = 0
            total_xp = 0
            compiled_ids = []
            for t_num in tiers_to_build:
                pkgs = get_system_packages(tier=t_num)
                t_new = 0
                for pkg in pkgs:
                    if self._install_system_package(pkg):
                        new_count += 1
                        t_new += 1
                        total_xp += 25
                    compiled_ids.append(pkg.id)
                t_info = SYSTEM_TIERS[t_num]
                status_tag = f"[bold green]+{t_new} novos[/bold green]" if t_new > 0 else "[yellow]já compilado (+0 XP)[/yellow]"
                lines.append(f"  [cyan]Tier {t_num}[/cyan] ({t_info['sections']}, {len(pkgs)} pacotes) ... {status_tag}")

                if t_new > 0:
                    self.engine.story_engine.flags[f"tier{t_num}_compiled"] = True

            if new_count > 0:
                self.engine.char.add_xp(total_xp)
                self.engine.telemetry.cpu_usage = min(98.0, self.engine.telemetry.cpu_usage + 25.0)
                lines.append(f"\n[bold green]★ {new_count} novos pacotes do sistema compilados e instalados em /usr/{{bin,sbin,lib}}! (+{total_xp} XP)[/bold green]")
            else:
                lines.append("\n[yellow]ℹ Todos os pacotes selecionados já estavam compilados e atualizados! (+0 XP)[/yellow]")

            prompts = []
            if "glibc-final" in compiled_ids and "glibc" not in self.engine.fs.system_checks_passed:
                prompts.append("Execute [bold green]make check[/bold green] para validar a Glibc e [bold green]localedef -i pt_BR -f UTF-8 pt_BR.UTF-8[/bold green] para os locales.")
            if "gcc-final" in compiled_ids and "gcc" not in self.engine.fs.system_checks_passed:
                prompts.append("Recomendado: execute [bold green]make -k check[/bold green] para auditar a suíte do GCC definitivo.")
            if prompts:
                lines.append("[bold magenta]K.E.R.N.E.L. Alerta de Validação:[/bold magenta] " + " ".join(prompts))

            return CommandResult(output="\n".join(lines), success=True, state_changed=new_count > 0)

        # Single package lookup in Chapter 8
        pkg = get_system_package(target)
        if not pkg:
            return CommandResult(
                output=(
                    f"lfs-compile-system: pacote ou tier '{target}' não encontrado no Capítulo 8.\n"
                    f"Use: lfs-compile-system [tier1|tier2|tier3|tier4|all|<pacote>] ou consulte 'lfs-status-system'."
                ),
                success=False
            )

        is_new = self._install_system_package(pkg)
        if not is_new:
            return CommandResult(
                output=f"[yellow]ℹ {pkg.name} ({pkg.version}) já está compilado e instalado no sistema. (+0 XP)[/yellow]",
                success=True,
                state_changed=False
            )

        xp = max(30, min(300, int(pkg.sbu * 20) + 40))
        self.engine.char.add_xp(xp)
        extra_hint = ""
        if pkg.id == "glibc-final":
            extra_hint = "\n[bold yellow]⚠ K.E.R.N.E.L.:[/bold yellow] Glibc definitiva instalada! Execute '[bold green]make check[/bold green]' e '[bold green]localedef -i pt_BR -f UTF-8 pt_BR.UTF-8[/bold green]'."
        elif pkg.id == "gcc-final":
            extra_hint = "\n[bold yellow]⚠ K.E.R.N.E.L.:[/bold yellow] GCC 16.2.0 definitivo forjado! Execute '[bold green]make -k check[/bold green]' para validar os compiladores."
        elif pkg.id == "binutils-final":
            extra_hint = "\n[bold yellow]⚠ K.E.R.N.E.L.:[/bold yellow] Binutils definitivo pronto! Você pode validar com '[bold green]make check binutils[/bold green]'."

        return CommandResult(
            output=f"[bold green]✔ {pkg.name} {pkg.version} (Tier {pkg.tier}, {pkg.sbu_label}) compilado e instalado em {pkg.install_path}! (+{xp} XP)[/bold green]{extra_hint}",
            success=True,
            state_changed=True
        )

    def _cmd_localedef(self, args: List[str]) -> CommandResult:
        """Compiles UTF-8 locale definitions into /usr/lib/locale/locale-archive."""
        guard = self._require_chroot("localedef")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("glibc-final"):
            return CommandResult(
                output="localedef: ERRO: Compile a Glibc definitiva (glibc-final / tier1) antes de gerar os locales.",
                success=False
            )

        pos_args = []
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-i", "-f", "--charmap", "--inputfile") and i + 1 < len(args):
                i += 2
            elif a.startswith("-"):
                i += 1
            else:
                pos_args.append(a)
                i += 1

        locale_name = pos_args[-1] if pos_args else "pt_BR.UTF-8"
        fs.mkdir("/usr/lib/locale", parents=True)
        fs.write_file("/usr/lib/locale/locale-archive", f"# Compiled locale archive\n{locale_name}\n", append=True)

        first_time = not fs.locales_configured
        fs.locales_configured = True
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        return CommandResult(
            output=f"[bold green]✔ Localidade '{locale_name}' compilada em /usr/lib/locale/locale-archive.{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_pwconv(self, args: List[str]) -> CommandResult:
        """Converts /etc/passwd entries to shadowed /etc/shadow."""
        guard = self._require_chroot("pwconv")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("shadow"):
            return CommandResult(
                output="pwconv: ERRO: O pacote Shadow ainda não foi compilado. Execute 'lfs-compile-system shadow' ou 'tier2'.",
                success=False
            )

        if not fs.exists("/etc/shadow"):
            fs.write_file("/etc/shadow", "root:!:20100:0:99999:7:::\n")
        fs.chmod("/etc/shadow", "0600")

        first_time = not fs.shadow_configured
        fs.shadow_configured = True
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(80)
            xp_msg = " (+80 XP)"

        return CommandResult(
            output=f"[bold green]✔ Senhas migradas com segurança para /etc/shadow (permissão 0600).{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_grpconv(self, args: List[str]) -> CommandResult:
        """Converts /etc/group entries to shadowed /etc/gshadow."""
        guard = self._require_chroot("grpconv")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("shadow"):
            return CommandResult(
                output="grpconv: ERRO: O pacote Shadow ainda não foi compilado. Execute 'lfs-compile-system shadow' ou 'tier2'.",
                success=False
            )

        first_time = not fs.exists("/etc/gshadow")
        if first_time:
            fs.write_file("/etc/gshadow", "root:*::\n")
            fs.chmod("/etc/gshadow", "0600")
            self.engine.char.add_xp(50)
            xp_msg = " (+50 XP)"
        else:
            xp_msg = ""

        fs.shadow_configured = True
        return CommandResult(
            output=f"[bold green]✔ Grupos sincronizados com /etc/gshadow (permissão 0600).{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_passwd(self, args: List[str]) -> CommandResult:
        """Sets password hash in /etc/shadow non-interactively (default: root)."""
        guard = self._require_chroot("passwd")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("shadow"):
            return CommandResult(
                output="passwd: ERRO: O pacote Shadow ainda não foi compilado. Execute 'lfs-compile-system shadow' ou 'tier2'.",
                success=False
            )

        target_user = next((a for a in args if not a.startswith("-")), "root")
        if target_user not in fs.users and target_user != "root":
            return CommandResult(output=f"passwd: usuário '{target_user}' não existe", success=False)

        shadow_hash = "$y$j9T$HeraStation2142QuantumSalt$8xK9vP2mL4nQ7rT1wZ5yB3cF6hJ0kM"
        fs.write_file("/etc/shadow", f"{target_user}:{shadow_hash}:20100:0:99999:7:::\n")
        fs.chmod("/etc/shadow", "0600")

        xp_msg = ""
        if target_user == "root":
            first_time = not fs.root_password_set
            fs.root_password_set = True
            if first_time:
                self.engine.char.add_xp(100)
                xp_msg = " (+100 XP)"

        return CommandResult(
            output=f"[bold green]✔ passwd: senha para '{target_user}' atualizada em /etc/shadow (hash yescrypt).{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_exec(self, args: List[str]) -> CommandResult:
        """Replaces current chroot shell with newly compiled Bash (exec /usr/bin/bash --login)."""
        guard = self._require_chroot("exec")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("bash-final"):
            return CommandResult(
                output="exec: ERRO: O Bash definitivo (bash-final / tier2) ainda não foi compilado.",
                success=False
            )

        if not args or not any("bash" in a or "sh" in a for a in args):
            return CommandResult(
                output="Uso: exec /usr/bin/bash --login",
                success=False
            )

        fs.env["SHELL"] = "/usr/bin/bash"
        fs.env["PATH"] = "/usr/bin:/usr/sbin"
        fs.env["PS1"] = "(lfs chroot) \\u:\\w\\$ "

        first_time = not fs.bash_restarted
        fs.bash_restarted = True
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        return CommandResult(
            output=f"[bold green]✔ Shell reiniciado com /usr/bin/bash 5.3 (--login)! Processo temporário substituído.{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_udev_hwdb(self, args: List[str]) -> CommandResult:
        """Updates the udev hardware database (/etc/udev/hwdb.bin)."""
        guard = self._require_chroot("udev-hwdb")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("udev"):
            return CommandResult(
                output="udev-hwdb: ERRO: O pacote Udev ainda não foi compilado. Execute 'lfs-compile-system udev' ou 'tier4'.",
                success=False
            )

        if "update" not in args:
            return CommandResult(output="Uso: udev-hwdb update", success=False)

        fs.mkdir("/etc/udev", parents=True)
        fs.write_file("/etc/udev/hwdb.bin", "# Binary udev hardware database (LFS 13.1)\n")

        first_time = not fs.udev_updated
        fs.udev_updated = True
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        return CommandResult(
            output=f"[bold green]✔ Banco de dados de hardware /etc/udev/hwdb.bin compilado e atualizado.{xp_msg}[/bold green]",
            success=True,
            state_changed=True
        )

    def _cmd_lfs_strip(self, args: List[str]) -> CommandResult:
        """Strips debug symbols from binaries and libraries (LFS Section 8.85) and cleans /tmp."""
        guard = self._require_chroot("lfs-strip")
        if guard:
            return guard

        fs = self.engine.fs
        first_time = not fs.debug_stripped
        fs.debug_stripped = True

        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(150)
            self.engine.telemetry.ram_mb = max(900, self.engine.telemetry.ram_mb - 180)
            xp_msg = " (+150 XP)"

        output = (
            f"[bold cyan]=== SEÇÃO 8.85: STRIPPING & LIMPEZA DE SÍMBOLOS DE DEPURAÇÃO ===[/bold cyan]\n"
            f"  [green]✔[/green] strip --strip-debug /usr/lib/*.a /usr/lib/*.so.*\n"
            f"  [green]✔[/green] strip --strip-unneeded /usr/bin/* /usr/sbin/*\n"
            f"  [green]✔[/green] rm -rf /tmp/* /usr/lib/lib{{bfd,opcodes}}.la\n"
            f"[bold green]★ Símbolos DWARF removidos! ~1.4 GB de armazenamento e recursos da estação liberados.{xp_msg}[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=first_time)

    def _cmd_strip(self, args: List[str]) -> CommandResult:
        """Unix strip command alias for Act 4 debug symbol stripping."""
        return self._cmd_lfs_strip(args)

    # --- Act 5: Chapter 9 & 10 Configuration, Kernel 7.1.8 & GRUB Handlers ---

    _KERNEL_SUBSYSTEMS = [
        ("CONFIG_64BIT", "Suporte à arquitetura x86_64 (64 bits)", True),
        ("CONFIG_DEVTMPFS", "Sistema de arquivos automático de dispositivos (/dev)", True),
        ("CONFIG_DEVTMPFS_MOUNT", "Montagem automática do devtmpfs pelo kernel no boot", True),
        ("CONFIG_EXT4_FS", "Suporte ao sistema de arquivos raiz ext4 (sem initramfs!)", True),
        ("CONFIG_SATA_AHCI", "Controlador de armazenamento SATA/AHCI (/dev/sda)", True),
        ("CONFIG_BINFMT_ELF", "Carregador de executáveis ELF (/sbin/init, bash, glibc)", True),
        ("CONFIG_NET", "Pilha de rede TCP/IP do núcleo Linux", False),
    ]

    def _cmd_lfs_install_bootscripts(self, args: List[str]) -> CommandResult:
        """Installs LFS-Bootscripts 20250827 into /etc/rc.d and /lib/services."""
        guard = self._require_chroot("lfs-install-bootscripts")
        if guard:
            return guard

        fs = self.engine.fs
        for d in ("/etc/rc.d/init.d", "/etc/rc.d/rc0.d", "/etc/rc.d/rc3.d", "/etc/rc.d/rcS.d", "/lib/services"):
            fs.mkdir(d, parents=True)

        fs.write_file("/etc/rc.d/init.d/rc", "#!/bin/sh\n# LFS-Bootscripts 20250827 SysV runlevel master script\n")
        fs.write_file("/etc/rc.d/init.d/functions", "#!/bin/sh\n# LFS init helper functions\n")
        fs.write_file("/etc/rc.d/init.d/network", "#!/bin/sh\n# LFS network initialization script\n")
        fs.write_file("/etc/rc.d/init.d/mountfs", "#!/bin/sh\n# LFS mount filesystems from /etc/fstab\n")
        fs.write_file("/etc/rc.d/init.d/udev", "#!/bin/sh\n# LFS udev device manager script\n")
        fs.write_file("/etc/rc.d/init.d/sysklogd", "#!/bin/sh\n# LFS system logger script\n")
        fs.write_file("/lib/services/ipv4-static", "#!/bin/sh\n# LFS static IPv4 network service\n")

        first_time = not fs.bootscripts_installed
        fs.bootscripts_installed = True
        fs.record_package_compiled("lfs-bootscripts")

        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(120)
            xp_msg = " (+120 XP)"

        output = (
            "[bold cyan]=== INSTALAÇÃO DO LFS-BOOTSCRIPTS 20250827 (CAPÍTULO 9.2) ===[/bold cyan]\n"
            "  INSTALL  /etc/rc.d/init.d/{rc,functions,network,mountfs,udev,sysklogd}\n"
            "  INSTALL  /lib/services/ipv4-static\n"
            f"[bold green]✔ Scripts de inicialização SysV instalados em /etc/rc.d e /lib/services.{xp_msg}[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=True)

    def _cmd_lfs_config_network(self, args: List[str]) -> CommandResult:
        """Configures Chapter 9.5 network files (/etc/hostname, /etc/hosts, /etc/resolv.conf, ifconfig.eth0)."""
        guard = self._require_chroot("lfs-config-network")
        if guard:
            return guard

        fs = self.engine.fs
        hostname = next((a for a in args if not a.startswith("-")), "hera-lfs").strip() or "hera-lfs"

        fs.mkdir("/etc/sysconfig", parents=True)
        was_configured = fs.network_configured

        fs.write_file("/etc/hostname", f"{hostname}\n")
        fs.write_file(
            "/etc/hosts",
            (
                "# Begin /etc/hosts\n"
                "127.0.0.1 localhost.localdomain localhost\n"
                f"127.0.1.1 {hostname}.hera.local {hostname}\n"
                "::1       localhost ip6-localhost ip6-loopback\n"
                "# End /etc/hosts\n"
            ),
        )
        fs.write_file(
            "/etc/resolv.conf",
            (
                "# Begin /etc/resolv.conf\n"
                "nameserver 10.0.2.3\n"
                "nameserver 1.1.1.1\n"
                "# End /etc/resolv.conf\n"
            ),
        )
        fs.write_file(
            "/etc/sysconfig/ifconfig.eth0",
            (
                "ONBOOT=yes\n"
                "IFACE=eth0\n"
                "SERVICE=ipv4-static\n"
                "IP=192.168.1.2\n"
                "GATEWAY=192.168.1.1\n"
                "PREFIX=24\n"
                "BROADCAST=192.168.1.255\n"
            ),
        )
        fs.network_configured = True

        xp_msg = ""
        if not was_configured:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        output = (
            "[bold cyan]=== CONFIGURAÇÃO DE REDE DO LFS (CAPÍTULO 9.5) ===[/bold cyan]\n"
            f"  [green]✔[/green] /etc/hostname -> '{hostname}'\n"
            "  [green]✔[/green] /etc/hosts -> localhost + entrada local\n"
            "  [green]✔[/green] /etc/resolv.conf -> nameserver 10.0.2.3\n"
            "  [green]✔[/green] /etc/sysconfig/ifconfig.eth0 -> ipv4-static (192.168.1.2/24)\n"
            f"[bold green]★ Rede configurada com sucesso.{xp_msg}[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=True)

    def _cmd_lfs_config_system(self, args: List[str]) -> CommandResult:
        """Generates Chapter 9.6-9.9 system configuration files (/etc/inittab, clock, console, profile, inputrc, shells)."""
        guard = self._require_chroot("lfs-config-system")
        if guard:
            return guard

        fs = self.engine.fs
        fs.mkdir("/etc/sysconfig", parents=True)
        was_configured = fs.sysconfig_configured

        fs.write_file(
            "/etc/inittab",
            (
                "# Begin /etc/inittab\n"
                "id:3:initdefault:\n\n"
                "si::sysinit:/etc/rc.d/init.d/rc S\n\n"
                "l0:0:wait:/etc/rc.d/init.d/rc 0\n"
                "l1:S1:wait:/etc/rc.d/init.d/rc 1\n"
                "l2:2:wait:/etc/rc.d/init.d/rc 2\n"
                "l3:3:wait:/etc/rc.d/init.d/rc 3\n"
                "l4:4:wait:/etc/rc.d/init.d/rc 4\n"
                "l5:5:wait:/etc/rc.d/init.d/rc 5\n"
                "l6:6:wait:/etc/rc.d/init.d/rc 6\n\n"
                "ca:12345:ctrlaltdel:/sbin/shutdown -t1 -a -r now\n\n"
                "1:2345:respawn:/sbin/agetty --noclear tty1 9600\n"
                "2:2345:respawn:/sbin/agetty tty2 9600\n"
                "# End /etc/inittab\n"
            ),
        )
        fs.write_file("/etc/sysconfig/clock", "# Begin /etc/sysconfig/clock\nUTC=1\n# End /etc/sysconfig/clock\n")
        fs.write_file(
            "/etc/sysconfig/console",
            "# Begin /etc/sysconfig/console\nKEYMAP=\"br-abnt2\"\nFONT=\"Lat2-Terminus16\"\n# End /etc/sysconfig/console\n",
        )
        fs.write_file(
            "/etc/profile",
            (
                "# Begin /etc/profile\n"
                "export LANG=pt_BR.UTF-8\n"
                "export PATH=/usr/bin:/usr/sbin\n"
                "# End /etc/profile\n"
            ),
        )
        fs.write_file(
            "/etc/inputrc",
            (
                "# Begin /etc/inputrc\n"
                "set horizontal-scroll-mode Off\n"
                "set meta-flag On\n"
                "set input-meta On\n"
                "set convert-meta Off\n"
                "set output-meta On\n"
                "set bell-style none\n"
                "# End /etc/inputrc\n"
            ),
        )
        fs.write_file(
            "/etc/shells",
            "# Begin /etc/shells\n/bin/sh\n/bin/bash\n# End /etc/shells\n",
        )
        fs.sysconfig_configured = True

        xp_msg = ""
        if not was_configured:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        output = (
            "[bold cyan]=== CONFIGURAÇÃO SYSVINIT & SHELL (CAPÍTULOS 9.6–9.9) ===[/bold cyan]\n"
            "  [green]✔[/green] /etc/inittab (runlevel padrão 3, consoles tty1-tty2)\n"
            "  [green]✔[/green] /etc/sysconfig/clock (UTC=1) & /etc/sysconfig/console (br-abnt2)\n"
            "  [green]✔[/green] /etc/profile (LANG=pt_BR.UTF-8)\n"
            "  [green]✔[/green] /etc/inputrc & /etc/shells\n"
            f"[bold green]★ Arquivos vitais do sistema gerados.{xp_msg}[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=True)

    def _cmd_lfs_check_config(self, args: List[str]) -> CommandResult:
        """Audits all Chapter 9 & 10 configuration files, kernel artifacts, and GRUB setup."""
        guard = self._require_chroot("lfs-check-config")
        if guard:
            return guard

        fs = self.engine.fs
        fs.sync_act5_state()

        def badge(ok: bool) -> str:
            return "[bold green]✔ OK[/bold green]" if ok else "[dim yellow]⏳ PENDENTE[/dim yellow]"

        net_ok = fs.has_valid_network_config() or fs.network_configured
        sys_ok = fs.has_valid_sysconfig() or fs.sysconfig_configured
        fstab_ok = fs.has_valid_fstab() or fs.fstab_configured
        k_img_ok = fs.has_valid_kernel_installed() or fs.kernel_installed
        grub_cfg_ok = fs.has_valid_grub_cfg() or fs.grub_cfg_created

        lines = [
            "[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ AUDITORIA DE CONFIGURAÇÃO DO SISTEMA, KERNEL E BOOT (ATO 5 - CAP. 9 & 10)    ║[/bold cyan]",
            "[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            f"  • LFS-Bootscripts (/etc/rc.d/*):              {badge(fs.bootscripts_installed)}",
            f"  • Rede (/etc/hostname, hosts, ifconfig, dns): {badge(net_ok)}",
            f"  • SysVinit & Shell (inittab, profile, shells):{badge(sys_ok)}",
            f"  • Tabela /etc/fstab (/dev/sda3 + swap):       {badge(fstab_ok)}",
            f"  • Kernel 7.1.8 Config (.config built-in [y]): {badge(fs.kernel_configured)}",
            f"  • Kernel 7.1.8 Compilado (bzImage):           {badge(fs.kernel_compiled)}",
            f"  • Kernel Instalado (/boot/vmlinuz-7.1.8...):  {badge(k_img_ok)}",
            f"  • GRUB no MBR (/dev/sda):                     {badge(fs.grub_mbr_installed)}",
            f"  • Menu GRUB (/boot/grub/grub.cfg):            {badge(grub_cfg_ok)}",
        ]
        return CommandResult(output="\n".join(lines), success=True)

    def _write_kernel_dot_config(self) -> None:
        """Persists /sources/linux-7.1.8/.config from VirtualFS.kernel_config."""
        fs = self.engine.fs
        fs.mkdir("/sources/linux-7.1.8", parents=True)
        lines = ["# Automatically generated Linux 7.1.8 Kernel Configuration (LFS 13.1)"]
        for flag, val in fs.kernel_config.items():
            if val == "n":
                lines.append(f"# {flag} is not set")
            else:
                lines.append(f"{flag}={val}")
        fs.write_file("/sources/linux-7.1.8/.config", "\n".join(lines) + "\n")

    def _format_kernel_menuconfig(self) -> str:
        """Formats the interactive Kernel menuconfig summary showing critical subsystems."""
        fs = self.engine.fs
        lines = [
            "[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║ LINUX KERNEL 7.1.8 - CONFIGURAÇÃO DE SUBSISTEMAS (MAKE MENUCONFIG)          ║[/bold cyan]",
            "[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            "[dim]Sem initramfs, o kernel monta '/' e '/dev' diretamente. Use built-in [y], NÃO módulo [m]![/dim]",
            "",
        ]
        for flag, desc, mandatory in self._KERNEL_SUBSYSTEMS:
            val = fs.kernel_config.get(flag, "n")
            if val == "y":
                tag = "[bold green][y] built-in[/bold green]"
            elif val == "m":
                tag = "[bold yellow][m] módulo[/bold yellow]"
            else:
                tag = "[bold red][ ] desativado[/bold red]"
            crit = "[red](CRÍTICO)[/red]" if mandatory else "[dim](Opcional)[/dim]"
            lines.append(f"  {tag:<26} [bold white]{flag:<22}[/bold white] {crit} {desc}")

        lines.extend([
            "",
            "[yellow]Comandos:[/yellow] [bold green]lfs-kernel-config <FLAG>=<y|m|n>[/bold green] para alternar | [bold green]lfs-kernel-config apply[/bold green] para aplicar padrão seguro [y].",
        ])
        return "\n".join(lines)

    def _kernel_mrproper(self) -> CommandResult:
        """Cleans the Linux 7.1.8 kernel source tree inside chroot."""
        guard = self._require_chroot("make mrproper")
        if guard:
            return guard
        fs = self.engine.fs
        fs.mkdir("/sources/linux-7.1.8", parents=True)
        if fs.exists("/sources/linux-7.1.8/.config"):
            fs.rm("/sources/linux-7.1.8/.config", force=True)
        fs.kernel_configured = False
        fs.kernel_compiled = False
        fs.configured_packages["_current"] = "linux-kernel"
        return CommandResult(
            output="make: mrproper concluído para a árvore do Linux 7.1.8 (/sources/linux-7.1.8).",
            success=True,
            state_changed=True,
        )

    def _kernel_defconfig(self) -> CommandResult:
        """Generates default .config for Linux 7.1.8 inside chroot."""
        guard = self._require_chroot("make defconfig")
        if guard:
            return guard
        fs = self.engine.fs
        fs.kernel_config = fs._default_kernel_config()
        first_time = not fs.kernel_configured
        fs.kernel_configured = True
        fs.configured_packages["_current"] = "linux-kernel"
        self._write_kernel_dot_config()
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(80)
            xp_msg = " (+80 XP)"
        return CommandResult(
            output=f"  HOSTCC  scripts/kconfig/conf.o\n# configuration written to /sources/linux-7.1.8/.config\n[bold green]✔ Configuração padrão defconfig aplicada para Linux 7.1.8.{xp_msg}[/bold green]",
            success=True,
            state_changed=True,
        )

    def _kernel_menuconfig(self) -> CommandResult:
        """Opens/saves Linux 7.1.8 menuconfig summary inside chroot."""
        guard = self._require_chroot("make menuconfig")
        if guard:
            return guard
        fs = self.engine.fs
        first_time = not fs.kernel_configured
        fs.kernel_configured = True
        fs.configured_packages["_current"] = "linux-kernel"
        self._write_kernel_dot_config()
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(100)
            xp_msg = f"\n[bold green]✔ .config salvo em /sources/linux-7.1.8/.config (+100 XP)[/bold green]"
        else:
            xp_msg = "\n[green]✔ .config atualizado em /sources/linux-7.1.8/.config[/green]"
        return CommandResult(
            output=self._format_kernel_menuconfig() + xp_msg,
            success=True,
            state_changed=True,
        )

    def _cmd_lfs_kernel_config(self, args: List[str]) -> CommandResult:
        """Interactive helper to inspect, toggle, or apply Linux 7.1.8 kernel configuration flags."""
        guard = self._require_chroot("lfs-kernel-config")
        if guard:
            return guard

        fs = self.engine.fs
        if not args or args[0].lower() in ("status", "show", "list"):
            return CommandResult(output=self._format_kernel_menuconfig(), success=True)

        arg0 = args[0].strip()
        if arg0.lower() in ("apply", "preset", "default"):
            fs.kernel_config = fs._default_kernel_config()
            first_time = not fs.kernel_configured
            fs.kernel_configured = True
            fs.configured_packages["_current"] = "linux-kernel"
            self._write_kernel_dot_config()
            xp_msg = " (+100 XP)" if first_time else ""
            if first_time:
                self.engine.char.add_xp(100)
            return CommandResult(
                output=self._format_kernel_menuconfig() + f"\n[bold green]✔ Preset seguro [y] aplicado em /sources/linux-7.1.8/.config.{xp_msg}[/bold green]",
                success=True,
                state_changed=True,
            )

        warnings: List[str] = []
        for token in args:
            if "=" not in token:
                return CommandResult(
                    output=f"lfs-kernel-config: argumento inválido '{token}'. Use FLAG=y|m|n (ex: CONFIG_EXT4_FS=y) ou 'apply'.",
                    success=False,
                )
            k_raw, v_raw = token.split("=", 1)
            flag = k_raw.strip().upper()
            if not flag.startswith("CONFIG_"):
                flag = "CONFIG_" + flag
            val = v_raw.strip().lower()
            if val not in ("y", "m", "n"):
                return CommandResult(
                    output=f"lfs-kernel-config: valor inválido '{v_raw}' para {flag}. Use 'y' (built-in), 'm' (módulo) ou 'n' (desativado).",
                    success=False,
                )
            fs.kernel_config[flag] = val
            if flag in ("CONFIG_64BIT", "CONFIG_DEVTMPFS", "CONFIG_DEVTMPFS_MOUNT", "CONFIG_EXT4_FS", "CONFIG_SATA_AHCI", "CONFIG_BINFMT_ELF") and val != "y":
                warnings.append(
                    f"[bold yellow]⚠ ALERTA KERNEL PANIC:[/bold yellow] {flag}={val} pode impedir o boot sem initramfs! Recomenda-se built-in [y]."
                )

        first_time = not fs.kernel_configured
        fs.kernel_configured = True
        fs.configured_packages["_current"] = "linux-kernel"
        self._write_kernel_dot_config()
        if first_time:
            self.engine.char.add_xp(100)

        msg = self._format_kernel_menuconfig()
        if warnings:
            msg += "\n" + "\n".join(warnings)
        return CommandResult(output=msg, success=True, state_changed=True)

    def _compile_linux_kernel(self, args: List[str]) -> CommandResult:
        """Simulates compiling Linux Kernel 7.1.8, validating critical built-in flags."""
        guard = self._require_chroot("make (Linux Kernel 7.1.8)")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.kernel_configured and not fs.exists("/sources/linux-7.1.8/.config"):
            return CommandResult(
                output="make: *** Sem regra para processar o alvo '.config'. Execute 'make menuconfig', 'make defconfig' ou 'lfs-kernel-config apply' primeiro.",
                success=False,
            )

        required_builtin = ("CONFIG_EXT4_FS", "CONFIG_DEVTMPFS", "CONFIG_BINFMT_ELF")
        broken_flags = [f for f in required_builtin if fs.kernel_config.get(f) != "y"]
        if broken_flags:
            details = ", ".join(f"{f}={fs.kernel_config.get(f, 'n')}" for f in broken_flags)
            return CommandResult(
                output=(
                    f"[bold red]✖ ERRO CRÍTICO DE CONFIGURAÇÃO DO KERNEL:[/bold red] Subsistemas vitais não estão built-in [y] ({details})!\n"
                    "[yellow]Sem initramfs, compilar ext4, devtmpfs ou BINFMT_ELF como módulo [m] ou desativado [n] causará Kernel Panic no boot.[/yellow]\n"
                    "Corrija com '[bold green]lfs-kernel-config apply[/bold green]' ou '[bold green]lfs-kernel-config <FLAG>=y[/bold green]'."
                ),
                success=False,
            )

        warn_lines = []
        for opt_flag in ("CONFIG_64BIT", "CONFIG_DEVTMPFS_MOUNT", "CONFIG_SATA_AHCI", "CONFIG_NET"):
            if fs.kernel_config.get(opt_flag) != "y":
                warn_lines.append(
                    f"[yellow]⚠ AVISO: {opt_flag}={fs.kernel_config.get(opt_flag, 'n')} não está built-in [y]; recursos podem falhar no boot.[/yellow]"
                )

        self.engine.telemetry.cpu_usage = min(99.0, self.engine.telemetry.cpu_usage + 35.0)
        self.engine.telemetry.temperature = min(88.0, self.engine.telemetry.temperature + 10.0)

        fs.mkdir("/sources/linux-7.1.8/arch/x86/boot", parents=True)
        fs.write_file("/sources/linux-7.1.8/arch/x86/boot/bzImage", "ELF/bzImage Linux 7.1.8-lfs-13.1\n")
        fs.write_file("/sources/linux-7.1.8/System.map", "ffffffff81000000 T _text\nffffffff81000100 T startup_64\n")
        self._write_kernel_dot_config()

        first_time = not fs.kernel_compiled
        fs.kernel_compiled = True
        fs.record_package_compiled("linux-kernel")
        fs.configured_packages["_current"] = "linux-kernel"

        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(250)
            xp_msg = " (+250 XP)"

        thermal_note = ""
        if self.engine.telemetry.temperature >= 80.0:
            thermal_note = f"\n[bold yellow]⚠ Telemetria Térmica:[/bold yellow] Núcleos atingiram {self.engine.telemetry.temperature:.1f}°C durante a compilação (3,5 SBU)!"

        lines = [
            "[bold cyan]=== COMPILAÇÃO DO KERNEL LINUX 7.1.8 (3,5 UPC / SBU) ===[/bold cyan]",
            "  CC      init/main.o",
            "  CC      fs/ext4/super.o",
            "  CC      drivers/base/devtmpfs.o",
            "  LD      vmlinux",
            "  OBJCOPY arch/x86/boot/bzImage",
            "Kernel: arch/x86/boot/bzImage is ready  (#1)",
            *warn_lines,
            f"[bold green]✔ Kernel Linux 7.1.8 compilado com sucesso!{xp_msg}[/bold green]{thermal_note}",
            "[dim]Próximos passos: 'make modules_install' e 'cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1'[/dim]",
        ]
        return CommandResult(output="\n".join(lines), success=True, state_changed=True)

    def _cmd_lfs_compile_kernel(self, args: List[str]) -> CommandResult:
        """Convenience wrapper to compile Linux Kernel 7.1.8 inside chroot."""
        return self._compile_linux_kernel(args)

    def _kernel_modules_install(self) -> CommandResult:
        """Installs compiled Linux 7.1.8 kernel modules into /lib/modules/7.1.8."""
        guard = self._require_chroot("make modules_install")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.kernel_compiled:
            return CommandResult(
                output="make modules_install: ERRO: Compile o Kernel 7.1.8 com 'make' ou 'lfs-compile-kernel' primeiro.",
                success=False,
            )

        first_time = not fs.exists("/lib/modules/7.1.8/modules.dep")
        fs.mkdir("/lib/modules/7.1.8/kernel/fs", parents=True)
        fs.write_file("/lib/modules/7.1.8/modules.dep", "# Linux 7.1.8 module dependency map\n")
        fs.record_package_compiled("linux-modules")

        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(100)
            xp_msg = " (+100 XP)"

        return CommandResult(
            output=f"  DEPMOD  /lib/modules/7.1.8\n[bold green]✔ Módulos do Kernel 7.1.8 instalados em /lib/modules/7.1.8.{xp_msg}[/bold green]",
            success=True,
            state_changed=True,
        )

    def _cmd_grub_install(self, args: List[str]) -> CommandResult:
        """Installs GRUB bootloader onto /dev/sda MBR inside chroot."""
        guard = self._require_chroot("grub-install")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("grub"):
            return CommandResult(
                output="grub-install: ERRO: O pacote GRUB 2.14 ainda não foi compilado. Execute 'lfs-compile-system grub' ou 'tier4'.",
                success=False,
            )

        target_dev = next((a for a in args if not a.startswith("-")), None)
        if not target_dev:
            return CommandResult(output="grub-install: erro: especifique o dispositivo de destino (ex: grub-install /dev/sda).", success=False)
        if not target_dev.startswith("/dev/sd"):
            return CommandResult(output=f"grub-install: erro: dispositivo '{target_dev}' inválido. Utilize o disco '/dev/sda'.", success=False)

        fs.mkdir("/boot/grub/i386-pc", parents=True)
        fs.write_file("/boot/grub/i386-pc/core.img", "# GRUB 2.14 core image\n")

        first_time = not fs.grub_mbr_installed
        fs.grub_mbr_installed = True
        xp_msg = ""
        if first_time:
            self.engine.char.add_xp(150)
            xp_msg = " (+150 XP)"

        output = (
            f"Instalando para plataforma i386-pc em {target_dev}...\n"
            "Instalação terminada. Nenhum erro informado.\n"
            f"[bold green]✔ GRUB 2.14 instalado no setor de boot de {target_dev}.{xp_msg}[/bold green]"
        )
        return CommandResult(output=output, success=True, state_changed=True)

    @staticmethod
    def _default_grub_cfg_content() -> str:
        return (
            "# Begin /boot/grub/grub.cfg\n"
            "set default=0\n"
            "set timeout=5\n\n"
            "insmod part_gpt\n"
            "insmod ext2\n"
            "set root=(hd0,3)\n\n"
            "menuentry \"GNU/Linux, Linux 7.1.8-lfs-13.1 (Estacao Hera)\" {\n"
            "        linux   /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda3 ro\n"
            "}\n"
        )

    def _cmd_grub_mkconfig(self, args: List[str]) -> CommandResult:
        """Generates /boot/grub/grub.cfg (with -o <path>) or prints configuration to stdout."""
        guard = self._require_chroot("grub-mkconfig")
        if guard:
            return guard

        fs = self.engine.fs
        if not fs.is_package_compiled("grub"):
            return CommandResult(
                output="grub-mkconfig: ERRO: O pacote GRUB 2.14 ainda não foi compilado. Execute 'lfs-compile-system grub' ou 'tier4'.",
                success=False,
            )

        out_path: Optional[str] = None
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-o", "--output") and i + 1 < len(args):
                out_path = args[i + 1]
                i += 2
            elif a.startswith("--output="):
                out_path = a.split("=", 1)[1]
                i += 1
            else:
                i += 1

        content = self._default_grub_cfg_content()
        if not out_path:
            return CommandResult(output=content.rstrip("\n"), success=True)

        fs.mkdir(posixpath.dirname(fs.resolve_path(out_path)), parents=True)
        was_created = fs.grub_cfg_created
        ok, err = fs.write_file(out_path, content)
        if not ok:
            return CommandResult(output=err, success=False)

        xp_msg = ""
        if not was_created and fs.grub_cfg_created:
            self.engine.char.add_xp(150)
            xp_msg = " (+150 XP)"

        return CommandResult(
            output=(
                f"Gerando arquivo de configuração do grub...\n"
                f"Imagem Linux encontrada: /boot/vmlinuz-7.1.8-lfs-13.1\n"
                f"[bold green]✔ Configuração salva em {out_path} (root=/dev/sda3).{xp_msg}[/bold green]"
            ),
            success=True,
            state_changed=True,
        )

    def _cmd_lfs_config_grub(self, args: List[str]) -> CommandResult:
        """Helper to generate valid /boot/grub/grub.cfg for Linux 7.1.8."""
        guard = self._require_chroot("lfs-config-grub")
        if guard:
            return guard
        return self._cmd_grub_mkconfig(["-o", "/boot/grub/grub.cfg"])

    # --- Sandbox / Test Navigation Mode ---

    def _cmd_lfs_jump(self, args: List[str]) -> CommandResult:
        """Lists sandbox jump targets or teleports the engine directly to an Act/Chapter."""
        from .sandbox import list_targets_table

        if not args or not args[0].strip() or args[0].strip().lower() in ("list", "--list", "-l", "help", "--help", "-h"):
            return CommandResult(output=list_targets_table(), success=True)

        target_arg = args[0].strip()
        ok, msg = self.engine.jump_to(target_arg)
        return CommandResult(
            output=msg,
            success=ok,
            state_changed=ok,
            system_event="REFRESH" if ok else None,
        )

    def _cmd_jump(self, args: List[str]) -> CommandResult:
        """Alias for lfs-jump."""
        return self._cmd_lfs_jump(args)

    def _cmd_test_act(self, args: List[str]) -> CommandResult:
        """Alias for lfs-jump."""
        return self._cmd_lfs_jump(args)

    def _cmd_goto_act(self, args: List[str]) -> CommandResult:
        """Alias for lfs-jump."""
        return self._cmd_lfs_jump(args)
