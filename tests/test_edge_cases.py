"""High-signal edge-case, boundary, security, and failure-recovery test suite.

Covers:
1. Corrupted/malformed save file handling and atomic recovery.
2. Shell command parser injection, weird characters, consecutive pipes/semicolons/&&.
3. Permission boundary enforcement (root vs unprivileged lfs user, disk/mount operations, inode ACLs).
4. Virtual filesystem path traversal edge cases (cd ../../../.., deep mkdir -p, redundant slashes).
5. SBU / Telemetry & character life-support boundary values (oxygen reaching 0, CPU spikes, UI gauge limits).
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import pytest

from lfs_game.core.engine import GameEngine, Telemetry
from lfs_game.core.virtual_fs import VirtualFS
from lfs_game.rpg.character import HackerCharacter
from lfs_game.rpg.save_system import save_game, load_game, get_save_path
from lfs_game.ui.status_view import StatusView


# ============================================================================
# 1. SAVE SYSTEM EDGE CASES & MALFORMED INPUT HANDLING
# ============================================================================

def test_save_load_nonexistent_file():
    """Verify that loading a nonexistent save returns False without crashing."""
    engine = GameEngine()
    ok, msg = load_game(engine, "nonexistent_save_file_12345.json")
    assert not ok
    assert "não encontrado" in msg.lower()


def test_save_load_empty_file():
    """Verify that loading an empty 0-byte file gracefully fails."""
    engine = GameEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_path = Path(tmpdir) / "empty.json"
        empty_path.write_text("", encoding="utf-8")

        ok, msg = load_game(engine, str(empty_path))
        assert not ok
        assert "falha ao carregar jogo" in msg.lower()


def test_save_load_corrupted_json_syntax():
    """Verify that loading malformed JSON (syntax error) gracefully fails."""
    engine = GameEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_path = Path(tmpdir) / "corrupt.json"
        corrupt_path.write_text("{\"fs\": { truncated json", encoding="utf-8")

        ok, msg = load_game(engine, str(corrupt_path))
        assert not ok
        assert "falha ao carregar jogo" in msg.lower()


def test_save_load_non_dict_json():
    """Verify that JSON root not being a dictionary is rejected."""
    engine = GameEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        list_json = Path(tmpdir) / "list.json"
        list_json.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        ok, msg = load_game(engine, str(list_json))
        assert not ok
        assert "inválido" in msg.lower()


def test_save_load_missing_required_keys():
    """Verify that JSON missing critical engine keys fails gracefully."""
    engine = GameEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Missing telemetry and char
        partial_json = Path(tmpdir) / "partial.json"
        partial_json.write_text(json.dumps({"fs": engine.fs.to_dict()}), encoding="utf-8")

        ok, msg = load_game(engine, str(partial_json))
        assert not ok
        assert "falha ao carregar jogo" in msg.lower()


def test_save_load_atomic_preservation_on_failure():
    """Verify that a failed load does NOT leave the current engine in a half-corrupted state."""
    engine = GameEngine()
    engine.char.name = "OriginalOperator"
    engine.fs.write_file("/root/vital.txt", "keep me safe")

    # Corrupt data where fs is valid but char is a broken integer
    corrupted_data = {
        "fs": engine.fs.to_dict(),
        "char": 99999,  # invalid: should be dict
        "story_engine": engine.story_engine.to_dict(),
        "telemetry": engine.telemetry.to_dict(),
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "half_broken.json"
        save_path.write_text(json.dumps(corrupted_data), encoding="utf-8")

        ok, msg = load_game(engine, str(save_path))
        assert not ok

        # Verify engine state was preserved intact
        assert engine.char.name == "OriginalOperator"
        ok_read, content = engine.fs.read_file("/root/vital.txt")
        assert ok_read
        assert content == "keep me safe"


def test_save_load_roundtrip_integrity():
    """Verify complete serialization and restoration of complex state."""
    engine = GameEngine()
    # Mutate state
    engine.char.modify_patience(-20)
    engine.char.modify_caffeine(+10)
    engine.telemetry.oxygen = 35.5
    engine.fs.useradd("lfs", create_home=True)
    engine.fs.mkdir("/mnt/lfs/sources", parents=True)
    engine.fs.write_file("/mnt/lfs/sources/kernel.tar.xz", "binary_data")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test custom name without extension (auto-appends .json)
        save_file = str(Path(tmpdir) / "session_alpha")
        ok_save, save_msg = save_game(engine, save_file)
        assert ok_save
        assert Path(save_file + ".json").exists()

        # Load into brand new engine
        new_engine = GameEngine()
        ok_load, load_msg = load_game(new_engine, save_file + ".json")
        assert ok_load

        # Assert full fidelity
        assert new_engine.char.patience == 80
        assert new_engine.telemetry.oxygen == 35.5
        assert "lfs" in new_engine.fs.users
        assert new_engine.fs.exists("/mnt/lfs/sources/kernel.tar.xz")
        ok_read, content = new_engine.fs.read_file("/mnt/lfs/sources/kernel.tar.xz")
        assert ok_read
        assert content == "binary_data"


def test_save_game_unwritable_path():
    """Verify that attempting to save to an invalid/unwritable location returns False."""
    engine = GameEngine()
    # Invalid path with null character or non-existent parent that cannot be created
    ok, msg = save_game(engine, "/proc/sys/kernel/forbidden_save_test.json")
    assert not ok
    assert "falha ao salvar jogo" in msg.lower()


# ============================================================================
# 2. SHELL PARSER INJECTION & WEIRD CHARACTERS HANDLING
# ============================================================================

def test_parser_empty_and_whitespace():
    """Verify that blank inputs or whitespace return success without crash."""
    engine = GameEngine()
    for blank in ["", "   ", "\t", "\n", "  \t  \n  "]:
        res = engine.parser.execute(blank)
        assert res.success
        assert res.output == ""


def test_parser_unmatched_quotes():
    """Verify that unmatched single and double quotes return syntax errors."""
    engine = GameEngine()
    res1 = engine.parser.execute("echo 'unclosed single quote")
    assert not res1.success
    assert "erro de sintaxe" in res1.output

    res2 = engine.parser.execute('echo "unclosed double quote')
    assert not res2.success
    assert "erro de sintaxe" in res2.output


def test_parser_consecutive_semicolons():
    """Verify that consecutive semicolons (;; or ; ;) are caught as syntax errors."""
    engine = GameEngine()
    res = engine.parser.execute("echo 1 ;; echo 2")
    assert not res.success
    assert "erro de sintaxe próximo ao token inesperado ';;'" in res.output

    res2 = engine.parser.execute(";;")
    assert not res2.success
    assert "erro de sintaxe" in res2.output


def test_parser_chained_and_edge_cases():
    """Verify that malformed '&&' chains (empty operands) trigger syntax errors."""
    engine = GameEngine()
    malformed_and_cases = [
        "&&",
        "echo 1 && && echo 2",
        "echo 1 &&",
        "&& echo 1",
        "echo 1 &&    ",
    ]
    for case in malformed_and_cases:
        res = engine.parser.execute(case)
        assert not res.success
        assert "erro de sintaxe próximo ao token inesperado '&&'" in res.output


def test_parser_pipe_tokens_handling():
    """Verify that unsupported/isolated pipe tokens trigger syntax errors."""
    engine = GameEngine()
    for pipe_case in ["|", "||", "| echo 1", "echo 1 |"]:
        res = engine.parser.execute(pipe_case)
        assert not res.success
        assert "erro de sintaxe" in res.output


def test_parser_variable_expansion_edge_cases():
    """Verify boundary cases in variable expansion ($ without name, empty ${}, non-existent)."""
    engine = GameEngine()
    fs = engine.fs

    # Lone dollar sign
    assert fs.expand_vars("echo $") == "echo $"
    # Empty curly braces
    assert fs.expand_vars("echo ${}") == "echo ${}"
    # Undefined variable expands to empty string
    assert fs.expand_vars("echo $NON_EXISTENT_VAR_12345") == "echo "

    # Set variable and expand with curly braces and normal notation
    fs.env["LFS"] = "/mnt/lfs"
    assert fs.expand_vars("$LFS/sources") == "/mnt/lfs/sources"
    assert fs.expand_vars("${LFS}/tools") == "/mnt/lfs/tools"


def test_parser_redirection_edge_cases():
    """Verify redirection boundary conditions: missing target, nested target."""
    engine = GameEngine()
    parser = engine.parser

    # Redirect to non-existent parent directory fails gracefully
    res = parser.execute("echo 'payload' > /nonexistent/dir/file.txt")
    assert not res.success
    assert "Arquivo ou diretório inexistente" in res.output

    # Missing target doesn't redirect or crash
    res = parser.execute("echo 'plain output' >")
    assert res.success
    assert "plain output" in res.output


def test_parser_dangerous_commands_protection():
    """Verify that dangerous destructive operations like rm -rf / are blocked."""
    engine = GameEngine()
    res = engine.parser.execute("rm -rf /")
    assert not res.success
    assert "é perigoso operar recursivamente em '/'" in res.output


def test_parser_unknown_command_reduces_patience():
    """Verify that non-existent commands decrease operator patience and offer guidance."""
    engine = GameEngine()
    initial_patience = engine.char.patience
    res = engine.parser.execute("foobar_command_xyz")
    assert not res.success
    assert "comando não encontrado" in res.output
    assert "help" in res.output
    assert engine.char.patience == initial_patience - 3


# ============================================================================
# 3. PERMISSION BOUNDARY ENFORCEMENT (ROOT VS UNPRIVILEGED LFS)
# ============================================================================

def test_permission_format_disk_requires_root():
    """Verify that formatting partitions is strictly forbidden for non-root users."""
    engine = GameEngine()
    engine.fs.useradd("lfs")
    engine.fs.su("lfs")
    assert engine.fs.current_user == "lfs"

    # Try formatting as unprivileged lfs
    res = engine.parser.execute("mkfs.ext4 /dev/sda3")
    assert not res.success
    assert "Permissão negada" in res.output

    # Try formatting swap as lfs
    res_swap = engine.parser.execute("mkswap /dev/sda2")
    assert not res_swap.success
    assert "Permissão negada" in res_swap.output

    # Switch back to root and verify it succeeds
    engine.parser.execute("exit")
    assert engine.fs.current_user == "root"
    res_root = engine.parser.execute("mkfs.ext4 /dev/sda3")
    assert res_root.success


def test_permission_mount_and_swap_require_root():
    """Verify mount, umount, swapon, swapoff require superuser privileges."""
    engine = GameEngine()
    engine.fs.useradd("lfs")
    engine.fs.mkdir("/mnt/lfs", parents=True)

    # Format as root first
    engine.fs.format_partition("/dev/sda3", "ext4")
    engine.fs.make_swap("/dev/sda2")

    # Switch to lfs
    engine.fs.su("lfs")

    # Mount forbidden
    res_mount = engine.parser.execute("mount -v -t ext4 /dev/sda3 /mnt/lfs")
    assert not res_mount.success
    assert "apenas o superusuário" in res_mount.output

    # Swapon forbidden
    res_swapon = engine.parser.execute("swapon /dev/sda2")
    assert not res_swapon.success
    assert "Operação não permitida" in res_swapon.output

    # Swapoff forbidden
    res_swapoff = engine.parser.execute("swapoff /dev/sda2")
    assert not res_swapoff.success
    assert "Operação não permitida" in res_swapoff.output


def test_permission_fdisk_requires_root():
    """Verify fdisk command refuses execution to non-root users."""
    engine = GameEngine()
    engine.fs.useradd("lfs")
    engine.fs.su("lfs")

    res = engine.parser.execute("fdisk /dev/sda")
    assert not res.success
    assert "Permissão negada" in res.output


def test_permission_useradd_groupadd_require_root():
    """Verify useradd and groupadd are blocked for unprivileged users."""
    engine = GameEngine()
    engine.fs.useradd("lfs")
    engine.fs.su("lfs")

    res_user = engine.parser.execute("useradd rogue")
    assert not res_user.success
    assert "Permissão negada" in res_user.output

    res_grp = engine.parser.execute("groupadd roguegroup")
    assert not res_grp.success
    assert "Permissão negada" in res_grp.output


def test_permission_chown_requires_root():
    """Verify chown command is restricted to root only."""
    engine = GameEngine()
    engine.fs.useradd("lfs")
    engine.fs.mkdir("/tmp/shared")

    # Switch to lfs and try chown
    engine.fs.su("lfs")
    res = engine.parser.execute("chown root:root /tmp/shared")
    assert not res.success
    assert "Operação não permitida" in res.output


def test_permission_root_home_isolated_from_nonroot():
    """Verify /root directory (mode 0700) cannot be accessed by user lfs."""
    engine = GameEngine()
    engine.fs.write_file("/root/secret.conf", "API_KEY=CLASSIFIED")
    engine.fs.useradd("lfs")

    # Switch to lfs
    engine.fs.su("lfs", login=True)
    assert engine.fs.current_user == "lfs"

    # Cannot cd into /root
    res_cd = engine.parser.execute("cd /root")
    assert not res_cd.success
    assert "Permissão negada" in res_cd.output

    # Cannot read files in /root
    res_cat = engine.parser.execute("cat /root/secret.conf")
    assert not res_cat.success
    assert "Permissão negada" in res_cat.output

    # Cannot touch files in /root
    res_touch = engine.parser.execute("touch /root/intruder.txt")
    assert not res_touch.success
    assert "Permissão negada" in res_touch.output


def test_permission_unprivileged_lfs_allowed_in_owned_dirs():
    """Verify that once root grants ownership of $LFS/tools to lfs, lfs can operate freely."""
    engine = GameEngine()
    fs = engine.fs

    fs.mkdir("/mnt/lfs/tools", parents=True)
    fs.useradd("lfs")
    fs.chown("/mnt/lfs/tools", "lfs:lfs")

    # Switch to lfs
    fs.su("lfs", login=True)
    assert fs.current_user == "lfs"

    # lfs can create dirs and files inside /mnt/lfs/tools
    ok_mkdir, msg = fs.mkdir("/mnt/lfs/tools/bin")
    assert ok_mkdir

    ok_write, msg = fs.write_file("/mnt/lfs/tools/bin/dummy_compiler", "#!/bin/sh\necho built")
    assert ok_write

    ok_read, content = fs.read_file("/mnt/lfs/tools/bin/dummy_compiler")
    assert ok_read
    assert "built" in content


def test_permission_chmod_restricted_to_owner_and_root():
    """Verify that chmod can only be executed by root or the inode owner."""
    engine = GameEngine()
    fs = engine.fs

    fs.useradd("lfs")
    fs.write_file("/tmp/root_file.txt", "root owned")

    # lfs cannot chmod file owned by root
    fs.su("lfs")
    ok, msg = fs.chmod("/tmp/root_file.txt", "777")
    assert not ok
    assert "Operação não permitida" in msg

    # lfs can chmod its own file in /home/lfs
    ok_create, msg = fs.write_file("/home/lfs/my_script.sh", "echo hi")
    assert ok_create
    ok_chmod, msg = fs.chmod("/home/lfs/my_script.sh", "+x")
    assert ok_chmod


# ============================================================================
# 4. VIRTUAL FILESYSTEM PATH TRAVERSAL EDGE CASES
# ============================================================================

def test_vfs_path_traversal_above_root():
    """Verify that traversing above root (cd ../../../..) remains safely at /."""
    fs = VirtualFS()
    ok, msg = fs.cd("/root")
    assert ok

    # Traverse upward past root
    ok, msg = fs.cd("../../../../../../../..")
    assert ok
    assert fs.pwd() == "/"

    # Upward again from root
    ok, msg = fs.cd("..")
    assert ok
    assert fs.pwd() == "/"


def test_vfs_deep_relative_traversal():
    """Verify deep nested relative directory creation and traversal."""
    fs = VirtualFS()
    ok, msg = fs.mkdir("/root/deep/nested/path/to/target", parents=True)
    assert ok
    assert fs.exists("/root/deep/nested/path/to/target")

    ok, msg = fs.cd("/root/deep/nested/path/to/target")
    assert ok
    assert fs.pwd() == "/root/deep/nested/path/to/target"

    # Step back 3 levels
    ok, msg = fs.cd("../../..")
    assert ok
    assert fs.pwd() == "/root/deep/nested"

    # Step back 1 more level to deep
    ok, msg = fs.cd("..")
    assert ok
    assert fs.pwd() == "/root/deep"


def test_vfs_redundant_slashes_and_dots():
    """Verify path normalization with repeated slashes and current-dir dots."""
    fs = VirtualFS()
    norm = fs.resolve_path("///root//./deep///./nested//")
    assert norm == "/root/deep/nested"

    fs.mkdir(norm, parents=True)
    assert fs.exists(norm)


def test_vfs_mkdir_without_parents_fails_on_missing_parent():
    """Verify mkdir fails when intermediate path components do not exist."""
    fs = VirtualFS()
    ok, msg = fs.mkdir("/a/b/c/d", parents=False)
    assert not ok
    assert "Arquivo ou diretório inexistente" in msg


def test_vfs_rm_directory_non_recursive_fails():
    """Verify rm without recursive flag fails on directories."""
    fs = VirtualFS()
    fs.mkdir("/tmp/test_dir")
    ok, msg = fs.rm("/tmp/test_dir", recursive=False)
    assert not ok
    assert "É um diretório" in msg

    # With recursive it succeeds
    ok, msg = fs.rm("/tmp/test_dir", recursive=True)
    assert ok
    assert not fs.exists("/tmp/test_dir")


def test_vfs_pushd_popd_stack_handling():
    """Verify pushd and popd directory stack management and empty stack error."""
    engine = GameEngine()
    parser = engine.parser

    engine.fs.mkdir("/tmp/dirA")
    engine.fs.mkdir("/tmp/dirB")

    # pushd to dirA
    res = parser.execute("pushd /tmp/dirA")
    assert res.success
    assert engine.fs.pwd() == "/tmp/dirA"

    # pushd to dirB
    res = parser.execute("pushd /tmp/dirB")
    assert res.success
    assert engine.fs.pwd() == "/tmp/dirB"

    # popd back to dirA
    res = parser.execute("popd")
    assert res.success
    assert engine.fs.pwd() == "/tmp/dirA"

    # popd back to /root
    res = parser.execute("popd")
    assert res.success
    assert engine.fs.pwd() == "/root"

    # popd on empty stack fails gracefully
    res = parser.execute("popd")
    assert not res.success
    assert "pilha de diretórios vazia" in res.output


# ============================================================================
# 5. SBU / TELEMETRY & CHARACTER LIFE-SUPPORT BOUNDARY VALUES
# ============================================================================

def test_telemetry_oxygen_drain_clamping_at_zero():
    """Verify oxygen drains on simulation tick and safely clamps at 0.0 without going negative."""
    engine = GameEngine()
    engine.telemetry.oxygen = 0.05

    # Run tick with large delta
    engine.tick(delta_seconds=100.0)
    assert engine.telemetry.oxygen == 0.0

    # Additional ticks stay at 0.0
    engine.tick(delta_seconds=3600.0)
    assert engine.telemetry.oxygen == 0.0


def test_telemetry_oxygen_recovery_after_act1():
    """Verify oxygen recovers and clamps at safe reserve (75.0%) once Act 1 is celebrated."""
    engine = GameEngine()
    engine.story_engine.flags["act1_celebrated"] = True
    engine.telemetry.oxygen = 74.5

    engine.tick(delta_seconds=20.0)
    assert engine.telemetry.oxygen == 75.0

    # Does not exceed 75.0
    engine.tick(delta_seconds=3600.0)
    assert engine.telemetry.oxygen == 75.0


def test_telemetry_cpu_jitter_and_temperature_bounds():
    """Verify CPU usage and temperature jitter remain within valid operational ranges."""
    engine = GameEngine()
    for _ in range(50):
        engine.tick(delta_seconds=1.0)
        assert 0.0 <= engine.telemetry.cpu_usage <= 100.0
        assert 38.0 <= engine.telemetry.temperature <= 85.0


def test_telemetry_ui_rendering_extreme_values():
    """Verify StatusView renders without crashing under extreme boundary sensor values."""
    engine = GameEngine()
    view = StatusView(engine)

    extreme_cases = [
        # (oxygen, temp, cpu, ram)
        (0.0, 0.0, 0.0, 0),
        (-25.0, -100.0, -50.0, -1024),
        (100.0, 100.0, 100.0, 8192),
        (250.0, 999.0, 500.0, 131072),
    ]

    for ox, temp, cpu, ram in extreme_cases:
        engine.telemetry = Telemetry(oxygen=ox, temperature=temp, cpu_usage=cpu, ram_mb=ram)
        panel = view.render()
        assert panel is not None
        # Verify status command output also formats without exception
        res = engine.parser.execute("status")
        assert res.success


def test_character_patience_and_caffeine_clamping():
    """Verify character attributes stay strictly clamped between 0 and 100."""
    char = HackerCharacter()

    # Drain patience to negative
    char.modify_patience(-200)
    assert char.patience == 0

    # Restore beyond max
    char.modify_patience(+500)
    assert char.patience == 100

    # Drain caffeine to negative
    char.modify_caffeine(-200)
    assert char.caffeine == 0

    # Coffee saturation behavior
    char.caffeine = 96
    msg = char.drink_coffee()
    assert "saturados" in msg.lower()
    assert char.caffeine == 96


def test_character_level_progression_and_titles():
    """Verify massive XP grant correctly advances levels and unlocks all cyberpunk titles."""
    char = HackerCharacter()
    assert char.level == 1
    assert char.title == "Aprendiz de Sucata"

    # Grant large XP amount
    leveled = char.add_xp(2500)
    assert leveled
    assert char.level >= 5
    assert "Compilador do Vácuo" in char.unlocked_titles
    assert char.title == "Compilador do Vácuo"
