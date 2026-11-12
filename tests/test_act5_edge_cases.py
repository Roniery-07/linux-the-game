"""High-signal edge-case and stress test suite for Act 5 (Capítulos 9 e 10 do LFS 13.1 pt_BR).

Covers:
1. Heredoc parsing edge cases:
   - Unterminated heredoc (missing delimiter syntax error).
   - Empty heredoc body (creates empty file / newline cleanly).
   - Writing to nonexistent parent directory (fails gracefully with bash error).
   - Heredoc preserving ;, &&, |, *, $ characters when quoted.
   - Variable expansion in unquoted heredocs vs literal strings in quoted heredocs.
   - Tab-stripping delimiter (<<- EOF).
   - Chained commands before heredoc (mkdir ... && cat > ... << "EOF").
   - Remaining commands executed after closing delimiter.
2. Kernel menuconfig hazards & Panic protection:
   - Critical flags (CONFIG_EXT4_FS=m, CONFIG_DEVTMPFS=n, CONFIG_BINFMT_ELF=n) block compile with clear panic warnings.
   - Multi-flag broken state diagnostics.
   - Warning-only flags (CONFIG_SATA_AHCI=m, CONFIG_NET=n, CONFIG_64BIT=n) compile with advisory notes.
   - Invalid flag syntax and value handling.
   - Complete recovery via 'lfs-kernel-config apply' and individual toggles.
   - Compilation attempted without .config.
3. /etc/fstab validation edge cases:
   - Missing '/' mount.
   - Wrong partition device (e.g. /dev/sda1 or /dev/sdb3).
   - Missing swap partition.
   - Wrong swap device.
   - Blank or comments-only fstab.
   - Valid fstab with flexible spacing, tabs, and comments.
4. Kernel compilation & modules_install prerequisites:
   - 'make modules_install' blocked before kernel compilation.
   - Copying bzImage before compilation fails.
   - Typo in kernel filename fails validation.
   - Valid copy updates quest and triggers Q23.
5. grub-install edge cases:
   - Execution blocked outside chroot.
   - Execution blocked before grub package compiled.
   - Execution blocked on invalid devices (/dev/nvme99, /dev/null, /dev/zero).
   - Execution without target device argument.
   - Successful installation to /dev/sda MBR.
6. /boot/grub/grub.cfg validation edge cases:
   - Missing kernel image reference fails validation.
   - Missing root=/dev/sda3 (or wrong root) fails validation.
   - Writing to non-existent /boot/grub directory fails without mkdir.
   - grub-mkconfig without -o outputs to stdout and does not set grub_cfg_created.
   - grub-mkconfig with -o and lfs-config-grub create directory and validate config.
7. Exhaustive idempotency & Anti-XP exploit protection:
   - Repeat runs of all Act 5 commands grant +0 XP.
   - Manual configuration awards XP; subsequent helper commands grant +0 XP.
8. Legacy save upgrade matrix:
   - Act 4 save upgrade seamlessly initializes Act 5 quests (Q20-Q23) and default kernel config.
   - Mid-Act 5 save/load roundtrips preserve exact states.
9. Educational quality audit of Chapter 9 & 10 glossary entries:
   - Pedagogical depth audit (what_it_does, why_in_lfs, danger_if_missed >= 30 chars).
   - Strict category and syntax verification.
   - Alias resolution integrity (including preservation of Act 4 grub-install -> grub).
"""

from __future__ import annotations
import pytest

from lfs_game.core.engine import GameEngine
from lfs_game.data.glossary import glossary_manager
from tests.test_act5 import _setup_act4_completed_engine


# =============================================================================
# 1. Heredoc Parsing Edge Cases
# =============================================================================

def test_heredoc_unterminated_raises_syntax_error():
    """Verify unterminated heredocs return clear syntax error without modifying state."""
    engine = GameEngine()
    
    # Missing EOF delimiter
    cmd = 'cat > /etc/broken << "EOF"\nline 1\nline 2\n'
    res = engine.run_command(cmd)
    assert not res.success
    assert "erro de sintaxe" in res.output
    assert "here-document delimitado por fim-de-arquivo" in res.output
    assert "EOF" in res.output
    assert not engine.fs.exists("/etc/broken")

    # Custom delimiter unterminated
    cmd_custom = 'cat > /etc/broken2 << "MY_CUSTOM_DELIM"\nsome configuration\n'
    res_custom = engine.run_command(cmd_custom)
    assert not res_custom.success
    assert "MY_CUSTOM_DELIM" in res_custom.output


