"""Comprehensive test suite for Act 4: Capítulo 8 do LFS 13.1 pt_BR - A Edificação da Alma do Sistema.

Tests:
1. Chapter 8 package catalog across 4 Tiers (81 packages), tier attribute, SYSTEM_TIERS, and lfs-book 8.
2. Chroot enforcement guard on Act 4 compilation & configuration commands.
3. Individual, Tier-based, and full batch compilation (lfs-compile-system) + binary paths in /usr/{bin,sbin,lib}.
4. Idempotency & anti-XP exploit across packages, tiers, test suites, and milestones.
5. make check / make -k check for glibc, binutils, and gcc.
6. localedef, pwconv, grpconv, passwd root, exec /usr/bin/bash --login, udev-hwdb update, and lfs-strip / strip.
7. lfs-status-system summary and tier detail views.
8. Act 4 didactic glossary entries and insights.
9. Full quest progression from Q15 through Q19 and unlocking title 'Arquiteto do Sistema'.
10. Save/Load roundtrip preservation of Act 4 state.
"""

from __future__ import annotations
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.data.lfs_manifest import (
    SYSTEM_TIERS,
    get_chapter_help,
    get_system_package,
    get_system_packages,
    get_toolchain_packages,
)
from lfs_game.data.glossary import glossary_manager


def _setup_act3_completed_engine() -> GameEngine:
    """Fast-forwards through Acts 1, 2, and 3 to reach the start of Act 4 (Q15 inside chroot)."""
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
    engine.run_command("mkdir -pv /{boot,home,mnt,opt,srv}")
    engine.run_command("install -dv -m 0750 /root")
    engine.run_command("install -dv -m 1777 /tmp /var/tmp")
    engine.run_command("ln -sfv /proc/self/mounts /etc/mtab")
    engine.run_command("lfs-compile-chroot all")
    engine.run_command("rm -rf /tools")

    assert engine.fs.in_chroot is True
    assert engine.story_engine.flags["act3_celebrated"] is True
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"
    return engine


def test_act4_manifest_tiers_and_book_guide():
    """Verify all 4 Tiers (81 packages), tier attribute defaults, SYSTEM_TIERS, and lfs-book 8."""
    # Chapters 5-7 retain tier == 0
    for ch in (5, 6, 7):
        for pkg in get_toolchain_packages(chapter=ch):
            assert pkg.tier == 0

    assert len(SYSTEM_TIERS) == 4
    tier1 = get_system_packages(tier=1)
    tier2 = get_system_packages(tier=2)
    tier3 = get_system_packages(tier=3)
    tier4 = get_system_packages(tier=4)
    all_sys = get_system_packages()

    assert len(tier1) == 19
    assert len(tier2) == 19
    assert len(tier3) == 20
    assert len(tier4) == 23
    assert len(all_sys) == 81

    assert [p.id for p in tier1] == [
        "man-pages", "iana-etc", "glibc-final", "zlib", "bzip2", "xz-final",
        "lz4", "zstd", "file-final", "readline", "pcre2", "m4-final",
        "bc", "flex", "tcl", "expect", "dejagnu", "ninja", "pkgconf",
    ]
    assert [p.id for p in tier2] == [
        "binutils-final", "gmp", "mpfr", "mpc", "attr", "acl", "libcap",
        "libxcrypt", "shadow", "gawk-final", "gcc-final", "ncurses-final",
        "sed-final", "psmisc", "gettext-final", "bison-final", "grep-final",
        "bash-final", "libtool",
    ]
    assert [p.id for p in tier3] == [
        "gdbm", "gperf", "expat", "inetutils", "less", "perl-final",
        "autoconf", "automake", "openssl", "libelf", "libffi", "sqlite",
        "mpdecimal-final", "python-final", "flit-core", "packaging",
        "wheel", "setuptools", "meson", "kmod",
    ]
    assert [p.id for p in tier4] == [
        "coreutils-final", "diffutils-final", "findutils-final", "groff",
        "grub", "gzip-final", "iproute2", "kbd", "libpipeline", "make-final",
        "patch-final", "tar-final", "texinfo-final", "vim", "markupsafe",
        "jinja2", "udev", "man-db", "procps-ng", "util-linux-final",
        "e2fsprogs", "sysklogd", "sysvinit",
    ]

    # Alias lookup for Chapter 8
    assert get_system_package("glibc").id == "glibc-final"
    assert get_system_package("gcc").id == "gcc-final"
    assert get_system_package("bash").id == "bash-final"
    assert get_system_package("python3").id == "python-final"
    assert get_system_package("openssl").tier == 3
    assert get_system_package("sysvinit").tier == 4

    # Portuguese guide for Chapter 8
    guide8 = get_chapter_help(8)
    assert "Capítulo 8" in guide8
    assert "Tier 1" in guide8 and "Tier 4" in guide8
    assert "lfs-compile-system" in guide8
    assert "localedef" in guide8
    assert "pwconv" in guide8
    assert "udev-hwdb update" in guide8
    assert "lfs-strip" in guide8


