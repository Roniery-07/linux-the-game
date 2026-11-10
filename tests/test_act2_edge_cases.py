"""High-signal edge-case test suite for Act 2 (Cross-Toolchain & Temporary Tools).

Covers:
1. Compilation requirements: Behavior when $LFS is unmounted or $LFS_TGT is missing.
2. Readelf program headers: Proper diagnostics on nonexistent files, directories, and non-ELF files.
3. Anomaly encounters: Invalid choices, wrong actions, usage errors, and command interleaving.
4. Toolchain package manager: Invalid package names and duplicate build handling (anti-XP exploit).
5. Persistence & Save/Load: Full round-trip serialization with active Act 2 state and unresolved anomalies.
"""

from __future__ import annotations
import os
import posixpath
import tempfile
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.rpg.combat import (
    AnomalyManager,
    CpuOverheatAnomaly,
    LinkerErrorAnomaly,
    ContaminationWarningAnomaly,
)
from lfs_game.rpg.save_system import save_game, load_game


def _setup_mounted_lfs_engine() -> GameEngine:
    """Helper to initialize an engine with partitions formatted and $LFS mounted."""
    engine = GameEngine()
    engine.run_command("1")  # prologue
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("mkfs.ext4 /dev/sda3")
    engine.run_command("mkswap /dev/sda2")
    engine.run_command("swapon /dev/sda2")
    engine.run_command("mkdir -pv $LFS")
    engine.run_command("mount -v -t ext4 /dev/sda3 $LFS")
    engine.run_command("export LFS_TGT=x86_64-lfs-linux-gnu")
    return engine


# --- 1. Edge Cases: Compiling without $LFS mounted or without $LFS_TGT ---

def test_compile_fails_when_lfs_not_mounted():
    """Verify configure and lfs-compile-tools fail when $LFS partition is not mounted."""
    engine = GameEngine()  # Fresh engine without mount
    engine.fs.env["LFS"] = "/mnt/lfs"
    engine.fs.env["LFS_TGT"] = "x86_64-lfs-linux-gnu"

    # Configure should fail because /mnt/lfs is not mounted
    res_conf = engine.run_command("../configure --prefix=$LFS/tools --target=$LFS_TGT")
    assert not res_conf.success
    assert "não está montado" in res_conf.output

    # lfs-compile-tools should also fail
    res_tools = engine.run_command("lfs-compile-tools binutils-pass1")
    assert not res_tools.success
    assert "não está montado" in res_tools.output

    # Now mount $LFS and verify both work
    engine.run_command("mkdir -pv /mnt/lfs")
    engine.run_command("mkfs.ext4 /dev/sda3")
    engine.run_command("mount -v -t ext4 /dev/sda3 /mnt/lfs")
    res_tools_ok = engine.run_command("lfs-compile-tools binutils-pass1")
    assert res_tools_ok.success

    # If unmounted again, it should fail again
    engine.run_command("umount /mnt/lfs")
    res_tools_unmounted = engine.run_command("lfs-compile-tools m4")
    assert not res_tools_unmounted.success
    assert "não está montado" in res_tools_unmounted.output


def test_compile_fails_when_lfs_tgt_unset():
    """Verify compiler and configure fail when target architecture $LFS_TGT is missing."""
    engine = _setup_mounted_lfs_engine()
    # Unset LFS_TGT
    if "LFS_TGT" in engine.fs.env:
        del engine.fs.env["LFS_TGT"]

    # Invoking $LFS_TGT-gcc expands to -gcc; should report variable unset
    res_gcc = engine.run_command("$LFS_TGT-gcc -v")
    assert not res_gcc.success
    assert "LFS_TGT" in res_gcc.output or "não encontrado" in res_gcc.output

    # Running configure with --target=$LFS_TGT when LFS_TGT is unset
    res_conf = engine.run_command("../configure --target=$LFS_TGT --prefix=$LFS/tools")
    assert not res_conf.success
    assert "LFS_TGT" in res_conf.output

    # Once exported, configure succeeds
    engine.run_command("export LFS_TGT=x86_64-lfs-linux-gnu")
    res_conf_ok = engine.run_command("../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT")
    assert res_conf_ok.success
    assert "binutils-pass1" in res_conf_ok.output


