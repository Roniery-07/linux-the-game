"""Manifest and package catalog for LFS 13.1 pt_BR."""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
import re
from typing import Dict, List, Optional


@dataclass
class LFSPackage:
    """Represents a source archive or patch required for LFS 13.1."""
    name: str
    version: str
    tarball: str
    size: str
    md5: str
    url: str
    home_url: str
    description: str = ""
    is_patch: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolchainPackage:
    """Represents a package built during Chapters 5, 6, 7, or 8."""
    id: str
    name: str
    version: str
    chapter: int
    sbu: float
    sbu_label: str
    description: str
    configure_flags: str
    build_steps: str
    install_path: str
    binaries: List[str] = field(default_factory=list)
    tier: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


SYSTEM_TIERS: Dict[int, dict] = {
    1: {
        "tier": 1,
        "name": "Tier 1: Fundação C, Compressão & Ferramentas de Build",
        "sections": "8.3–8.21",
        "description": "Páginas man, iana-etc, Glibc definitiva, bibliotecas de compressão e ferramentas de parser/teste (Tcl, Expect, DejaGNU, Ninja, Pkgconf).",
    },
    2: {
        "tier": 2,
        "name": "Tier 2: Toolchain Nativa, Segurança Shadow & Shell",
        "sections": "8.22–8.40",
        "description": "Binutils e GCC definitivos com bibliotecas matemáticas, ACLs, Shadow (senhas), Ncurses, Sed, Bison, Grep e Bash final.",
    },
    3: {
        "tier": 3,
        "name": "Tier 3: Criptografia, Perl, Python, Meson & Kmod",
        "sections": "8.41–8.60",
        "description": "OpenSSL 4.0, Perl, Autoconf/Automake, SQLite, Python 3.14 definitivo, empacotamento Python, Meson e Kmod.",
    },
    4: {
        "tier": 4,
        "name": "Tier 4: Utilitários Core, Bootloader GRUB, Udev & SysVinit",
        "sections": "8.61–8.83",
        "description": "Coreutils, IPRoute2, GRUB, Vim, Udev, Man-DB, Procps-ng, Util-linux, E2fsprogs, Sysklogd e SysVinit.",
    },
}


_PACKAGES_CACHE: Optional[List[LFSPackage]] = None


def _clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_html_book(html_path: Path) -> List[LFSPackage]:
    """Parses LFS 13.1 packages and patches from the single-page HTML book."""
    if not html_path.exists():
        return []

    try:
        content = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    sec_packages_start = content.find('id="ch-materials-packages"')
    sec_patches_start = content.find('id="ch-materials-patches"')
    sec_preps_start = content.find('4. Preparações Finais', sec_patches_start if sec_patches_start != -1 else 0)

    if sec_packages_start == -1 or sec_patches_start == -1:
        return []

    if sec_preps_start == -1:
        sec_preps_start = len(content)

    items: List[LFSPackage] = []

    def extract_section(section_html: str, is_patch: bool) -> List[LFSPackage]:
        res: List[LFSPackage] = []
        matches = re.findall(
            r"<dt>\s*<span class=\"term\">(.*?)\s*</span>\s*</dt>\s*<dd>(.*?)</dd>",
            section_html,
            re.DOTALL
        )
        for term_raw, body_raw in matches:
            term_clean = _clean_whitespace(re.sub(r"<[^>]+>", "", term_raw))
            # Extract size
            size_m = re.search(r"-\s*([\d\.]+\s*(?:KB|MB))", term_clean)
            size = size_m.group(1) if size_m else ""

            # Extract version
            ver_m = re.search(r"\(([^)]+)\)", term_clean)
            version = ver_m.group(1) if ver_m else ""

            # Extract package name
            name_m = re.match(r"^([^\(-]+)", term_clean)
            name = _clean_whitespace(name_m.group(1)) if name_m else term_clean

            # MD5
            md5_m = re.search(r"([a-f0-9]{32})", body_raw)
            md5 = md5_m.group(1) if md5_m else ""

            # URLs
            urls = re.findall(r"href=\s*\"([^\"]+)\"", body_raw)
            home_url = urls[0] if len(urls) > 0 else ""
            dl_url = urls[1] if len(urls) > 1 else (urls[0] if urls else "")
            tarball = dl_url.split("/")[-1] if dl_url else ""

            if not tarball and not is_patch:
                # fallback tarball name
                ver_slug = f"-{version}" if version else ""
                tarball = f"{name.lower()}{ver_slug}.tar.xz"

            res.append(
                LFSPackage(
                    name=name,
                    version=version,
                    tarball=tarball,
                    size=size,
                    md5=md5,
                    url=dl_url,
                    home_url=home_url,
                    description=f"{name} {version} ({size})" if version else f"{name} ({size})",
                    is_patch=is_patch
                )
            )
        return res

    pkgs = extract_section(content[sec_packages_start:sec_patches_start], is_patch=False)
    patches = extract_section(content[sec_patches_start:sec_preps_start], is_patch=True)
    items.extend(pkgs)
    items.extend(patches)
    return items


def _get_fallback_catalog() -> List[LFSPackage]:
    """Curated fallback catalog if HTML file is not found."""
    return [
        LFSPackage("Acl", "2.4.0", "acl-2.4.0.tar.xz", "376 KB", "e289f370161698a96f50b2a3fdadf411", "https://download.savannah.gnu.org/releases/acl/acl-2.4.0.tar.xz", "https://savannah.nongnu.org/projects/acl"),
        LFSPackage("Attr", "2.6.0", "attr-2.6.0.tar.gz", "495 KB", "910a09c3ae0a211569d180586371cf7e", "https://download.savannah.gnu.org/releases/attr/attr-2.6.0.tar.gz", "https://savannah.nongnu.org/projects/attr"),
        LFSPackage("Autoconf", "2.73", "autoconf-2.73.tar.xz", "1.385 KB", "9cbad9a116ef845bafeed8e7bc771bf4", "https://ftpmirror.gnu.org/autoconf/autoconf-2.73.tar.xz", "https://www.gnu.org/software/autoconf/"),
        LFSPackage("Automake", "1.18.1", "automake-1.18.1.tar.xz", "1.614 KB", "cea31dbf1120f890cbf2a3032cfb9a68", "https://ftpmirror.gnu.org/automake/automake-1.18.1.tar.xz", "https://www.gnu.org/software/automake/"),
        LFSPackage("Bash", "5.3", "bash-5.3.tar.gz", "11.089 KB", "977c8c0c5ae6309191e7768e28ebc951", "https://ftpmirror.gnu.org/bash/bash-5.3.tar.gz", "https://www.gnu.org/software/bash/"),
        LFSPackage("Bc", "7.0.3", "bc-7.0.3.tar.xz", "490 KB", "64ddda77e1df2ef5a022d26d36e2f1cf", "https://github.com/gavinhoward/bc/releases/download/7.0.3/bc-7.0.3.tar.xz", "https://git.gavinhoward.com/gavin/bc"),
        LFSPackage("Binutils", "2.44", "binutils-2.44.tar.xz", "26.312 KB", "18ff3439bceebbe98e3b5e40e2c8fa40", "https://ftpmirror.gnu.org/binutils/binutils-2.44.tar.xz", "https://www.gnu.org/software/binutils/"),
        LFSPackage("Bison", "3.8.2", "bison-3.8.2.tar.xz", "2.756 KB", "c28f119f404e2978cf5989f6db444db8", "https://ftpmirror.gnu.org/bison/bison-3.8.2.tar.xz", "https://www.gnu.org/software/bison/"),
        LFSPackage("Bzip2", "1.0.8", "bzip2-1.0.8.tar.gz", "1.028 KB", "67e0518f2c04e7d2e241700d380e3029", "https://www.sourceware.org/pub/bzip2/bzip2-1.0.8.tar.gz", "https://sourceware.org/bzip2/"),
        LFSPackage("Coreutils", "9.11", "coreutils-9.11.tar.xz", "6.084 KB", "44aa3bbddb44be58ea9c1a59fb605e5d", "https://ftpmirror.gnu.org/coreutils/coreutils-9.11.tar.xz", "https://www.gnu.org/software/coreutils/"),
        LFSPackage("Diffutils", "3.12", "diffutils-3.12.tar.xz", "1.748 KB", "d2454ec7753e1f0e47063d8d69784572", "https://ftpmirror.gnu.org/diffutils/diffutils-3.12.tar.xz", "https://www.gnu.org/software/diffutils/"),
        LFSPackage("E2fsprogs", "1.47.4", "e2fsprogs-1.47.4.tar.gz", "9.832 KB", "036ba7dfa2db7f8ecad8a970e5138ba4", "https://downloads.sourceforge.net/project/e2fsprogs/e2fsprogs/v1.47.4/e2fsprogs-1.47.4.tar.gz", "https://e2fsprogs.sourceforge.net/"),
        LFSPackage("File", "5.46", "file-5.46.tar.gz", "1.250 KB", "c7e1d5a7ef6409fe0f058cf273d42e01", "https://astron.com/pub/file/file-5.46.tar.gz", "https://darwinsys.com/file/"),
        LFSPackage("Findutils", "4.10.0", "findutils-4.10.0.tar.xz", "2.190 KB", "1387e0766723fe21d4c2b92eb18ff220", "https://ftpmirror.gnu.org/findutils/findutils-4.10.0.tar.xz", "https://www.gnu.org/software/findutils/"),
        LFSPackage("Gawk", "5.3.1", "gawk-5.3.1.tar.xz", "3.380 KB", "75cfc21ff213fbe4e52ec778bd14cfef", "https://ftpmirror.gnu.org/gawk/gawk-5.3.1.tar.xz", "https://www.gnu.org/software/gawk/"),
        LFSPackage("GCC", "16.2.0", "gcc-16.2.0.tar.xz", "94.200 KB", "fa5df7bce17fa2b0a94b5952fdf3dbe2", "https://ftpmirror.gnu.org/gcc/gcc-16.2.0/gcc-16.2.0.tar.xz", "https://gcc.gnu.org/"),
        LFSPackage("Glibc", "2.44", "glibc-2.44.tar.xz", "19.380 KB", "7cf6fbbfb92d847cb59e5e783ca1e73a", "https://ftpmirror.gnu.org/glibc/glibc-2.44.tar.xz", "https://www.gnu.org/software/libc/"),
        LFSPackage("GMP", "6.3.0", "gmp-6.3.0.tar.xz", "2.050 KB", "95ab32fd86ca844cb1783e449a0eec9a", "https://ftpmirror.gnu.org/gmp/gmp-6.3.0.tar.xz", "https://gmplib.org/"),
        LFSPackage("Grep", "3.12", "grep-3.12.tar.xz", "1.750 KB", "be57d6d3bc0a66d03a557b47318ec802", "https://ftpmirror.gnu.org/grep/grep-3.12.tar.xz", "https://www.gnu.org/software/grep/"),
        LFSPackage("Gzip", "1.14", "gzip-1.14.tar.xz", "835 KB", "1028fa6052df6e0261ca6d5fbd7f8674", "https://ftpmirror.gnu.org/gzip/gzip-1.14.tar.xz", "https://www.gnu.org/software/gzip/"),
        LFSPackage("Linux Kernel", "6.14.7", "linux-6.14.7.tar.xz", "147.220 KB", "1d97f8c0a5a3a78912345678abcdef01", "https://www.kernel.org/pub/linux/kernel/v6.x/linux-6.14.7.tar.xz", "https://www.kernel.org/"),
        LFSPackage("M4", "1.4.19", "m4-1.4.19.tar.xz", "1.650 KB", "0b67e716eeefd348a05c74eb1c28c688", "https://ftpmirror.gnu.org/m4/m4-1.4.19.tar.xz", "https://www.gnu.org/software/m4/"),
        LFSPackage("Make", "4.4.1", "make-4.4.1.tar.gz", "2.327 KB", "882798e16e09be036573c09b265d64cb", "https://ftpmirror.gnu.org/make/make-4.4.1.tar.gz", "https://www.gnu.org/software/make/"),
        LFSPackage("MPC", "1.4.1", "mpc-1.4.1.tar.gz", "750 KB", "22ea782b84784400cf9d7e35b71db3f4", "https://ftpmirror.gnu.org/mpc/mpc-1.4.1.tar.gz", "https://www.multiprecision.org/"),
        LFSPackage("MPFR", "4.2.2", "mpfr-4.2.2.tar.xz", "1.520 KB", "f4c2196144e311093557e5ab48386de6", "https://ftpmirror.gnu.org/mpfr/mpfr-4.2.2.tar.xz", "https://www.mpfr.org/"),
        LFSPackage("Ncurses", "6.5", "ncurses-6.5.tar.gz", "3.600 KB", "9a386dae034ce025b6ff4f33100fe324", "https://invisible-mirror.net/archives/ncurses/ncurses-6.5.tar.gz", "https://invisible-island.net/ncurses/"),
        LFSPackage("Patch", "2.7.6", "patch-2.7.6.tar.xz", "764 KB", "78ad9937e4caadcba152669f49ec45fb", "https://ftpmirror.gnu.org/patch/patch-2.7.6.tar.xz", "https://savannah.gnu.org/projects/patch/"),
        LFSPackage("Sed", "4.9", "sed-4.9.tar.xz", "1.365 KB", "6df448218184511ba5ec3e00e84c9878", "https://ftpmirror.gnu.org/sed/sed-4.9.tar.xz", "https://www.gnu.org/software/sed/"),
        LFSPackage("Tar", "1.35", "tar-1.35.tar.xz", "2.264 KB", "35a5cb35560938f36c57f9ed314cb6d6", "https://ftpmirror.gnu.org/tar/tar-1.35.tar.xz", "https://www.gnu.org/software/tar/"),
        LFSPackage("Xz", "5.8.1", "xz-5.8.1.tar.xz", "1.320 KB", "85d564fa7e8efea03b4142f1cf57df66", "https://github.com/tukaani-project/xz/releases/download/v5.8.1/xz-5.8.1.tar.xz", "https://tukaani.org/xz/"),
        # Patches
        LFSPackage("Remendo da Documentação do Bzip2", "", "bzip2-1.0.8-install_docs-1.patch", "1.6 KB", "6a5ac7e89b791aae556de0f745916f7f", "https://www.linuxfromscratch.org/patches/lfs/13.1/bzip2-1.0.8-install_docs-1.patch", "https://www.linuxfromscratch.org/patches/lfs/13.1/bzip2-1.0.8-install_docs-1.patch", is_patch=True),
        LFSPackage("Remendo de Correções de Internacionalização do Coreutils", "", "coreutils-9.11-i18n-1.patch", "67 KB", "900d64d9936516b68613271c9ebc0059", "https://www.linuxfromscratch.org/patches/lfs/13.1/coreutils-9.11-i18n-1.patch", "https://www.linuxfromscratch.org/patches/lfs/13.1/coreutils-9.11-i18n-1.patch", is_patch=True),
        LFSPackage("Remendo GCC15 do Expect", "", "expect-5.45.4-gcc15-1.patch", "12 KB", "0ca4d6bb8d572fbcdb13cb36cd34833e", "https://www.linuxfromscratch.org/patches/lfs/13.1/expect-5.45.4-gcc15-1.patch", "https://www.linuxfromscratch.org/patches/lfs/13.1/expect-5.45.4-gcc15-1.patch", is_patch=True),
    ]