def test_act4_commands_blocked_outside_chroot():
    """Verify Act 4 compilation & configuration commands fail cleanly outside chroot."""
    engine = GameEngine()
    assert engine.fs.in_chroot is False

    blocked_cmds = [
        "lfs-compile-system tier1",
        "lfs-compile-system glibc-final",
        "make check",
        "make -k check",
        "localedef -i pt_BR -f UTF-8 pt_BR.UTF-8",
        "pwconv",
        "grpconv",
        "passwd root",
        "exec /usr/bin/bash --login",
        "udev-hwdb update",
        "lfs-strip",
        "strip --strip-debug",
    ]
    for cmd in blocked_cmds:
        res = engine.run_command(cmd)
        assert not res.success, f"Command '{cmd}' should fail outside chroot!"
        assert "chroot" in res.output.lower()


def test_act4_compile_system_packages_tiers_and_idempotency():
    """Verify compiling single packages, tiers, binary paths, and zero-XP idempotency."""
    engine = _setup_act3_completed_engine()
    fs = engine.fs

    # Invalid package fails
    res_bad = engine.run_command("lfs-compile-system pacote-inexistente")
    assert not res_bad.success
    assert "não encontrado" in res_bad.output

    # Single package: glibc-final prompts make check & localedef
    res_glibc = engine.run_command("lfs-compile-system glibc-final")
    assert res_glibc.success
    assert fs.is_package_compiled("glibc-final")
    assert "make check" in res_glibc.output
    assert "localedef" in res_glibc.output
    assert fs.exists("/usr/lib/libc.so.6")
    assert fs.exists("/usr/bin/localedef")

    # Idempotent single package recompile -> +0 XP
    lvl_before, xp_before = engine.char.level, engine.char.xp
    res_glibc_again = engine.run_command("lfs-compile-system glibc-final")
    assert res_glibc_again.success
    assert "+0 XP" in res_glibc_again.output
    assert (engine.char.level, engine.char.xp) == (lvl_before, xp_before)

    # Compile rest of Tier 1
    res_t1 = engine.run_command("lfs-compile-system tier1")
    assert res_t1.success
    assert "+18 novos" in res_t1.output
    for p in get_system_packages(tier=1):
        assert fs.is_package_compiled(p.id)

    # Idempotent Tier 1 recompile -> +0 XP
    lvl_t1, xp_t1 = engine.char.level, engine.char.xp
    res_t1_again = engine.run_command("lfs-compile-system tier1")
    assert res_t1_again.success
    assert "+0 XP" in res_t1_again.output
    assert (engine.char.level, engine.char.xp) == (lvl_t1, xp_t1)

    # Compile Tier 2, Tier 3, Tier 4 and verify /usr/sbin & /usr/lib & /usr/bin binaries
    assert engine.run_command("lfs-compile-system tier2").success
    assert fs.exists("/usr/sbin/pwconv")
    assert fs.exists("/usr/bin/gcc")
    assert fs.exists("/usr/bin/bash")

    assert engine.run_command("lfs-compile-system tier3").success
    assert fs.exists("/usr/bin/openssl")
    assert fs.exists("/usr/bin/meson")
    assert fs.exists("/usr/bin/kmod")

    assert engine.run_command("lfs-compile-system tier4").success
    assert fs.exists("/usr/sbin/grub-install")
    assert fs.exists("/usr/sbin/init")
    assert fs.exists("/usr/bin/udevadm")

    # Re-running 'lfs-compile-system all' yields +0 XP
    lvl_all, xp_all = engine.char.level, engine.char.xp
    res_all_again = engine.run_command("lfs-compile-system all")
    assert res_all_again.success
    assert "+0 XP" in res_all_again.output
    assert (engine.char.level, engine.char.xp) == (lvl_all, xp_all)


