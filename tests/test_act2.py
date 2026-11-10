"""Comprehensive test suite for Act 2 (LFS 13.1 pt_BR): Cross-Toolchain & Temporary Tools.

Tests:
1. Configure and make execution for Binutils Pass 1, GCC Pass 1, Linux Headers, and Glibc.
2. Compiler sanity check ($LFS_TGT-gcc + readelf + grep pipeline).
3. Libstdc++ Pass 1 installation.
4. Temporary tools compilation (individual and batch via lfs-compile-tools).
5. Toolchain status checklist (lfs-status-tools) and book guides (lfs-book 5, 6).
6. Compilation anomalies and mini-game encounters (combat system).
7. Full end-to-end Act 2 quest progression and climax celebration.
"""

import posixpath
import pytest
from lfs_game.core.engine import GameEngine
from lfs_game.data.lfs_manifest import get_chapter_help, get_toolchain_packages, get_toolchain_package
from lfs_game.rpg.combat import AnomalyManager, CpuOverheatAnomaly, LinkerErrorAnomaly, ContaminationWarningAnomaly


def _setup_sterile_lfs_engine() -> GameEngine:
    """Helper to initialize an engine at the beginning of Act 2."""
    engine = GameEngine()
    # Fast forward through Act 1
    engine.run_command("1")  # prologue
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
    engine.run_command("groupadd lfs")
    engine.run_command("useradd -s /bin/bash -g lfs -m -k /dev/null lfs")
    engine.run_command("chown -v lfs $LFS/tools")
    engine.run_command("chown -v lfs $LFS/sources")
    engine.run_command("su - lfs")
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("export LC_ALL=POSIX")
    engine.run_command("export LFS_TGT=x86_64-lfs-linux-gnu")
    engine.run_command("export PATH=/usr/bin:/bin")
    return engine


def test_act2_manifest_catalog_and_guides():
    """Verify Chapter 5 and 6 catalog metadata and book guides."""
    # Chapter 5 & 6 packages in catalog
    ch5_pkgs = get_toolchain_packages(chapter=5)
    ch6_pkgs = get_toolchain_packages(chapter=6)
    assert len(ch5_pkgs) == 5
    assert len(ch6_pkgs) == 17

    # Specific package lookups
    binutils1 = get_toolchain_package("binutils-pass1")
    assert binutils1 is not None
    assert binutils1.sbu == 1.0
    assert "$LFS_TGT-ld" in binutils1.binaries

    gcc1 = get_toolchain_package("gcc-pass1")
    assert gcc1 is not None
    assert gcc1.sbu == 4.3
    assert "$LFS_TGT-gcc" in gcc1.binaries

    # Chapter guide rendering
    guide5 = get_chapter_help(5)
    assert "Capítulo 5" in guide5
    assert "Binutils - Passagem 1" in guide5
    assert "GCC - Passagem 1" in guide5
    assert "readelf" in guide5

    guide6 = get_chapter_help(6)
    assert "Capítulo 6" in guide6
    assert "lfs-compile-tools all" in guide6
    assert "Binutils - Passagem 2" in guide6


def test_binutils_pass1_compilation():
    """Test Binutils Pass 1 configure, build and installation."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    engine.run_command("cd $LFS/sources")
    engine.run_command("mkdir -v binutils-build")
    engine.run_command("cd binutils-build")

    # Configure Binutils Pass 1
    res_conf = engine.run_command("../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT --disable-nls")
    assert res_conf.success
    assert "Configuração de 'binutils-pass1' concluída" in res_conf.output
    assert fs.exists("/mnt/lfs/sources/binutils-build/Makefile")

    # Make & Make install
    res_make = engine.run_command("make")
    assert res_make.success
    assert "Compilação de 'binutils-pass1' concluída" in res_make.output

    res_inst = engine.run_command("make install")
    assert res_inst.success
    assert "Binutils Passagem 1 instalado" in res_inst.output

    # Verify virtual binaries in $LFS/tools/bin
    assert fs.is_package_compiled("binutils-pass1")
    assert fs.exists("/mnt/lfs/tools/bin/x86_64-lfs-linux-gnu-ld")
    assert fs.exists("/mnt/lfs/tools/bin/x86_64-lfs-linux-gnu-as")


def test_gcc_pass1_compilation():
    """Test GCC Pass 1 configure, build, and limits.h generation."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    # First compile binutils pass 1
    engine.run_command("lfs-compile-tools binutils-pass1")

    engine.run_command("cd $LFS/sources")
    engine.run_command("mkdir -v gcc-build")
    engine.run_command("cd gcc-build")

    # Configure GCC Pass 1
    res_conf = engine.run_command(
        "../configure --target=$LFS_TGT --prefix=$LFS/tools --with-glibc-version=2.44 "
        "--with-sysroot=$LFS --with-newlib --without-headers --enable-languages=c,c++"
    )
    assert res_conf.success
    assert "Configuração de 'gcc-pass1' concluída" in res_conf.output

    res_inst = engine.run_command("make && make install")
    assert res_inst.success
    assert "GCC Passagem 1 instalado" in res_inst.output

    assert fs.is_package_compiled("gcc-pass1")
    assert fs.exists("/mnt/lfs/tools/bin/x86_64-lfs-linux-gnu-gcc")
    assert fs.exists("/mnt/lfs/tools/bin/x86_64-lfs-linux-gnu-g++")

    # Quest 5 should now be completed
    assert engine.story_engine.current_quest.id == "Q6_LINUX_HEADERS_AND_GLIBC"


