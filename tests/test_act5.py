"""Comprehensive test suite for Act 5: Capítulos 9 e 10 do LFS 13.1 pt_BR.

Covers:
1. Manifest entries (`lfs-bootscripts`, `linux-kernel`) and `lfs-book 9` / `lfs-book 10`.
2. Chroot enforcement guard on Act 5 commands (while preserving Act 2 `make mrproper`).
3. Multiline Heredoc parsing (`<< "EOF"`, `<< EOF`, `<< 'EOF'`, redirections, variable expansion).
4. Chapter 9 Bootscripts, Network, and SysVinit/Shell configuration (both manual files and helpers) + idempotency.
5. `/etc/fstab` validation (rejecting incomplete/wrong fstab, accepting `/dev/sda3 /` + `/dev/sda2 swap`).
6. Chapter 10 Kernel 7.1.8 `menuconfig`, `defconfig`, `lfs-kernel-config` validation, compilation (`make -j4`), `make modules_install`, and `cp` to `/boot/vmlinuz-7.1.8-lfs-13.1`.
7. GRUB (`grub-install /dev/sda`, `grub-mkconfig -o /boot/grub/grub.cfg`, `lfs-config-grub`, and manual `grub.cfg`).
8. Full quest progression Q20 -> Q23, title unlock 'Forjador do Kernel', and Act 6 readiness message.
9. Chapter 9 & 10 didactic glossary entries (without breaking Act 4 `grub-install` -> `grub` alias).
10. Save/Load roundtrip of Act 5 state and seamless upgrade from Act 4 save to Q20-Q23.
"""

from __future__ import annotations
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.data.glossary import glossary_manager
from lfs_game.data.lfs_manifest import (
    get_chapter_help,
    get_toolchain_package,
    get_toolchain_packages,
)


def _setup_act4_completed_engine() -> GameEngine:
    """Fast-forwards through Acts 1–4 to reach the start of Act 5 (Q20 inside chroot)."""
    engine = GameEngine()
    fs = engine.fs

    # --- Act 1 ---
    engine.run_command("1")
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
    engine.run_command("exit")
    engine.run_command("cd /root")

    # --- Act 3 ---
    engine.run_command("chown --from lfs -R root:root $LFS/{usr,var,etc,tools}")
    engine.run_command("mkdir -pv $LFS/{dev,proc,sys,run}")
    engine.run_command("mount -v --bind /dev $LFS/dev")
    engine.run_command("mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts")
    engine.run_command("mount -vt proc proc $LFS/proc")
    engine.run_command("mount -vt sysfs sysfs $LFS/sys")
    engine.run_command("mount -vt tmpfs tmpfs $LFS/run")
    engine.run_command("chroot $LFS")
    engine.run_command("mkdir -pv /{boot,home,mnt,opt,srv,etc/sysconfig}")
    engine.run_command("install -dv -m 0750 /root")
    engine.run_command("install -dv -m 1777 /tmp /var/tmp")
    engine.run_command("ln -sfv /proc/self/mounts /etc/mtab")
    engine.run_command("lfs-compile-chroot all")
    engine.run_command("rm -rf /tools")

    # --- Act 4 ---
    engine.run_command("lfs-compile-system tier1")
    engine.run_command("make check")
    engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    engine.run_command("lfs-compile-system tier2")
    engine.run_command("pwconv")
    engine.run_command("grpconv")
    engine.run_command("passwd root")
    engine.run_command("exec /usr/bin/bash --login")
    engine.run_command("lfs-compile-system tier3")
    engine.run_command("lfs-compile-system tier4")
    engine.run_command("udev-hwdb update")
    engine.run_command("lfs-strip")

    assert engine.fs.in_chroot is True
    assert engine.story_engine.flags["act4_celebrated"] is True
    assert engine.story_engine.current_quest.id == "Q20_SYSTEM_CONFIG_NETWORK"
    return engine


