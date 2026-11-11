"""Comprehensive test suite for Act 3: O Ritual do Chroot e Ferramentas Temporárias Adicionais (LFS 13.1 pt_BR).

Tests:
1. Chown with '--from lfs' ownership transfer to root.
2. Kernel virtual filesystems mounting (/dev bind mount, devpts, proc, sysfs, tmpfs).
3. Entering and exiting chroot jail, prompt string updates, and jail boundary enforcement.
4. Path resolution inside chroot jail (virtual '/' mapping to host '$LFS').
5. Directory hierarchy creation (FHS standard) and 'install -dv -m' utility.
6. Shell 'case $(uname -m) in x86_64) ... ;; esac' matching.
7. Chapter 7 package catalog, SBU telemetry, and compilation (lfs-compile-chroot).
8. Cleanup, documentation strip, and /tools removal.
9. End-to-end Act 3 quest progression and 'Pioneiro do Chroot' title unlock.
10. Didactic glossary entries for chroot, bind-mount, procfs, sysfs, devtmpfs, install.
11. State serialization (save/load) preserving chroot state.
"""

import pytest
from lfs_game.core.engine import GameEngine
from lfs_game.data.lfs_manifest import get_chapter_help, get_toolchain_packages, get_toolchain_package
from lfs_game.data.glossary import glossary_manager


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
    assert engine.fs.current_user == "root"
    assert engine.story_engine.flags["act2_celebrated"] is True
    assert engine.story_engine.current_quest.id == "Q10_CHROOT_PREPARATION"
    return engine


def test_act3_manifest_catalog_and_guides():
    """Verify Chapter 7 packages metadata, SBUs and Portuguese book guide."""
    ch7_pkgs = get_toolchain_packages(chapter=7)
    assert len(ch7_pkgs) == 6

    # Verify specific packages
    gettext_pkg = get_toolchain_package("gettext")
    assert gettext_pkg is not None
    assert gettext_pkg.chapter == 7
    assert gettext_pkg.version == "1.0"
    assert "msgfmt" in gettext_pkg.binaries

    bison_pkg = get_toolchain_package("bison")
    assert bison_pkg is not None
    assert bison_pkg.chapter == 7
    assert bison_pkg.version == "3.8.2"

    perl_pkg = get_toolchain_package("perl")
    assert perl_pkg is not None
    assert perl_pkg.chapter == 7
    assert perl_pkg.version == "5.44.0"

    python_pkg = get_toolchain_package("python")
    assert python_pkg is not None
    assert python_pkg.chapter == 7
    assert python_pkg.version == "3.14.7"

    # Alias check for python3
    python3_alias = get_toolchain_package("python3")
    assert python3_alias is not None
    assert python3_alias.id == "python"

    texinfo_pkg = get_toolchain_package("texinfo")
    assert texinfo_pkg is not None
    assert texinfo_pkg.chapter == 7

    util_linux_pkg = get_toolchain_package("util-linux")
    assert util_linux_pkg is not None
    assert util_linux_pkg.chapter == 7
    assert "mount" in util_linux_pkg.binaries

    # Chapter guide
    guide7 = get_chapter_help(7)
    assert "Capítulo 7" in guide7
    assert "chroot" in guide7
    assert "chown --from lfs" in guide7
    assert "mount -v --bind /dev $LFS/dev" in guide7
    assert "lfs-compile-chroot" in guide7