def test_act4_make_check_suites_and_idempotency():
    """Verify make check and make -k check for glibc, binutils, and gcc."""
    engine = _setup_act3_completed_engine()
    fs = engine.fs

    # Cannot run make check before compiling glibc/binutils/gcc
    res_early = engine.run_command("make check")
    assert not res_early.success

    # Compile Tier 1 + Tier 2
    engine.run_command("lfs-compile-system tier1")
    engine.run_command("lfs-compile-system tier2")

    # 1. make check -> runs glibc
    res_glibc_chk = engine.run_command("make check")
    assert res_glibc_chk.success
    assert "Glibc 2.44 Test Suite" in res_glibc_chk.output
    assert "glibc" in fs.system_checks_passed

    # 2. make -k check -> runs gcc
    res_gcc_chk = engine.run_command("make -k check")
    assert res_gcc_chk.success
    assert "GCC 16.2.0 Test Suite" in res_gcc_chk.output
    assert "gcc" in fs.system_checks_passed

    # 3. make check -> runs binutils (next unchecked suite)
    res_bin_chk = engine.run_command("make check")
    assert res_bin_chk.success
    assert "Binutils 2.47 Test Suite" in res_bin_chk.output
    assert "binutils" in fs.system_checks_passed

    # 4. Idempotency: running make check glibc again gives +0 XP
    lvl, xp = engine.char.level, engine.char.xp
    res_repeat = engine.run_command("make check glibc")
    assert res_repeat.success
    assert "+0 XP" in res_repeat.output
    assert (engine.char.level, engine.char.xp) == (lvl, xp)


def test_act4_system_milestones_and_status_display():
    """Verify localedef, pwconv, grpconv, passwd, exec bash, udev-hwdb, lfs-strip, and lfs-status-system."""
    engine = _setup_act3_completed_engine()
    fs = engine.fs

    # Prerequisites check: localedef needs glibc-final, pwconv needs shadow, exec needs bash-final, udev-hwdb needs udev
    assert not engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8").success
    assert not engine.run_command("pwconv").success
    assert not engine.run_command("exec /usr/bin/bash --login").success
    assert not engine.run_command("udev-hwdb update").success

    # Compile all tiers
    engine.run_command("lfs-compile-system all")

    # 1. localedef
    res_loc = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert res_loc.success
    assert fs.locales_configured is True
    assert fs.exists("/usr/lib/locale/locale-archive")
    ok_loc, loc_content = fs.read_file("/usr/lib/locale/locale-archive")
    assert ok_loc and "pt_BR.UTF-8" in loc_content

    engine.run_command("localedef -i C.UTF-8 -f UTF-8 C.UTF-8")
    ok_loc2, loc_content2 = fs.read_file("/usr/lib/locale/locale-archive")
    assert ok_loc2 and "C.UTF-8" in loc_content2

    # 2. pwconv, grpconv, passwd root
    res_pw = engine.run_command("pwconv")
    assert res_pw.success
    assert fs.shadow_configured is True
    assert fs.exists("/etc/shadow")
    assert fs._resolve_node("/etc/shadow").mode == 0o600

    res_grp = engine.run_command("grpconv")
    assert res_grp.success
    assert fs.exists("/etc/gshadow")

    res_passwd = engine.run_command("passwd root")
    assert res_passwd.success
    assert fs.root_password_set is True
    ok_sh, sh_content = fs.read_file("/etc/shadow")
    assert ok_sh and "$y$" in sh_content

    # 3. exec /usr/bin/bash --login
    res_exec = engine.run_command("exec /usr/bin/bash --login")
    assert res_exec.success
    assert fs.bash_restarted is True
    assert fs.env["SHELL"] == "/usr/bin/bash"

    # 4. udev-hwdb update
    res_udev = engine.run_command("udev-hwdb update")
    assert res_udev.success
    assert fs.udev_updated is True
    assert fs.exists("/etc/udev/hwdb.bin")

    # 5. lfs-strip / strip
    ram_before = engine.telemetry.ram_mb
    res_strip = engine.run_command("lfs-strip")
    assert res_strip.success
    assert fs.debug_stripped is True
    assert engine.telemetry.ram_mb <= ram_before

    # 6. lfs-status-system output
    res_status = engine.run_command("lfs-status-system")
    assert res_status.success
    assert "81/81 pacotes (100.0%)" in res_status.output
    assert "Localidades UTF-8" in res_status.output
    assert "Senhas Ocultas Shadow" in res_status.output
    assert "Banco de Hardware" in res_status.output
    assert "Stripping de Depuração" in res_status.output

    # Tier filter in lfs-status-system
    res_st1 = engine.run_command("lfs-status-system tier1")
    assert res_st1.success
    assert "Glibc (Definitiva)" in res_st1.output
    assert "19/19 pacotes compilados" in res_st1.output


