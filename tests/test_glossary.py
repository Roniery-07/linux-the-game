"""Tests for Didactic Glossary (Glossário Didático do LFS), explain, and didactic mode."""

import asyncio
import pytest
from lfs_game.core.engine import GameEngine
from lfs_game.data.glossary import (
    GlossaryEntry,
    GlossaryManager,
    glossary_manager,
    CATEGORIES,
)
from lfs_game.ui.app import LFSGameApp
from textual.widgets import RichLog


# =============================================================================
# 1. Glossary Data Model & Manager Tests
# =============================================================================

def test_glossary_categories_and_population():
    """Verify that all standard LFS categories exist and contain entries."""
    by_cat = glossary_manager.list_by_category()
    for cat in CATEGORIES:
        assert cat in by_cat
        assert len(by_cat[cat]) > 0


def test_glossary_all_required_terms_exist():
    """Verify all terms required by the didactic specification exist."""
    required_terms = [
        # Basic & Host
        "export", "env", "echo", "mkdir", "cd", "ls", "cat", "rm", "touch",
        "chown", "chmod", "su", "useradd", "groupadd", "whoami",
        # Disks & Mounts
        "fdisk", "cfdisk", "mkfs.ext4", "mkswap", "swapon", "swapoff", "mount", "umount", "df",
        # Packages & Verification
        "tar", "md5sum", "patch",
        # LFS Variables
        "$LFS", "$LFS_TGT", "PATH", "LC_ALL=POSIX",
        # Toolchain & Compilers
        "./configure", "--prefix", "--host", "--target", "--with-sysroot",
        "--with-headers", "--disable-nls", "make", "make install", "DESTDIR",
        "$LFS_TGT-gcc", "readelf", "ld-linux", "limits.h",
        # Future / Virtual Filesystem concepts
        "chroot", "/dev", "/proc", "/sys",
    ]
    for term in required_terms:
        entry = glossary_manager.get(term)
        assert entry is not None, f"Required term '{term}' not found in glossary!"
        assert entry.name
        assert entry.what_it_does
        assert entry.why_in_lfs
        assert entry.danger_if_missed


def test_glossary_alias_resolution():
    """Verify that common aliases correctly resolve to the canonical entry."""
    test_cases = [
        ("sysroot", "--with-sysroot"),
        ("with-sysroot", "--with-sysroot"),
        ("destdir", "DESTDIR"),
        ("lfs_tgt", "$LFS_TGT"),
        ("LFS_TGT", "$LFS_TGT"),
        ("tgt", "$LFS_TGT"),
        ("lfs", "$LFS"),
        ("LFS", "$LFS"),
        ("/mnt/lfs", "$LFS"),
        ("cross-gcc", "$LFS_TGT-gcc"),
        ("gcc", "$LFS_TGT-gcc"),
        ("configure", "./configure"),
        ("../configure", "./configure"),
        ("make-install", "make install"),
        ("posix", "LC_ALL=POSIX"),
        ("LC_ALL", "LC_ALL=POSIX"),
        ("ext4", "mkfs.ext4"),
        ("swap", "mkswap"),
        ("dev", "/dev"),
        ("proc", "/proc"),
        ("sys", "/sys"),
        ("exportar", "export"),
        ("su - lfs", "su"),
    ]
    for alias_query, expected_canonical in test_cases:
        entry = glossary_manager.get(alias_query)
        assert entry is not None, f"Alias '{alias_query}' failed to resolve!"
        assert entry.term == expected_canonical, (
            f"Alias '{alias_query}' resolved to '{entry.term}' instead of '{expected_canonical}'"
        )


def test_glossary_search():
    """Verify search finds terms by content, keywords, and ranked relevance."""
    # Search for compiler
    results = glossary_manager.search("compilador")
    assert len(results) > 0
    terms = [e.term for e in results]
    assert "$LFS_TGT-gcc" in terms or "./configure" in terms

    # Search for isolamento
    results_iso = glossary_manager.search("isolamento")
    assert len(results_iso) > 0

    # Search for empty
    assert glossary_manager.search("") == []


def test_glossary_formatting():
    """Verify that format_entry and format_index output Rich-styled texts."""
    entry = glossary_manager.get("export")
    assert entry is not None
    formatted_card = glossary_manager.format_entry(entry)
    assert "GLOSSÁRIO DIDÁTICO LFS" in formatted_card
    assert "📖 O QUE FAZ:" in formatted_card
    assert "🎯 POR QUE NO LFS?" in formatted_card
    assert "⚠️ PERIGO SE ESQUECER" in formatted_card
    assert "🔗 Termos Relacionados:" in formatted_card

    index_text = glossary_manager.format_index()
    assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in index_text
    assert "📂 Básico & Hospedeiro" in index_text
    assert "📂 Toolchain & Compiladores" in index_text