def test_act3_chown_from_lfs():
    """Verify that 'chown --from lfs -R root:root' only alters files owned by 'lfs'."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Create dummy files: one owned by lfs, one owned by root
    fs.mkdir("/mnt/lfs/usr/local", parents=True)
    fs.touch("/mnt/lfs/usr/local/lfs_file")
    fs.touch("/mnt/lfs/usr/local/root_file")
    fs.chown("/mnt/lfs/usr/local/lfs_file", "lfs:lfs")
    fs.chown("/mnt/lfs/usr/local/root_file", "root:root")

    node_lfs = fs._resolve_node("/mnt/lfs/usr/local/lfs_file")
    node_root = fs._resolve_node("/mnt/lfs/usr/local/root_file")
    assert node_lfs.owner == "lfs"
    assert node_root.owner == "root"

    # Execute chown with --from lfs
    res = engine.run_command("chown --from lfs -R root:root $LFS/usr")
    assert res.success

    # Check that lfs_file was changed to root, but root_file was unchanged
    assert node_lfs.owner == "root"
    assert node_root.owner == "root"

    # Also check $LFS/tools
    res_tools = engine.run_command("chown --from lfs -R root:root $LFS/tools")
    assert res_tools.success
    tools_node = fs._resolve_node("/mnt/lfs/tools")
    assert tools_node.owner == "root"


def test_kernel_virtual_filesystems_mount():
    """Verify mounting bind /dev and virtual filesystems (proc, sysfs, tmpfs, devpts)."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Create directories for mounting
    res_mkdir = engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    assert res_mkdir.success
    assert fs.exists("/mnt/lfs/dev")
    assert fs.exists("/mnt/lfs/proc")
    assert fs.exists("/mnt/lfs/sys")
    assert fs.exists("/mnt/lfs/run")

    # Bind mount /dev
    res_bind = engine.run_command("mount -v --bind /dev $LFS/dev")
    assert res_bind.success
    assert "montagem vinculada" in res_bind.output or "montado" in res_bind.output

    # Dev nodes should now be accessible inside $LFS/dev
    assert fs.exists("/mnt/lfs/dev/null")
    assert fs.exists("/mnt/lfs/dev/zero")

    # Mount devpts
    res_pts = engine.run_command("mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts")
    assert res_pts.success

    # Mount proc, sysfs, tmpfs
    res_proc = engine.run_command("mount -vt proc proc $LFS/proc")
    assert res_proc.success
    assert fs.exists("/mnt/lfs/proc/self/mounts")
    assert fs.exists("/mnt/lfs/proc/cpuinfo")

    res_sys = engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    assert res_sys.success
    assert fs.exists("/mnt/lfs/sys/devices")

    res_run = engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    assert res_run.success

    # Verify mount table output
    res_mount_table = engine.run_command("mount")
    assert res_mount_table.success
    assert "proc" in res_mount_table.output
    assert "sysfs" in res_mount_table.output
    assert "tmpfs" in res_mount_table.output


def test_chroot_transition_and_jail_isolation():
    """Verify entering chroot, prompt update, path translation and exit."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Prepare mounts
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")

    # Initially on host
    assert not fs.in_chroot
    assert engine.get_prompt() == "root@hera:/root# "

    # Enter chroot
    chroot_cmd = (
        'chroot "$LFS" /usr/bin/env -i '
        'HOME=/root TERM="$TERM" PS1=\'(lfs chroot) \\u:\\w\\$ \' '
        'PATH=/usr/bin:/usr/sbin /bin/bash --login'
    )
    res_chroot = engine.run_command(chroot_cmd)
    assert res_chroot.success
    assert "Adentrando o ambiente chroot" in res_chroot.output
    assert fs.in_chroot is True
    assert fs.current_user == "root"
    assert fs.pwd() == "/"
    assert fs.env["HOME"] == "/root"
    assert fs.env["PATH"] == "/usr/bin:/usr/sbin"

    # Prompt check
    assert engine.get_prompt() == "(lfs chroot) root:/# "

    # Jail Boundary: Cannot cd .. beyond root
    res_cd = engine.run_command("cd ..")
    assert res_cd.success
    assert fs.pwd() == "/"
    assert engine.get_prompt() == "(lfs chroot) root:/# "

    # Inside chroot, creating a file at /test_chroot.txt writes to host /mnt/lfs/test_chroot.txt
    res_write = engine.run_command("echo 'pure system' > /test_chroot.txt")
    assert res_write.success
    assert fs.exists("/test_chroot.txt")
    assert fs.exists("/mnt/lfs/test_chroot.txt")

    # Exit chroot back to host
    res_exit = engine.run_command("exit")
    assert res_exit.success
    assert "logout" in res_exit.output
    assert not fs.in_chroot
    assert engine.get_prompt().startswith("root@hera:")

    # From host, /mnt/lfs/test_chroot.txt exists
    assert fs.exists("/mnt/lfs/test_chroot.txt")


def test_install_command_and_directory_tree():
    """Verify 'install -dv -m' utility and standard directory tree creation."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Enter chroot
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    engine.run_command("chroot $LFS")
    assert fs.in_chroot

    # Create root directories
    res_dirs = engine.run_command("mkdir -pv /{boot,home,mnt,opt,srv}")
    assert res_dirs.success
    assert fs.exists("/boot")
    assert fs.exists("/home")
    assert fs.exists("/mnt")

    # Create nested directories
    engine.run_command("mkdir -pv /etc/{opt,sysconfig} /lib/firmware /media/{floppy,cdrom}")
    engine.run_command("mkdir -pv /usr/{,local/}{bin,include,lib,sbin,src}")
    engine.run_command("mkdir -pv /var/{cache,local,log,mail,opt,spool} /var/lib/{color,misc,locate}")
    assert fs.exists("/usr/local/bin")
    assert fs.exists("/var/log")

    # Test install -dv -m 0750 /root
    res_inst_root = engine.run_command("install -dv -m 0750 /root")
    assert res_inst_root.success
    root_node = fs._resolve_node("/root")
    assert root_node is not None
    assert root_node.mode == 0o750

    # Test install -dv -m 1777 /tmp /var/tmp
    res_inst_tmp = engine.run_command("install -dv -m 1777 /tmp /var/tmp")
    assert res_inst_tmp.success
    tmp_node = fs._resolve_node("/tmp")
    var_tmp_node = fs._resolve_node("/var/tmp")
    assert tmp_node is not None
    assert tmp_node.mode == 0o1777
    assert var_tmp_node.mode == 0o1777

    # Test symlinks: /var/run -> /run and /etc/mtab -> /proc/self/mounts
    res_ln = engine.run_command("ln -sfv /run /var/run")
    assert res_ln.success
    res_mtab = engine.run_command("ln -sfv /proc/self/mounts /etc/mtab")
    assert res_mtab.success
    assert fs.exists("/etc/mtab")

    # Read /etc/mtab
    ok, mtab_content = fs.read_file("/etc/mtab")
    assert ok
    assert "proc /proc proc" in mtab_content