def init_catalog(html_path: Optional[Path | str] = None) -> List[LFSPackage]:
    """Loads and caches the package catalog from HTML or fallback."""
    global _PACKAGES_CACHE
    if _PACKAGES_CACHE is not None:
        return _PACKAGES_CACHE

    target_path = Path(html_path) if html_path else Path("LFS-SYSV-BOOK-13.1-pt_BR-NOCHUNKS.html")
    if not target_path.exists():
        target_path = Path(__file__).resolve().parents[3] / "LFS-SYSV-BOOK-13.1-pt_BR-NOCHUNKS.html"

    packages = _parse_html_book(target_path)
    if not packages:
        packages = _get_fallback_catalog()

    _PACKAGES_CACHE = packages
    return _PACKAGES_CACHE


def list_packages(include_patches: bool = True) -> List[LFSPackage]:
    """Returns list of packages (and optionally patches)."""
    catalog = init_catalog()
    if include_patches:
        return catalog
    return [p for p in catalog if not p.is_patch]


def get_package(name_or_tarball: str) -> Optional[LFSPackage]:
    """Finds a package by name or tarball name."""
    catalog = init_catalog()
    query = name_or_tarball.strip().lower()
    for p in catalog:
        if (
            p.name.lower() == query
            or p.tarball.lower() == query
            or p.tarball.lower().startswith(query + "-")
            or p.name.lower().startswith(query)
        ):
            return p
    return None


def get_md5sums_text() -> str:
    """Generates the md5sums file content formatted as '<md5>  <tarball>'."""
    catalog = init_catalog()
    lines = []
    for p in catalog:
        if p.md5 and p.tarball:
            lines.append(f"{p.md5}  {p.tarball}")
    return "\n".join(lines) + "\n"


# ============================================================================
# CHAPTER 5 & 6 TOOLCHAIN CATALOG
# ============================================================================

