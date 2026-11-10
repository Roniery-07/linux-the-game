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
    """Represents a package built during Chapter 5 or Chapter 6."""
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

    def to_dict(self) -> dict:
        return asdict(self)


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
}


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
    for p in TOOLCHAIN_CATALOG.values():
        if p.id.lower() == q or p.name.lower() == q or p.id.replace("-", "").lower() == q:
            return p
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
"""
}


def get_chapter_help(chapter_num: int) -> str:
    """Returns guide for a given chapter."""
    if chapter_num in CHAPTER_GUIDES:
        return CHAPTER_GUIDES[chapter_num]
    return f"[yellow]Capítulo {chapter_num} ainda em transmissão pela rede da Estação Hera.[/yellow]"