def test_shell_case_statement_support():
    """Verify bash 'case $(uname -m) in x86_64) ... ;; esac' matching."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Single-line case
    res1 = engine.run_command("case $(uname -m) in x86_64) mkdir -pv $LFS/lib64 ;; esac")
    assert res1.success
    assert fs.exists("/mnt/lfs/lib64")

    # Multiline case
    multiline_case = """case $(uname -m) in
  x86_64) ln -sfv lib /mnt/lfs/lib64 ;;
esac"""
    res2 = engine.run_command(multiline_case)
    assert res2.success
    assert fs.exists("/mnt/lfs/lib64")

    # Case statement with chown
    res3 = engine.run_command("case $(uname -m) in x86_64) chown --from lfs -R root:root $LFS/lib64 ;; esac")
    assert res3.success


def test_chroot_tools_compilation():
    """Verify compiling Chapter 7 tools (Gettext, Bison, Perl, Python, Texinfo, Util-linux)."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs

    # Prepare chroot
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    engine.run_command("chroot $LFS")

    # Status check before build
    res_status = engine.run_command("lfs-status-chroot")
    assert res_status.success
    assert "Gettext" in res_status.output
    assert "Python 3" in res_status.output
    assert "Util-linux" in res_status.output
    assert "PENDENTE" in res_status.output

    # Compile a single tool: Bison
    res_bison = engine.run_command("lfs-compile-chroot bison")
    assert res_bison.success
    assert "Bison" in res_bison.output
    assert fs.is_package_compiled("bison")
    assert fs.exists("/usr/bin/bison")

    # Compile all remaining Chapter 7 tools
    res_all = engine.run_command("lfs-compile-chroot all")
    assert res_all.success
    assert "Todas as 6 ferramentas" in res_all.output

    # Check compiled packages
    for pkg_id in ["gettext", "bison", "perl", "python", "texinfo", "util-linux"]:
        assert fs.is_package_compiled(pkg_id)

    # Check installed binaries
    assert fs.exists("/usr/bin/msgfmt")
    assert fs.exists("/usr/bin/perl")
    assert fs.exists("/usr/bin/python3")
    assert fs.exists("/usr/bin/makeinfo")
    assert fs.exists("/usr/bin/mount")

    # Status check after build
    res_status2 = engine.run_command("lfs-status-chroot")
    assert "100.0%" in res_status2.output
    assert "INSTALADO" in res_status2.output