TOOLCHAIN_CATALOG: Dict[str, ToolchainPackage] = {
    # --- Chapter 5: Cross-Toolchain ---
    "binutils-pass1": ToolchainPackage(
        id="binutils-pass1",
        name="Binutils - Passagem 1",
        version="2.44",
        chapter=5,
        sbu=1.0,
        sbu_label="1,0 UPC (SBU)",
        description="Montador (as), vinculador (ld) e ferramentas de manipulação de binários ELF.",
        configure_flags="../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT --disable-nls --enable-gprofng=no --disable-werror --enable-new-dtags --enable-default-hash-style=gnu",
        build_steps="mkdir build; cd build; ../configure ...; make; make install",
        install_path="$LFS/tools",
        binaries=["$LFS_TGT-ld", "$LFS_TGT-as", "$LFS_TGT-ar", "$LFS_TGT-nm", "$LFS_TGT-objcopy", "$LFS_TGT-objdump", "$LFS_TGT-ranlib", "$LFS_TGT-readelf", "$LFS_TGT-strip"]
    ),
    "gcc-pass1": ToolchainPackage(
        id="gcc-pass1",
        name="GCC - Passagem 1",
        version="16.2.0",
        chapter=5,
        sbu=4.3,
        sbu_label="4,3 UPC (SBU)",
        description="Compilador C/C++ cruzado inicial gerado com suporte a GMP, MPFR e MPC.",
        configure_flags="../configure --target=$LFS_TGT --prefix=$LFS/tools --with-glibc-version=2.44 --with-sysroot=$LFS --with-newlib --without-headers --enable-default-pie --enable-default-ssp --disable-fixincludes --disable-nls --disable-shared --disable-multilib --disable-threads --disable-libatomic --disable-libgomp --disable-libquadmath --disable-libssp --disable-libvtv --disable-libstdcxx --enable-languages=c,c++",
        build_steps="tar -xf mpfr, gmp, mpc; mkdir build; cd build; ../configure ...; make; make install",
        install_path="$LFS/tools",
        binaries=["$LFS_TGT-gcc", "$LFS_TGT-g++", "$LFS_TGT-cpp"]
    ),
    "linux-headers": ToolchainPackage(
        id="linux-headers",
        name="Linux API Headers",
        version="6.14.7",
        chapter=5,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Cabeçalhos de API do núcleo Linux expostos para uso da Glibc e aplicações do espaço de usuário.",
        configure_flags="make mrproper && make headers",
        build_steps="make mrproper; make headers; cp -rv usr/include $LFS/usr",
        install_path="$LFS/usr/include",
        binaries=[]
    ),
    "glibc": ToolchainPackage(
        id="glibc",
        name="Glibc",
        version="2.44",
        chapter=5,
        sbu=1.3,
        sbu_label="1,3 UPC (SBU)",
        description="Biblioteca Principal C da GNU: chamadas de sistema, alocador de memória e interpretador dinâmico ld-linux.",
        configure_flags="../configure --prefix=/usr --host=$LFS_TGT --build=$(../scripts/config.guess) --disable-nscd libc_cv_slibdir=/usr/lib --enable-kernel=5.10",
        build_steps="mkdir build; cd build; ../configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr",
        binaries=["ldd", "libc.so.6", "ld-linux-x86-64.so.2"]
    ),
    "libstdc++": ToolchainPackage(
        id="libstdc++",
        name="Libstdc++ - Passagem 1",
        version="16.2.0",
        chapter=5,
        sbu=0.3,
        sbu_label="0,3 UPC (SBU)",
        description="Biblioteca Padrão C++ do GCC necessária para compilar programas em C++ na toolchain.",
        configure_flags="../libstdc++-v3/configure --host=$LFS_TGT --build=$(../config.guess) CXX=$LFS_TGT-gcc --prefix=/usr --disable-multilib --disable-nls --disable-libstdcxx-pch --with-gxx-include-dir=/tools/$LFS_TGT/include/c++/16.2.0",
        build_steps="mkdir build; cd build; ../libstdc++-v3/configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/lib",
        binaries=["libstdc++.so", "libstdc++.so.6"]
    ),

    # --- Chapter 6: Cross-Compiled Temporary Tools ---
    "m4": ToolchainPackage(
        id="m4",
        name="M4",
        version="1.4.19",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Processador clássico de macros para Unix.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["m4"]
    ),
    "ncurses": ToolchainPackage(
        id="ncurses",
        name="Ncurses",
        version="6.5",
        chapter=6,
        sbu=0.4,
        sbu_label="0,4 UPC (SBU)",
        description="Biblioteca de manipulação de telas de terminal e consoles de texto.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(./config.guess) --mandir=/usr/share/man --with-shared --without-debug --without-ada --without-normal --enable-widec",
        build_steps="./configure ...; make TIC_PATH=$(pwd)/progs/tic; make DESTDIR=$LFS TIC_PATH=$(pwd)/progs/tic install",
        install_path="$LFS/usr/bin",
        binaries=["tic", "clear", "tput", "libncursesw.so.6"]
    ),
    "bash": ToolchainPackage(
        id="bash",
        name="Bash",
        version="5.3",
        chapter=6,
        sbu=0.2,
        sbu_label="0,2 UPC (SBU)",
        description="Bourne-Again SHell, o interpretador de comandos padrão do LFS.",
        configure_flags="./configure --prefix=/usr --build=$(support/config.guess) --host=$LFS_TGT --without-bash-malloc",
        build_steps="./configure ...; make; make DESTDIR=$LFS install; ln -sv bash $LFS/bin/sh",
        install_path="$LFS/usr/bin",
        binaries=["bash", "sh"]
    ),
    "coreutils": ToolchainPackage(
        id="coreutils",
        name="Coreutils",
        version="9.11",
        chapter=6,
        sbu=0.3,
        sbu_label="0,3 UPC (SBU)",
        description="Utilitários centrais do GNU para gerenciamento de arquivos, texto e processos.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess) --enable-install-program=hostname --enable-no-install-program=kill,uptime",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["cat", "ls", "cp", "mv", "rm", "mkdir", "rmdir", "chmod", "chown", "uname", "echo"]
    ),
    "diffutils": ToolchainPackage(
        id="diffutils",
        name="Diffutils",
        version="3.12",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Ferramentas para encontrar diferenças entre arquivos de texto.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["diff", "cmp", "sdiff", "diff3"]
    ),
    "file": ToolchainPackage(
        id="file",
        name="File",
        version="5.46",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Utilitário para determinar o tipo de arquivo por assinaturas 'magic'.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(./config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["file"]
    ),
    "findutils": ToolchainPackage(
        id="findutils",
        name="Findutils",
        version="4.10.0",
        chapter=6,
        sbu=0.2,
        sbu_label="0,2 UPC (SBU)",
        description="Programas para localizar e executar comandos em árvores de diretórios.",
        configure_flags="./configure --prefix=/usr --localstatedir=/var/lib/locate --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["find", "xargs"]
    ),
    "gawk": ToolchainPackage(
        id="gawk",
        name="Gawk",
        version="5.3.1",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Processador de padrões e linguagem de varredura de texto AWK.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["gawk", "awk"]
    ),
    "grep": ToolchainPackage(
        id="grep",
        name="Grep",
        version="3.12",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Buscador de padrões com expressões regulares em texto.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["grep", "egrep", "fgrep"]
    ),
    "gzip": ToolchainPackage(
        id="gzip",
        name="Gzip",
        version="1.14",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Compactador e descompactador clássico de arquivos .gz.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["gzip", "gunzip", "zcat"]
    ),
    "make": ToolchainPackage(
        id="make",
        name="Make",
        version="4.4.1",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Utilitário de automação de compilação baseado em Makefiles.",
        configure_flags="./configure --prefix=/usr --without-guile --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["make"]
    ),
    "patch": ToolchainPackage(
        id="patch",
        name="Patch",
        version="2.7.6",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Aplica diferenças e remendos de código a arquivos fonte.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["patch"]
    ),
    "sed": ToolchainPackage(
        id="sed",
        name="Sed",
        version="4.9",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Editor de fluxo para transformações de texto em linha de comando.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["sed"]
    ),
    "tar": ToolchainPackage(
        id="tar",
        name="Tar",
        version="1.35",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Utilitário de arquivamento em fita e manipulação de tarballs.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess)",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["tar"]
    ),
    "xz": ToolchainPackage(
        id="xz",
        name="Xz",
        version="5.8.1",
        chapter=6,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Compactador de dados de alta eficiência baseado no algoritmo LZMA.",
        configure_flags="./configure --prefix=/usr --host=$LFS_TGT --build=$(build-aux/config.guess) --disable-static --docdir=/usr/share/doc/xz-5.8.1",
        build_steps="./configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["xz", "lzma", "unxz"]
    ),
    "binutils-pass2": ToolchainPackage(
        id="binutils-pass2",
        name="Binutils - Passagem 2",
        version="2.44",
        chapter=6,
        sbu=0.4,
        sbu_label="0,4 UPC (SBU)",
        description="Segunda passagem do Binutils: vinculação nativa contra a recém-criada Glibc.",
        configure_flags="../configure --prefix=/usr --build=$(../config.guess) --host=$LFS_TGT --disable-nls --enable-shared --enable-gprofng=no --disable-werror --enable-64-bit-bfd --enable-new-dtags --enable-default-hash-style=gnu",
        build_steps="mkdir build; cd build; ../configure ...; make; make DESTDIR=$LFS install",
        install_path="$LFS/usr/bin",
        binaries=["ld", "as", "readelf", "nm", "objdump", "strip"]
    ),
    "gcc-pass2": ToolchainPackage(
        id="gcc-pass2",
        name="GCC - Passagem 2",
        version="16.2.0",
        chapter=6,
        sbu=5.2,
        sbu_label="5,2 UPC (SBU)",
        description="A Boss Fight do Ato 2! Segunda passagem do compilador GCC com libstdc++ completa e limites de sistema estéreis.",
        configure_flags="../configure --build=$(../config.guess) --host=$LFS_TGT --target=$LFS_TGT LDFLAGS_FOR_TARGET=-L$PWD/$LFS_TGT/libgcc --prefix=/usr --with-sysroot=$LFS --enable-languages=c,c++ --enable-default-pie --enable-default-ssp --disable-nls --disable-multilib",
        build_steps="mkdir build; cd build; ../configure ...; make; make DESTDIR=$LFS install; ln -sv gcc $LFS/usr/bin/cc",
        install_path="$LFS/usr/bin",
        binaries=["gcc", "g++", "cpp", "cc"]
    ),

    # --- Chapter 7: Additional Chroot Temporary Tools ---
    "gettext": ToolchainPackage(
        id="gettext",
        name="Gettext",
        version="1.0",
        chapter=7,
        sbu=1.5,
        sbu_label="1,5 UPC (SBU)",
        description="Utilitários para internacionalização e localização (NLS) do sistema no chroot.",
        configure_flags="./configure --disable-shared",
        build_steps="./configure --disable-shared; make; cp -v src/{msgfmt,msgmerge,xgettext} /usr/bin",
        install_path="/usr/bin",
        binaries=["msgfmt", "xgettext", "msgmerge", "gettext"]
    ),
    "bison": ToolchainPackage(
        id="bison",
        name="Bison",
        version="3.8.2",
        chapter=7,
        sbu=0.2,
        sbu_label="0,2 UPC (SBU)",
        description="Gerador de analisadores sintáticos compatível com Yacc, essencial para compilações futuras.",
        configure_flags="./configure --prefix=/usr --docdir=/usr/share/doc/bison-3.8.2",
        build_steps="./configure --prefix=/usr --docdir=/usr/share/doc/bison-3.8.2; make; make install",
        install_path="/usr/bin",
        binaries=["bison", "yacc"]
    ),
    "perl": ToolchainPackage(
        id="perl",
        name="Perl",
        version="5.44.0",
        chapter=7,
        sbu=0.6,
        sbu_label="0,6 UPC (SBU)",
        description="Practical Extraction and Report Language: interpretador poderoso exigido pelas suítes de build.",
        configure_flags="sh Configure -des -Dprefix=/usr -Dvendorprefix=/usr -Duseshrplib -Dprivlib=/usr/lib/perl5/5.44/core_perl",
        build_steps="sh Configure ...; make; make install",
        install_path="/usr/bin",
        binaries=["perl", "perl5"]
    ),
    "python": ToolchainPackage(
        id="python",
        name="Python 3",
        version="3.14.7",
        chapter=7,
        sbu=0.5,
        sbu_label="0,5 UPC (SBU)",
        description="Ambiente de script e desenvolvimento Python 3 para utilitários do sistema moderno.",
        configure_flags="./configure --prefix=/usr --enable-shared --without-ensurepip --without-static-libpython",
        build_steps="./configure --prefix=/usr --enable-shared --without-ensurepip; make; make install",
        install_path="/usr/bin",
        binaries=["python3", "pip3", "python"]
    ),
    "texinfo": ToolchainPackage(
        id="texinfo",
        name="Texinfo",
        version="7.2",
        chapter=7,
        sbu=0.2,
        sbu_label="0,2 UPC (SBU)",
        description="Ferramentas para leitura, escrita e conversão de manuais e documentação GNU info.",
        configure_flags="./configure --prefix=/usr",
        build_steps="./configure --prefix=/usr; make; make install",
        install_path="/usr/bin",
        binaries=["makeinfo", "info", "texi2any"]
    ),
    "util-linux": ToolchainPackage(
        id="util-linux",
        name="Util-linux",
        version="2.41.3",
        chapter=7,
        sbu=0.2,
        sbu_label="0,2 UPC (SBU)",
        description="Coleção de utilitários de baixo nível do sistema Linux (mount, umount, dmesg, rfkill, etc.).",
        configure_flags="./configure --libdir=/usr/lib --runstatedir=/run --disable-chfn-chsh --disable-login --disable-su --without-python",
        build_steps="./configure ...; make; make install",
        install_path="/usr/bin",
        binaries=["mount", "umount", "dmesg", "more", "rfkill", "findmnt"]
    ),

    # --- Chapter 9 & 10: System Configuration, Kernel & Bootloader ---
    "lfs-bootscripts": ToolchainPackage(
        id="lfs-bootscripts",
        name="LFS-Bootscripts",
        version="20250827",
        chapter=9,
        sbu=0.1,
        sbu_label="0,1 UPC (SBU)",
        description="Conjunto de scripts de inicialização SysVinit (/etc/rc.d/* e /lib/services/*) para rede, montagens e daemons.",
        configure_flags="make install",
        build_steps="tar -xf lfs-bootscripts-20250827.tar.xz; cd lfs-bootscripts-20250827; make install",
        install_path="/etc/rc.d",
        binaries=["/etc/rc.d/init.d/rc", "/etc/rc.d/init.d/network", "/lib/services/ipv4-static"]
    ),
    "linux-kernel": ToolchainPackage(
        id="linux-kernel",
        name="Linux Kernel",
        version="7.1.8",
        chapter=10,
        sbu=3.5,
        sbu_label="3,5 UPC (SBU)",
        description="Núcleo Linux 7.1.8 definitivo com suporte built-in a ext4, devtmpfs, SATA AHCI e ELF para boot direto.",
        configure_flags="make mrproper && make defconfig && make menuconfig",
        build_steps="make mrproper; make menuconfig; make; make modules_install; cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1",
        install_path="/boot",
        binaries=["vmlinuz-7.1.8-lfs-13.1", "System.map-7.1.8", "config-7.1.8"]
    ),
}