def test_act5_manifest_packages_and_book_guides():
    """Verify Chapter 9 & 10 packages in TOOLCHAIN_CATALOG and lfs-book 9 / 10."""
    bootscripts = get_toolchain_package("lfs-bootscripts")
    assert bootscripts is not None
    assert bootscripts.version == "20250827"
    assert bootscripts.chapter == 9
    assert bootscripts.sbu == 0.1

    kernel = get_toolchain_package("linux-kernel")
    assert kernel is not None
    assert kernel.version == "7.1.8"
    assert kernel.chapter == 10
    assert kernel.sbu == 3.5

    assert [p.id for p in get_toolchain_packages(chapter=9)] == ["lfs-bootscripts"]
    assert [p.id for p in get_toolchain_packages(chapter=10)] == ["linux-kernel"]

    guide9 = get_chapter_help(9)
    assert "Capítulo 9" in guide9
    assert "LFS-Bootscripts-20250827" in guide9
    assert "/etc/inittab" in guide9
    assert "/etc/hostname" in guide9

    guide10 = get_chapter_help(10)
    assert "Capítulo 10" in guide10
    assert "Linux 7.1.8" in guide10
    assert "/etc/fstab" in guide10
    assert "grub-install /dev/sda" in guide10
    assert "vmlinuz-7.1.8-lfs-13.1" in guide10


def test_act5_commands_blocked_outside_chroot():
    """Verify all Act 5 commands require chroot while Act 2 make mrproper still works on host."""
    engine = GameEngine()
    assert engine.fs.in_chroot is False

    # Act 2 host make mrproper still works
    res_mrp = engine.run_command("make mrproper")
    assert res_mrp.success

    blocked_cmds = [
        "lfs-install-bootscripts",
        "lfs-config-network",
        "lfs-config-system",
        "lfs-check-config",
        "make menuconfig",
        "make defconfig",
        "lfs-kernel-config",
        "lfs-compile-kernel",
        "make modules_install",
        "grub-install /dev/sda",
        "grub-mkconfig -o /boot/grub/grub.cfg",
        "lfs-config-grub",
    ]
    for cmd in blocked_cmds:
        res = engine.run_command(cmd)
        assert not res.success, f"Command '{cmd}' must fail outside chroot!"
        assert "chroot" in res.output.lower()


def test_heredoc_multiline_creation_and_quoting():
    """Verify multiline heredocs (<< \"EOF\", << 'EOF', << EOF) preserve ; | && and handle var expansion."""
    engine = GameEngine()
    engine.run_command("export TEST_HOST=hera-station")

    # 1. Quoted delimiter preserves $TEST_HOST literally and preserves semicolons/pipes
    cmd_quoted = (
        'cat > /etc/test_quoted << "EOF"\n'
        '# comment with ; and && and |\n'
        'HOST=$TEST_HOST\n'
        'id:3:initdefault:\n'
        'EOF'
    )
    res_q = engine.run_command(cmd_quoted)
    assert res_q.success
    ok, content_q = engine.fs.read_file("/etc/test_quoted")
    assert ok
    assert "# comment with ; and && and |" in content_q
    assert "HOST=$TEST_HOST" in content_q
    assert "id:3:initdefault:" in content_q

    # 2. Unquoted delimiter expands $TEST_HOST and supports redirect before <<
    cmd_unquoted = (
        'cat << EOF > /etc/test_unquoted\n'
        'HOST=$TEST_HOST\n'
        'EOF'
    )
    res_u = engine.run_command(cmd_unquoted)
    assert res_u.success
    ok, content_u = engine.fs.read_file("/etc/test_unquoted")
    assert ok
    assert "HOST=hera-station" in content_u

    # 3. Append mode with single-quoted delimiter
    cmd_append = (
        "cat >> /etc/test_unquoted << 'EOF'\n"
        "SECOND_LINE=true\n"
        "EOF"
    )
    res_a = engine.run_command(cmd_append)
    assert res_a.success
    ok, content_a = engine.fs.read_file("/etc/test_unquoted")
    assert ok
    assert "HOST=hera-station" in content_a
    assert "SECOND_LINE=true" in content_a

    # 4. Missing closing delimiter returns syntax error
    res_err = engine.run_command('cat > /etc/broken << "EOF"\nline1\n')
    assert not res_err.success


