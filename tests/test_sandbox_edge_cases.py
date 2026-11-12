"""Comprehensive edge case and stress test suite for Test / Sandbox Navigation Mode."""

from __future__ import annotations
import asyncio
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.core.sandbox import resolve_target
from lfs_game.ui.app import LFSGameApp, SandboxModalScreen
from lfs_game.ui.story_view import StoryView
from lfs_game.ui.terminal_view import TerminalView


# ============================================================================
# 1. Backward Jumping and Zero-Leak Isolation Stress Tests
# ============================================================================

def test_backward_jump_ready_to_act1_zero_leaks():
    """Jump forward to 'ready' (full chroot, 150+ pkgs, lvl 18, 'Forjador do Kernel'),

    then jump backward to '1'. Verify zero leaked files, zero leaked packages,
    clean character progression, clean anomaly manager, and proper quest state.
    """
    engine = GameEngine()

    # Step 1: Jump forward to end state
    ok, msg = engine.jump_to("ready")
    assert ok is True
    assert engine.fs.in_chroot is True
    assert engine.char.title == "Forjador do Kernel"
    assert "Forjador do Kernel" in engine.char.unlocked_titles
    assert engine.char.level >= 18
    assert len(engine.fs.compiled_packages) >= 80
    assert engine.fs.exists("/boot/vmlinuz-7.1.8-lfs-13.1")
    assert engine.fs.exists("/etc/fstab")
    assert engine.fs.fstab_configured is True
    assert engine.fs.kernel_installed is True

    # Step 2: Jump backward to Act 1
    ok, msg = engine.jump_to("1")
    assert ok is True
    assert "Teleporte Sandbox concluído" in msg

    # Verification: Zero chroot or host leaks
    assert engine.fs.in_chroot is False
    assert engine.fs.current_user == "root"
    assert engine.fs.pwd() == "/root"

    # Partitions and mounts in Act 1: not mounted yet!
    assert "/mnt/lfs" not in engine.fs.mounts
    assert not engine.fs.exists("/mnt/lfs")
    assert not engine.fs.exists("/boot/vmlinuz-7.1.8-lfs-13.1")
    assert not engine.fs.exists("/boot/grub/grub.cfg")
    assert not engine.fs.exists("/etc/fstab")
    assert not engine.fs.exists("/etc/shadow")

    # Clean packages & toolchain
    assert len(engine.fs.compiled_packages) == 0
    assert len(engine.fs.installed_tools) == 0

    # Clean character
    assert engine.char.level == 1
    assert engine.char.xp == 50  # Only prologue completed (Q0_PROLOGUE gives 50 XP)
    assert engine.char.title == "Aprendiz de Sucata"
    assert "Forjador do Kernel" not in engine.char.unlocked_titles
    assert "Arquiteto do Sistema" not in engine.char.unlocked_titles
    assert "Mestre da Toolchain Cruzada" not in engine.char.unlocked_titles

    # Clean story engine
    assert engine.story_engine.current_quest.id == "Q1_PARTITION_AND_MOUNT"
    assert engine.story_engine.current_quest.completed is False
    assert engine.story_engine.flags.get("act1_celebrated") is not True

    # Clean anomaly manager and parser dir_stack
    assert engine.anomaly_manager.active_anomaly is None
    assert engine.anomaly_manager.resolved_history == []
    assert len(engine.parser.dir_stack) == 0