def test_linux_headers_and_glibc():
    """Test Linux API headers generation and Glibc installation."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")

    # Linux Headers
    res_hdr = engine.run_command("make mrproper && make headers")
    assert res_hdr.success
    assert "Cabeçalhos da API do Linux" in res_hdr.output
    assert fs.is_package_compiled("linux-headers")

    res_cp = engine.run_command("cp -rv usr/include $LFS/usr")
    assert res_cp.success
    assert fs.exists("/mnt/lfs/usr/include")

    # Glibc 2.44
    engine.run_command("mkdir -v /mnt/lfs/sources/glibc-build")
    engine.run_command("cd /mnt/lfs/sources/glibc-build")
    res_glibc_conf = engine.run_command(
        "../configure --prefix=/usr --host=$LFS_TGT libc_cv_slibdir=/usr/lib --enable-kernel=5.10"
    )
    assert res_glibc_conf.success

    res_glibc_inst = engine.run_command("make && make DESTDIR=$LFS install")
    assert res_glibc_inst.success
    assert fs.is_package_compiled("glibc")
    assert fs.exists("/mnt/lfs/lib64/ld-linux-x86-64.so.2")
    assert fs.exists("/mnt/lfs/usr/lib/libc.so.6")


def test_compiler_sanity_check_pipeline():
    """Test full LFS 13.1 sanity check with $LFS_TGT-gcc, readelf, and pipe filtering."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    # Prepare toolchain prereqs
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    engine.run_command("lfs-compile-tools linux-headers")
    engine.run_command("lfs-compile-tools glibc")

    # 1. Compile dummy program via stdin pipe
    res_compile = engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc -")
    assert res_compile.success
    assert fs.exists(posixpath.join(fs.cwd, "a.out"))

    # 2. Inspect with readelf and pipe to grep ld-linux
    res_readelf_pipe = engine.run_command("readelf -l a.out | grep ld-linux")
    assert res_readelf_pipe.success
    assert "/lib/ld-linux-x86-64.so.2" in res_readelf_pipe.output
    assert engine.story_engine.flags["sanity_check_passed"]

    # 3. Verbose compiler log generation and inspection
    res_verbose = engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc - -v -Wl,--verbose &> dummy.log")
    assert res_verbose.success
    assert fs.exists(posixpath.join(fs.cwd, "dummy.log"))

    res_grep_crt = engine.run_command("grep crt1 dummy.log")
    assert res_grep_crt.success
    assert "crt1.o succeeded" in res_grep_crt.output

    res_grep_found = engine.run_command("grep found dummy.log")
    assert res_grep_found.success
    assert "libc.so.6" in res_grep_found.output

    # Clean up test artifacts
    res_rm = engine.run_command("rm -v a.out dummy.log")
    assert res_rm.success
    assert not fs.exists(posixpath.join(fs.cwd, "a.out"))