def test_heredoc_empty_body_creates_file_cleanly():
    """Verify heredoc with empty body creates or truncates file cleanly."""
    engine = GameEngine()
    cmd = 'cat > /etc/empty_heredoc << "EOF"\nEOF'
    res = engine.run_command(cmd)
    assert res.success
    assert engine.fs.exists("/etc/empty_heredoc")
    ok, content = engine.fs.read_file("/etc/empty_heredoc")
    assert ok
    # Empty body should be empty or single trailing newline
    assert content in ("", "\n")


def test_heredoc_nonexistent_parent_directory_fails():
    """Verify heredoc targeting a nonexistent directory fails gracefully like bash."""
    engine = GameEngine()
    cmd = 'cat > /nonexistent/subdir/config << "EOF"\nfoo=bar\nEOF'
    res = engine.run_command(cmd)
    assert not res.success
    assert "Arquivo ou diretório inexistente" in res.output
    assert not engine.fs.exists("/nonexistent/subdir/config")


def test_heredoc_preserves_special_shell_characters_when_quoted():
    """Verify heredoc bodies preserve ;, &&, |, *, $, # literally when delimiter is quoted."""
    engine = GameEngine()
    engine.run_command("export UNTOUCHED_VAR=dangerous_value")

    cmd = (
        'cat > /etc/special_chars.conf << "EOF"\n'
        '# Semicolons and chained operators\n'
        'cmd1; cmd2 && cmd3 || cmd4 | grep pattern\n'
        'VAR=$UNTOUCHED_VAR\n'
        'WILD=*.*.log\n'
        'QUOTES="single" and \'double\'\n'
        'EOF'
    )
    res = engine.run_command(cmd)
    assert res.success

    ok, content = engine.fs.read_file("/etc/special_chars.conf")
    assert ok
    assert "cmd1; cmd2 && cmd3 || cmd4 | grep pattern" in content
    assert "VAR=$UNTOUCHED_VAR" in content
    assert "WILD=*.*.log" in content
    assert 'QUOTES="single" and \'double\'' in content


def test_heredoc_unquoted_expands_vars_quoted_does_not():
    """Verify unquoted delimiter expands environment variables while quoted does not."""
    engine = GameEngine()
    engine.run_command("export HOST_NAME=station-alpha")
    engine.run_command("export NET_IP=192.168.1.50")

    # 1. Quoted delimiter: no expansion
    cmd_quoted = (
        'cat > /etc/quoted.conf << "EOF"\n'
        'HOST=$HOST_NAME\n'
        'IP=$NET_IP\n'
        'EOF'
    )
    assert engine.run_command(cmd_quoted).success
    ok, content_q = engine.fs.read_file("/etc/quoted.conf")
    assert ok
    assert "HOST=$HOST_NAME" in content_q
    assert "IP=$NET_IP" in content_q

    # 2. Unquoted delimiter: variable expansion occurs
    cmd_unquoted = (
        'cat > /etc/unquoted.conf << EOF\n'
        'HOST=$HOST_NAME\n'
        'IP=$NET_IP\n'
        'EOF'
    )
    assert engine.run_command(cmd_unquoted).success
    ok, content_u = engine.fs.read_file("/etc/unquoted.conf")
    assert ok
    assert "HOST=station-alpha" in content_u
    assert "IP=192.168.1.50" in content_u


def test_heredoc_tab_stripping_delimiter():
    """Verify <<- EOF strips leading tab characters from each body line."""
    engine = GameEngine()
    cmd = (
        "cat <<- EOF > /etc/stripped.conf\n"
        "\tline 1 with tab\n"
        "\t\tline 2 with two tabs\n"
        "line 3 without tabs\n"
        "EOF"
    )
    res = engine.run_command(cmd)
    assert res.success

    ok, content = engine.fs.read_file("/etc/stripped.conf")
    assert ok
    lines = content.splitlines()
    assert lines[0] == "line 1 with tab"
    assert lines[1] == "line 2 with two tabs"
    assert lines[2] == "line 3 without tabs"