def test_backward_jump_ready_to_prologue_absolute_reset():
    """Jump forward to 'ready', then jump backward to 'prologue'.

    Verify absolute beginning state: level 1, 0 XP, Q0_PROLOGUE, and pristine filesystem.
    """
    engine = GameEngine()
    engine.jump_to("ready")

    # Backward jump to prologue
    ok, msg = engine.jump_to("prologue")
    assert ok is True

    assert engine.fs.in_chroot is False
    assert engine.fs.current_user == "root"
    assert engine.fs.pwd() == "/root"
    assert not engine.fs.exists("/mnt/lfs")
    assert not engine.fs.exists("/boot/vmlinuz-7.1.8-lfs-13.1")
    assert engine.fs.ls("/boot") == (True, "")

    assert len(engine.fs.compiled_packages) == 0
    assert engine.char.level == 1
    assert engine.char.xp == 0
    assert engine.char.title == "Aprendiz de Sucata"
    assert engine.char.unlocked_titles == ["Aprendiz de Sucata"]

    assert engine.story_engine.current_quest.id == "Q0_PROLOGUE"
    assert engine.story_engine.current_quest.completed is False
    assert engine.story_engine.flags.get("prologue_done") is not True

    assert engine.anomaly_manager.active_anomaly is None
    assert engine.anomaly_manager.resolved_history == []
    assert len(engine.parser.dir_stack) == 0


def test_backward_jump_act5_to_act2_lfs_environment():
    """Jump forward to '5' (Act 5, chroot), then backward to '2' (Act 2, sterile lfs user).

    Verify lfs environment, no chroot, no Act 3/4/5 packages, and clean level/titles.
    """
    engine = GameEngine()
    engine.jump_to("5")
    assert engine.fs.in_chroot is True
    assert engine.char.title == "Arquiteto do Sistema"

    ok, msg = engine.jump_to("2")
    assert ok is True

    assert engine.fs.in_chroot is False
    assert engine.fs.current_user == "lfs"
    assert engine.fs.pwd() == "/home/lfs"
    assert engine.fs.env.get("LFS") == "/mnt/lfs"
    assert engine.fs.env.get("LFS_TGT") == "x86_64-lfs-linux-gnu"

    # In Act 2, packages are ready to compile; 0 compiled so far
    assert len(engine.fs.compiled_packages) == 0

    # Titles up to Act 1 completed, but NOT Act 3, 4, or 5
    assert engine.char.level == 5
    assert engine.char.xp == 200
    assert engine.char.title == "Compilador do Vácuo"
    assert "Arquiteto do Sistema" not in engine.char.unlocked_titles
    assert "Forjador do Kernel" not in engine.char.unlocked_titles
    assert "Pioneiro do Chroot" not in engine.char.unlocked_titles

    assert engine.story_engine.current_quest.id == "Q5_CROSS_TOOLCHAIN_CORE"
    assert engine.story_engine.current_quest.completed is False


def test_user_mutations_and_anomalies_do_not_leak_across_backward_jump():
    """Create manual user files, environment variables, pushd directories, and trigger

    anomalies in ready state, then jump backward to '1'. Verify zero leaks.
    """
    engine = GameEngine()
    engine.jump_to("ready")

    # Dirty the state
    engine.run_command("touch /tmp/infiltrator.sh")
    engine.run_command("export TROJAN_PAYLOAD=active")
    engine.run_command("pushd /boot")
    engine.anomaly_manager.trigger_anomaly("CPU_OVERHEAT")
    assert engine.anomaly_manager.active_anomaly is not None
    assert len(engine.parser.dir_stack) > 0

    # Jump backward
    ok, _ = engine.jump_to("1")
    assert ok is True

    assert not engine.fs.exists("/tmp/infiltrator.sh")
    assert "TROJAN_PAYLOAD" not in engine.fs.env
    assert len(engine.parser.dir_stack) == 0
    assert engine.anomaly_manager.active_anomaly is None
    assert engine.anomaly_manager.resolved_history == []


# ============================================================================
# 2. Chaotic Repeated Jumping Sequences
# ============================================================================

