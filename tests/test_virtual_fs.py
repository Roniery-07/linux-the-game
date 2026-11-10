"""Tests for VirtualFS filesystem, users, and partition management."""

import pytest
from lfs_game.core.virtual_fs import VirtualFS, Partition


def test_virtual_fs_initial_state():
    fs = VirtualFS()
    assert fs.current_user == "root"
    assert fs.pwd() == "/root"
    assert fs.exists("/root")
    assert fs.exists("/dev/sda1")
    assert fs.exists("/dev/sda2")
    assert fs.exists("/dev/sda3")
    assert "/dev/sda3" in fs.partitions


def test_mkdir_and_file_ops():
    fs = VirtualFS()
    # Create nested directories
    ok, msg = fs.mkdir("/mnt/lfs/sources", parents=True, verbose=True)
    assert ok
    assert fs.exists("/mnt/lfs/sources")
    assert fs.is_dir("/mnt/lfs/sources")

    # Write file
    ok, err = fs.write_file("/mnt/lfs/sources/test.txt", "hello lfs")
    assert ok
    assert fs.exists("/mnt/lfs/sources/test.txt")
    assert not fs.is_dir("/mnt/lfs/sources/test.txt")

    # Read file
    ok, content = fs.read_file("/mnt/lfs/sources/test.txt")
    assert ok
    assert content == "hello lfs"

    # Append to file
    ok, err = fs.write_file("/mnt/lfs/sources/test.txt", "\nsecond line", append=True)
    assert ok
    ok, content = fs.read_file("/mnt/lfs/sources/test.txt")
    assert content == "hello lfs\nsecond line"

    # Remove file
    ok, err = fs.rm("/mnt/lfs/sources/test.txt")
    assert ok
    assert not fs.exists("/mnt/lfs/sources/test.txt")


def test_partition_formatting_and_mount():
    fs = VirtualFS()
    # Format ext4
    ok, msg = fs.format_partition("/dev/sda3", "ext4")
    assert ok
    assert fs.partitions["/dev/sda3"].filesystem == "ext4"

    # Format swap & activate
    ok, msg = fs.make_swap("/dev/sda2")
    assert ok
    assert fs.partitions["/dev/sda2"].filesystem == "swap"

    ok, msg = fs.swapon("/dev/sda2")
    assert ok
    assert fs.partitions["/dev/sda2"].is_swap_active

    # Mount
    fs.mkdir("/mnt/lfs", parents=True)
    ok, msg = fs.mount("/dev/sda3", "/mnt/lfs", fstype="ext4", verbose=True)
    assert ok
    assert "/mnt/lfs" in fs.mounts
    assert fs.partitions["/dev/sda3"].mount_point == "/mnt/lfs"

    # Unmount
    ok, msg = fs.umount("/mnt/lfs", verbose=True)
    assert ok
    assert "/mnt/lfs" not in fs.mounts


def test_user_management_and_su():
    fs = VirtualFS()
    # Add group and user
    ok, msg = fs.groupadd("lfs")
    assert ok
    ok, msg = fs.useradd("lfs", group="lfs", create_home=True)
    assert ok
    assert "lfs" in fs.users
    assert fs.exists("/home/lfs")

    # Switch user with login
    ok, msg = fs.su("lfs", login=True)
    assert ok
    assert fs.current_user == "lfs"
    assert fs.pwd() == "/home/lfs"
    assert fs.env["USER"] == "lfs"

    # Exit back to root
    ok, msg = fs.exit_user()
    assert ok
    assert fs.current_user == "root"
    assert fs.pwd() == "/root"


def test_permissions_chown_chmod():
    fs = VirtualFS()
    fs.mkdir("/mnt/lfs/tools", parents=True)
    fs.useradd("lfs", group="lfs")

    # Change owner
    ok, msg = fs.chown("/mnt/lfs/tools", "lfs:lfs", verbose=True)
    assert ok
    node = fs._resolve_node("/mnt/lfs/tools")
    assert node.owner == "lfs"
    assert node.group == "lfs"

    # Change permissions
    ok, msg = fs.chmod("/mnt/lfs/tools", "755", verbose=True)
    assert ok
    assert node.mode == 0o755