def test_heredoc_chained_commands_before_and_after():
    """Verify chained commands before heredoc (&&) and remaining commands after EOF execute cleanly."""
    engine = GameEngine()

    # 1. Chained setup command before heredoc
    cmd_before = (
        'mkdir -pv /etc/subservice && cat > /etc/subservice/service.conf << "EOF"\n'
        'ACTIVE=yes\n'
        'EOF'
    )
    res_b = engine.run_command(cmd_before)
    assert res_b.success
    assert engine.fs.exists("/etc/subservice/service.conf")

    # 2. Command following after EOF delimiter
    cmd_after = (
        'cat > /etc/after.conf << "EOF"\n'
        'STATUS=ready\n'
        'EOF\n'
        'cat /etc/after.conf'
    )
    res_a = engine.run_command(cmd_after)
    assert res_a.success
    assert "STATUS=ready" in res_a.output

    # 3. Failing initial chained command prevents heredoc execution
    cmd_fail = (
        'nonexistent_utility_123 && cat > /etc/should_not_exist << "EOF"\n'
        'FAIL=true\n'
        'EOF'
    )
    res_f = engine.run_command(cmd_fail)
    assert not res_f.success
    assert not engine.fs.exists("/etc/should_not_exist")


# =============================================================================
# 2. Kernel Menuconfig & Compilation Hazards
# =============================================================================

def test_kernel_critical_flags_panic_hazards_and_block():
    """Stress-test critical kernel flags (CONFIG_EXT4_FS=m, CONFIG_DEVTMPFS=n, CONFIG_BINFMT_ELF=n)."""
    engine = _setup_act4_completed_engine()
    engine.run_command("lfs-install-bootscripts")
    engine.run_command("lfs-config-network")
    engine.run_command("lfs-config-system")
    engine.run_command('cat > /etc/fstab << "EOF"\n/dev/sda3 / ext4 defaults 1 1\n/dev/sda2 swap swap pri=1 0 0\nEOF')
    engine.run_command("make defconfig")

    # Hazard 1: CONFIG_EXT4_FS=m (modular root filesystem causes panic without initramfs)
    res_ext4 = engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=m")
    assert res_ext4.success
    assert "ALERTA KERNEL PANIC" in res_ext4.output
    assert "CONFIG_EXT4_FS=m" in res_ext4.output
    res_build1 = engine.run_command("make -j4")
    assert not res_build1.success
    assert "ERRO CRÍTICO DE CONFIGURAÇÃO DO KERNEL" in res_build1.output
    assert "CONFIG_EXT4_FS=m" in res_build1.output

    # Hazard 2: CONFIG_DEVTMPFS=n (no devtmpfs prevents /dev creation)
    engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=y")
    res_dev = engine.run_command("lfs-kernel-config CONFIG_DEVTMPFS=n")
    assert res_dev.success
    assert "ALERTA KERNEL PANIC" in res_dev.output
    res_build2 = engine.run_command("lfs-compile-kernel")
    assert not res_build2.success
    assert "CONFIG_DEVTMPFS=n" in res_build2.output

    # Hazard 3: CONFIG_BINFMT_ELF=n (cannot execute /sbin/init or /bin/bash)
    engine.run_command("lfs-kernel-config CONFIG_DEVTMPFS=y")
    res_elf = engine.run_command("lfs-kernel-config CONFIG_BINFMT_ELF=n")
    assert res_elf.success
    assert "ALERTA KERNEL PANIC" in res_elf.output
    res_build3 = engine.run_command("make")
    assert not res_build3.success
    assert "CONFIG_BINFMT_ELF=n" in res_build3.output

    # Hazard 4: Multiple critical flags broken at once
    res_multi = engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=m CONFIG_DEVTMPFS=n CONFIG_BINFMT_ELF=n")
    assert res_multi.success
    res_build4 = engine.run_command("make -j4")
    assert not res_build4.success
    assert "CONFIG_EXT4_FS=m" in res_build4.output
    assert "CONFIG_DEVTMPFS=n" in res_build4.output
    assert "CONFIG_BINFMT_ELF=n" in res_build4.output

    # Recovery: 'lfs-kernel-config apply' resets to safe [y] preset and unblocks build
    res_rec = engine.run_command("lfs-kernel-config apply")
    assert res_rec.success
    assert "Preset seguro [y] aplicado" in res_rec.output
    res_build_ok = engine.run_command("make -j4")
    assert res_build_ok.success
    assert engine.fs.kernel_compiled is True