# =============================================================================
# 2. ShellParser Command Tests: glossario & explain
# =============================================================================

def test_parser_cmd_glossario():
    """Verify 'glossario' and 'glossary' command variations."""
    engine = GameEngine()

    # Full index
    res = engine.parser.execute("glossario")
    assert res.success
    assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in res.output

    # English alias
    res_en = engine.parser.execute("glossary")
    assert res_en.success
    assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in res_en.output

    # Category filter
    res_cat = engine.parser.execute("glossario Discos")
    assert res_cat.success
    assert "📂 Discos & Montagens" in res_cat.output

    # Direct term via glossario
    res_term = engine.parser.execute("glossario mount")
    assert res_term.success
    assert "GLOSSÁRIO DIDÁTICO LFS" in res_term.output
    assert "mount" in res_term.output.lower()

    # Search match via glossario
    res_search = engine.parser.execute("glossario particao")
    assert res_search.success

    # Completely unknown
    res_unknown = engine.parser.execute("glossario xkcd_non_existent")
    assert not res_unknown.success
    assert "Nenhum termo ou categoria" in res_unknown.output


def test_parser_cmd_explain():
    """Verify 'explain', 'explicar', and 'oquee' command variations."""
    engine = GameEngine()

    # No arguments
    res_noarg = engine.parser.execute("explain")
    assert res_noarg.success
    assert "Uso:" in res_noarg.output

    # Canonical term
    res_mount = engine.parser.execute("explain mount")
    assert res_mount.success
    assert "GLOSSÁRIO DIDÁTICO LFS" in res_mount.output
    assert "PONTO_DE_MONTAGEM" in res_mount.output
    assert "📖 O QUE FAZ:" in res_mount.output

    # Aliases: explicar and oquee
    res_explicar = engine.parser.execute("explicar sysroot")
    assert res_explicar.success
    assert "--with-sysroot" in res_explicar.output

    res_oquee = engine.parser.execute("oquee chroot")
    assert res_oquee.success
    assert "chroot" in res_oquee.output

    # Variable lookup: $LFS
    res_lfs = engine.parser.execute("explain $LFS")
    assert res_lfs.success
    assert "$LFS" in res_lfs.output

    # Multi-token term: make install
    res_make_inst = engine.parser.execute("explain make install")
    assert res_make_inst.success
    assert "make install" in res_make_inst.output

    # Suggestions for unknown terms
    res_approx = engine.parser.execute("explain compil")
    assert res_approx.success
    assert "Você quis dizer" in res_approx.output or "GLOSSÁRIO DIDÁTICO LFS" in res_approx.output

    # Complete miss
    res_miss = engine.parser.execute("explain zzznonexistent")
    assert not res_miss.success
    assert "não encontrado no glossário" in res_miss.output


# =============================================================================
# 3. Didactic Mode Toggle & Insight Generation Tests
# =============================================================================

def test_parser_cmd_didactic_toggle():
    """Verify turning didactic mode on and off."""
    engine = GameEngine()
    parser = engine.parser

    assert parser.didactic_enabled is True

    # Status query
    res_status = parser.execute("didactic")
    assert res_status.success
    assert "ATIVADO" in res_status.output

    # Turn off
    res_off = parser.execute("didactic off")
    assert res_off.success
    assert "DESATIVADO" in res_off.output
    assert parser.didactic_enabled is False

    # Turn on using Portuguese alias
    res_on = parser.execute("didatico on")
    assert res_on.success
    assert "ATIVADO" in res_on.output
    assert parser.didactic_enabled is True

    # Invalid option
    res_err = parser.execute("didactic invalid_option")
    assert not res_err.success
    assert "Uso: didactic [on|off]" in res_err.output


