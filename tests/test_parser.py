"""Tests for ShellParser, command execution, and syntax expansion."""

import pytest
from lfs_game.core.engine import GameEngine
from lfs_game.core.parser import brace_expand


def test_brace_expand():
    text = "$LFS/{usr{,/*},lib,var,etc,bin,sbin,tools}"
    res = brace_expand(text)
    assert len(res) == 8
    assert "$LFS/usr" in res
    assert "$LFS/usr/*" in res
    assert "$LFS/tools" in res


def test_parser_basic_commands():
    engine = GameEngine()
    parser = engine.parser

    # pwd
    res = parser.execute("pwd")
    assert res.success
    assert res.output == "/root"

    # export and env expansion
    res = parser.execute("export LFS=/mnt/lfs")
    assert res.success
    assert engine.fs.env["LFS"] == "/mnt/lfs"

    # echo with redirect
    res = parser.execute("echo 'hello world' > /root/hello.txt")
    assert res.success
    ok, content = engine.fs.read_file("/root/hello.txt")
    assert ok
    assert "hello world" in content


def test_parser_chained_commands():
    engine = GameEngine()
    parser = engine.parser

    res = parser.execute("export TEST=123 && echo $TEST")
    assert res.success
    assert "123" in res.output

    res = parser.execute("mkdir -pv /tmp/test1 ; mkdir -pv /tmp/test2")
    assert res.success
    assert engine.fs.exists("/tmp/test1")
    assert engine.fs.exists("/tmp/test2")


def test_parser_chapter2_flow():
    engine = GameEngine()
    parser = engine.parser

    res = parser.execute("export LFS=/mnt/lfs")
    assert res.success

    res = parser.execute("mkfs.ext4 /dev/sda3")
    assert res.success

    res = parser.execute("mkswap /dev/sda2")
    assert res.success

    res = parser.execute("swapon /dev/sda2")
    assert res.success

    res = parser.execute("mkdir -pv $LFS")
    assert res.success
    assert engine.fs.exists("/mnt/lfs")

    res = parser.execute("mount -v -t ext4 /dev/sda3 $LFS")
    assert res.success
    assert "/mnt/lfs" in engine.fs.mounts


def test_parser_sources_and_md5():
    engine = GameEngine()
    parser = engine.parser

    parser.execute("export LFS=/mnt/lfs")
    parser.execute("mkdir -pv $LFS/sources")
    res = parser.execute("lfs-get-sources")
    assert res.success
    assert engine.fs.exists("/mnt/lfs/sources/md5sums")

    res = parser.execute("cd $LFS/sources && md5sum -c md5sums")
    assert res.success
    assert "100% de integridade" in res.output