def test_act5_chapter9_manual_and_helper_config_and_idempotency():
    """Verify Chapter 9 bootscripts, manual heredoc network/sysconfig, helper commands, and XP idempotency."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # Install bootscripts via make install inside extracted tarball dir
    assert engine.run_command("cd /sources").success
    assert engine.run_command("tar -xf lfs-bootscripts-20250827.tar.xz").success
    assert engine.run_command("cd lfs-bootscripts-20250827").success
    res_bs = engine.run_command("make install")
    assert res_bs.success
    assert fs.bootscripts_installed is True
    assert fs.exists("/etc/rc.d/init.d/rc")
    assert fs.exists("/lib/services/ipv4-static")

    # Idempotency on lfs-install-bootscripts (+0 XP)
    lvl, xp = engine.char.level, engine.char.xp
    res_bs_again = engine.run_command("lfs-install-bootscripts")
    assert res_bs_again.success
    assert (engine.char.level, engine.char.xp) == (lvl, xp)

    # Configure network manually using echo and heredoc
    assert engine.run_command('echo "hera-lfs" > /etc/hostname').success
    assert engine.run_command(
        'cat > /etc/hosts << "EOF"\n'
        '127.0.0.1 localhost.localdomain localhost\n'
        '127.0.1.1 hera-lfs.hera.local hera-lfs\n'
        'EOF'
    ).success
    assert engine.run_command(
        'cat > /etc/resolv.conf << "EOF"\n'
        'nameserver 10.0.2.3\n'
        'EOF'
    ).success
    assert engine.run_command(
        'cat > /etc/sysconfig/ifconfig.eth0 << "EOF"\n'
        'ONBOOT=yes\n'
        'IFACE=eth0\n'
        'SERVICE=ipv4-static\n'
        'IP=192.168.1.2\n'
        'EOF'
    ).success
    assert fs.network_configured is True

    # Configure SysVinit & Shell manually via heredoc
    assert engine.run_command(
        'cat > /etc/inittab << "EOF"\n'
        'id:3:initdefault:\n'
        'si::sysinit:/etc/rc.d/init.d/rc S\n'
        '1:2345:respawn:/sbin/agetty --noclear tty1 9600\n'
        'EOF'
    ).success
    assert engine.run_command('echo "export LANG=pt_BR.UTF-8" > /etc/profile').success
    assert engine.run_command('echo "set bell-style none" > /etc/inputrc').success
    res_shells = engine.run_command(
        'cat > /etc/shells << "EOF"\n'
        '/bin/sh\n'
        '/bin/bash\n'
        'EOF'
    )
    assert res_shells.success
    assert fs.sysconfig_configured is True

    # Manual completion must advance Q20 -> Q21!
    assert engine.story_engine.current_quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG"
    assert engine.story_engine.flags["system_configured"] is True

    # Helper commands also work cleanly and stay idempotent on XP
    lvl2, xp2 = engine.char.level, engine.char.xp
    assert engine.run_command("lfs-config-network hera-alpha").success
    ok, host_txt = fs.read_file("/etc/hostname")
    assert ok and host_txt.strip() == "hera-alpha"
    assert engine.run_command("lfs-config-system").success
    assert (engine.char.level, engine.char.xp) == (lvl2, xp2)

    res_chk = engine.run_command("lfs-check-config")
    assert res_chk.success
    assert "LFS-Bootscripts" in res_chk.output


def test_act5_fstab_and_kernel_menuconfig_compilation_and_grub():
    """Verify fstab validation, kernel menuconfig toggling, compilation, modules_install, bzImage copy, and GRUB."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # Complete Chapter 9 using helpers
    assert engine.run_command("lfs-install-bootscripts").success
    assert engine.run_command("lfs-config-network hera-lfs").success
    assert engine.run_command("lfs-config-system").success
    assert engine.story_engine.current_quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG"

    # Invalid /etc/fstab (missing swap) must NOT mark fstab_configured
    assert engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '/dev/sda3 / ext4 defaults 1 1\n'
        'EOF'
    ).success
    assert fs.fstab_configured is False

    # Valid /etc/fstab
    assert engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '# Begin /etc/fstab\n'
        '/dev/sda3     /            ext4     defaults            1     1\n'
        '/dev/sda2     swap         swap     pri=1               0     0\n'
        'proc          /proc        proc     nosuid,noexec,nodev 0     0\n'
        'EOF'
    ).success
    assert fs.fstab_configured is True

    # Kernel cannot compile before .config is created
    assert engine.run_command("cd /sources").success
    assert engine.run_command("tar -xf linux-7.1.8.tar.xz").success
    assert engine.run_command("cd linux-7.1.8").success
    assert engine.run_command("make mrproper").success
    assert not engine.run_command("make -j4").success

    # Open menuconfig -> shows 7 critical subsystems and writes .config
    res_mc = engine.run_command("make menuconfig")
    assert res_mc.success
    for flag in (
        "CONFIG_64BIT",
        "CONFIG_DEVTMPFS",
        "CONFIG_DEVTMPFS_MOUNT",
        "CONFIG_EXT4_FS",
        "CONFIG_SATA_AHCI",
        "CONFIG_BINFMT_ELF",
        "CONFIG_NET",
    ):
        assert flag in res_mc.output
    assert fs.kernel_configured is True
    assert fs.exists("/sources/linux-7.1.8/.config")
    assert engine.story_engine.current_quest.id == "Q22_KERNEL_FORGE"

    # Toggling critical CONFIG_EXT4_FS=m warns and blocks kernel compilation
    res_mod = engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=m")
    assert res_mod.success
    assert "ALERTA KERNEL PANIC" in res_mod.output
    res_fail_build = engine.run_command("make -j4")
    assert not res_fail_build.success
    assert "CONFIG_EXT4_FS=m" in res_fail_build.output

    # Restore built-in [y] and compile kernel
    assert engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=y").success
    temp_before = engine.telemetry.temperature
    res_build = engine.run_command("make -j4")
    assert res_build.success
    assert fs.kernel_compiled is True
    assert fs.is_package_compiled("linux-kernel")
    assert engine.telemetry.temperature > temp_before
    assert fs.exists("/sources/linux-7.1.8/arch/x86/boot/bzImage")
    assert fs.exists("/sources/linux-7.1.8/System.map")

    # Install modules & copy bzImage/System.map/.config to /boot
    res_mods = engine.run_command("make modules_install")
    assert res_mods.success
    assert fs.exists("/lib/modules/7.1.8/modules.dep")

    assert engine.run_command("cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1").success
    assert engine.run_command("cp -iv System.map /boot/System.map-7.1.8").success
    assert engine.run_command("cp -iv .config /boot/config-7.1.8").success
    assert fs.kernel_installed is True
    assert engine.story_engine.current_quest.id == "Q23_GRUB_BOOTLOADER"
    assert engine.story_engine.flags["kernel_forged"] is True

    # GRUB validation: invalid device fails
    assert not engine.run_command("grub-install /dev/null").success
    res_gi = engine.run_command("grub-install /dev/sda")
    assert res_gi.success
    assert fs.grub_mbr_installed is True

    # Invalid manual grub.cfg (wrong root) does not trigger grub_cfg_created
    assert engine.run_command("mkdir -pv /boot/grub").success
    assert engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'linux /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda1 ro\n'
        'EOF'
    ).success
    assert fs.grub_cfg_created is False
    assert not engine.story_engine.flags["act5_celebrated"]

    # Valid grub-mkconfig completes Q23 & unlocks "Forjador do Kernel"
    res_gcfg = engine.run_command("grub-mkconfig -o /boot/grub/grub.cfg")
    assert res_gcfg.success
    assert fs.grub_cfg_created is True
    assert engine.story_engine.flags["act5_celebrated"] is True
    assert engine.char.title == "Forjador do Kernel"
    assert "Forjador do Kernel" in engine.char.unlocked_titles
    assert "ATO 5 CONCLUÍDO" in res_gcfg.output
    assert "Forjador do Kernel" in res_gcfg.output
    assert "Ato 6" in res_gcfg.output