def test_configure_token_boundary_avoids_tar_substring_bug():
    """Verify configure does not confuse '--target=' with the 'tar' package."""
    engine = _setup_mounted_lfs_engine()

    # Pass --target without having tar in cwd
    res = engine.run_command("../configure --prefix=$LFS/tools --target=$LFS_TGT --with-sysroot=$LFS")
    assert res.success
    # Must match binutils-pass1, NEVER 'tar'
    assert "Configuração de 'binutils-pass1' concluída" in res.output
    assert "Configuração de 'tar'" not in res.output


# --- 2. Edge Cases: readelf Diagnostics on Invalid / Non-ELF Targets ---

def test_readelf_nonexistent_file():
    """readelf must return error code and diagnostic when target file does not exist."""
    engine = _setup_mounted_lfs_engine()
    res = engine.run_command("readelf -l /mnt/lfs/nonexistent.bin")
    assert not res.success
    assert "No such file" in res.output
    assert not engine.story_engine.flags.get("sanity_check_passed")


def test_readelf_directory_target():
    """readelf must reject directories and NOT pass sanity check."""
    engine = _setup_mounted_lfs_engine()
    engine.run_command("mkdir -pv /mnt/lfs/somedir")

    res = engine.run_command("readelf -l /mnt/lfs/somedir")
    assert not res.success
    assert "is not an ordinary file" in res.output
    assert not engine.story_engine.flags.get("sanity_check_passed")


def test_readelf_non_elf_text_file():
    """readelf must reject plain text/ASCII files and NOT set sanity_check_passed."""
    engine = _setup_mounted_lfs_engine()
    engine.fs.write_file("/mnt/lfs/plain.txt", "This is just a text file, not an ELF binary.\n")

    res = engine.run_command("readelf -l /mnt/lfs/plain.txt")
    assert not res.success
    assert "Not an ELF file" in res.output
    assert "magic bytes" in res.output
    assert not engine.story_engine.flags.get("sanity_check_passed")


def test_readelf_valid_elf_sanity_check_success():
    """readelf accepts legitimate ELF binaries created by compiler and sets sanity flag."""
    engine = _setup_mounted_lfs_engine()
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")

    # Compile sanity check binary
    res_gcc = engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc -")
    assert res_gcc.success
    assert engine.fs.exists("a.out")

    # readelf should succeed
    res_elf = engine.run_command("readelf -l a.out")
    assert res_elf.success
    assert "Elf file type is EXEC" in res_elf.output
    assert "/lib/ld-linux-x86-64.so.2" in res_elf.output
    assert engine.story_engine.flags.get("sanity_check_passed")


# --- 3. Edge Cases: Anomaly Engine & Invalid Actions ---

def test_anomaly_invalid_shortcut_and_command_options():
    """Test entering invalid choices when an anomaly is active."""
    engine = _setup_mounted_lfs_engine()
    am = engine.anomaly_manager

    # Trigger CPU overheat (choices are 1 and 2)
    am.trigger_anomaly("CPU_OVERHEAT")
    assert am.active_anomaly is not None
    initial_patience = engine.char.patience
    initial_temp = engine.telemetry.temperature

    # 1. Invalid numeric shortcut '9'
    res_inv = engine.run_command("9")
    assert not res_inv.success
    assert "inválida" in res_inv.output
    assert am.active_anomaly is not None  # Anomaly still active
    assert engine.char.patience == initial_patience  # No penalty for invalid option

    # 2. lfs-resolve without arguments
    res_noarg = engine.run_command("lfs-resolve")
    assert not res_noarg.success
    assert "Uso:" in res_noarg.output
    assert am.active_anomaly is not None

    # 3. lfs-resolve with nonexistent option 'foo'
    res_foo = engine.run_command("lfs-resolve foo")
    assert not res_foo.success
    assert "inválida" in res_foo.output
    assert am.active_anomaly is not None

    # 4. Standard shell command executed while anomaly is active should not crash
    res_ls = engine.run_command("ls /")
    assert res_ls.success
    assert am.active_anomaly is not None  # Anomaly still waiting

    # 5. Wrong answer '2' applies penalties but keeps anomaly active
    res_wrong = engine.run_command("2")
    assert not res_wrong.success
    assert "FALHA" in res_wrong.output
    assert engine.char.patience < initial_patience
    assert engine.telemetry.temperature > initial_temp
    assert am.active_anomaly is not None

    # 6. Correct answer '1' resolves anomaly
    res_correct = engine.run_command("1")
    assert res_correct.success
    assert "SUCESSO" in res_correct.output
    assert am.active_anomaly is None
    assert "CPU_OVERHEAT" in am.resolved_history

    # 7. lfs-resolve when no anomaly is active
    res_none = engine.run_command("lfs-resolve 1")
    assert not res_none.success
    assert "Nenhuma anomalia" in res_none.output