def test_full_act3_quest_progression_and_title_unlock():
    """End-to-end walkthrough of Act 3 from Q10 through Q14, culminating in title unlock."""
    engine = _setup_act2_completed_engine()
    fs = engine.fs
    char = engine.char

    # Start: Q10
    assert engine.story_engine.current_quest.id == "Q10_CHROOT_PREPARATION"

    # Step 1: Change owner & mount virtual filesystems
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    res_q10 = engine.run_command("mount -vt tmpfs tmpfs $LFS/run")

    assert "O Ritual do Chroot" in res_q10.output
    assert engine.story_engine.current_quest.id == "Q11_ENTERING_CHROOT"

    # Step 2: Enter Chroot
    res_q11 = engine.run_command("chroot $LFS")
    assert "TRANSLAÇÃO CONCLUÍDA" in res_q11.output
    assert fs.in_chroot
    assert engine.story_engine.current_quest.id == "Q12_CHROOT_BASE_DIRECTORIES"

    # Step 3: Base directories & essential files
    engine.run_command("mkdir -pv /{boot,home,mnt,opt,srv}")
    engine.run_command("mkdir -pv /etc/{opt,sysconfig} /lib/firmware /media/{floppy,cdrom}")
    engine.run_command("mkdir -pv /usr/{,local/}{bin,include,lib,sbin,src}")
    engine.run_command("mkdir -pv /var/{cache,local,log,mail,opt,spool} /var/lib/{color,misc,locate}")
    engine.run_command("install -dv -m 0750 /root")
    engine.run_command("install -dv -m 1777 /tmp /var/tmp")
    res_q12 = engine.run_command("ln -sfv /proc/self/mounts /etc/mtab")

    assert "A espinha dorsal do sistema de arquivos está erguida" in res_q12.output
    assert engine.story_engine.current_quest.id == "Q13_CHROOT_TEMP_TOOLS"

    # Step 4: Compile chapter 7 tools
    res_q13 = engine.run_command("lfs-compile-chroot all")
    assert "Ferramentas do chroot totalmente compiladas" in res_q13.output
    assert engine.story_engine.current_quest.id == "Q14_CLEANUP_AND_STRIP"

    # Step 5: Cleanup and strip /tools
    engine.run_command("rm -rf /usr/share/info/*")
    engine.run_command("find /usr/lib -name '*.la' -delete")
    res_q14 = engine.run_command("rm -rf /tools")

    # Climax check: Act 3 completed & Title unlocked
    assert "ATO 3 CONCLUÍDO COM DISTINÇÃO SUPREMA" in res_q14.output
    assert "Pioneiro do Chroot" in res_q14.output
    assert engine.story_engine.flags["act3_celebrated"] is True
    assert char.title == "Pioneiro do Chroot"
    assert "Pioneiro do Chroot" in char.unlocked_titles


def test_act3_didactic_glossary_entries():
    """Verify didactic explanations for chroot, bind-mount, procfs, sysfs, devtmpfs, install."""
    # 1. chroot
    entry_chroot = glossary_manager.get("chroot")
    assert entry_chroot is not None
    assert "cordão umbilical" in entry_chroot.why_in_lfs
    assert "sobrescreverão as bibliotecas" in entry_chroot.danger_if_missed

    # 2. bind-mount
    entry_bind = glossary_manager.get("bind-mount")
    assert entry_bind is not None
    assert "espelha" in entry_bind.what_it_does
    assert "/dev" in entry_bind.why_in_lfs
    assert "/dev/null" in entry_bind.danger_if_missed

    # Alias check for 'mount --bind'
    assert glossary_manager.get("mount --bind") == entry_bind

    # 3. procfs
    entry_proc = glossary_manager.get("procfs")
    assert entry_proc is not None
    assert "memória RAM" in entry_proc.what_it_does
    assert "/proc" in entry_proc.why_in_lfs

    # 4. sysfs
    entry_sys = glossary_manager.get("sysfs")
    assert entry_sys is not None
    assert "dispositivos" in entry_sys.what_it_does
    assert "udev" in entry_sys.why_in_lfs or "GRUB" in entry_sys.danger_if_missed

    # 5. devtmpfs
    entry_dev = glossary_manager.get("devtmpfs")
    assert entry_dev is not None
    assert "nós de dispositivos" in entry_dev.what_it_does

    # 6. install
    entry_inst = glossary_manager.get("install")
    assert entry_inst is not None
    assert "mkdir" in entry_inst.what_it_does
    assert "chmod" in entry_inst.what_it_does
    assert "0750" in entry_inst.why_in_lfs
    assert "1777" in entry_inst.why_in_lfs
    assert "sticky bit" in entry_inst.why_in_lfs


def test_act3_save_and_load_chroot_state():
    """Verify that saving and loading state while in chroot properly restores in_chroot."""
    engine = _setup_act2_completed_engine()
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("chroot $LFS")
    assert engine.fs.in_chroot is True

    # Save state to dict
    saved_state = engine.to_dict()
    assert saved_state["fs"]["in_chroot"] is True
    assert saved_state["fs"]["cwd"] == "/"

    # Create new engine and restore
    new_engine = GameEngine()
    new_engine.from_dict(saved_state)
    assert new_engine.fs.in_chroot is True
    assert new_engine.fs.current_user == "root"
    assert new_engine.fs.pwd() == "/"
    assert new_engine.get_prompt() == "(lfs chroot) root:/# "
