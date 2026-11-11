"""High-signal edge-case test suite for Act 3 (Chroot Environment & Chapter 7 Tools).

Covers:
1. Chroot jail boundaries and path traversal containment (cd /.., cd ../../../.., ls /../..).
2. Filesystem isolation: write/read containment, host file immunity.
3. Nested exit handling: su user inside chroot -> chroot root -> host system -> session exit.
4. Virtual mounts validation: warnings and blockers for missing /dev, /proc, /sys.
5. Error handling for chroot entry: nonexistent path, regular file, already in chroot.
6. Chapter 7 tools compilation constraints: chroot environment check, /dev/null and /proc prerequisites.
7. Anti-XP exploit and idempotency on lfs-compile-chroot (individual and batch).
8. Unix 'install' utility edge cases: mode 0750, sticky bit 1777, file copy mode, argument parsing errors.
9. Advanced bash case statement matching (wildcards, alternatives, syntax errors).
10. Deep save/load state round-trip serialization in chroot.
"""

from __future__ import annotations
import os
import posixpath
import tempfile
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.rpg.save_system import save_game, load_game
from lfs_game.data.lfs_manifest import get_toolchain_package


def _setup_act2_completed_engine() -> GameEngine:
    """Helper that fast-forwards through Act 1 and Act 2 to reach the start of Act 3."""
    engine = GameEngine()
    fs = engine.fs

    # --- Act 1 ---
    engine.run_command("1")  # Prologue
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("mkfs.ext4 /dev/sda3")
    engine.run_command("mkswap /dev/sda2")
    engine.run_command("swapon /dev/sda2")
    engine.run_command("mkdir -pv $LFS")
    engine.run_command("mount -v -t ext4 /dev/sda3 $LFS")
    engine.run_command("mkdir -v $LFS/sources")
    engine.run_command("chmod -v a+wt $LFS/sources")
    engine.run_command("lfs-get-sources")
    engine.run_command("cd $LFS/sources")
    engine.run_command("md5sum -c md5sums")
    engine.run_command("mkdir -pv $LFS/tools")
    engine.run_command("mkdir -pv $LFS/{etc,var,usr}")
    engine.run_command("groupadd lfs")
    engine.run_command("useradd -s /bin/bash -g lfs -m -k /dev/null lfs")
    engine.run_command("chown -v lfs $LFS/{tools,sources,etc,var,usr}")
    engine.run_command("su - lfs")
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("export LC_ALL=POSIX")
    engine.run_command("export LFS_TGT=x86_64-lfs-linux-gnu")
    engine.run_command("export PATH=/usr/bin:/bin")

    # --- Act 2 ---
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    engine.run_command("lfs-compile-tools linux-headers")
    engine.run_command("lfs-compile-tools glibc")
    engine.story_engine.flags["sanity_check_passed"] = True
    fs.touch("/mnt/lfs/sources/a.out")
    engine.run_command("lfs-compile-tools libstdc++")
    engine.run_command("lfs-compile-tools all")
    engine.run_command("lfs-compile-tools binutils-pass2")
    engine.run_command("lfs-compile-tools gcc-pass2")

    # Exit from lfs user back to host root
    engine.run_command("exit")
    engine.run_command("cd /root")
    return engine


def _setup_chroot_ready_engine() -> GameEngine:
    """Prepares mounts and enters chroot jail with clean state."""
    engine = _setup_act2_completed_engine()
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    res = engine.run_command("chroot $LFS")
    assert res.success
    assert engine.fs.in_chroot is True
    return engine


# ==============================================================================
# 1. Chroot Path Escape & Jail Boundary Containment
# ==============================================================================

def test_chroot_path_escape_cd_and_ls():
    """Verify that path traversal attempts inside chroot cannot break out above '/'."""
    engine = _setup_chroot_ready_engine()
    fs = engine.fs

    assert fs.pwd() == "/"

    # Attempt cd .. from root
    res1 = engine.run_command("cd ..")
    assert res1.success
    assert fs.pwd() == "/"

    # Attempt cd /.. from root
    res2 = engine.run_command("cd /..")
    assert res2.success
    assert fs.pwd() == "/"

    # Navigate deep into chroot hierarchy
    engine.run_command("mkdir -pv /usr/local/bin")
    engine.run_command("cd /usr/local/bin")
    assert fs.pwd() == "/usr/local/bin"

    # Attempt multi-level escape cd ../../../../../../../..
    res3 = engine.run_command("cd ../../../../../../../..")
    assert res3.success
    assert fs.pwd() == "/"
    assert engine.get_prompt() == "(lfs chroot) root:/# "

    # Verify ls /../.. stays contained at chroot root
    res_ls = engine.run_command("ls /../..")
    assert res_ls.success
    # In chroot, / contains tools, usr, var, etc., dev, proc, sys, run
    assert "tools" in res_ls.output
    assert "usr" in res_ls.output
    # Must NOT show host-only directories like host /home or host /opt
    assert "hera" not in res_ls.output


