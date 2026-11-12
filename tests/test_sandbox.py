"""Comprehensive test suite for Test / Sandbox Navigation Mode."""

from __future__ import annotations
import asyncio
import subprocess
import sys
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.core.sandbox import SANDBOX_TARGETS, list_targets_table, resolve_target
from lfs_game.ui.app import LFSGameApp, SandboxModalScreen


EXPECTED_TARGET_QUESTS = {
    "prologue": ("Q0_PROLOGUE", False, "root", False),
    "1": ("Q1_PARTITION_AND_MOUNT", False, "root", False),
    "ch3": ("Q2_PACKAGES_AND_PATCHES", False, "root", False),
    "ch4": ("Q3_FINAL_PREPARATIONS", False, "root", False),
    "2": ("Q5_CROSS_TOOLCHAIN_CORE", False, "lfs", False),
    "ch6": ("Q8_TEMP_TOOLS", False, "lfs", False),
    "3": ("Q10_CHROOT_PREPARATION", False, "root", False),
    "chroot": ("Q12_CHROOT_BASE_DIRECTORIES", False, "root", True),
    "4": ("Q15_SYSTEM_TIER1_GLIBC", False, "root", True),
    "5": ("Q20_SYSTEM_CONFIG_NETWORK", False, "root", True),
    "ch10": ("Q21_FSTAB_AND_KERNEL_CONFIG", False, "root", True),
    "ready": ("Q23_GRUB_BOOTLOADER", True, "root", True),
}


@pytest.mark.parametrize("target_key,expected", EXPECTED_TARGET_QUESTS.items())
def test_jump_every_target_and_check_progress_stability(target_key, expected):
    """Jumping to every target provisions exact quest, user, chroot, and stays stable under check_progress."""
    quest_id, quest_completed, expected_user, expected_chroot = expected
    engine = GameEngine()

    ok, msg = engine.jump_to(target_key)
    assert ok is True
    assert msg
    assert engine.test_mode is True
    assert engine.fs.current_user == expected_user
    assert engine.fs.in_chroot is expected_chroot
    assert engine.story_engine.current_quest.id == quest_id
    assert engine.story_engine.current_quest.completed is quest_completed

    # check_progress must NOT prematurely skip or advance the target quest
    broadcasts = engine.story_engine.check_progress(engine.fs, engine.char)
    assert broadcasts == []
    assert engine.story_engine.current_quest.id == quest_id
    assert engine.story_engine.current_quest.completed is quest_completed


def test_sandbox_aliases_and_table():
    """Verify all documented aliases resolve to the expected canonical target and table renders."""
    alias_pairs = [
        ("0", "prologue"),
        ("ch1", "prologue"),
        ("ato1", "1"),
        ("ch2", "1"),
        ("ato2", "2"),
        ("ch5", "2"),
        ("ato3", "3"),
        ("ch7", "3"),
        ("ato4", "4"),
        ("ch8", "4"),
        ("ato5", "5"),
        ("ch9", "5"),
        ("kernel", "ch10"),
        ("5.2", "ch10"),
        ("5.end", "ready"),
        ("boot-ready", "ready"),
    ]
    for alias, canonical in alias_pairs:
        resolved = resolve_target(alias)
        assert resolved is not None
        assert resolved.key == canonical

    assert len(SANDBOX_TARGETS) == 12
    table = list_targets_table()
    for t in SANDBOX_TARGETS:
        assert t.key in table


def test_continuity_act2_compile_binutils_pass1():
    """Jump to '2' -> can compile binutils-pass1 immediately via configure/make and lfs-compile-tools."""
    engine = GameEngine()
    ok, _ = engine.jump_to("2")
    assert ok

    assert engine.fs.current_user == "lfs"
    assert engine.fs.env.get("LFS") == "/mnt/lfs"
    assert engine.fs.env.get("LFS_TGT") == "x86_64-lfs-linux-gnu"

    res_cd = engine.run_command("cd $LFS/sources && mkdir -v binutils-build && cd binutils-build")
    assert res_cd.success
    res_conf = engine.run_command("../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT --disable-nls")
    assert res_conf.success
    res_make = engine.run_command("make")
    assert res_make.success
    res_inst = engine.run_command("make install")
    assert res_inst.success
    assert engine.fs.is_package_compiled("binutils-pass1")


def test_continuity_act3_chown_and_mount_virtual_fs():
    """Jump to '3' -> can chown --from lfs -R root:root and mount virtual FS immediately."""
    engine = GameEngine()
    ok, _ = engine.jump_to("3")
    assert ok
    assert engine.fs.current_user == "root"

    res_chown = engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    assert res_chown.success

    res_mkdir = engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    assert res_mkdir.success

    for cmd in (
        "mount -v --bind /dev $LFS/dev",
        "mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts",
        "mount -vt proc proc $LFS/proc",
        "mount -vt sysfs sysfs $LFS/sys",
        "mount -vt tmpfs tmpfs $LFS/run",
    ):
        res = engine.run_command(cmd)
        assert res.success, f"Failed: {cmd} -> {res.output}"

    # Q10 should advance to Q11_ENTERING_CHROOT
    assert engine.story_engine.current_quest.id == "Q11_ENTERING_CHROOT"


def test_continuity_act4_chroot_compile_system_tier1():
    """Jump to '4' -> is in chroot and can run lfs-compile-system tier1 immediately."""
    engine = GameEngine()
    ok, _ = engine.jump_to("4")
    assert ok
    assert engine.fs.in_chroot is True

    res = engine.run_command("lfs-compile-system tier1")
    assert res.success
    assert engine.fs.is_package_compiled("glibc-final")
    assert engine.story_engine.flags["tier1_compiled"] is True