def test_chaotic_jumping_sequence_stability():
    """Repeated jumping across targets in chaotic order:

    ready -> 2 -> 4 -> ch3 -> 5 -> prologue -> ch10.
    Verify exact target state at each step and verify check_progress stays stable.
    """
    engine = GameEngine()
    sequence = [
        ("ready", "Q23_GRUB_BOOTLOADER", True, "root", True),
        ("2", "Q5_CROSS_TOOLCHAIN_CORE", False, "lfs", False),
        ("4", "Q15_SYSTEM_TIER1_GLIBC", False, "root", True),
        ("ch3", "Q2_PACKAGES_AND_PATCHES", False, "root", False),
        ("5", "Q20_SYSTEM_CONFIG_NETWORK", False, "root", True),
        ("prologue", "Q0_PROLOGUE", False, "root", False),
        ("ch10", "Q21_FSTAB_AND_KERNEL_CONFIG", False, "root", True),
    ]

    for target_key, expected_quest, expected_completed, expected_user, expected_chroot in sequence:
        ok, msg = engine.jump_to(target_key)
        assert ok is True, f"Jump to {target_key} failed: {msg}"

        assert engine.fs.current_user == expected_user, f"User mismatch on {target_key}"
        assert engine.fs.in_chroot is expected_chroot, f"Chroot mismatch on {target_key}"
        assert engine.story_engine.current_quest.id == expected_quest, f"Quest mismatch on {target_key}"
        assert engine.story_engine.current_quest.completed is expected_completed

        # check_progress must NOT prematurely advance quests
        broadcasts = engine.story_engine.check_progress(engine.fs, engine.char)
        assert broadcasts == [], f"check_progress unexpectedly fired broadcasts on {target_key}: {broadcasts}"
        assert engine.story_engine.current_quest.id == expected_quest


# ============================================================================
# 3. Chained Commands Involving lfs-jump
# ============================================================================

def test_chained_jump_success_with_double_ampersand():
    """Verify 'lfs-jump ch10 && make menuconfig' provisions ch10 and configures kernel immediately."""
    engine = GameEngine()
    res = engine.run_command("lfs-jump ch10 && make menuconfig")

    assert res.success is True
    assert "Teleporte Sandbox concluído" in res.output
    assert "LINUX KERNEL 7.1.8 - CONFIGURAÇÃO DE SUBSISTEMAS" in res.output
    assert engine.fs.in_chroot is True
    assert engine.fs.kernel_configured is True
    assert engine.fs.exists("/sources/linux-7.1.8/.config")


def test_chained_jump_semicolon_preserves_subsequent_execution():
    """Verify 'lfs-jump 4; pwd' executes both commands and outputs '/' as cwd in chroot."""
    engine = GameEngine()
    res = engine.run_command("lfs-jump 4; pwd")

    assert res.success is True
    assert "Teleporte Sandbox concluído" in res.output
    assert "/" in res.output
    assert engine.fs.in_chroot is True
    assert engine.fs.pwd() == "/"
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"


def test_chained_jump_failure_short_circuits_and_preserves_safety():
    """Verify 'lfs-jump nonexistent && make menuconfig' halts on error and does NOT configure kernel."""
    engine = GameEngine()
    res = engine.run_command("lfs-jump nonexistent && make menuconfig")

    assert res.success is False
    assert "alvo 'nonexistent' inválido" in res.output
    assert engine.fs.kernel_configured is False
    assert not engine.fs.exists("/sources/linux-7.1.8/.config")


def test_chained_jump_multiple_sequential_jumps_in_single_line():
    """Verify 'lfs-jump prologue; lfs-jump 2; lfs-jump 4' settles precisely on Act 4."""
    engine = GameEngine()
    res = engine.run_command("lfs-jump prologue; lfs-jump 2; lfs-jump 4")

    assert res.success is True
    assert engine.fs.in_chroot is True
    assert engine.fs.current_user == "root"
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"


# ============================================================================
# 4. TUI Modal Tests (F4, #jump-ch10, Cancel, Escape)
# ============================================================================