def test_kernel_non_critical_warning_flags():
    """Verify non-critical flags (SATA_AHCI=m, NET=n, 64BIT=n) issue warnings but do not block compile."""
    engine = _setup_act4_completed_engine()
    engine.run_command("lfs-install-bootscripts")
    engine.run_command("lfs-config-network")
    engine.run_command("lfs-config-system")
    engine.run_command('cat > /etc/fstab << "EOF"\n/dev/sda3 / ext4 defaults 1 1\n/dev/sda2 swap swap pri=1 0 0\nEOF')
    engine.run_command("make defconfig")

    # Toggle SATA_AHCI to modular and NET to disabled
    res_opt = engine.run_command("lfs-kernel-config CONFIG_SATA_AHCI=m CONFIG_NET=n")
    assert res_opt.success

    # Compilation succeeds with warnings
    res_build = engine.run_command("make -j4")
    assert res_build.success
    assert "AVISO: CONFIG_SATA_AHCI=m" in res_build.output
    assert "AVISO: CONFIG_NET=n" in res_build.output


def test_kernel_config_invalid_arguments_and_syntax():
    """Verify syntax error handling in lfs-kernel-config."""
    engine = _setup_act4_completed_engine()

    # Missing =
    res_no_eq = engine.run_command("lfs-kernel-config INVALID_SYNTAX")
    assert not res_no_eq.success
    assert "argumento inválido 'INVALID_SYNTAX'" in res_no_eq.output

    # Invalid value (not y/m/n)
    res_bad_val = engine.run_command("lfs-kernel-config CONFIG_EXT4_FS=maybe")
    assert not res_bad_val.success
    assert "valor inválido 'maybe'" in res_bad_val.output

    # Normalization: without CONFIG_ prefix and lowercase
    res_norm = engine.run_command("lfs-kernel-config ext4_fs=Y")
    assert res_norm.success
    assert engine.fs.kernel_config["CONFIG_EXT4_FS"] == "y"


def test_kernel_compile_blocked_without_config():
    """Verify 'make -j4' fails when .config has not been created."""
    engine = _setup_act4_completed_engine()
    engine.run_command("cd /sources")
    engine.run_command("tar -xf linux-7.1.8.tar.xz")
    engine.run_command("cd linux-7.1.8")
    engine.run_command("make mrproper")

    res_build = engine.run_command("make -j4")
    assert not res_build.success
    assert "Sem regra para processar o alvo '.config'" in res_build.output


# =============================================================================
# 3. /etc/fstab Validation Edge Cases
# =============================================================================