def test_continuity_act5_bootscripts_and_network():
    """Jump to '5' -> can run lfs-install-bootscripts and lfs-config-network immediately."""
    engine = GameEngine()
    ok, _ = engine.jump_to("5")
    assert ok
    assert engine.fs.in_chroot is True

    res_bs = engine.run_command("lfs-install-bootscripts")
    assert res_bs.success
    assert engine.fs.bootscripts_installed is True

    res_net = engine.run_command("lfs-config-network hera-lfs")
    assert res_net.success
    assert engine.fs.network_configured is True


def test_continuity_ch10_menuconfig_and_compile_kernel():
    """Jump to 'ch10' -> can run make menuconfig and lfs-compile-kernel immediately."""
    engine = GameEngine()
    ok, _ = engine.jump_to("ch10")
    assert ok
    assert engine.fs.in_chroot is True

    res_mc = engine.run_command("make menuconfig")
    assert res_mc.success
    assert engine.fs.kernel_configured is True

    res_kc = engine.run_command("lfs-compile-kernel")
    assert res_kc.success
    assert engine.fs.kernel_compiled is True
    assert engine.fs.exists("/sources/linux-7.1.8/arch/x86/boot/bzImage")


def test_parser_lfs_jump_commands_and_help():
    """Verify lfs-jump listing, valid jump, aliases, invalid jump, and help listing."""
    engine = GameEngine()

    # Help mentions lfs-jump
    res_help = engine.run_command("help")
    assert res_help.success
    assert "lfs-jump" in res_help.output

    # Listing with no args
    res_list = engine.run_command("lfs-jump")
    assert res_list.success
    assert "SANDBOX" in res_list.output
    assert "chroot" in res_list.output

    # Valid jump with alias
    res_ok = engine.run_command("jump kernel")
    assert res_ok.success
    assert res_ok.state_changed is True
    assert res_ok.system_event == "REFRESH"
    assert engine.story_engine.current_quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG"

    # Aliases test-act / goto-act
    res_alias = engine.run_command("goto-act ato2")
    assert res_alias.success
    assert engine.fs.current_user == "lfs"
    assert engine.story_engine.current_quest.id == "Q5_CROSS_TOOLCHAIN_CORE"

    res_alias2 = engine.run_command("test-act 4")
    assert res_alias2.success
    assert engine.fs.in_chroot is True
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"

    # Invalid jump
    res_bad = engine.run_command("lfs-jump nao-existe")
    assert res_bad.success is False
    assert res_bad.state_changed is False
    assert res_bad.system_event is None
    # State remains at previous valid jump (4)
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"


def test_engine_serialization_preserves_test_mode():
    """Verify test_mode survives to_dict() / from_dict() roundtrip."""
    engine = GameEngine()
    engine.jump_to("5")
    assert engine.test_mode is True

    data = engine.to_dict()
    assert data["test_mode"] is True

    restored = GameEngine()
    restored.from_dict(data)
    assert restored.test_mode is True
    assert restored.story_engine.current_quest.id == "Q20_SYSTEM_CONFIG_NETWORK"

    # Backward compatibility when test_mode is absent from legacy saves
    del data["test_mode"]
    legacy = GameEngine()
    legacy.from_dict(data)
    assert legacy.test_mode is False


def test_cli_invalid_act_exits_nonzero():
    """Verify CLI --act with invalid target prints available options and exits non-zero."""
    proc = subprocess.run(
        [sys.executable, "-m", "lfs_game.main", "--act", "invalid-target"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "inválido" in combined.lower() or "sandbox" in combined.lower()
    assert "chroot" in combined


def test_cli_valid_act_and_test_mode_headless():
    """Verify CLI --act and --test-mode launch headless cleanly with sandbox banner."""
    proc = subprocess.run(
        [sys.executable, "-m", "lfs_game.main", "--headless", "--test-mode", "--act", "ready"],
        input="lfs-check-config\nexit\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "MODO TESTE / SANDBOX ATIVO" in proc.stdout
    assert "Forjador do Kernel" in proc.stdout or "Teleporte Sandbox concluído" in proc.stdout
    assert "AUDITORIA DE CONFIGURAÇÃO DO SISTEMA" in proc.stdout
    assert "PENDENTE" not in proc.stdout


def test_tui_f4_sandbox_modal_and_jump():
    """Verify TUI F4 opens SandboxModalScreen, jumps cleanly, and updates prompt & views."""
    async def _run():
        engine = GameEngine()
        app = LFSGameApp(engine=engine)
        async with app.run_test() as pilot:
            # Open Sandbox modal via F4
            await pilot.press("f4")
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            # Cancel via ESC
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, SandboxModalScreen)
            assert app.engine.story_engine.current_quest.id == "Q0_PROLOGUE"

            # Re-open via action_open_sandbox and click target '5'
            app.action_open_sandbox()
            await pilot.pause()
            assert isinstance(app.screen, SandboxModalScreen)

            btn_5 = app.screen.query_one("#sandbox-btn-5")
            btn_5.press()
            await pilot.pause()

            assert not isinstance(app.screen, SandboxModalScreen)
            assert app.engine.test_mode is True
            assert app.engine.fs.in_chroot is True
            assert app.engine.story_engine.current_quest.id == "Q20_SYSTEM_CONFIG_NETWORK"

            # StoryView renders updated quest cleanly
            story_panel = app.query_one("#story-view").render()
            assert story_panel is not None

            # TerminalView echo & prompt work in chroot without crashing
            term_input = app.query_one("#terminal-input")
            term_input.value = "lfs-install-bootscripts"
            await pilot.press("enter")
            await pilot.pause()
            assert app.engine.fs.bootscripts_installed is True

    asyncio.run(_run())