def test_act4_full_quest_progression_and_title_unlock():
    """End-to-end walkthrough of Act 4 from Q15 through Q19 unlocking 'Arquiteto do Sistema'."""
    engine = _setup_act3_completed_engine()
    char = engine.char

    # Q15: Tier 1 + make check + localedef
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"
    engine.run_command("lfs-compile-system tier1")
    assert engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"
    engine.run_command("make check")
    res_q15 = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert "Tier 1 consolidado" in res_q15.output
    assert engine.story_engine.current_quest.id == "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW"

    # Q16: Tier 2 + pwconv + passwd root + exec bash
    engine.run_command("lfs-compile-system tier2")
    engine.run_command("make -k check")
    engine.run_command("pwconv")
    engine.run_command("passwd root")
    res_q16 = engine.run_command("exec /usr/bin/bash --login")
    assert "Toolchain nativa definitiva" in res_q16.output
    assert engine.story_engine.current_quest.id == "Q17_SYSTEM_TIER3_CRYPTO_PYTHON"

    # Q17: Tier 3
    res_q17 = engine.run_command("lfs-compile-system tier3")
    assert "Tier 3 finalizado" in res_q17.output
    assert engine.story_engine.current_quest.id == "Q18_SYSTEM_TIER4_UTILS_INIT"

    # Q18: Tier 4 + udev-hwdb update
    engine.run_command("lfs-compile-system tier4")
    assert engine.story_engine.current_quest.id == "Q18_SYSTEM_TIER4_UTILS_INIT"
    res_q18 = engine.run_command("udev-hwdb update")
    assert "81 pacotes do Capítulo 8" in res_q18.output
    assert engine.story_engine.current_quest.id == "Q19_STRIPPING_AND_ACT4_CLIMAX"

    # Q19: Stripping & Act 4 Climax
    res_q19 = engine.run_command("lfs-strip")
    assert "ATO 4 CONCLUÍDO COM MAESTRIA ABSOLUTA" in res_q19.output
    assert "Arquiteto do Sistema" in res_q19.output
    assert engine.story_engine.flags["act4_celebrated"] is True
    assert char.title == "Arquiteto do Sistema"
    assert "Arquiteto do Sistema" in char.unlocked_titles


def test_act4_didactic_glossary_entries():
    """Verify all Chapter 8 didactic glossary terms and aliases resolve properly."""
    required_terms = [
        ("make-check", ["make check", "make -k check"]),
        ("localedef", ["locales", "locale-archive"]),
        ("shadow", ["pwconv", "grpconv", "passwd"]),
        ("exec", ["exec bash"]),
        ("openssl", ["tls", "ssl"]),
        ("meson", ["ninja"]),
        ("udev", ["udev-hwdb", "hwdb"]),
        ("sysvinit", ["init"]),
        ("grub", ["bootloader", "grub-install"]),
        ("strip", ["lfs-strip"]),
    ]
    for canonical, aliases in required_terms:
        entry = glossary_manager.get(canonical)
        assert entry is not None, f"Glossary entry '{canonical}' missing!"
        assert len(entry.what_it_does) >= 30
        assert len(entry.why_in_lfs) >= 30
        assert len(entry.danger_if_missed) >= 30
        for alias in aliases:
            resolved = glossary_manager.get(alias)
            assert resolved is not None and resolved.term == canonical


def test_act4_save_and_load_roundtrip():
    """Verify saving and loading preserves all Act 4 VirtualFS flags, checks, and StoryEngine state."""
    engine = _setup_act3_completed_engine()
    engine.run_command("lfs-compile-system tier1")
    engine.run_command("make check")
    engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    engine.run_command("lfs-compile-system tier2")
    engine.run_command("make -k check")
    engine.run_command("pwconv")
    engine.run_command("passwd root")

    saved = engine.to_dict()
    assert saved["fs"]["locales_configured"] is True
    assert saved["fs"]["shadow_configured"] is True
    assert saved["fs"]["root_password_set"] is True
    assert "glibc" in saved["fs"]["system_checks_passed"]
    assert "gcc" in saved["fs"]["system_checks_passed"]

    restored = GameEngine()
    restored.from_dict(saved)

    assert restored.fs.in_chroot is True
    assert restored.fs.locales_configured is True
    assert restored.fs.shadow_configured is True
    assert restored.fs.root_password_set is True
    assert restored.fs.bash_restarted is False
    assert restored.fs.system_checks_passed == {"glibc", "gcc"}
    assert restored.story_engine.current_quest.id == "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW"

    # Continue seamlessly after restore
    res = restored.run_command("exec /usr/bin/bash --login")
    assert res.success
    assert restored.fs.bash_restarted is True
    assert restored.story_engine.current_quest.id == "Q17_SYSTEM_TIER3_CRYPTO_PYTHON"