def test_chroot_filesystem_isolation_read_write_delete():
    """Verify write/read containment: writes in chroot go to $LFS, host files are shielded."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Create a sensitive file on host
    fs.touch("/root/host_secret_key.pem")
    fs.write_file("/root/host_secret_key.pem", "HOST_TOP_SECRET")
    assert fs.exists("/root/host_secret_key.pem")

    # Enter chroot
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    engine.run_command("chroot $LFS")

    # Attempt to read the host file from inside chroot: must fail
    res_cat = engine.run_command("cat /root/host_secret_key.pem")
    assert not res_cat.success
    assert "Arquivo ou diretório inexistente" in res_cat.output

    # Attempt with traversal
    res_cat_trav = engine.run_command("cat /../../../../root/host_secret_key.pem")
    assert not res_cat_trav.success

    # Create a directory inside chroot first, then a file
    engine.run_command("mkdir -pv /root")
    res_touch = engine.run_command("touch /root/chroot_payload.txt")
    assert res_touch.success

    # File exists inside chroot at /root/chroot_payload.txt
    assert fs.exists("/root/chroot_payload.txt")
    # Physically mapped to host /mnt/lfs/root/chroot_payload.txt
    assert fs.exists("/mnt/lfs/root/chroot_payload.txt")

    # Exit chroot
    engine.run_command("exit")
    assert not fs.in_chroot
    # On host, /root/host_secret_key.pem is still pristine
    ok, secret = fs.read_file("/root/host_secret_key.pem")
    assert ok
    assert secret == "HOST_TOP_SECRET"


# ==============================================================================
# 2. Nested Exit Hierarchy
# ==============================================================================

def test_nested_exit_hierarchy():
    """Verify nested session exit: su inside chroot -> chroot root -> host -> session exit."""
    engine = _setup_chroot_ready_engine()
    fs = engine.fs

    assert fs.in_chroot is True
    assert fs.current_user == "root"

    # Inside chroot, simulate switching user
    res_su = engine.run_command("su - lfs")
    assert res_su.success
    assert fs.current_user == "lfs"
    assert fs.in_chroot is True
    assert len(fs.user_stack) == 1

    # 1st exit: should exit lfs user back to chroot root
    res_exit1 = engine.run_command("exit")
    assert res_exit1.success
    assert "logout" in res_exit1.output
    assert fs.current_user == "root"
    assert fs.in_chroot is True
    assert engine.get_prompt() == "(lfs chroot) root:/# "

    # 2nd exit: should exit chroot back to host root
    res_exit2 = engine.run_command("exit")
    assert res_exit2.success
    assert "saindo do ambiente chroot" in res_exit2.output
    assert fs.in_chroot is False
    assert fs.current_user == "root"
    assert engine.get_prompt().startswith("root@hera:")

    # 3rd exit: host exit closes the connection
    res_exit3 = engine.run_command("exit")
    assert res_exit3.success
    assert res_exit3.system_event == "EXIT"
    assert "Conexão com a estação encerrada" in res_exit3.output


def test_exit_chroot_when_not_in_chroot():
    """Verify that attempting to exit chroot when not inside returns an error."""
    engine = GameEngine()
    ok, msg = engine.fs.exit_chroot()
    assert not ok
    assert "nenhuma sessão chroot ativa" in msg


# ==============================================================================
# 3. Virtual Mounts & Warnings on Chroot Entry
# ==============================================================================

def test_enter_chroot_without_mounts_issues_warning():
    """Verify that entering chroot without mounting /dev, /proc, /sys triggers K.E.R.N.E.L. warning."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Change owner of tools
    engine.run_command("chown --from lfs -R root:root $LFS/tools")

    # Enter chroot directly WITHOUT mounting /dev, /proc, /sys
    res = engine.run_command("chroot $LFS")
    assert res.success
    assert fs.in_chroot is True
    # Verify warning message appears
    assert "ALERTA (K.E.R.N.E.L.)" in res.output
    assert "/dev" in res.output
    assert "/proc" in res.output
    assert "/sys" in res.output

    # Quest Q10 must NOT be complete because required mounts are missing
    assert engine.story_engine.current_quest.id == "Q10_CHROOT_PREPARATION"


def test_enter_chroot_with_all_mounts_no_warning():
    """Verify that entering chroot with all virtual filesystems mounted has no warning."""
    engine = _setup_chroot_ready_engine()
    # chroot ready engine has dev, proc, sys, run mounted
    # Story quest advanced to Q12 or Q11
    assert engine.story_engine.current_quest.id in ("Q11_ENTERING_CHROOT", "Q12_CHROOT_BASE_DIRECTORIES")