def test_libstdcxx_pass1():
    """Test Libstdc++ Pass 1 configure and make install."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    engine.run_command("lfs-compile-tools linux-headers")
    engine.run_command("lfs-compile-tools glibc")
    engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc -")
    engine.run_command("readelf -l a.out | grep ld-linux")

    # Configure and install Libstdc++
    res_conf = engine.run_command("../libstdc++-v3/configure --host=$LFS_TGT --prefix=/usr")
    assert res_conf.success

    res_inst = engine.run_command("make && make DESTDIR=$LFS install")
    assert res_inst.success
    assert "Libstdc++ Passagem 1 instalada" in res_inst.output
    assert fs.is_package_compiled("libstdc++")
    assert fs.exists("/mnt/lfs/usr/lib/libstdc++.so")

    # Quest 7 should be completed, advancing to Q8
    assert engine.story_engine.current_quest.id == "Q8_TEMP_TOOLS"


def test_temp_tools_batch_compilation():
    """Test Chapter 6 batch temporary tools compilation via lfs-compile-tools all."""
    engine = _setup_sterile_lfs_engine()
    fs = engine.fs

    # Advance to Chapter 6
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    engine.run_command("lfs-compile-tools linux-headers")
    engine.run_command("lfs-compile-tools glibc")
    engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc -")
    engine.run_command("readelf -l a.out | grep ld-linux")
    engine.run_command("lfs-compile-tools libstdc++")

    assert engine.story_engine.current_quest.id == "Q8_TEMP_TOOLS"

    # Batch compile all 15 temporary tools
    res_all = engine.run_command("lfs-compile-tools all")
    assert res_all.success
    assert "Todas as 15 ferramentas temporárias foram instaladas" in res_all.output

    # Verify virtual binaries installed
    for bin_name in ["m4", "bash", "cat", "diff", "file", "find", "gawk", "grep", "gzip", "make", "patch", "sed", "tar", "xz"]:
        assert fs.exists(f"/mnt/lfs/usr/bin/{bin_name}")
        assert fs.is_package_compiled(bin_name)

    # Quest 8 should be completed, advancing to Q9
    assert engine.story_engine.current_quest.id == "Q9_PASS2_AND_CLIMAX"


def test_lfs_status_tools_display():
    """Verify lfs-status-tools checklist rendering and SBU calculation."""
    engine = _setup_sterile_lfs_engine()

    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")

    res_status = engine.run_command("lfs-status-tools")
    assert res_status.success
    assert "CHECKLIST DA TOOLCHAIN" in res_status.output
    assert "Binutils - Passagem 1" in res_status.output
    assert "✔ INSTALADO" in res_status.output
    assert "⏳ PENDENTE" in res_status.output
    assert "SBU Concluído:" in res_status.output


def test_anomaly_system_and_combat():
    """Test compilation hazard trigger and player resolution mechanics."""
    engine = _setup_sterile_lfs_engine()
    am = engine.anomaly_manager

    # 1. Trigger CPU Overheat anomaly
    anomaly = am.trigger_anomaly("CPU_OVERHEAT")
    assert isinstance(anomaly, CpuOverheatAnomaly)
    assert am.active_anomaly is not None

    # Inspect prompt
    prompt = am.format_active_prompt()
    assert "ALERTA TÉRMICO" in prompt
    assert "[1]" in prompt
    assert "[2]" in prompt

    # Wrong answer: option 2
    ok_fail, fail_msg = am.resolve("2", engine)
    assert not ok_fail
    assert "ERRO GRAVE" in fail_msg
    assert am.active_anomaly is not None  # stays active

    # Correct answer: option 1
    initial_xp = engine.char.xp
    ok_succ, succ_msg = am.resolve("1", engine)
    assert ok_succ
    assert "Decisão correta" in succ_msg
    assert am.active_anomaly is None
    assert engine.char.xp > initial_xp
    assert "CPU_OVERHEAT" in am.resolved_history

    # 2. Trigger Linker Error anomaly
    anomaly_linker = am.trigger_anomaly("LINKER_ERROR")
    assert isinstance(anomaly_linker, LinkerErrorAnomaly)

    res_cmd = engine.run_command("1")  # Choice 1 directly via command input
    assert res_cmd.success
    assert "SUCESSO" in res_cmd.output
    assert am.active_anomaly is None

    # 3. Trigger Host Contamination anomaly
    anomaly_contam = am.trigger_anomaly("HOST_CONTAMINATION")
    assert isinstance(anomaly_contam, ContaminationWarningAnomaly)
    res_res = engine.run_command("lfs-resolve 1")
    assert res_res.success
    assert "Perfeito" in res_res.output
    assert am.active_anomaly is None


def test_act2_full_progression_and_climax():
    """End-to-end progression of Act 2 leading to celebration and title unlock."""
    engine = _setup_sterile_lfs_engine()

    # Chapter 5: Q5 Cross-Toolchain Core
    assert engine.story_engine.current_quest.id == "Q5_CROSS_TOOLCHAIN_CORE"
    engine.run_command("lfs-compile-tools binutils-pass1")
    engine.run_command("lfs-compile-tools gcc-pass1")
    assert engine.story_engine.current_quest.id == "Q6_LINUX_HEADERS_AND_GLIBC"

    # Chapter 5: Q6 Linux Headers & Glibc + Sanity Check
    engine.run_command("make mrproper && make headers && cp -rv usr/include $LFS/usr")
    engine.run_command("lfs-compile-tools glibc")
    engine.run_command("echo 'int main(){}' | $LFS_TGT-gcc -xc -")
    engine.run_command("readelf -l a.out | grep ld-linux")
    assert engine.story_engine.current_quest.id == "Q7_LIBSTDCXX"

    # Chapter 5: Q7 Libstdc++
    engine.run_command("lfs-compile-tools libstdc++")
    assert engine.story_engine.current_quest.id == "Q8_TEMP_TOOLS"

    # Chapter 6: Q8 Temporary Tools
    engine.run_command("lfs-compile-tools all")
    assert engine.story_engine.current_quest.id == "Q9_PASS2_AND_CLIMAX"

    # Chapter 6: Q9 Boss Fight (Binutils Pass 2 and GCC Pass 2)
    engine.run_command("lfs-compile-tools binutils-pass2")

    # GCC Pass 2 compilation (triggers Boss Fight Anomaly or can be compiled)
    engine.run_command("lfs-compile-tools gcc-pass2")

    # Verify Act 2 completed and celebrated!
    assert engine.story_engine.flags.get("act2_celebrated")
    assert "Mestre da Toolchain Cruzada" in engine.char.unlocked_titles
    assert engine.char.title == "Mestre da Toolchain Cruzada"
    assert engine.char.level >= 5
