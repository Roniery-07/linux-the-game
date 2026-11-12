"""Comprehensive high-signal edge-case test suite for Act 4 (Capítulo 8 do LFS 13.1 pt_BR).

Covers:
1. Running Act 4 commands outside chroot (in_chroot=False).
2. Strict dependency ordering guards (pwconv, udev-hwdb, exec, localedef, make check).
3. make check edge cases: unknown targets, specific package prerequisites.
4. Invalid package and tier names in lfs-compile-system and lfs-status-system.
5. lfs-status-system package lookup and tier filtering.
6. Exhaustive idempotency & anti-XP exploit protection across all Act 4 commands.
7. Backward compatibility: loading a legacy Act 3 save seamlessly upgrades into Act 4.
8. Educational quality audit of all 10 Chapter 8 glossary entries and didactic insights.
9. Package alias resolution and filesystem placement verification.
"""

from __future__ import annotations
import posixpath
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.data.lfs_manifest import (
    SYSTEM_TIERS,
    get_system_package,
    get_system_packages,
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


def test_act4_commands_blocked_outside_chroot_exhaustive():
    """Verify all Act 4 compilation, test suites, and milestone commands fail outside chroot."""
    engine = GameEngine()
    assert engine.fs.in_chroot is False

    commands_to_block = [
        "lfs-compile-system",
        "lfs-compile-system all",
        "lfs-compile-system tier1",
        "lfs-compile-system tier2",
        "lfs-compile-system tier3",
        "lfs-compile-system tier4",
        "lfs-compile-system glibc-final",
        "lfs-compile-system gcc-final",
        "make check",
        "make -k check",
        "make check glibc",
        "make check binutils",
        "make check gcc",
        "make check all",
        "localedef -i pt_BR -f UTF-8 pt_BR.UTF-8",
        "localedef -i C.UTF-8 -f UTF-8 C.UTF-8",
        "pwconv",
        "grpconv",
        "passwd root",
        "passwd lfs",
        "exec /usr/bin/bash --login",
        "udev-hwdb update",
        "lfs-strip",
        "strip",
        "strip --strip-debug",
        "strip --strip-unneeded",
    ]

    initial_xp = engine.char.xp
    initial_level = engine.char.level

    for cmd in commands_to_block:
        res = engine.run_command(cmd)
        assert not res.success, f"Command '{cmd}' succeeded outside chroot!"
        assert "chroot" in res.output.lower(), f"Expected chroot guard error in '{cmd}': {res.output}"
        # No XP exploit while outside chroot
        assert (engine.char.level, engine.char.xp) == (initial_level, initial_xp)


def test_act4_dependency_ordering_guards():
    """Verify strict prerequisite checks: commands cannot run before their dependencies are compiled."""
    engine = _setup_act3_completed_engine()
    fs = engine.fs

    # 1. At start of Act 4, no Chapter 8 packages are compiled yet
    assert not fs.is_package_compiled("glibc-final")
    assert not fs.is_package_compiled("shadow")
    assert not fs.is_package_compiled("bash-final")
    assert not fs.is_package_compiled("udev")

    # 2. localedef requires glibc-final
    res_loc = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert not res_loc.success
    assert "glibc" in res_loc.output.lower()
    assert not fs.locales_configured

    # 3. pwconv, grpconv, and passwd require shadow
    res_pw = engine.run_command("pwconv")
    assert not res_pw.success
    assert "shadow" in res_pw.output.lower()
    assert not fs.shadow_configured

    res_grp = engine.run_command("grpconv")
    assert not res_grp.success
    assert "shadow" in res_grp.output.lower()

    res_passwd = engine.run_command("passwd root")
    assert not res_passwd.success
    assert "shadow" in res_passwd.output.lower()
    assert not fs.root_password_set

    # 4. exec /usr/bin/bash --login requires bash-final
    res_exec = engine.run_command("exec /usr/bin/bash --login")
    assert not res_exec.success
    assert "bash" in res_exec.output.lower()
    assert not fs.bash_restarted

    # 5. udev-hwdb update requires udev
    res_udev = engine.run_command("udev-hwdb update")
    assert not res_udev.success
    assert "udev" in res_udev.output.lower()
    assert not fs.udev_updated

    # 6. make check without any test suite package compiled
    res_chk = engine.run_command("make check")
    assert not res_chk.success
    assert "compile glibc-final" in res_chk.output.lower()

    # 7. Compile ONLY glibc-final
    assert engine.run_command("lfs-compile-system glibc-final").success

    # Now make check glibc succeeds, but binutils and gcc suites still fail
    res_chk_glibc = engine.run_command("make check glibc")
    assert res_chk_glibc.success
    assert "Glibc 2.44 Test Suite" in res_chk_glibc.output

    res_chk_bin = engine.run_command("make check binutils")
    assert not res_chk_bin.success
    assert "binutils-final" in res_chk_bin.output

    res_chk_gcc = engine.run_command("make check gcc")
    assert not res_chk_gcc.success
    assert "gcc-final" in res_chk_gcc.output

    # localedef now succeeds because glibc-final is compiled
    res_loc_ok = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert res_loc_ok.success
    assert fs.locales_configured

    # shadow commands still fail because shadow is not yet compiled
    assert not engine.run_command("pwconv").success
    assert not engine.run_command("passwd root").success

    # 8. Compile shadow
    assert engine.run_command("lfs-compile-system shadow").success
    assert engine.run_command("pwconv").success
    assert engine.run_command("grpconv").success
    assert engine.run_command("passwd root").success

    # passwd on nonexistent user fails cleanly
    res_bad_user = engine.run_command("passwd usuario_inexistente_99")
    assert not res_bad_user.success
    assert "não existe" in res_bad_user.output

    # 9. Compile bash-final and test exec
    assert engine.run_command("lfs-compile-system bash-final").success
    # Invalid exec syntax
    assert not engine.run_command("exec").success
    assert not engine.run_command("exec /usr/bin/python3").success
    # Valid exec
    assert engine.run_command("exec /usr/bin/bash --login").success
    assert fs.bash_restarted

    # 10. Compile udev and test udev-hwdb
    assert engine.run_command("lfs-compile-system udev").success
    # Missing 'update' argument
    res_udev_bad = engine.run_command("udev-hwdb")
    assert not res_udev_bad.success
    assert "Uso: udev-hwdb update" in res_udev_bad.output

    res_udev_bad2 = engine.run_command("udev-hwdb status")
    assert not res_udev_bad2.success
    assert "Uso: udev-hwdb update" in res_udev_bad2.output

    # Valid udev-hwdb update
    assert engine.run_command("udev-hwdb update").success
    assert fs.udev_updated


def test_make_check_unknown_suite_target_and_all():
    """Verify make check rejects unknown suite targets and properly executes 'all'."""
    engine = _setup_act3_completed_engine()

    # Compile glibc-final and binutils-final
    engine.run_command("lfs-compile-system glibc-final")
    engine.run_command("lfs-compile-system binutils-final")

    # Unknown suite target fails
    res_unknown = engine.run_command("make check python")
    assert not res_unknown.success
    assert "desconhecido" in res_unknown.output

    res_unknown2 = engine.run_command("make check kernel")
    assert not res_unknown2.success
    assert "desconhecido" in res_unknown2.output

    # make check all executes all currently compiled suites
    res_all = engine.run_command("make check all")
    assert res_all.success
    assert "Glibc 2.44 Test Suite" in res_all.output
    assert "Binutils 2.47 Test Suite" in res_all.output


def test_lfs_compile_system_invalid_packages_and_tiers():
    """Verify lfs-compile-system rejects nonexistent tiers and package names."""
    engine = _setup_act3_completed_engine()

    invalid_targets = [
        "pacote_inexistente",
        "tier0",
        "tier5",
        "tier99",
        "tier-1",
        "kernel-linux",
        "systemd-complete",
    ]
    for target in invalid_targets:
        res = engine.run_command(f"lfs-compile-system {target}")
        assert not res.success
        assert "não encontrado" in res.output


def test_lfs_status_system_arguments_and_filtering():
    """Verify lfs-status-system tier filtering, individual package lookup, and error handling on bad args."""
    engine = _setup_act3_completed_engine()

    # 1. Full system status without args
    res_all = engine.run_command("lfs-status-system")
    assert res_all.success
    assert "TELEMETRIA DO SISTEMA DEFINITIVO" in res_all.output
    assert "Tier 1" in res_all.output and "Tier 4" in res_all.output

    # 2. Tier filters (case-insensitive, with or without 'tier' prefix)
    for t in (1, 2, 3, 4):
        res_t = engine.run_command(f"lfs-status-system tier{t}")
        assert res_t.success
        assert f"Tier {t}" in res_t.output

        res_num = engine.run_command(f"lfs-status-system {t}")
        assert res_num.success
        assert f"Tier {t}" in res_num.output

    # 3. Specific package lookup
    res_pkg = engine.run_command("lfs-status-system glibc")
    assert res_pkg.success
    assert "DETALHES DO PACOTE: Glibc (Definitiva)" in res_pkg.output
    assert "libc.so.6" in res_pkg.output

    res_gcc = engine.run_command("lfs-status-system gcc")
    assert res_gcc.success
    assert "DETALHES DO PACOTE: GCC (Definitivo)" in res_gcc.output

    # 4. Invalid arguments return clean errors
    bad_args = ["tier0", "tier5", "tier99", "pacote_desconhecido", "foo_bar"]
    for bad in bad_args:
        res_bad = engine.run_command(f"lfs-status-system {bad}")
        assert not res_bad.success
        assert "não encontrado" in res_bad.output


def test_act4_idempotency_and_anti_xp_exploit_all_commands():
    """Verify that running Act 4 commands repeatedly never grants duplicate XP or breaks state."""
    engine = _setup_act3_completed_engine()
    char = engine.char
    fs = engine.fs

    # 1. Single package: glibc-final
    res_g1 = engine.run_command("lfs-compile-system glibc-final")
    assert res_g1.success
    lvl1, xp1 = char.level, char.xp

    res_g2 = engine.run_command("lfs-compile-system glibc-final")
    assert res_g2.success
    assert "+0 XP" in res_g2.output
    assert (char.level, char.xp) == (lvl1, xp1)

    # 2. make check glibc
    res_mc1 = engine.run_command("make check glibc")
    assert res_mc1.success
    lvl2, xp2 = char.level, char.xp
    assert xp2 > xp1

    res_mc2 = engine.run_command("make check glibc")
    assert res_mc2.success
    assert "+0 XP" in res_mc2.output
    assert (char.level, char.xp) == (lvl2, xp2)

    # 3. localedef
    res_loc1 = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert res_loc1.success
    lvl3, xp3 = char.level, char.xp
    assert xp3 > xp2

    res_loc2 = engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert res_loc2.success
    assert "+100 XP" not in res_loc2.output
    assert (char.level, char.xp) == (lvl3, xp3)

    # 4. Compile shadow
    engine.run_command("lfs-compile-system shadow")
    lvl_sh, xp_sh = char.level, char.xp

    # 5. pwconv
    res_pw1 = engine.run_command("pwconv")
    assert res_pw1.success
    lvl4, xp4 = char.level, char.xp
    assert xp4 > xp_sh

    res_pw2 = engine.run_command("pwconv")
    assert res_pw2.success
    assert "+80 XP" not in res_pw2.output
    assert (char.level, char.xp) == (lvl4, xp4)

    # 6. grpconv
    res_grp1 = engine.run_command("grpconv")
    assert res_grp1.success
    lvl5, xp5 = char.level, char.xp
    assert xp5 > xp4

    res_grp2 = engine.run_command("grpconv")
    assert res_grp2.success
    assert "+50 XP" not in res_grp2.output
    assert (char.level, char.xp) == (lvl5, xp5)

    # 7. passwd root
    res_pwd1 = engine.run_command("passwd root")
    assert res_pwd1.success
    lvl6, xp6 = char.level, char.xp
    assert xp6 > xp5

    res_pwd2 = engine.run_command("passwd root")
    assert res_pwd2.success
    assert "+100 XP" not in res_pwd2.output
    assert (char.level, char.xp) == (lvl6, xp6)

    # 8. bash-final & exec
    engine.run_command("lfs-compile-system bash-final")
    lvl_b, xp_b = char.level, char.xp

    res_ex1 = engine.run_command("exec /usr/bin/bash --login")
    assert res_ex1.success
    lvl7, xp7 = char.level, char.xp
    assert xp7 > xp_b

    res_ex2 = engine.run_command("exec /usr/bin/bash --login")
    assert res_ex2.success
    assert "+100 XP" not in res_ex2.output
    assert (char.level, char.xp) == (lvl7, xp7)

    # 9. udev & udev-hwdb update
    engine.run_command("lfs-compile-system udev")
    lvl_u, xp_u = char.level, char.xp

    res_ud1 = engine.run_command("udev-hwdb update")
    assert res_ud1.success
    lvl8, xp8 = char.level, char.xp
    assert xp8 > xp_u

    res_ud2 = engine.run_command("udev-hwdb update")
    assert res_ud2.success
    assert "+100 XP" not in res_ud2.output
    assert (char.level, char.xp) == (lvl8, xp8)

    # 10. lfs-strip and strip alias
    ram_before = engine.telemetry.ram_mb
    res_st1 = engine.run_command("lfs-strip")
    assert res_st1.success
    lvl9, xp9 = char.level, char.xp
    assert xp9 > xp8
    ram_after_st1 = engine.telemetry.ram_mb
    assert ram_after_st1 <= ram_before

    res_st2 = engine.run_command("lfs-strip")
    assert res_st2.success
    assert "+150 XP" not in res_st2.output
    assert (char.level, char.xp) == (lvl9, xp9)
    assert engine.telemetry.ram_mb == ram_after_st1  # RAM not deducted repeatedly

    res_st3 = engine.run_command("strip --strip-debug")
    assert res_st3.success
    assert "+150 XP" not in res_st3.output
    assert (char.level, char.xp) == (lvl9, xp9)
    assert engine.telemetry.ram_mb == ram_after_st1

    # 11. Tier 1 batch idempotency
    res_t1_1 = engine.run_command("lfs-compile-system tier1")
    assert res_t1_1.success
    lvl_t1, xp_t1 = char.level, char.xp

    res_t1_2 = engine.run_command("lfs-compile-system tier1")
    assert res_t1_2.success
    assert "+0 XP" in res_t1_2.output
    assert (char.level, char.xp) == (lvl_t1, xp_t1)

    # 12. Full batch compilation 'all' idempotency
    assert engine.run_command("lfs-compile-system all").success
    lvl_all, xp_all = char.level, char.xp

    res_all_again = engine.run_command("lfs-compile-system all")
    assert res_all_again.success
    assert "+0 XP" in res_all_again.output
    assert (char.level, char.xp) == (lvl_all, xp_all)


def test_act3_legacy_save_clean_upgrade_and_act4_continuation():
    """Verify that loading an Act 3 completed save (missing all Act 4 data) upgrades cleanly into Act 4."""
    # Build a realistic Act 3 completed GameEngine state
    live_engine = _setup_act3_completed_engine()
    raw_dict = live_engine.to_dict()

    # Strip out all Act 4 fields to simulate an older save file from Act 3
    # 1. VirtualFS Act 4 fields
    for f in [
        "locales_configured",
        "shadow_configured",
        "root_password_set",
        "bash_restarted",
        "udev_updated",
        "debug_stripped",
        "system_checks_passed",
    ]:
        raw_dict["fs"].pop(f, None)

    # 2. StoryEngine: keep only quests up to Q14 (15 quests)
    raw_dict["story_engine"]["quests"] = [
        q for q in raw_dict["story_engine"]["quests"]
        if q["id"] not in (
            "Q15_SYSTEM_TIER1_GLIBC",
            "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW",
            "Q17_SYSTEM_TIER3_CRYPTO_PYTHON",
            "Q18_SYSTEM_TIER4_UTILS_INIT",
            "Q19_STRIPPING_AND_ACT4_CLIMAX",
        )
    ]
    raw_dict["story_engine"]["current_quest_index"] = 15

    # 3. StoryEngine flags: pop Act 4 flags
    for flg in [
        "tier1_compiled",
        "tier2_compiled",
        "tier3_compiled",
        "tier4_compiled",
        "act4_celebrated",
    ]:
        raw_dict["story_engine"]["flags"].pop(flg, None)

    # Deserialize into a fresh GameEngine instance
    upgraded_engine = GameEngine()
    upgraded_engine.from_dict(raw_dict)

    # Verify VirtualFS fields defaulted gracefully
    assert upgraded_engine.fs.in_chroot is True
    assert upgraded_engine.fs.locales_configured is False
    assert upgraded_engine.fs.shadow_configured is False
    assert upgraded_engine.fs.root_password_set is False
    assert upgraded_engine.fs.bash_restarted is False
    assert upgraded_engine.fs.udev_updated is False
    assert upgraded_engine.fs.debug_stripped is False
    assert upgraded_engine.fs.system_checks_passed == set()

    # Verify StoryEngine dynamically attached Q15-Q19 (plus any newer act quests)
    assert len(upgraded_engine.story_engine.quests) >= 20
    attached_ids = {q.id for q in upgraded_engine.story_engine.quests}
    assert {"Q15_SYSTEM_TIER1_GLIBC", "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW", "Q17_SYSTEM_TIER3_CRYPTO_PYTHON", "Q18_SYSTEM_TIER4_UTILS_INIT", "Q19_STRIPPING_AND_ACT4_CLIMAX"}.issubset(attached_ids)
    assert upgraded_engine.story_engine.current_quest.id == "Q15_SYSTEM_TIER1_GLIBC"

    # Verify the player can seamlessly continue into Act 4 without any glitch
    res_t1 = upgraded_engine.run_command("lfs-compile-system tier1")
    assert res_t1.success
    assert upgraded_engine.fs.is_package_compiled("glibc-final")

    res_mc = upgraded_engine.run_command("make check")
    assert res_mc.success
    assert "glibc" in upgraded_engine.fs.system_checks_passed

    res_loc = upgraded_engine.run_command("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8")
    assert res_loc.success
    assert upgraded_engine.fs.locales_configured is True

    # Quest successfully progressed to Q16!
    assert upgraded_engine.story_engine.current_quest.id == "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW"


def test_act4_glossary_quality_and_educational_standards():
    """Verify that all 10 Chapter 8 glossary entries meet high educational standards."""
    required_entries = {
        "make-check": {
            "title_contains": "make check",
            "aliases": ["make check", "make -k check", "check"],
            "must_mention": ["Glibc", "Binutils", "GCC", "ABI"],
        },
        "localedef": {
            "title_contains": "localedef",
            "aliases": ["locales", "locale-archive", "pt_BR.UTF-8"],
            "must_mention": ["locale-archive", "UTF-8", "pt_BR"],
        },
        "shadow": {
            "title_contains": "Shadow",
            "aliases": ["pwconv", "grpconv", "/etc/shadow", "passwd"],
            "must_mention": ["/etc/shadow", "/etc/passwd", "root"],
        },
        "exec": {
            "title_contains": "exec",
            "aliases": ["exec bash", "exec /usr/bin/bash --login"],
            "must_mention": ["processo", "Bash", "PID"],
        },
        "openssl": {
            "title_contains": "OpenSSL",
            "aliases": ["tls", "ssl", "libssl"],
            "must_mention": ["criptográfic", "TLS", "Python"],
        },
        "meson": {
            "title_contains": "Meson",
            "aliases": ["ninja", "meson-ninja", "meson & ninja"],
            "must_mention": ["Ninja", "Python", "Kmod"],
        },
        "udev": {
            "title_contains": "Udev",
            "aliases": ["udev-hwdb", "hwdb", "udev-hwdb update"],
            "must_mention": ["/dev", "hwdb.bin", "hardware"],
        },
        "sysvinit": {
            "title_contains": "SysVinit",
            "aliases": ["init", "sysv", "/sbin/init"],
            "must_mention": ["PID 1", "/sbin/init", "inittab"],
        },
        "grub": {
            "title_contains": "GRUB",
            "aliases": ["bootloader", "grub-install"],
            "must_mention": ["boot", "kernel", "vmlinuz"],
        },
        "strip": {
            "title_contains": "strip",
            "aliases": ["lfs-strip"],
            "must_mention": ["depuração", "DWARF", "binários"],
        },
    }

    assert len(required_entries) == 10

    for term, meta in required_entries.items():
        entry = glossary_manager.get(term)
        assert entry is not None, f"Glossary entry '{term}' not found!"
        assert entry.category == "Sistema Final & Inicialização"
        assert meta["title_contains"].lower() in entry.name.lower()
        assert len(entry.syntax) >= 5

        # Check educational depth of explanations (>= 50 chars each)
        assert len(entry.what_it_does) >= 50, f"Entry '{term}' what_it_does too short!"
        assert len(entry.why_in_lfs) >= 50, f"Entry '{term}' why_in_lfs too short!"
        assert len(entry.danger_if_missed) >= 50, f"Entry '{term}' danger_if_missed too short!"

        full_text = f"{entry.what_it_does} {entry.why_in_lfs} {entry.danger_if_missed}".lower()
        for kw in meta["must_mention"]:
            assert kw.lower() in full_text, f"Entry '{term}' should mention '{kw}'!"

        # Verify alias resolution
        for alias in meta["aliases"]:
            resolved = glossary_manager.get(alias)
            assert resolved is not None, f"Alias '{alias}' failed to resolve!"
            assert resolved.term == term, f"Alias '{alias}' resolved to '{resolved.term}', expected '{term}'"


def test_didactic_insights_during_act4_commands():
    """Verify didactic insights trigger appropriately on Act 4 command execution."""
    engine = _setup_act3_completed_engine()

    # Pre-compile tier 1 and tier 2
    engine.run_command("lfs-compile-system tier1")
    engine.run_command("lfs-compile-system tier2")

    didactic_cases = [
        ("make check", "make check"),
        ("localedef -i pt_BR -f UTF-8 pt_BR.UTF-8", "localedef"),
        ("pwconv", "shadow"),
        ("lfs-strip", "strip"),
    ]

    for cmd, expected_topic in didactic_cases:
        res = engine.run_command(cmd)
        assert res.success
        assert "Insight LFS" in res.output, f"Didactic insight expected for '{cmd}'!"
        assert expected_topic in res.output.lower()


def test_act4_system_package_lookup_aliases_and_destinations():
    """Verify all system packages have valid destinations (/usr/bin, /usr/sbin, /usr/lib, /etc)."""
    packages = get_system_packages()
    assert len(packages) == 81

    valid_destinations = {"/usr/bin", "/usr/sbin", "/sbin", "/usr/lib", "/etc", "/usr/share/man"}

    for pkg in packages:
        assert pkg.chapter == 8
        assert pkg.tier in (1, 2, 3, 4)
        assert pkg.install_path in valid_destinations, f"Package {pkg.id} has invalid install_path: {pkg.install_path}"
        assert pkg.sbu > 0.0
        assert len(pkg.version) >= 1

    # Verify alias mapping
    aliases = {
        "glibc": "glibc-final",
        "gcc": "gcc-final",
        "bash": "bash-final",
        "python": "python-final",
        "python3": "python-final",
        "perl": "perl-final",
        "coreutils": "coreutils-final",
        "binutils": "binutils-final",
        "tar": "tar-final",
        "sed": "sed-final",
        "grep": "grep-final",
        "findutils": "findutils-final",
        "diffutils": "diffutils-final",
        "util-linux": "util-linux-final",
    }
    for alias, canonical_id in aliases.items():
        found = get_system_package(alias)
        assert found is not None, f"Alias '{alias}' not found!"
        assert found.id == canonical_id, f"Alias '{alias}' expected {canonical_id}, got {found.id}"