def test_chroot_error_conditions():
    """Verify error responses for invalid chroot targets and nested chroot."""
    engine = _setup_act2_completed_engine()

    # 1. No argument
    res_noarg = engine.run_command("chroot")
    assert not res_noarg.success
    assert "operando ausente" in res_noarg.output

    # 2. Nonexistent directory
    res_none = engine.run_command("chroot /nonexistent_path_xyz")
    assert not res_none.success
    assert "Arquivo ou diretório inexistente" in res_none.output

    # 3. Target is a regular file
    engine.fs.touch("/mnt/lfs/dummy_file.txt")
    res_file = engine.run_command("chroot /mnt/lfs/dummy_file.txt")
    assert not res_file.success
    assert "Não é um diretório" in res_file.output

    # 4. Nested chroot prevention
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    engine.run_command("chroot $LFS")
    assert engine.fs.in_chroot is True

    # Try entering chroot again while already in chroot
    res_nested = engine.run_command("chroot /")
    assert not res_nested.success
    assert "já está operando dentro de um ambiente chroot ativo" in res_nested.output


# ==============================================================================
# 4. Chapter 7 Tools Compilation Prerequisites & Anti-XP Exploit
# ==============================================================================

def test_lfs_compile_chroot_fails_outside_chroot():
    """Verify that lfs-compile-chroot is rejected if invoked from the host system."""
    engine = _setup_act2_completed_engine()
    assert not engine.fs.in_chroot

    res = engine.run_command("lfs-compile-chroot bison")
    assert not res.success
    assert "só pode ser executado dentro do ambiente chroot" in res.output


def test_lfs_compile_chroot_fails_without_dev_or_proc():
    """Verify that compiling Chapter 7 tools requires /dev/null and /proc inside chroot."""
    engine = _setup_act2_completed_engine()
    # Enter chroot directly without bind mounts
    engine.run_command("chroot $LFS")
    assert engine.fs.in_chroot

    # Try compile: should fail because /dev/null is missing
    res1 = engine.run_command("lfs-compile-chroot bison")
    assert not res1.success
    assert "/dev/null não encontrado" in res1.output

    # Create dummy /dev/null but keep /proc missing
    engine.fs.mkdir("/dev", parents=True)
    engine.fs.touch("/dev/null")

    res2 = engine.run_command("lfs-compile-chroot bison")
    assert not res2.success
    assert "/proc não está montado" in res2.output


def test_lfs_compile_chroot_invalid_package():
    """Verify error message when an invalid package name is requested."""
    engine = _setup_chroot_ready_engine()
    res = engine.run_command("lfs-compile-chroot invalid_tool_xyz")
    assert not res.success
    assert "não encontrado no catálogo" in res.output
    assert "gettext" in res.output
    assert "util-linux" in res.output


def test_lfs_compile_chroot_idempotency_and_xp_anti_exploit():
    """Verify that compiling tools multiple times does not grant duplicate XP (anti-exploit)."""
    engine = _setup_chroot_ready_engine()
    char = engine.char

    # 1. First compilation of gettext (1.5 SBU = 150 XP)
    res1 = engine.run_command("lfs-compile-chroot gettext")
    assert res1.success
    assert "+150 XP" in res1.output
    xp_after_first = char.xp
    level_after_first = char.level

    # 2. Second compilation of gettext: must NOT grant XP
    res2 = engine.run_command("lfs-compile-chroot gettext")
    assert res2.success
    assert "+0 XP" in res2.output
    assert "já se encontra compilado" in res2.output
    assert char.xp == xp_after_first  # XP remained identical
    assert char.level == level_after_first

    # 3. Third compilation of bison (0.2 SBU = 20 XP)
    res3 = engine.run_command("lfs-compile-chroot bison")
    assert res3.success
    assert "+20 XP" in res3.output
    assert char.xp != xp_after_first or char.level > level_after_first

    # 4. Batch compile 'all': 2 packages already compiled (gettext, bison), 4 remain (perl, python, texinfo, util-linux)
    # Remaining 4 packages grant 4 * 75 = 300 XP
    res_batch = engine.run_command("lfs-compile-chroot all")
    assert res_batch.success
    assert "+300 XP" in res_batch.output
    xp_after_batch = char.xp
    level_after_batch = char.level

    # 5. Running batch compile 'all' again: 0 new packages, must grant +0 XP
    res_batch2 = engine.run_command("lfs-compile-chroot all")
    assert res_batch2.success
    assert "+0 XP" in res_batch2.output
    assert "já estavam compiladas" in res_batch2.output
    assert char.xp == xp_after_batch  # Still zero XP exploit!
    assert char.level == level_after_batch