def test_tui_modal_jump_using_jump_id_and_views_update():
    """Under Textual run_test():

    - Open F4 modal
    - Query target button via '#jump-ch10' (or '#sandbox-btn-ch10')
    - Press the button
    - Verify modal dismisses cleanly
    - Verify StoryView reflects the new quest
    - Verify TerminalView prompt reflects '(lfs chroot) root:/# '
    """
    async def _run():
        engine = GameEngine()
        app = LFSGameApp(engine=engine)
        async with app.run_test() as pilot:
            # 1. Open F4 modal
            await pilot.press("f4")
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            # 2. Query target button via '#jump-ch10'
            btn_ch10 = app.screen.query_one("#jump-ch10")
            assert btn_ch10 is not None

            # 3. Press target button
            btn_ch10.press()
            await pilot.pause()

            # 4. Verify modal dismissed cleanly
            assert not isinstance(app.screen, SandboxModalScreen)
            assert app.engine.test_mode is True
            assert app.engine.fs.in_chroot is True
            assert app.engine.story_engine.current_quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG"

            # 5. Verify StoryView reflects new Act & transmission
            story_render = app.query_one("#story-view", StoryView).render()
            assert story_render is not None
            assert app.engine.story_engine.current_dialogue is not None
            assert "ATO 5" in app.engine.story_engine.current_dialogue.text

            # 6. Verify TerminalView prompt reflects chroot
            prompt_widget = app.query_one("#terminal-prompt-label")
            rendered_prompt = str(prompt_widget.render())
            assert "(lfs chroot)" in rendered_prompt
            assert "root" in rendered_prompt
            assert "#" in rendered_prompt

    asyncio.run(_run())


def test_tui_modal_cancel_button_and_escape_key():
    """Verify clicking Cancel button and pressing Escape dismiss modal with zero side-effects."""
    async def _run():
        engine = GameEngine()
        app = LFSGameApp(engine=engine)
        async with app.run_test() as pilot:
            # Test 1: Open F4 and press Escape
            await pilot.press("f4")
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, SandboxModalScreen)
            assert app.engine.story_engine.current_quest.id == "Q0_PROLOGUE"
            assert app.engine.fs.in_chroot is False

            # Test 2: Re-open F4 and click Cancel button
            await pilot.press("f4")
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            btn_cancel = app.screen.query_one("#sandbox-btn-cancel")
            btn_cancel.press()
            await pilot.pause()
            assert not isinstance(app.screen, SandboxModalScreen)
            assert app.engine.story_engine.current_quest.id == "Q0_PROLOGUE"
            assert app.engine.fs.in_chroot is False

            # Test 3: Alias #jump-cancel
            await pilot.press("f4")
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            btn_jump_cancel = app.screen.query_one("#jump-cancel")
            btn_jump_cancel.press()
            await pilot.pause()
            assert not isinstance(app.screen, SandboxModalScreen)

    asyncio.run(_run())


# ============================================================================
# 5. Case Sensitivity, Whitespace, and Invalid Targets
# ============================================================================

def test_jump_case_insensitivity_and_whitespace():
    """Verify commands and arguments are case-insensitive and tolerate diverse whitespace."""
    engine = GameEngine()

    # Uppercase command and argument
    res1 = engine.run_command("LFS-JUMP KERNEL")
    assert res1.success is True
    assert engine.story_engine.current_quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG"

    # Mixed case command and alias
    res2 = engine.run_command("JuMp ChRoOt")
    assert res2.success is True
    assert engine.fs.in_chroot is True
    assert engine.story_engine.current_quest.id == "Q12_CHROOT_BASE_DIRECTORIES"

    # Excessive whitespace
    res3 = engine.run_command("   lfs-jump     prologue    ")
    assert res3.success is True
    assert engine.story_engine.current_quest.id == "Q0_PROLOGUE"

    # Whitespace only after lfs-jump shows targets table
    res_ws = engine.run_command("lfs-jump   ")
    assert res_ws.success is True
    assert "MODO SANDBOX / TESTE" in res_ws.output


def test_jump_invalid_targets_fail_gracefully_and_preserve_state():
    """Verify invalid targets produce informative errors without corrupting active state."""
    engine = GameEngine()
    engine.jump_to("4")
    original_quest_id = engine.story_engine.current_quest.id

    for bad_target in ("nonexistent", "9999", "kernel@lfs", "act99", "--invalid-flag"):
        res = engine.run_command(f"lfs-jump {bad_target}")
        assert res.success is False
        assert f"alvo '{bad_target}' inválido" in res.output
        # State must remain intact at Act 4
        assert engine.story_engine.current_quest.id == original_quest_id
        assert engine.fs.in_chroot is True