def test_didactic_insights_on_architectural_milestones():
    """Verify that didactic insights appear on key commands when mode is ON."""
    engine = GameEngine()

    # 1. export LFS
    res = engine.parser.execute("export LFS=/mnt/lfs")
    assert res.success
    assert "💡 [bold cyan]Insight LFS ($LFS):[/bold cyan]" in res.output

    # 2. export LFS_TGT
    res_tgt = engine.parser.execute("export LFS_TGT=x86_64-lfs-linux-gnu")
    assert res_tgt.success
    assert "💡 [bold cyan]Insight LFS ($LFS_TGT):[/bold cyan]" in res_tgt.output

    # 3. Create user lfs and test useradd insight + su insight
    engine.parser.execute("groupadd lfs")
    res_useradd = engine.parser.execute("useradd -s /bin/bash -k /dev/null -m lfs")
    assert res_useradd.success
    assert "💡 [bold cyan]Insight LFS (useradd lfs):[/bold cyan]" in res_useradd.output

    res_su = engine.parser.execute("su - lfs")
    assert res_su.success
    assert "💡 [bold cyan]Insight LFS (su - lfs):[/bold cyan]" in res_su.output

    # Return to root
    res_exit = engine.parser.execute("exit")
    assert res_exit.success

    # 4. readelf sanity check
    # Create mock elf
    engine.fs.write_file(
        "/root/dummy",
        "\x7fELF" + "A" * 50 + "/tools/lib64/ld-linux-x86-64.so.2"
    )
    res_readelf = engine.parser.execute("readelf -l /root/dummy")
    assert res_readelf.success
    assert "💡 [bold cyan]Insight LFS (readelf):[/bold cyan]" in res_readelf.output

    # 5. When didactic mode is OFF, insights must NOT be appended
    engine.parser.execute("didactic off")
    res_silent = engine.parser.execute("export LFS=/mnt/lfs")
    assert res_silent.success
    assert "💡 [bold cyan]Insight LFS" not in res_silent.output


def test_save_load_preserves_didactic_state():
    """Verify that saving and loading preserves the didactic_enabled toggle."""
    engine = GameEngine()
    engine.parser.didactic_enabled = False

    data = engine.to_dict()
    assert data["didactic_enabled"] is False

    new_engine = GameEngine()
    new_engine.from_dict(data)
    assert new_engine.parser.didactic_enabled is False


# =============================================================================
# 4. UI F3 Hotkey Integration Test
# =============================================================================

def test_ui_f3_glossary_action():
    """Verify that action_show_glossary executes and outputs the glossary index."""
    async def _run():
        engine = GameEngine()
        app = LFSGameApp(engine=engine)
        async with app.run_test() as pilot:
            log_widget = app.query_one("#terminal-log", RichLog)
            initial_lines = len(log_widget.lines)

            # Trigger glossary action directly
            app.action_show_glossary()
            await pilot.pause()

            # Ensure new lines were written containing the glossary title
            assert len(log_widget.lines) > initial_lines
            full_text = "\n".join(str(line.text) for line in log_widget.lines)
            assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in full_text

    asyncio.run(_run())


# =============================================================================
# 5. Stress Testing & Edge Cases
# =============================================================================

def test_glossary_edge_cases_regex_characters():
    """Verify queries containing regex meta-characters do not crash the engine."""
    engine = GameEngine()

    # Query with '[': should match entries containing brackets safely without regex syntax error
    res_bracket = engine.parser.execute("explain [")
    assert res_bracket.success
    assert "GLOSSÁRIO DIDÁTICO LFS" in res_bracket.output or "LC_ALL" in res_bracket.output

    # Query with '.*': literal search, fails gracefully without crash
    res_dotstar = engine.parser.execute("explain .*")
    assert not res_dotstar.success
    assert "Termo '.*' não encontrado" in res_dotstar.output

    # Query with '$': safely searches terms containing '$' (like $LFS, $LFS_TGT)
    res_dollar = engine.parser.execute("explain $")
    assert res_dollar.success
    assert "$LFS" in res_dollar.output

    # Query with other regex symbols: '?', '^', '+', '\\'
    for sym in ["?", "^", "+", "\\"]:
        res_sym = engine.parser.execute(f"explain {sym}")
        # Must return a valid CommandResult without throwing an uncaught exception
        assert isinstance(res_sym.output, str)


def test_glossary_edge_cases_unicode_accents_and_casing():
    """Verify uppercase commands and accent-insensitive category matching."""
    engine = GameEngine()

    # Uppercase command: EXPLAIN SYSROOT
    res_upper_explain = engine.parser.execute("EXPLAIN SYSROOT")
    assert res_upper_explain.success
    assert "--with-sysroot" in res_upper_explain.output.lower() or "sysroot" in res_upper_explain.output.lower()

    # Uppercase command: GLOSSARIO
    res_upper_glossario = engine.parser.execute("GLOSSARIO")
    assert res_upper_glossario.success
    assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in res_upper_glossario.output

    # Uppercase command: DIDACTIC OFF / ON
    res_upper_didactic = engine.parser.execute("DIDACTIC OFF")
    assert res_upper_didactic.success
    assert engine.parser.didactic_enabled is False
    res_re_on = engine.parser.execute("DIDACTIC ON")
    assert res_re_on.success
    assert engine.parser.didactic_enabled is True

    # Category query with accent: 'glossario variáveis'
    res_cat_accent = engine.parser.execute("glossario variáveis")
    assert res_cat_accent.success
    assert "📂 Variáveis LFS" in res_cat_accent.output

    # Category query without accent: 'glossario variaveis'
    res_cat_no_accent = engine.parser.execute("glossario variaveis")
    assert res_cat_no_accent.success
    assert "📂 Variáveis LFS" in res_cat_no_accent.output

    # Category query with accent: 'glossario básico' vs 'glossario basico'
    res_cat_basico1 = engine.parser.execute("glossario básico")
    assert res_cat_basico1.success
    assert "📂 Básico & Hospedeiro" in res_cat_basico1.output

    res_cat_basico2 = engine.parser.execute("glossario basico")
    assert res_cat_basico2.success
    assert "📂 Básico & Hospedeiro" in res_cat_basico2.output