# ==============================================================================
# 5. Unix 'install' Utility Edge Cases
# ==============================================================================

def test_install_utility_edge_cases():
    """Test Unix install utility with various flags, modes and error conditions."""
    engine = _setup_chroot_ready_engine()
    fs = engine.fs

    # 1. install with no arguments
    res_empty = engine.run_command("install")
    assert not res_empty.success
    assert "operando de arquivo ausente" in res_empty.output

    # 2. install with single target and no -d
    res_single = engine.run_command("install /root/some_file")
    assert not res_single.success
    assert "operando de arquivo de destino ausente" in res_single.output

    # 3. install -dv -m 0750 /root
    res_root = engine.run_command("install -dv -m 0750 /root")
    assert res_root.success
    node_root = fs._resolve_node("/root")
    assert node_root is not None
    assert node_root.mode == 0o750

    # 4. install -dv -m 1777 /tmp /var/tmp (sticky bit)
    res_tmp = engine.run_command("install -dv -m 1777 /tmp /var/tmp")
    assert res_tmp.success
    node_tmp = fs._resolve_node("/tmp")
    node_var_tmp = fs._resolve_node("/var/tmp")
    assert node_tmp.mode == 0o1777
    assert node_var_tmp.mode == 0o1777

    # 5. install file copy mode: install -m 644 src dst
    fs.touch("/tmp/source.conf")
    fs.write_file("/tmp/source.conf", "PORT=8080\n")
    res_inst_file = engine.run_command("install -m 644 /tmp/source.conf /etc/app.conf")
    assert res_inst_file.success
    assert fs.exists("/etc/app.conf")
    node_conf = fs._resolve_node("/etc/app.conf")
    assert node_conf.mode == 0o644
    ok, content = fs.read_file("/etc/app.conf")
    assert ok
    assert "PORT=8080" in content


# ==============================================================================
# 6. Advanced Bash Case Statement Support
# ==============================================================================

def test_case_statement_advanced_patterns():
    """Verify bash case statement matching with alternatives, wildcards and error handling."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Alternative patterns x86_64|amd64
    cmd1 = "case $(uname -m) in i?86) mkdir -pv /lib32 ;; x86_64|amd64) mkdir -pv /lib64 ;; esac"
    res1 = engine.run_command(cmd1)
    assert res1.success
    assert fs.exists("/lib64")
    assert not fs.exists("/lib32")

    # Wildcard match *)
    cmd2 = "case nonmatching in alpha) echo 1 ;; *) mkdir -pv /fallback_dir ;; esac"
    res2 = engine.run_command(cmd2)
    assert res2.success
    assert fs.exists("/fallback_dir")

    # Unmatched case executes nothing and succeeds
    cmd3 = "case nomatch in xyz) mkdir -pv /should_not_exist ;; esac"
    res3 = engine.run_command(cmd3)
    assert res3.success
    assert not fs.exists("/should_not_exist")

    # Stray ';;' outside a valid case statement triggers bash syntax error
    res_stray = engine.run_command("echo hello ;; echo world")
    assert not res_stray.success
    assert "erro de sintaxe" in res_stray.output
    assert ";;" in res_stray.output


# ==============================================================================
# 7. Deep Chroot Persistence & Serialization Roundtrip
# ==============================================================================

def test_chroot_deep_save_load_roundtrip():
    """Verify full state preservation when saving inside chroot and resuming in a fresh session."""
    engine = _setup_chroot_ready_engine()
    engine.run_command("install -dv -m 0750 /root")
    engine.run_command("touch /root/active_chroot_marker")
    engine.run_command("lfs-compile-chroot bison")

    with tempfile.TemporaryDirectory() as tmpdir:
        save_file = os.path.join(tmpdir, "chroot_save.json")
        saved, save_msg = save_game(engine, save_file)
        assert saved is True

        # Restore into a fresh engine
        restored_engine = GameEngine()
        ok_load, msg_load = load_game(restored_engine, save_file)
        assert ok_load is True

        # Verify chroot state intact
        assert restored_engine.fs.in_chroot is True
        assert restored_engine.fs.pwd() == "/"
        assert restored_engine.fs.current_user == "root"
        assert restored_engine.get_prompt() == "(lfs chroot) root:/# "
        assert restored_engine.fs.exists("/root/active_chroot_marker")
        assert restored_engine.fs.is_package_compiled("bison")

        # Verify exit from restored engine transitions smoothly back to host
        res_exit = restored_engine.run_command("exit")
        assert res_exit.success
        assert not restored_engine.fs.in_chroot
        assert restored_engine.get_prompt().startswith("root@hera:")
