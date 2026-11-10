"""Tests for LFS 13.1 package catalog and HTML parsing."""

import pytest
from lfs_game.data.lfs_manifest import init_catalog, list_packages, get_package, get_md5sums_text, get_chapter_help


def test_catalog_loaded():
    packages = list_packages(include_patches=True)
    assert len(packages) >= 80

    # Ensure critical toolchain packages exist
    bash = get_package("bash")
    assert bash is not None
    assert bash.version == "5.3"
    assert "977c8c0c5ae6309191e7768e28ebc951" in bash.md5

    binutils = get_package("binutils")
    assert binutils is not None

    gcc = get_package("gcc")
    assert gcc is not None

    glibc = get_package("glibc")
    assert glibc is not None


def test_md5sums_format():
    md5_text = get_md5sums_text()
    lines = md5_text.strip().splitlines()
    assert len(lines) >= 80
    for line in lines:
        parts = line.split()
        assert len(parts) == 2
        assert len(parts[0]) == 32  # 32-character hex MD5


def test_chapter_help():
    guide2 = get_chapter_help(2)
    assert "Capítulo 2" in guide2
    assert "export LFS=/mnt/lfs" in guide2
    assert "mount -v -t ext4" in guide2

    guide3 = get_chapter_help(3)
    assert "Capítulo 3" in guide3
    assert "$LFS/sources" in guide3
    assert "md5sum -c md5sums" in guide3