def test_didactic_edge_cases_chained_commands():
    """Verify chained commands (&& and ;) correctly retain didactic insights."""
    engine = GameEngine()

    # Chained with '&&': first command triggers insight, second executes and combines output
    res_and = engine.parser.execute("export LFS=/mnt/lfs && mkdir -pv $LFS")
    assert res_and.success
    assert "💡 [bold cyan]Insight LFS ($LFS):[/bold cyan]" in res_and.output
    assert "mkdir: criado o diretório '/mnt/lfs'" in res_and.output
    assert engine.fs.env.get("LFS") == "/mnt/lfs"
    assert engine.fs.is_dir("/mnt/lfs")

    # Chained with ';': both execute and insight is preserved
    res_semi = engine.parser.execute("export LFS_TGT=x86_64-lfs-linux-gnu ; echo $LFS_TGT")
    assert res_semi.success
    assert "💡 [bold cyan]Insight LFS ($LFS_TGT):[/bold cyan]" in res_semi.output
    assert "x86_64-lfs-linux-gnu" in res_semi.output


def test_didactic_edge_cases_redirection_formatting():
    """Verify didactic insights are displayed in terminal while clean stdout goes to file."""
    engine = GameEngine()

    # Redirection of command with milestone insight
    res = engine.parser.execute("export LFS=/mnt/lfs > /tmp/export.log")
    assert res.success
    # The insight remains visible in res.output (for terminal presentation)
    assert "💡 [bold cyan]Insight LFS ($LFS):[/bold cyan]" in res.output
    # The target file contains only the command's stdout
    ok, content = engine.fs.read_file("/tmp/export.log")
    assert ok
    # Export has empty stdout, so file contains newline
    assert content.strip() == ""

    # Redirection of explain command writes formatted content to file
    res_explain = engine.parser.execute("explain mount > /tmp/mount_help.txt")
    assert res_explain.success
    assert res_explain.output == ""  # Redirected completely
    ok_m, content_m = engine.fs.read_file("/tmp/mount_help.txt")
    assert ok_m
    assert "GLOSSÁRIO DIDÁTICO LFS" in content_m
    assert "mount" in content_m


def test_glossary_empty_and_whitespace_queries():
    """Verify empty or pure whitespace arguments gracefully show usage guides."""
    engine = GameEngine()

    # Empty string argument
    res_empty = engine.parser.execute('explain ""')
    assert res_empty.success
    assert "Uso:" in res_empty.output

    # Whitespace only argument
    res_spaces = engine.parser.execute('explain "   "')
    assert res_spaces.success
    assert "Uso:" in res_spaces.output

    # Glossario with empty quotes shows index
    res_gloss_empty = engine.parser.execute('glossario ""')
    assert res_gloss_empty.success
    assert "GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH" in res_gloss_empty.output


def test_glossary_entries_educational_quality_audit():
    """Audit all glossary entries to ensure high pedagogical rigor and complete metadata."""
    from lfs_game.data.glossary import GLOSSARY_ENTRIES

    assert len(GLOSSARY_ENTRIES) >= 50

    for entry in GLOSSARY_ENTRIES:
        # 1. Term & Name
        assert entry.term.strip()
        assert entry.name.strip()
        assert entry.category in CATEGORIES

        # 2. Syntax
        assert entry.syntax.strip()

        # 3. Didactic fields: Must be substantial explanations (> 30 chars)
        assert len(entry.what_it_does.strip()) >= 30, f"Entry '{entry.term}' what_it_does is too brief!"
        assert len(entry.why_in_lfs.strip()) >= 30, f"Entry '{entry.term}' why_in_lfs is too brief!"
        assert len(entry.danger_if_missed.strip()) >= 30, f"Entry '{entry.term}' danger_if_missed is too brief!"