# --- 4. Edge Cases: lfs-compile-tools Package Catalog & Duplicate XP Exploit ---

def test_lfs_compile_tools_invalid_package():
    """Verify compiler rejects unknown package IDs with helpful error."""
    engine = _setup_mounted_lfs_engine()
    res = engine.run_command("lfs-compile-tools superpackage-9000")
    assert not res.success
    assert "não encontrado no catálogo" in res.output
    assert "lfs-status-tools" in res.output


def test_lfs_compile_tools_no_duplicate_xp_exploit():
    """Prevent infinite XP farming by compiling the same package multiple times."""
    engine = _setup_mounted_lfs_engine()

    # 1st compilation grants XP
    res1 = engine.run_command("lfs-compile-tools m4")
    assert res1.success
    assert "+60 XP" in res1.output
    xp_after_1st = engine.char.xp

    # 2nd compilation of same package must grant 0 XP
    res2 = engine.run_command("lfs-compile-tools m4")
    assert res2.success
    assert "+0 XP" in res2.output or "já se encontra compilado" in res2.output
    assert engine.char.xp == xp_after_1st

    # 3rd compilation also grants 0 XP
    res3 = engine.run_command("lfs-compile-tools m4")
    assert res3.success
    assert engine.char.xp == xp_after_1st


def test_lfs_compile_tools_all_idempotent():
    """lfs-compile-tools all grants XP on first run, and 0 XP on subsequent runs."""
    engine = _setup_mounted_lfs_engine()

    res1 = engine.run_command("lfs-compile-tools all")
    assert res1.success
    assert "foram instaladas com sucesso" in res1.output
    xp_after_first = engine.char.xp

    res2 = engine.run_command("lfs-compile-tools all")
    assert res2.success
    assert "+0 XP" in res2.output or "já estavam previamente compiladas" in res2.output
    assert engine.char.xp == xp_after_first


# --- 5. Edge Cases: Save/Load Round-Trip with Active Act 2 State & Anomalies ---

def test_save_load_roundtrip_with_active_anomaly_and_act2_state():
    """Test full JSON serialization and restoration of active compilation anomalies."""
    engine = _setup_mounted_lfs_engine()

    # Progress partially into Act 2
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    engine.run_command("lfs-compile-tools linux-headers")

    # Trigger active Linker Error anomaly and record past overheat
    engine.anomaly_manager.trigger_anomaly("LINKER_ERROR")
    engine.anomaly_manager.resolved_history.append("CPU_OVERHEAT")
    assert engine.anomaly_manager.active_anomaly is not None

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        save_path = f.name

    try:
        ok_save, msg_save = save_game(engine, save_path)
        assert ok_save

        # Restore into a fresh engine instance
        restored = GameEngine()
        ok_load, msg_load = load_game(restored, save_path)
        assert ok_load

        # Verify filesystem state
        assert restored.fs.is_package_compiled("binutils-pass1")
        assert restored.fs.is_package_compiled("gcc-pass1")
        assert restored.fs.is_package_compiled("linux-headers")
        assert restored.fs.exists("/mnt/lfs/tools/bin/x86_64-lfs-linux-gnu-gcc")
        assert "/mnt/lfs" in restored.fs.mounts

        # Verify active anomaly state
        assert restored.anomaly_manager.active_anomaly is not None
        assert restored.anomaly_manager.active_anomaly.id == "LINKER_ERROR"
        assert "CPU_OVERHEAT" in restored.anomaly_manager.resolved_history
        assert len(restored.anomaly_manager.active_anomaly.choices) == 2

        # Verify prompt format works on restored anomaly
        prompt = restored.anomaly_manager.format_active_prompt()
        assert "Falha de Vinculação Cruzada" in prompt

        # Resolve the active anomaly on the restored engine via command
        res_solve = restored.run_command("1")
        assert res_solve.success
        assert "SUCESSO" in res_solve.output
        assert restored.anomaly_manager.active_anomaly is None
        assert "LINKER_ERROR" in restored.anomaly_manager.resolved_history

    finally:
        if os.path.exists(save_path):
            os.remove(save_path)