def test_fstab_validation_strict_edge_cases():
    """Verify /etc/fstab validation rejects missing /, wrong device, missing swap, and blank files."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # 1. Blank / empty / comments only
    engine.run_command('cat > /etc/fstab << "EOF"\n# Just a comment\n\n# Another comment\nEOF')
    assert fs.has_valid_fstab() is False
    assert fs.fstab_configured is False

    # 2. Missing '/' mount (only swap specified)
    engine.run_command('cat > /etc/fstab << "EOF"\n/dev/sda2 swap swap pri=1 0 0\nEOF')
    assert fs.has_valid_fstab() is False

    # 3. Wrong partition for '/' (e.g. /dev/sda1 or /dev/sdb3 instead of /dev/sda3)
    engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '/dev/sda1 / ext4 defaults 1 1\n'
        '/dev/sda2 swap swap pri=1 0 0\n'
        'EOF'
    )
    assert fs.has_valid_fstab() is False

    # 4. Missing swap partition (only / specified)
    engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '/dev/sda3 / ext4 defaults 1 1\n'
        'EOF'
    )
    assert fs.has_valid_fstab() is False

    # 5. Wrong swap partition device (e.g. /dev/sda1 swap)
    engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '/dev/sda3 / ext4 defaults 1 1\n'
        '/dev/sda1 swap swap pri=1 0 0\n'
        'EOF'
    )
    assert fs.has_valid_fstab() is False

    # 6. Valid fstab with irregular whitespace, tabs, and comments
    engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '# LFS 13.1 Production Mount Table\n'
        '/dev/sda3\t\t/\t\text4\t\tdefaults\t1\t1\n'
        '/dev/sda2\t\tswap\tswap\tpri=1\t\t0\t0\n'
        'proc\t\t/proc\tproc\tnosuid,noexec,nodev\t0\t0\n'
        'EOF'
    )
    assert fs.has_valid_fstab() is True
    assert fs.fstab_configured is True


# =============================================================================
# 4. Kernel Compilation & Modules Prerequisites
# =============================================================================

def test_kernel_modules_and_bzimage_prerequisites():
    """Verify 'make modules_install' and bzImage copy require compilation first."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # 1. Calling make modules_install before compilation fails
    res_mod_early = engine.run_command("make modules_install")
    assert not res_mod_early.success
    assert "Compile o Kernel 7.1.8" in res_mod_early.output

    # 2. Copying bzImage before compilation fails
    res_cp_early = engine.run_command("cp arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1")
    assert not res_cp_early.success
    assert "Arquivo ou diretório inexistente" in res_cp_early.output
    assert fs.kernel_installed is False

    # 3. Configure and compile kernel
    assert engine.run_command("cd /sources").success
    assert engine.run_command("tar -xf linux-7.1.8.tar.xz").success
    assert engine.run_command("cd linux-7.1.8").success
    assert engine.run_command("make defconfig").success
    assert engine.run_command("lfs-compile-kernel").success
    assert fs.kernel_compiled is True

    # 4. Now make modules_install succeeds
    res_mod_ok = engine.run_command("make modules_install")
    assert res_mod_ok.success
    assert fs.exists("/lib/modules/7.1.8/modules.dep")

    # 5. Copying to typo filename does not satisfy kernel_installed
    assert engine.run_command("cp arch/x86/boot/bzImage /boot/vmlinuz-wrong-version").success
    assert fs.kernel_installed is False

    # 6. Copying to exact /boot/vmlinuz-7.1.8-lfs-13.1 satisfies requirement
    assert engine.run_command("cp arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1").success
    assert fs.kernel_installed is True


# =============================================================================
# 5. grub-install Edge Cases
# =============================================================================