def test_act5_manual_grub_cfg_and_grub_prerequisite():
    """Verify grub-install fails if grub package wasn't compiled, and manual grub.cfg completes Q23."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # Simulate grub not compiled
    fs.compiled_packages.discard("grub")
    res_no_grub = engine.run_command("grub-install /dev/sda")
    assert not res_no_grub.success
    assert "GRUB" in res_no_grub.output

    # Recompile grub and progress to Q23
    assert engine.run_command("lfs-compile-system grub").success
    assert engine.run_command("lfs-install-bootscripts").success
    assert engine.run_command("lfs-config-network").success
    assert engine.run_command("lfs-config-system").success
    assert engine.run_command(
        'cat > /etc/fstab << "EOF"\n/dev/sda3 / ext4 defaults 1 1\n/dev/sda2 swap swap pri=1 0 0\nEOF'
    ).success
    assert engine.run_command("make defconfig").success
    assert engine.run_command("lfs-compile-kernel").success
    assert engine.run_command("make modules_install").success
    assert engine.run_command("cp /sources/linux-7.1.8/arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1").success
    assert engine.story_engine.current_quest.id == "Q23_GRUB_BOOTLOADER"

    assert engine.run_command("grub-install /dev/sda").success
    res_manual_cfg = engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'set default=0\n'
        'set timeout=5\n'
        'menuentry "LFS 13.1" {\n'
        '    linux /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda3 ro\n'
        '}\n'
        'EOF'
    )
    assert res_manual_cfg.success
    assert fs.grub_cfg_created is True
    assert engine.story_engine.flags["act5_celebrated"] is True
    assert engine.char.title == "Forjador do Kernel"


def test_act5_didactic_glossary_entries():
    """Verify Chapter 9 & 10 didactic glossary entries resolve cleanly without breaking Act 4 aliases."""
    expected_terms = [
        ("lfs-bootscripts", ["bootscripts", "lfs-install-bootscripts"]),
        ("hostname", ["/etc/hostname", "/etc/hosts"]),
        ("inittab", ["/etc/inittab", "runlevel"]),
        ("inputrc", ["/etc/inputrc", "/etc/shells"]),
        ("fstab", ["/etc/fstab"]),
        ("menuconfig", ["make menuconfig", "lfs-kernel-config"]),
        ("bzimage", ["vmlinuz", "vmlinuz-7.1.8-lfs-13.1"]),
        ("grub", ["grub-install", "bootloader"]),
        ("grub.cfg", ["grub-mkconfig", "/boot/grub/grub.cfg"]),
    ]
    for canonical, aliases in expected_terms:
        entry = glossary_manager.get(canonical)
        assert entry is not None, f"Missing glossary entry '{canonical}'"
        assert len(entry.what_it_does) >= 30
        assert len(entry.why_in_lfs) >= 30
        assert len(entry.danger_if_missed) >= 30
        for alias in aliases:
            resolved = glossary_manager.get(alias)
            assert resolved is not None and resolved.term == canonical


def test_act5_save_load_roundtrip_and_act4_upgrade():
    """Verify Save/Load preserves Act 5 state and legacy Act 4 saves upgrade cleanly to Q20-Q23."""
    engine = _setup_act4_completed_engine()
    engine.run_command("lfs-install-bootscripts")
    engine.run_command("lfs-config-network hera-node")
    engine.run_command("lfs-config-system")
    engine.run_command('cat > /etc/fstab << "EOF"\n/dev/sda3 / ext4 defaults 1 1\n/dev/sda2 swap swap pri=1 0 0\nEOF')
    engine.run_command("lfs-kernel-config CONFIG_NET=n")

    saved = engine.to_dict()
    assert saved["fs"]["bootscripts_installed"] is True
    assert saved["fs"]["network_configured"] is True
    assert saved["fs"]["sysconfig_configured"] is True
    assert saved["fs"]["fstab_configured"] is True
    assert saved["fs"]["kernel_configured"] is True
    assert saved["fs"]["kernel_config"]["CONFIG_NET"] == "n"

    restored = GameEngine()
    restored.from_dict(saved)
    assert restored.fs.bootscripts_installed is True
    assert restored.fs.network_configured is True
    assert restored.fs.sysconfig_configured is True
    assert restored.fs.fstab_configured is True
    assert restored.fs.kernel_configured is True
    assert restored.fs.kernel_config["CONFIG_NET"] == "n"
    assert restored.story_engine.current_quest.id == "Q22_KERNEL_FORGE"

    # Legacy Act 4 save upgrade (missing Q20-Q23 & Act 5 fields)
    act4_save = engine.to_dict()
    for key in (
        "bootscripts_installed", "network_configured", "sysconfig_configured",
        "fstab_configured", "kernel_config", "kernel_configured",
        "kernel_compiled", "kernel_installed", "grub_mbr_installed", "grub_cfg_created",
    ):
        act4_save["fs"].pop(key, None)
    act4_save["story_engine"]["quests"] = [
        q for q in act4_save["story_engine"]["quests"]
        if not q["id"].startswith(("Q20_", "Q21_", "Q22_", "Q23_"))
    ]
    act4_save["story_engine"]["current_quest_index"] = 20
    for flg in ("system_configured", "kernel_forged", "act5_celebrated"):
        act4_save["story_engine"]["flags"].pop(flg, None)

    upgraded = GameEngine()
    upgraded.from_dict(act4_save)
    assert len(upgraded.story_engine.quests) == 24
    assert upgraded.story_engine.current_quest.id == "Q20_SYSTEM_CONFIG_NETWORK"
    assert upgraded.fs.kernel_config["CONFIG_EXT4_FS"] == "y"
    assert upgraded.story_engine.flags["act5_celebrated"] is False