# ============================================================================
# CHAPTER 8: INSTALLING BASIC SYSTEM SOFTWARE (TIERS 1-4, LFS 13.1 8.3-8.83)
# ============================================================================

_CH8_SPECS = [
    # --- Tier 1 (8.3 - 8.21) ---
    (1, "man-pages", "Man-pages", "6.18", 0.1, "Páginas de manual do kernel Linux e chamadas de sistema POSIX.", "make -R GIT=false prefix=/usr install", "/usr/share/man", []),
    (1, "iana-etc", "Iana-Etc", "20260805", 0.1, "Dados para serviços de rede (/etc/services) e protocolos (/etc/protocols).", "cp services protocols /etc", "/etc", []),
    (1, "glibc-final", "Glibc (Definitiva)", "2.44", 19.0, "Biblioteca C GNU definitiva com suporte completo a locales e suíte de testes.", "../configure --prefix=/usr --disable-werror --enable-stack-protector=strong --disable-nscd libc_cv_slibdir=/usr/lib", "/usr/lib", ["ldd", "localedef", "iconv", "libc.so.6", "ld-linux-x86-64.so.2"]),
    (1, "zlib", "Zlib", "1.3.2", 0.1, "Biblioteca de compressão e descompressão DEFLATE usada por inúmeros pacotes.", "./configure --prefix=/usr", "/usr/lib", ["libz.so.1"]),
    (1, "bzip2", "Bzip2", "1.0.8", 0.1, "Compactador de blocos de alta taxa de compressão.", "make -f Makefile-libbz2_so && make && make PREFIX=/usr install", "/usr/bin", ["bzip2", "bunzip2", "bzcat", "libbz2.so.1.0"]),
    (1, "xz-final", "Xz (Definitivo)", "5.8.3", 0.1, "Utilitários e biblioteca liblzma definitivos para arquivos .xz.", "./configure --prefix=/usr --disable-static --docdir=/usr/share/doc/xz-5.8.3", "/usr/bin", ["xz", "unxz", "lzma", "liblzma.so.5"]),
    (1, "lz4", "Lz4", "1.10.0", 0.1, "Algoritmo de compressão sem perdas de altíssima velocidade.", "make BUILD_STATIC=no PREFIX=/usr && make BUILD_STATIC=no PREFIX=/usr install", "/usr/bin", ["lz4", "unlz4", "liblz4.so.1"]),
    (1, "zstd", "Zstd", "1.5.7", 0.5, "Zstandard: compressão moderna rápida com suporte a kernel e tar.", "make prefix=/usr && make prefix=/usr install", "/usr/bin", ["zstd", "unzstd", "zstdcat", "libzstd.so.1"]),
    (1, "file-final", "File (Definitivo)", "5.48", 0.1, "Identificador de tipos de arquivo e biblioteca libmagic.", "./configure --prefix=/usr", "/usr/bin", ["file", "libmagic.so.1"]),
    (1, "readline", "Readline", "8.3", 0.1, "Biblioteca de edição de linha de comando e histórico para Bash e afins.", "./configure --prefix=/usr --disable-static --with-curses", "/usr/lib", ["libreadline.so.8", "libhistory.so.8"]),
    (1, "pcre2", "Pcre2", "10.47", 0.4, "Expressões regulares compatíveis com Perl (versão 2).", "./configure --prefix=/usr --enable-unicode --enable-jit --enable-pcre2-16 --enable-pcre2-32 --disable-static", "/usr/lib", ["pcre2grep", "libpcre2-8.so.0"]),
    (1, "m4-final", "M4 (Definitivo)", "1.4.21", 0.2, "Processador de macros definitivo exigido pelo Autoconf e Bison.", "./configure --prefix=/usr", "/usr/bin", ["m4"]),
    (1, "bc", "Bc", "7.0.3", 0.1, "Calculadora de precisão arbitrária usada durante a compilação do kernel Linux.", "CC='gcc -std=c99' ./configure --prefix=/usr -G -O3 -r", "/usr/bin", ["bc", "dc"]),
    (1, "flex", "Flex", "2.6.4", 0.1, "Gerador de analisadores léxicos (Fast Lexical Analyzer).", "./configure --prefix=/usr --docdir=/usr/share/doc/flex-2.6.4 --disable-static", "/usr/bin", ["flex", "lex"]),
    (1, "tcl", "Tcl", "8.6.18", 2.9, "Linguagem de script Tool Command Language, base para Expect e DejaGNU.", "./configure --prefix=/usr --mandir=/usr/share/man --disable-rpath", "/usr/bin", ["tclsh", "tclsh8.6", "libtcl8.6.so"]),
    (1, "expect", "Expect", "5.45.4", 0.2, "Ferramenta de automação interativa para execução de suítes de testes.", "./configure --prefix=/usr --with-tcl=/usr/lib --enable-shared --disable-rpath", "/usr/bin", ["expect"]),
    (1, "dejagnu", "DejaGNU", "1.6.3", 0.1, "Framework de testes automatizados requerido pelas suítes do GCC e Binutils.", "../configure --prefix=/usr", "/usr/bin", ["runtest"]),
    (1, "ninja", "Ninja", "1.13.2", 0.2, "Sistema de build minimalista de alta velocidade usado pelo Meson.", "python3 configure.py --bootstrap", "/usr/bin", ["ninja"]),
    (1, "pkgconf", "Pkgconf", "3.0.5", 0.1, "Gerenciador de flags de compilação e vinculação de bibliotecas (pkg-config).", "./configure --prefix=/usr --disable-static --docdir=/usr/share/doc/pkgconf-3.0.5", "/usr/bin", ["pkgconf", "pkg-config"]),

    # --- Tier 2 (8.22 - 8.40) ---
    (2, "binutils-final", "Binutils (Definitivo)", "2.47", 4.5, "Montador, vinculador e ferramentas ELF nativas definitivas do sistema.", "../configure --prefix=/usr --sysconfdir=/etc --enable-ld=default --enable-plugins --enable-shared --disable-werror --enable-64-bit-bfd --enable-new-dtags --with-system-zlib --enable-default-hash-style=gnu", "/usr/bin", ["ld", "as", "ar", "nm", "objcopy", "objdump", "ranlib", "readelf", "strip"]),
    (2, "gmp", "GMP", "6.3.0", 0.4, "Biblioteca aritmética de precisão arbitrária (GNU Multiple Precision).", "./configure --prefix=/usr --enable-cxx --disable-static --docdir=/usr/share/doc/gmp-6.3.0", "/usr/lib", ["libgmp.so.10", "libgmpxx.so.4"]),
    (2, "mpfr", "MPFR", "4.2.2", 0.3, "Biblioteca de ponto flutuante de múltipla precisão com arredondamento exato.", "./configure --prefix=/usr --disable-static --enable-thread-safe", "/usr/lib", ["libmpfr.so.6"]),
    (2, "mpc", "MPC", "1.4.1", 0.1, "Biblioteca aritmética de números complexos de alta precisão.", "./configure --prefix=/usr --disable-static", "/usr/lib", ["libmpc.so.3"]),
    (2, "attr", "Attr", "2.6.0", 0.1, "Utilitários e biblioteca para atributos estendidos do sistema de arquivos.", "./configure --prefix=/usr --disable-static --sysconfdir=/etc", "/usr/bin", ["attr", "getfattr", "setfattr", "libattr.so.1"]),
    (2, "acl", "Acl", "2.4.0", 0.1, "Ferramentas de gerenciamento de Listas de Controle de Acesso POSIX.", "./configure --prefix=/usr --disable-static", "/usr/bin", ["getfacl", "setfacl", "chacl", "libacl.so.1"]),
    (2, "libcap", "Libcap", "2.78", 0.1, "Interface de espaço de usuário para POSIX 1003.1e capabilities do kernel.", "make prefix=/usr lib=lib && make prefix=/usr lib=lib install", "/usr/sbin", ["getcap", "setcap", "capsh", "libcap.so.2"]),
    (2, "libxcrypt", "Libxcrypt", "4.5.2", 0.1, "Biblioteca moderna de hashing de senhas (SHA-512, yescrypt, bcrypt).", "./configure --prefix=/usr --enable-hashes=strong,glibc --enable-obsolete-api=no --disable-static", "/usr/lib", ["libcrypt.so.2"]),
    (2, "shadow", "Shadow", "4.20.2", 0.2, "Programas de gerenciamento seguro de contas e senhas criptografadas (/etc/shadow).", "./configure --sysconfdir=/etc --disable-static --with-{b,yes}crypt --without-libbsd", "/usr/sbin", ["pwconv", "grpconv", "passwd", "useradd", "groupadd", "su", "login"]),
    (2, "gawk-final", "Gawk (Definitivo)", "5.4.1", 0.2, "Interpretador definitivo da linguagem AWK.", "./configure --prefix=/usr", "/usr/bin", ["gawk", "awk"]),
    (2, "gcc-final", "GCC (Definitivo)", "16.2.0", 62.0, "Compilador definitivo C/C++ nativo do sistema LFS com suíte completa de testes.", "../configure --prefix=/usr LD=ld --enable-languages=c,c++ --enable-default-pie --enable-default-ssp --enable-host-pie --disable-multilib --disable-bootstrap --disable-fixincludes --with-system-zlib", "/usr/bin", ["gcc", "g++", "cc", "cpp", "gcov"]),
    (2, "ncurses-final", "Ncurses (Definitivo)", "6.6", 0.5, "Bibliotecas de terminal wide-character definitivas para interface TUI.", "./configure --prefix=/usr --mandir=/usr/share/man --with-shared --without-debug --without-normal --with-cxx-shared --enable-pc-files --with-pkg-config-libdir=/usr/lib/pkgconfig", "/usr/lib", ["tput", "clear", "tic", "infocmp", "libncursesw.so.6"]),
    (2, "sed-final", "Sed (Definitivo)", "4.10", 0.2, "Editor de fluxo de texto definitivo.", "./configure --prefix=/usr", "/usr/bin", ["sed"]),
    (2, "psmisc", "Psmisc", "23.7", 0.1, "Utilitários de inspeção e controle de processos (/proc): killall, fuser, pstree.", "./configure --prefix=/usr", "/usr/bin", ["fuser", "killall", "pstree"]),
    (2, "gettext-final", "Gettext (Definitivo)", "1.0", 2.0, "Suíte definitiva de internacionalização e tradução de mensagens.", "./configure --prefix=/usr --disable-static", "/usr/bin", ["gettext", "msgfmt", "msgmerge", "xgettext"]),
    (2, "bison-final", "Bison (Definitivo)", "3.8.2", 0.4, "Gerador de analisadores sintáticos definitivo compatível com Yacc.", "./configure --prefix=/usr", "/usr/bin", ["bison", "yacc"]),
    (2, "grep-final", "Grep (Definitivo)", "3.12", 0.4, "Buscador definitivo de expressões regulares.", "./configure --prefix=/usr", "/usr/bin", ["grep", "egrep", "fgrep"]),
    (2, "bash-final", "Bash (Definitivo)", "5.3", 1.3, "Interpretador de shell definitivo compilado contra Readline e Ncurses nativos.", "./configure --prefix=/usr --without-bash-malloc --with-installed-readline", "/usr/bin", ["bash", "sh"]),
    (2, "libtool", "Libtool", "2.6.2", 1.0, "Script genérico de suporte à criação de bibliotecas compartilhadas.", "./configure --prefix=/usr", "/usr/bin", ["libtool", "libtoolize", "libltdl.so.7"]),

    # --- Tier 3 (8.41 - 8.60) ---
    (3, "gdbm", "GDBM", "1.26", 0.1, "GNU Database Manager: biblioteca de banco de dados chave-valor.", "./configure --prefix=/usr --disable-static --enable-libgdbm-compat", "/usr/lib", ["gdbmtool", "libgdbm.so.6"]),
    (3, "gperf", "Gperf", "3.3", 0.1, "Gerador de funções hash perfeitas usado pelo Udev e GCC.", "./configure --prefix=/usr", "/usr/bin", ["gperf"]),
    (3, "expat", "Expat", "2.8.3", 0.1, "Biblioteca parser XML orientada a fluxo usada pelo Python e D-Bus.", "./configure --prefix=/usr --disable-static", "/usr/lib", ["xmlwf", "libexpat.so.1"]),
    (3, "inetutils", "Inetutils", "2.8", 0.3, "Programas básicos de rede: hostname, ping, ifconfig, traceroute.", "./configure --prefix=/usr --bindir=/usr/bin --localstatedir=/var --disable-logger --disable-whois --disable-rcp --disable-rexec --disable-rlogin --disable-rsh --disable-servers", "/usr/bin", ["hostname", "ping", "traceroute", "ifconfig"]),
    (3, "less", "Less", "704", 0.1, "Paginador de arquivos de texto para terminal.", "./configure --prefix=/usr --sysconfdir=/etc", "/usr/bin", ["less", "lessecho", "lesskey"]),
    (3, "perl-final", "Perl (Definitivo)", "5.44.0", 1.9, "Interpretador Perl 5 definitivo com módulos completos.", "sh Configure -des -Dprefix=/usr -Dvendorprefix=/usr -Duseshrplib -Dusethreads", "/usr/bin", ["perl", "cpan", "perldoc"]),
    (3, "autoconf", "Autoconf", "2.73", 0.9, "Gerador de scripts ./configure portáveis para pacotes GNU.", "./configure --prefix=/usr", "/usr/bin", ["autoconf", "autoheader", "autoreconf"]),
    (3, "automake", "Automake", "1.18.1", 1.8, "Gerador de Makefiles compatíveis com os padrões GNU.", "./configure --prefix=/usr", "/usr/bin", ["automake", "aclocal"]),
    (3, "openssl", "OpenSSL", "4.0.1", 3.1, "Biblioteca criptográfica e protocolo TLS/SSL essencial para segurança e kernel.", "./config --prefix=/usr --openssldir=/etc/ssl --libdir=lib shared zlib-dynamic", "/usr/bin", ["openssl", "libssl.so.4", "libcrypto.so.4"]),
    (3, "libelf", "Libelf (Elfutils)", "0.195", 0.5, "Biblioteca de leitura e manipulação de binários ELF exigida para compilar o kernel Linux.", "./configure --prefix=/usr --disable-debuginfod --enable-libdebuginfod=dummy", "/usr/lib", ["libelf.so.1"]),
    (3, "libffi", "Libffi", "3.8.0", 0.1, "Foreign Function Interface: ponte de chamadas C para Python e linguagens dinâmicas.", "./configure --prefix=/usr --disable-static --with-gcc-arch=native", "/usr/lib", ["libffi.so.8"]),
    (3, "sqlite", "SQLite", "3530400", 0.4, "Motor de banco de dados SQL embutido sem servidor.", "./configure --prefix=/usr --disable-static --enable-fts5", "/usr/bin", ["sqlite3", "libsqlite3.so.0"]),
    (3, "mpdecimal-final", "mpdecimal", "4.0.1", 0.1, "Biblioteca de aritmética decimal de precisão arbitrária usada pelo módulo decimal do Python.", "./configure --prefix=/usr --disable-static", "/usr/lib", ["libmpdec.so.4"]),
    (3, "python-final", "Python 3 (Definitivo)", "3.14.7", 2.0, "Interpretador Python 3.14 definitivo com suporte completo a OpenSSL, SQLite e libffi.", "./configure --prefix=/usr --enable-shared --with-system-expat --enable-optimizations", "/usr/bin", ["python3", "python", "idle3", "libpython3.14.so"]),
    (3, "flit-core", "Flit-Core", "4.0.2", 0.1, "Backend de construção PEP 517 mínimo para pacotes Python.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/lib", []),
    (3, "packaging", "Packaging", "26.3", 0.1, "Utilitários centrais de versionamento e especificadores para pacotes Python.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/lib", []),
    (3, "wheel", "Wheel", "0.48.0", 0.1, "Implementação do formato de distribuição binária Python Wheel.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/bin", ["wheel"]),
    (3, "setuptools", "Setuptools", "84.0.0", 0.1, "Ferramenta padrão de empacotamento exigida pelo Meson e módulos Python.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/lib", []),
    (3, "meson", "Meson", "1.12.0", 0.1, "Sistema de automação de build moderno que gera arquivos para Ninja.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/bin", ["meson"]),
    (3, "kmod", "Kmod", "34.2", 0.1, "Conjunto de ferramentas para carregar e gerenciar módulos do kernel Linux (modprobe, lsmod).", "meson setup build --prefix=/usr --buildtype=release -Dmanpages=false && ninja -C build install", "/usr/bin", ["kmod", "lsmod", "modprobe", "insmod", "rmmod", "depmod"]),

    # --- Tier 4 (8.61 - 8.83) ---
    (4, "coreutils-final", "Coreutils (Definitivo)", "9.11", 1.8, "Utilitários fundamentais GNU definitivos (ls, cp, mv, chmod, cat, etc.).", "./configure --prefix=/usr --enable-no-install-program=kill,uptime", "/usr/bin", ["cat", "ls", "cp", "mv", "rm", "mkdir", "chmod", "chown", "dd", "df", "uname"]),
    (4, "diffutils-final", "Diffutils (Definitivo)", "3.12", 0.2, "Utilitários definitivos de comparação de arquivos.", "./configure --prefix=/usr", "/usr/bin", ["diff", "cmp", "diff3", "sdiff"]),
    (4, "findutils-final", "Findutils (Definitivo)", "4.11.0", 0.7, "Utilitários definitivos de busca de arquivos e execução em lote.", "./configure --prefix=/usr --localstatedir=/var/lib/locate", "/usr/bin", ["find", "xargs", "locate"]),
    (4, "groff", "Groff", "1.24.1", 0.2, "Sistema de formatação de documentos usado pelo Man-DB para renderizar páginas man.", "PAGE=A4 ./configure --prefix=/usr", "/usr/bin", ["groff", "troff", "nroff", "eqn", "tbl"]),
    (4, "grub", "GRUB", "2.14", 0.5, "GRand Unified Bootloader: carregador de inicialização do kernel Linux.", "./configure --prefix=/usr --sysconfdir=/etc --disable-efiemu --disable-werror", "/usr/sbin", ["grub-install", "grub-mkconfig", "grub-probe"]),
    (4, "gzip-final", "Gzip (Definitivo)", "1.14", 0.1, "Utilitário definitivo de compressão .gz.", "./configure --prefix=/usr", "/usr/bin", ["gzip", "gunzip", "zcat"]),
    (4, "iproute2", "IPRoute2", "7.1.0", 0.1, "Suíte moderna de configuração de rede, interfaces, rotas e túneis do kernel Linux.", "make NETNS_RUN_DIR=/run/netns && make SBINDIR=/usr/sbin install", "/usr/sbin", ["ip", "ss", "bridge", "tc"]),
    (4, "kbd", "Kbd", "2.10.0", 0.1, "Tabelas de mapeamento de teclado (keymaps) e fontes para o console Linux.", "./configure --prefix=/usr --disable-vlock", "/usr/bin", ["loadkeys", "setfont", "kbd_mode"]),
    (4, "libpipeline", "Libpipeline", "1.5.8", 0.1, "Biblioteca C para manipulação flexível de pipelines de subprocessos (usada pelo Man-DB).", "./configure --prefix=/usr", "/usr/lib", ["libpipeline.so.1"]),
    (4, "make-final", "Make (Definitivo)", "4.4.1", 0.3, "Utilitário GNU Make definitivo para orquestração de compilações.", "./configure --prefix=/usr", "/usr/bin", ["make"]),
    (4, "patch-final", "Patch (Definitivo)", "2.8", 0.1, "Utilitário definitivo de aplicação de remendos diff.", "./configure --prefix=/usr", "/usr/bin", ["patch"]),
    (4, "tar-final", "Tar (Definitivo)", "1.35", 1.2, "Arquivador GNU Tar definitivo.", "./configure --prefix=/usr", "/usr/bin", ["tar"]),
    (4, "texinfo-final", "Texinfo (Definitivo)", "7.3", 0.5, "Sistema definitivo de documentação GNU Info.", "./configure --prefix=/usr", "/usr/bin", ["makeinfo", "info", "install-info"]),
    (4, "vim", "Vim", "9.2.1025", 1.8, "Editor de textos modal clássico para administração do sistema.", "./configure --prefix=/usr", "/usr/bin", ["vim", "vi", "vimdiff"]),
    (4, "markupsafe", "MarkupSafe", "3.0.3", 0.1, "Biblioteca Python de escape seguro de strings HTML/XML (dependência do Jinja2).", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/lib", []),
    (4, "jinja2", "Jinja2", "3.1.6", 0.1, "Motor de templates Python requerido durante a geração de código do Udev.", "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD", "/usr/lib", []),
    (4, "udev", "Udev (Systemd-Udev)", "261.2", 0.6, "Gerenciador dinâmico de dispositivos em /dev baseado em eventos do kernel e banco hwdb.", "meson setup build --prefix=/usr --buildtype=release -Dmode=release && ninja -C build udevadm systemd-hwdb", "/usr/bin", ["udevadm", "udev-hwdb", "udevd"]),
    (4, "man-db", "Man-DB", "2.13.1", 0.4, "Motor de leitura e indexação das páginas de manual do sistema.", "./configure --prefix=/usr --docdir=/usr/share/doc/man-db-2.13.1 --sysconfdir=/etc --disable-setuid --enable-cache-owner=bin", "/usr/bin", ["man", "mandb", "apropos", "whatis"]),
    (4, "procps-ng", "Procps-ng", "4.0.7", 0.1, "Monitoramento de processos e sistema via /proc: ps, top, free, vmstat, sysctl.", "./configure --prefix=/usr --disable-static --disable-kill", "/usr/bin", ["ps", "top", "free", "vmstat", "pgrep", "pkill", "sysctl"]),
    (4, "util-linux-final", "Util-linux (Definitivo)", "2.42.2", 0.5, "Utilitários essenciais definitivos do sistema: fdisk, mount, swapon, login, dmesg.", "./configure --bindir=/usr/bin --libdir=/usr/lib --runstatedir=/run --sbindir=/usr/sbin --disable-chfn-chsh --disable-login --disable-su --disable-setpriv", "/usr/bin", ["mount", "umount", "fdisk", "mkswap", "swapon", "swapoff", "dmesg", "blkid", "lsblk"]),
    (4, "e2fsprogs", "E2fsprogs", "1.47.4", 1.8, "Ferramentas de criação, checagem e reparo de sistemas de arquivos ext2/ext3/ext4.", "../configure --prefix=/usr --sysconfdir=/etc --enable-elf-shlibs --disable-libblkid --disable-libuuid --disable-uuidd --disable-fsck", "/usr/sbin", ["mkfs.ext4", "e2fsck", "fsck.ext4", "tune2fs", "resize2fs"]),
    (4, "sysklogd", "Sysklogd", "2.7.2", 0.1, "Daemons de registro de logs do sistema e mensagens do kernel (/var/log).", "./configure --prefix=/usr --sysconfdir=/etc --runstatedir=/run --without-logger", "/usr/sbin", ["syslogd"]),
    (4, "sysvinit", "SysVinit", "3.14", 0.1, "Sistema clássico de inicialização PID 1: init, halt, reboot, shutdown, runlevel.", "make && make install", "/usr/sbin", ["init", "halt", "reboot", "shutdown", "runlevel", "telinit"]),
]

for _tier, _pid, _name, _ver, _sbu, _desc, _build, _ipath, _bins in _CH8_SPECS:
    _sbu_str = f"{_sbu:.1f}".replace(".", ",") + " UPC (SBU)"
    TOOLCHAIN_CATALOG[_pid] = ToolchainPackage(
        id=_pid,
        name=_name,
        version=_ver,
        chapter=8,
        sbu=_sbu,
        sbu_label=_sbu_str,
        description=_desc,
        configure_flags=_build,
        build_steps=f"{_build}; make; make install",
        install_path=_ipath,
        binaries=_bins,
        tier=_tier,
    )


def get_toolchain_packages(chapter: Optional[int] = None) -> List[ToolchainPackage]:
    """Returns list of toolchain packages, optionally filtered by chapter."""
    if chapter is None:
        return list(TOOLCHAIN_CATALOG.values())
    return [p for p in TOOLCHAIN_CATALOG.values() if p.chapter == chapter]


def get_toolchain_package(query: str) -> Optional[ToolchainPackage]:
    """Finds a toolchain package by ID, name or tarball."""
    q = query.strip().lower()
    if q in TOOLCHAIN_CATALOG:
        return TOOLCHAIN_CATALOG[q]
    if q in ("python3", "python-3.14.7", "python3.14") and "python" in TOOLCHAIN_CATALOG:
        return TOOLCHAIN_CATALOG["python"]
    for p in TOOLCHAIN_CATALOG.values():
        if p.id.lower() == q or p.name.lower() == q or p.id.replace("-", "").lower() == q:
            return p
        if q in p.id.lower() or q in p.name.lower() or any(q == b.lower() for b in p.binaries):
            return p
    return None


def get_system_packages(tier: Optional[int] = None) -> List[ToolchainPackage]:
    """Returns list of Chapter 8 system packages, optionally filtered by tier (1..4)."""
    pkgs = [p for p in TOOLCHAIN_CATALOG.values() if p.chapter == 8]
    if tier is not None:
        return [p for p in pkgs if p.tier == tier]
    return pkgs


def get_system_package(query: str) -> Optional[ToolchainPackage]:
    """Finds a Chapter 8 system package by ID, short name (e.g. 'glibc' -> 'glibc-final'), name, or binary."""
    q = query.strip().lower()
    ch8 = get_system_packages()
    ch8_map = {p.id.lower(): p for p in ch8}
    if q in ch8_map:
        return ch8_map[q]
    if f"{q}-final" in ch8_map:
        return ch8_map[f"{q}-final"]
    alias_map = {
        "python": "python-final",
        "python3": "python-final",
        "elfutils": "libelf",
        "e2fsck": "e2fsprogs",
        "eudev": "udev",
        "systemd-udev": "udev",
        "init": "sysvinit",
        "manpages": "man-pages",
        "mandb": "man-db",
    }
    if q in alias_map and alias_map[q] in ch8_map:
        return ch8_map[alias_map[q]]
    for p in ch8:
        if p.name.lower() == q or p.id.replace("-", "").lower() == q:
            return p
        if any(q == b.lower() for b in p.binaries):
            return p
    for p in ch8:
        if q in p.id.lower() or q in p.name.lower():
            return p
    return None


CHAPTER_GUIDES: Dict[int, str] = {
    1: """[bold cyan]=== LFS 13.1 - Capítulo 1: Informações Críticas ===[/bold cyan]
[yellow]Objetivo:[/yellow] Compreender os princípios do Linux From Scratch.
- Você está operando como 'root' no sistema anfitrião.
- A variável fundamental $LFS definirá onde o novo sistema será construído.
- Jamais compile no sistema anfitrião sem isolamento!
[green]Dica da IA K.E.R.N.E.L.:[/green] "Não tente cortar caminho, operador. Um único link simbólico errado destrói o kernel antes mesmo do boot."
""",
    2: """[bold cyan]=== LFS 13.1 - Capítulo 2: Preparando o Hospedeiro ===[/bold cyan]
[yellow]Comandos Principais:[/yellow]
1. Definir a variável $LFS:
   [bold green]export LFS=/mnt/lfs[/bold green]
   [dim]# Verifique com:[/dim] [bold]echo $LFS[/bold]
2. Inspecionar e particionar o disco:
   [bold green]fdisk /dev/sda[/bold green]
   [dim]# Partições esperadas:[/dim]
   #   /dev/sda1 (EFI/Boot - 512MB)
   #   /dev/sda2 (Swap - 4GB)
   #   /dev/sda3 (Root Linux - restante)
3. Formatar as partições:
   [bold green]mkfs.ext4 /dev/sda3[/bold green]
   [bold green]mkswap /dev/sda2[/bold green]
   [bold green]swapon /dev/sda2[/bold green]
4. Criar o ponto de montagem e montar:
   [bold green]mkdir -pv $LFS[/bold green]
   [bold green]mount -v -t ext4 /dev/sda3 $LFS[/bold green]
""",
    3: """[bold cyan]=== LFS 13.1 - Capítulo 3: Pacotes e Remendos ===[/bold cyan]
[yellow]Comandos Principais:[/yellow]
1. Criar o diretório de fontes:
   [bold green]mkdir -v $LFS/sources[/bold green]
   [bold green]chmod -v a+wt $LFS/sources[/bold green]
2. Validar a integridade dos arquivos transferidos:
   [bold green]pushd $LFS/sources[/bold green]
   [bold green]md5sum -c md5sums[/bold green]
   [bold green]popd[/bold green]
[green]Dica da IA K.E.R.N.E.L.:[/green] "Corrupção de bits é sentença de morte na compilação cruzada. Se o MD5 não bater, descarte o tarball."
""",
    4: """[bold cyan]=== LFS 13.1 - Capítulo 4: Preparações Finais ===[/bold cyan]
[yellow]Comandos Principais:[/yellow]
1. Criar o diretório de ferramentas temporárias:
   [bold green]mkdir -pv $LFS/tools[/bold green]
2. Criar grupo e usuário isolado 'lfs':
   [bold green]groupadd lfs[/bold green]
   [bold green]useradd -s /bin/bash -g lfs -m -k /dev/null lfs[/bold green]
3. Transferir posse das pastas do LFS:
   [bold green]chown -v lfs $LFS/{usr{,/*},lib,var,etc,bin,sbin,tools}[/bold green]
   [bold green]chown -v lfs $LFS/sources[/bold green]
4. Configurar o ambiente estéril de compilação:
   [dim]No arquivo ~lfs/.bash_profile:[/dim]
   [bold green]exec env -i HOME=$HOME TERM=$TERM PS1='\\u:\\w\\$ ' /bin/bash[/bold green]
   [dim]No arquivo ~lfs/.bashrc:[/dim]
   [bold green]set +h; umask 022; LFS=/mnt/lfs; LC_ALL=POSIX; LFS_TGT=x86_64-lfs-linux-gnu; PATH=/usr/bin:/bin; export LFS LC_ALL LFS_TGT PATH[/bold green]
5. Alternar para o usuário lfs:
   [bold green]su - lfs[/bold green]
""",
    5: """[bold cyan]=== LFS 13.1 - Capítulo 5: Compilando um Conjunto Cruzado de Ferramentas ===[/bold cyan]
[yellow]Objetivo:[/yellow] Forjar o compilador cruzado e a biblioteca C limpa em $LFS/tools.
Este capítulo constrói o primeiro par de ferramentas cruzadas: o vinculador (ld) e o compilador (gcc) que operam no hospedeiro, mas geram código isolado para $LFS_TGT.

[bold yellow]Etapas do Capítulo 5:[/bold yellow]
1. [bold green]Binutils - Passagem 1 (1,0 UPC)[/bold green]
   [dim]../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT --disable-nls --enable-gprofng=no --disable-werror --enable-new-dtags --enable-default-hash-style=gnu[/dim]
   [dim]make && make install[/dim]

2. [bold green]GCC - Passagem 1 (4,3 UPC)[/bold green]
   [dim]../configure --target=$LFS_TGT --prefix=$LFS/tools --with-glibc-version=2.44 --with-sysroot=$LFS --with-newlib --without-headers --enable-default-pie --enable-default-ssp --disable-fixincludes --disable-nls --disable-shared --disable-multilib --disable-threads --disable-libatomic --disable-libgomp --disable-libquadmath --disable-libssp --disable-libvtv --disable-libstdcxx --enable-languages=c,c++[/dim]
   [dim]make && make install[/dim]

3. [bold green]Linux 6.14.7 API Headers (0,1 UPC)[/bold green]
   [dim]make mrproper && make headers && cp -rv usr/include $LFS/usr[/dim]

4. [bold green]Glibc 2.44 (1,3 UPC)[/bold green]
   [dim]../configure --prefix=/usr --host=$LFS_TGT --build=$(../scripts/config.guess) --disable-nscd libc_cv_slibdir=/usr/lib --enable-kernel=5.10[/dim]
   [dim]make && make DESTDIR=$LFS install[/dim]

5. [bold yellow]Teste de Sanidade da Toolchain (CRÍTICO!):[/bold yellow]
   [bold green]echo 'int main(){}' | $LFS_TGT-gcc -xc -[/bold green]
   [bold green]readelf -l a.out | grep ld-linux[/bold green]
   [dim]# Deve apontar para: /lib/ld-linux-x86-64.so.2[/dim]

6. [bold green]Libstdc++ da Passagem 1 (0,3 UPC)[/bold green]
   [dim]../libstdc++-v3/configure --host=$LFS_TGT --prefix=/usr ...[/dim]
   [dim]make && make DESTDIR=$LFS install[/dim]

[green]Dica da IA K.E.R.N.E.L.:[/green] "Se o teste de sanidade com readelf falhar, pare tudo! Prosseguir com uma toolchain contaminada condenará o novo kernel."
""",
    6: """[bold cyan]=== LFS 13.1 - Capítulo 6: Compilando Cruzadamente Ferramentas Temporárias ===[/bold cyan]
[yellow]Objetivo:[/yellow] Compilar os utilitários básicos do sistema usando a recém-criada cross-toolchain.
Essas ferramentas temporárias residirão em $LFS/usr/bin e formarão o ambiente isolado necessário para o futuro 'chroot'.

[bold yellow]Pacotes de Ferramentas Temporárias:[/bold yellow]
• M4 1.4.19 (0,1 UPC)
• Ncurses 6.5 (0,4 UPC)
• Bash 5.3 (0,2 UPC)
• Coreutils 9.11 (0,3 UPC)
• Diffutils 3.12 (0,1 UPC)
• File 5.46 (0,1 UPC)
• Findutils 4.10.0 (0,2 UPC)
• Gawk 5.3.1 (0,1 UPC)
• Grep 3.12 (0,1 UPC)
• Gzip 1.14 (0,1 UPC)
• Make 4.4.1 (0,1 UPC)
• Patch 2.7.6 (0,1 UPC)
• Sed 4.9 (0,1 UPC)
• Tar 1.35 (0,1 UPC)
• Xz 5.8.1 (0,1 UPC)

[bold yellow]Clímax do Capítulo 6 (A Boss Fight do Ato 2):[/bold yellow]
• [bold green]Binutils - Passagem 2 (0,4 UPC)[/bold green]: Vinculação nativa contra a Glibc de $LFS.
• [bold green]GCC - Passagem 2 (5,2 UPC)[/bold green]: O compilador completo pronto para o chroot.

[bold magenta]Comandos Auxiliares no Jogo:[/bold magenta]
- [bold green]lfs-status-tools[/bold green]: Exibe a lista completa de pacotes com status de compilação e SBU.
- [bold green]lfs-compile-tools all[/bold green]: Compila em lote as ferramentas temporárias com telemetria e gestão de anomalias.
- [bold green]lfs-compile-tools <pacote>[/bold green]: Compila um pacote temporário específico (ex: lfs-compile-tools m4).
""",
    7: """[bold cyan]=== LFS 13.1 - Capítulo 7: Entrando no Chroot e Construindo Ferramentas Temporárias Adicionais ===[/bold cyan]
[yellow]Objetivo:[/yellow] Cortar o cordão umbilical com o sistema hospedeiro.
O ambiente 'chroot' isola completamente o processo de compilação, permitindo forjar as ferramentas finais em um ambiente puro.

[bold yellow]Passos Principais do Capítulo 7:[/bold yellow]
1. [bold green]Mudando Propriedade (como root no hospedeiro):[/bold green]
   [bold green]chown --from lfs -R root:root $LFS/{usr,var,etc,tools}[/bold green]
   [bold green]case $(uname -m) in x86_64) chown --from lfs -R root:root $LFS/lib64 ;; esac[/bold green]

2. [bold green]Montando Sistemas de Arquivos Virtuais do Núcleo:[/bold green]
   [bold green]mkdir -pv $LFS/{dev,proc,sys,run}[/bold green]
   [bold green]mount -v --bind /dev $LFS/dev[/bold green]
   [bold green]mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts[/bold green]
   [bold green]mount -vt proc proc $LFS/proc[/bold green]
   [bold green]mount -vt sysfs sysfs $LFS/sys[/bold green]
   [bold green]mount -vt tmpfs tmpfs $LFS/run[/bold green]

3. [bold green]O Ritual do Chroot (Transição Sagrada):[/bold green]
   [bold green]chroot "$LFS" /usr/bin/env -i HOME=/root TERM="$TERM" PS1='(lfs chroot) \\u:\\w\\$ ' PATH=/usr/bin:/usr/sbin /bin/bash --login[/bold green]
   [dim]# Seu prompt agora se torna: (lfs chroot) root:/# [/dim]

4. [bold green]Criando a Árvore de Diretórios Padrão no Chroot:[/bold green]
   [bold green]mkdir -pv /{boot,home,mnt,opt,srv}[/bold green]
   [bold green]mkdir -pv /etc/{opt,sysconfig} /lib/firmware /media/{floppy,cdrom}[/bold green]
   [bold green]mkdir -pv /usr/{,local/}{bin,include,lib,sbin,src}[/bold green]
   [bold green]mkdir -pv /usr/{,local/}share/{color,dict,doc,info,locale,man}[/bold green]
   [bold green]mkdir -pv /var/{cache,local,log,mail,opt,spool} /var/lib/{color,misc,locate}[/bold green]
   [bold green]ln -sfv /run /var/run && ln -sfv /run/lock /var/lock[/bold green]
   [bold green]install -dv -m 0750 /root[/bold green]
   [bold green]install -dv -m 1777 /tmp /var/tmp[/bold green]
   [bold green]case $(uname -m) in x86_64) ln -sfv lib /lib64 ;; esac[/bold green]

5. [bold green]Criando Arquivos Essenciais e Links:[/bold green]
   [bold green]ln -sfv /proc/self/mounts /etc/mtab[/bold green]
   [dim]# Os arquivos /etc/passwd e /etc/group já contêm o superusuário root[/dim]

6. [bold green]Compilando as Ferramentas Temporárias do Chroot:[/bold green]
   • Gettext-1.0 (1,5 UPC)
   • Bison-3.8.2 (0,2 UPC)
   • Perl-5.44.0 (0,6 UPC)
   • Python-3.14.7 (0,5 UPC)
   • Texinfo-7.2 (0,2 UPC)
   • Util-linux-2.41.3 (0,2 UPC)
   [bold magenta]Comandos Auxiliares no Jogo:[/bold magenta]
   - [bold green]lfs-compile-chroot all[/bold green]: Compila em lote as 6 ferramentas temporárias do chroot.
   - [bold green]lfs-compile-chroot <pacote>[/bold green]: Compila uma ferramenta específica (ex: lfs-compile-chroot perl).
   - [bold green]lfs-status-chroot[/bold green]: Exibe a telemetria e o progresso das ferramentas do chroot.

7. [bold green]Limpando e Descartando o Diretório /tools:[/bold green]
   [bold green]rm -rf /usr/share/{info,man,doc}/*[/bold green]
   [bold green]find /usr/{lib,libexec} -name \\*.la -delete[/bold green]
   [bold green]rm -rf /tools[/bold green]

[green]Dica da IA K.E.R.N.E.L.:[/green] "O chroot é onde homens se separam de máquinas, operador. Um único passo em falso na montagem do procfs ou devpts deixará seu novo sistema mudo e cego."
""",
    8: """[bold cyan]=== LFS 13.1 - Capítulo 8: Instalando Aplicativos Básicos de Sistema (Ato 4) ===[/bold cyan]
[yellow]Objetivo:[/yellow] Forjar os 81 pacotes definitivos do sistema operacional dentro do ambiente [bold]chroot[/bold].
Todos os comandos abaixo DEVEM ser executados dentro do chroot ([bold](lfs chroot) root:/#[/bold]).

[bold yellow]Organização em 4 Tiers Lógicos (Seções 8.3 a 8.83):[/bold yellow]
• [bold cyan]Tier 1 (8.3–8.21):[/bold cyan] Man-pages, Iana-Etc, Glibc 2.44 definitiva, Zlib, Bzip2, Xz, Lz4, Zstd, File, Readline, Pcre2, M4, Bc, Flex, Tcl, Expect, DejaGNU, Ninja, Pkgconf.
  - [bold green]Testes críticos:[/bold green] [bold]make check[/bold] (validar a Glibc!)
  - [bold green]Localidades:[/bold green] [bold]localedef -i pt_BR -f UTF-8 pt_BR.UTF-8[/bold] (e C.UTF-8)

• [bold cyan]Tier 2 (8.22–8.40):[/bold cyan] Binutils 2.47, GMP, MPFR, MPC, Attr, Acl, Libcap, Libxcrypt, Shadow, Gawk, GCC 16.2.0 definitivo, Ncurses, Sed, Psmisc, Gettext, Bison, Grep, Bash 5.3, Libtool.
  - [bold green]Testes da Toolchain:[/bold green] [bold]make -k check[/bold] (suíte do GCC/Binutils)
  - [bold green]Segurança Shadow:[/bold green] [bold]pwconv[/bold], [bold]grpconv[/bold] e [bold]passwd root[/bold]
  - [bold green]Reinício do Shell:[/bold green] [bold]exec /usr/bin/bash --login[/bold] (ativa o Bash definitivo recém-compilado!)

• [bold cyan]Tier 3 (8.41–8.60):[/bold cyan] GDBM, Gperf, Expat, Inetutils, Less, Perl, Autoconf, Automake, OpenSSL 4.0, Libelf, Libffi, SQLite, mpdecimal, Python 3.14 definitivo, Flit-Core, Packaging, Wheel, Setuptools, Meson, Kmod.

• [bold cyan]Tier 4 (8.61–8.83):[/bold cyan] Coreutils, Diffutils, Findutils, Groff, GRUB 2.14, Gzip, IPRoute2, Kbd, Libpipeline, Make, Patch, Tar, Texinfo, Vim, MarkupSafe, Jinja2, Udev, Man-DB, Procps-ng, Util-linux, E2fsprogs, Sysklogd, SysVinit.
  - [bold green]Banco de Hardware:[/bold green] [bold]udev-hwdb update[/bold] (compila /etc/udev/hwdb.bin)

• [bold cyan]Seção 8.85 (Stripping & Limpeza):[/bold cyan]
  - Execute [bold green]lfs-strip[/bold green] (ou [bold green]strip --strip-debug[/bold green]) para remover símbolos de depuração e liberar espaço vital!

[bold magenta]Comandos Auxiliares do Ato 4:[/bold magenta]
- [bold green]lfs-status-system[/bold green]: Exibe progresso dos Tiers 1–4, suítes 'make check' e marcos especiais.
- [bold green]lfs-compile-system tier1|tier2|tier3|tier4|all|<pacote>[/bold green]: Compila pacotes definitivos dentro do chroot.
- [bold green]make check[/bold green] / [bold green]make -k check[/bold green]: Executa as suítes de testes da Glibc, Binutils e GCC.

[green]Dica da IA K.E.R.N.E.L.:[/green] "É aqui que a alma do sistema nasce, operador. Não pule os testes da Glibc nem esqueça de definir a senha de root com Shadow!"
""",
    9: """[bold cyan]=== LFS 13.1 - Capítulo 9: Configuração do Sistema (Ato 5) ===[/bold cyan]
[yellow]Objetivo:[/yellow] Instalar os scripts de inicialização SysVinit e configurar rede, fuso horário, console e shell do sistema LFS dentro do [bold]chroot[/bold].

[bold yellow]Etapas Principais do Capítulo 9:[/bold yellow]
1. [bold green]9.2. LFS-Bootscripts-20250827 (0,1 UPC):[/bold green]
   Instala os scripts de boot em [bold]/etc/rc.d/*[/bold] e serviços em [bold]/lib/services/*[/bold].
   [dim]Comando real:[/dim] [bold green]make install[/bold green] (ou atalho: [bold green]lfs-install-bootscripts[/bold green])

2. [bold green]9.5. Configuração Geral de Rede:[/bold green]
   • [bold]/etc/sysconfig/ifconfig.eth0[/bold]: interface estática IPv4 ([dim]ONBOOT=yes, IFACE=eth0, SERVICE=ipv4-static, IP=...[/dim])
   • [bold]/etc/resolv.conf[/bold]: servidores DNS ([dim]nameserver 10.0.2.3[/dim])
   • [bold]/etc/hostname[/bold]: nome do computador na rede ([dim]echo "hera-lfs" > /etc/hostname[/dim])
   • [bold]/etc/hosts[/bold]: resolução local ([dim]127.0.0.1 localhost.localdomain localhost[/dim])
   [dim]Atalho no simulador:[/dim] [bold green]lfs-config-network [hostname][/bold green]

3. [bold green]9.6. System V Bootscripts & Configuração do Sistema:[/bold green]
   • [bold]/etc/inittab[/bold]: define o runlevel padrão ([dim]id:3:initdefault:[/dim]) e os terminais getty
   • [bold]/etc/sysconfig/clock[/bold] e [bold]/etc/sysconfig/console[/bold]: relógio UTC e teclado/fonte
   • [bold]/etc/profile[/bold]: variáveis globais de login ([dim]LANG=pt_BR.UTF-8[/dim])
   • [bold]/etc/inputrc[/bold]: configuração da biblioteca Readline (teclas Home/End/Delete)
   • [bold]/etc/shells[/bold]: shells de login válidos ([dim]/bin/sh[/dim], [bold]/bin/bash[/bold])
   [dim]Atalho no simulador:[/dim] [bold green]lfs-config-system[/bold green] (ou crie manualmente via [bold]cat > arquivo << "EOF"[/bold])

[bold magenta]Auditoria do Ato 5:[/bold magenta]
- [bold green]lfs-check-config[/bold green]: Valida todos os arquivos críticos dos Capítulos 9 e 10.

[green]Dica da IA K.E.R.N.E.L.:[/green] "Um sistema operacional sem /etc/inittab ou scripts de rede acorda mudo e cego no primeiro boot. Verifique cada arquivo com atenção!"
""",
    10: """[bold cyan]=== LFS 13.1 - Capítulo 10: Tornando o Sistema LFS Inicializável (Ato 5) ===[/bold cyan]
[yellow]Objetivo:[/yellow] Criar o [bold]/etc/fstab[/bold], configurar e compilar o [bold]Kernel Linux 7.1.8[/bold] e instalar o carregador de boot [bold]GRUB[/bold].

[bold yellow]Etapas Principais do Capítulo 10:[/bold yellow]
1. [bold green]10.2. Criando o arquivo /etc/fstab:[/bold green]
   Define os pontos de montagem automáticos no boot:
   [dim]/dev/sda3   /      ext4   defaults            1   1[/dim]
   [dim]/dev/sda2   swap   swap   pri=1               0   0[/dim]
   [dim]Use:[/dim] [bold green]cat > /etc/fstab << "EOF" ... EOF[/bold green]

2. [bold green]10.3. Kernel Linux 7.1.8 (3,5 UPC):[/bold green]
   Entre em [bold]/sources/linux-7.1.8[/bold] e prepare a árvore:
   • [bold green]make mrproper[/bold green] (limpa a árvore do núcleo)
   • [bold green]make defconfig[/bold green] / [bold green]make menuconfig[/bold green] (ou [bold green]lfs-kernel-config[/bold green])
   [yellow]ATENÇÃO CRÍTICA:[/yellow] Sem initramfs, os drivers vitais DEVEM ser compilados como built-in ([bold][y][/bold]), NUNCA módulo ([bold][m][/bold]):
     - [bold]CONFIG_64BIT=y[/bold], [bold]CONFIG_BINFMT_ELF=y[/bold]
     - [bold]CONFIG_DEVTMPFS=y[/bold], [bold]CONFIG_DEVTMPFS_MOUNT=y[/bold]
     - [bold]CONFIG_EXT4_FS=y[/bold], [bold]CONFIG_SATA_AHCI=y[/bold]
   • Compile e instale os módulos e a imagem:
     [bold green]make -j4[/bold green] (ou [bold green]lfs-compile-kernel[/bold green])
     [bold green]make modules_install[/bold green]
     [bold green]cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1[/bold green]
     [bold green]cp -iv System.map /boot/System.map-7.1.8[/bold green]
     [bold green]cp -iv .config /boot/config-7.1.8[/bold green]

3. [bold green]10.4. Usando o GRUB para Configurar o Boot:[/bold green]
   • Instale o GRUB no MBR de /dev/sda:
     [bold green]grub-install /dev/sda[/bold green]
   • Gere o menu [bold]/boot/grub/grub.cfg[/bold] apontando para [bold]vmlinuz-7.1.8-lfs-13.1[/bold] e [bold]root=/dev/sda3[/bold]:
     [bold green]grub-mkconfig -o /boot/grub/grub.cfg[/bold green] (ou [bold green]lfs-config-grub[/bold green] / [bold]cat > /boot/grub/grub.cfg << "EOF"[/bold])

[green]Dica da IA K.E.R.N.E.L.:[/green] "Compilar CONFIG_EXT4_FS como módulo [m] sem initrd garante um Kernel Panic instantâneo no boot! Mantenha os pilares em [y] e conquiste o título de Forjador do Kernel."
"""
}


def get_chapter_help(chapter_num: int) -> str:
    """Returns guide for a given chapter."""
    if chapter_num in CHAPTER_GUIDES:
        return CHAPTER_GUIDES[chapter_num]
    return f"[yellow]Capítulo {chapter_num} ainda em transmissão pela rede da Estação Hera.[/yellow]"