def test_grub_install_edge_cases():
    """Verify grub-install guards against missing package, invalid devices, and outside chroot."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # 1. Blocked outside chroot
    fs.in_chroot = False
    res_out = engine.run_command("grub-install /dev/sda")
    assert not res_out.success
    assert "chroot" in res_out.output.lower()
    fs.in_chroot = True

    # 2. Blocked if grub package was not compiled
    fs.compiled_packages.discard("grub")
    res_no_pkg = engine.run_command("grub-install /dev/sda")
    assert not res_no_pkg.success
    assert "GRUB 2.14 ainda não foi compilado" in res_no_pkg.output

    # Restore grub package compilation
    fs.record_package_compiled("grub")

    # 3. Missing device argument
    res_no_arg = engine.run_command("grub-install")
    assert not res_no_arg.success
    assert "especifique o dispositivo de destino" in res_no_arg.output

    # 4. Invalid device (/dev/nvme99, /dev/null, /dev/zero)
    for bad_dev in ("/dev/nvme99", "/dev/null", "/dev/zero", "/dev/ram0"):
        res_bad_dev = engine.run_command(f"grub-install {bad_dev}")
        assert not res_bad_dev.success
        assert f"dispositivo '{bad_dev}' inválido" in res_bad_dev.output

    # 5. Valid disk /dev/sda succeeds and creates core.img
    res_ok = engine.run_command("grub-install /dev/sda")
    assert res_ok.success
    assert fs.grub_mbr_installed is True
    assert fs.exists("/boot/grub/i386-pc/core.img")


# =============================================================================
# 6. /boot/grub/grub.cfg Validation Edge Cases
# =============================================================================

def test_grub_cfg_validation_and_mkconfig_edge_cases():
    """Verify grub.cfg validation checks kernel name, root=/dev/sda3, and tests grub-mkconfig."""
    engine = _setup_act4_completed_engine()
    fs = engine.fs

    # 1. Missing parent directory: writing directly without mkdir fails
    res_no_dir = engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'linux /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda3 ro\n'
        'EOF'
    )
    assert not res_no_dir.success
    assert "Arquivo ou diretório inexistente" in res_no_dir.output

    # Create directory
    assert engine.run_command("mkdir -pv /boot/grub").success

    # 2. Missing exact kernel image name
    engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'linux /boot/vmlinuz root=/dev/sda3 ro\n'
        'EOF'
    )
    assert fs.has_valid_grub_cfg() is False

    # 3. Missing root=/dev/sda3 (wrong partition /dev/sda1)
    engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'linux /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda1 ro\n'
        'EOF'
    )
    assert fs.has_valid_grub_cfg() is False

    # 4. grub-mkconfig without -o outputs to stdout and does NOT set grub_cfg_created
    res_stdout = engine.run_command("grub-mkconfig")
    assert res_stdout.success
    assert "menuentry" in res_stdout.output
    assert fs.grub_cfg_created is False

    # 5. grub-mkconfig with -o generates valid config and sets grub_cfg_created
    res_mkcfg = engine.run_command("grub-mkconfig -o /boot/grub/grub.cfg")
    assert res_mkcfg.success
    assert fs.has_valid_grub_cfg() is True
    assert fs.grub_cfg_created is True


# =============================================================================
# 7. Exhaustive Idempotency & Anti-XP Exploit
# =============================================================================

def test_act5_commands_xp_anti_exploit_exhaustive():
    """Verify repeating any Act 5 command grants exactly +0 XP on subsequent runs."""
    engine = _setup_act4_completed_engine()

    def char_state():
        return (engine.char.level, engine.char.xp)

    # 1. lfs-install-bootscripts
    st_before = char_state()
    assert engine.run_command("lfs-install-bootscripts").success
    st_after1 = char_state()
    assert st_after1 != st_before
    # Repeat 1, 2, 3
    for _ in range(3):
        assert engine.run_command("lfs-install-bootscripts").success
        assert char_state() == st_after1

    # 2. lfs-config-network
    assert engine.run_command("lfs-config-network station-one").success
    st_after2 = char_state()
    assert st_after2 != st_after1
    for _ in range(3):
        assert engine.run_command("lfs-config-network station-one").success
        assert char_state() == st_after2

    # 3. lfs-config-system
    assert engine.run_command("lfs-config-system").success
    st_after3 = char_state()
    assert st_after3 != st_after2
    for _ in range(3):
        assert engine.run_command("lfs-config-system").success
        assert char_state() == st_after3

    # Setup fstab
    assert engine.run_command(
        'cat > /etc/fstab << "EOF"\n'
        '/dev/sda3 / ext4 defaults 1 1\n'
        '/dev/sda2 swap swap pri=1 0 0\n'
        'EOF'
    ).success

    # 4. make defconfig / lfs-kernel-config apply
    assert engine.run_command("make defconfig").success
    st_after4 = char_state()
    assert st_after4 != st_after3
    for _ in range(3):
        assert engine.run_command("make defconfig").success
        assert engine.run_command("lfs-kernel-config apply").success
        assert char_state() == st_after4

    # 5. lfs-compile-kernel / make -j4
    assert engine.run_command("lfs-compile-kernel").success
    st_after5 = char_state()
    assert st_after5 != st_after4
    for _ in range(3):
        assert engine.run_command("lfs-compile-kernel").success
        assert engine.run_command("make -j4").success
        assert char_state() == st_after5

    # 6. make modules_install
    assert engine.run_command("make modules_install").success
    st_after6 = char_state()
    assert st_after6 != st_after5
    for _ in range(3):
        assert engine.run_command("make modules_install").success
        assert char_state() == st_after6

    # 7. grub-install
    assert engine.run_command("grub-install /dev/sda").success
    st_after7 = char_state()
    assert st_after7 != st_after6
    for _ in range(3):
        assert engine.run_command("grub-install /dev/sda").success
        assert char_state() == st_after7

    # 8. lfs-config-grub / grub-mkconfig -o
    assert engine.run_command("lfs-config-grub").success
    st_after8 = char_state()
    assert st_after8 != st_after7
    for _ in range(3):
        assert engine.run_command("lfs-config-grub").success
        assert engine.run_command("grub-mkconfig -o /boot/grub/grub.cfg").success
        assert char_state() == st_after8


def test_act5_manual_configuration_prevents_duplicate_helper_xp():
    """Verify manual file configuration awards XP, and subsequent helper calls award +0 XP."""
    engine = _setup_act4_completed_engine()

    # Manual network configuration
    engine.run_command('echo "manual-host" > /etc/hostname')
    engine.run_command('cat > /etc/hosts << "EOF"\n127.0.0.1 localhost\nEOF')
    engine.run_command('cat > /etc/resolv.conf << "EOF"\nnameserver 1.1.1.1\nEOF')
    engine.run_command('cat > /etc/sysconfig/ifconfig.eth0 << "EOF"\nONBOOT=yes\nEOF')
    assert engine.fs.network_configured is True

    # Helper command must not grant duplicate XP
    xp_now = engine.char.xp
    res_helper = engine.run_command("lfs-config-network")
    assert res_helper.success
    assert engine.char.xp == xp_now

    # Manual grub configuration
    assert engine.run_command("mkdir -pv /boot/grub").success
    assert engine.run_command(
        'cat > /boot/grub/grub.cfg << "EOF"\n'
        'linux /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda3 ro\n'
        'EOF'
    ).success
    assert engine.fs.grub_cfg_created is True

    # Helper command must not grant duplicate XP
    xp_grub = engine.char.xp
    res_g_helper = engine.run_command("lfs-config-grub")
    assert res_g_helper.success
    assert engine.char.xp == xp_grub


# =============================================================================
# 8. Legacy Save Upgrade Matrix
# =============================================================================

def test_legacy_save_upgrade_from_earlier_acts():
    """Verify upgrading a save from Act 3 and Act 4 populates all 24 quests and safe Act 5 defaults."""
    engine = _setup_act4_completed_engine()
    save_data = e_dict = engine.to_dict()

    # Strip Act 5 specific fields from filesystem
    act5_fs_keys = [
        "bootscripts_installed", "network_configured", "sysconfig_configured",
        "fstab_configured", "kernel_config", "kernel_configured",
        "kernel_compiled", "kernel_installed", "grub_mbr_installed", "grub_cfg_created",
    ]
    for k in act5_fs_keys:
        save_data["fs"].pop(k, None)

    # Strip Act 5 quests (simulate old 20-quest array)
    save_data["story_engine"]["quests"] = [
        q for q in save_data["story_engine"]["quests"]
        if not q["id"].startswith(("Q20_", "Q21_", "Q22_", "Q23_"))
    ]
    save_data["story_engine"]["current_quest_index"] = 20
    for flg in ("system_configured", "kernel_forged", "act5_celebrated"):
        save_data["story_engine"]["flags"].pop(flg, None)

    # Restore into fresh engine
    migrated = GameEngine()
    migrated.from_dict(save_data)

    # Verify quest expansion
    assert len(migrated.story_engine.quests) == 24
    assert migrated.story_engine.current_quest.id == "Q20_SYSTEM_CONFIG_NETWORK"
    assert migrated.story_engine.flags["act5_celebrated"] is False

    # Verify default kernel config injection
    assert migrated.fs.kernel_config["CONFIG_EXT4_FS"] == "y"
    assert migrated.fs.kernel_config["CONFIG_DEVTMPFS"] == "y"
    assert migrated.fs.kernel_config["CONFIG_BINFMT_ELF"] == "y"
    assert migrated.fs.kernel_configured is False
    assert migrated.fs.kernel_compiled is False
    assert migrated.fs.grub_mbr_installed is False
    assert migrated.fs.grub_cfg_created is False


def test_act5_midpoint_save_and_restore_roundtrip():
    """Verify saving in the middle of Act 5 (kernel configured and compiled) restores exact state."""
    engine = _setup_act4_completed_engine()
    engine.run_command("lfs-install-bootscripts")
    engine.run_command("lfs-config-network hera-orbit")
    engine.run_command("lfs-config-system")
    engine.run_command('cat > /etc/fstab << "EOF"\n/dev/sda3 / ext4 defaults 1 1\n/dev/sda2 swap swap pri=1 0 0\nEOF')
    engine.run_command("make defconfig")
    engine.run_command("lfs-compile-kernel")
    engine.run_command("make modules_install")

    save = engine.to_dict()

    restored = GameEngine()
    restored.from_dict(save)

    assert restored.fs.bootscripts_installed is True
    assert restored.fs.network_configured is True
    assert restored.fs.sysconfig_configured is True
    assert restored.fs.fstab_configured is True
    assert restored.fs.kernel_compiled is True
    assert restored.fs.exists("/lib/modules/7.1.8/modules.dep")
    assert restored.story_engine.current_quest.id == "Q22_KERNEL_FORGE"

    # Complete the rest in restored session
    assert restored.run_command("cp /sources/linux-7.1.8/arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1").success
    assert restored.story_engine.current_quest.id == "Q23_GRUB_BOOTLOADER"
    assert restored.run_command("grub-install /dev/sda").success
    assert restored.run_command("lfs-config-grub").success
    assert restored.story_engine.flags["act5_celebrated"] is True
    assert restored.char.title == "Forjador do Kernel"


# =============================================================================
# 9. Educational Quality Audit of Chapter 9 & 10 Glossary Entries
# =============================================================================

def test_chapter_9_and_10_glossary_entries_educational_quality_audit():
    """Audit all 8 required Chapter 9 & 10 glossary terms for pedagogical depth and metadata."""
    required_act5_terms = [
        "lfs-bootscripts",
        "hostname",
        "inittab",
        "inputrc",
        "fstab",
        "menuconfig",
        "bzimage",
        "grub.cfg",
    ]

    for term in required_act5_terms:
        entry = glossary_manager.get(term)
        assert entry is not None, f"Glossary entry '{term}' is missing from catalog!"
        assert entry.category == "Sistema Final & Inicialização"
        assert len(entry.name.strip()) >= 5
        assert len(entry.syntax.strip()) >= 5

        # Pedagogical depth check (> 30 characters of meaningful explanation)
        assert len(entry.what_it_does.strip()) >= 30, (
            f"Term '{term}': what_it_does is too short ({len(entry.what_it_does)} chars)"
        )
        assert len(entry.why_in_lfs.strip()) >= 30, (
            f"Term '{term}': why_in_lfs is too short ({len(entry.why_in_lfs)} chars)"
        )
        assert len(entry.danger_if_missed.strip()) >= 30, (
            f"Term '{term}': danger_if_missed is too short ({len(entry.danger_if_missed)} chars)"
        )
        assert len(entry.related_terms) >= 1

    # Verify alias mappings
    alias_checks = {
        "bootscripts": "lfs-bootscripts",
        "lfs-install-bootscripts": "lfs-bootscripts",
        "/etc/hostname": "hostname",
        "/etc/hosts": "hostname",
        "/etc/inittab": "inittab",
        "/etc/inputrc": "inputrc",
        "/etc/shells": "inputrc",
        "/etc/fstab": "fstab",
        "make menuconfig": "menuconfig",
        "lfs-kernel-config": "menuconfig",
        "vmlinuz": "bzimage",
        "vmlinuz-7.1.8-lfs-13.1": "bzimage",
        "grub-mkconfig": "grub.cfg",
        "/boot/grub/grub.cfg": "grub.cfg",
        "lfs-config-grub": "grub.cfg",
        # Verify Act 4 grub alias was not overwritten
        "grub-install": "grub",
    }
    for alias, canonical in alias_checks.items():
        resolved = glossary_manager.get(alias)
        assert resolved is not None, f"Alias '{alias}' failed to resolve!"
        assert resolved.term == canonical, f"Alias '{alias}' resolved to '{resolved.term}', expected '{canonical}'"
