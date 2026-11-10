"""Tests for StoryEngine, quest progression, and Act 1 milestones."""

import pytest
from lfs_game.core.engine import GameEngine


def test_story_prologue_and_choice():
    engine = GameEngine()
    story = engine.story_engine

    assert story.current_quest.id == "Q0_PROLOGUE"
    assert story.current_dialogue is not None

    # Choose option 1
    res = engine.run_command("1")
    assert res.success
    assert story.flags.get("prologue_done")
    assert story.current_quest.id == "Q1_PARTITION_AND_MOUNT"


def test_story_act1_full_progression():
    engine = GameEngine()

    # Pass prologue
    engine.run_command("1")
    assert engine.story_engine.current_quest.id == "Q1_PARTITION_AND_MOUNT"

    # Complete Chapter 2 requirements
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("mkfs.ext4 /dev/sda3")
    engine.run_command("mkswap /dev/sda2")
    engine.run_command("swapon /dev/sda2")
    engine.run_command("mkdir -pv $LFS")
    engine.run_command("mount -v -t ext4 /dev/sda3 $LFS")

    assert engine.story_engine.current_quest.id == "Q2_PACKAGES_AND_PATCHES"

    # Complete Chapter 3 requirements
    engine.run_command("mkdir -v $LFS/sources")
    engine.run_command("chmod -v a+wt $LFS/sources")
    engine.run_command("lfs-get-sources")
    engine.run_command("cd $LFS/sources")
    engine.run_command("md5sum -c md5sums")

    assert engine.story_engine.current_quest.id == "Q3_FINAL_PREPARATIONS"

    # Complete Chapter 4 preps requirements
    engine.run_command("mkdir -pv $LFS/tools")
    engine.run_command("groupadd lfs")
    engine.run_command("useradd -s /bin/bash -g lfs -m -k /dev/null lfs")
    engine.run_command("chown -v lfs $LFS/tools")
    engine.run_command("chown -v lfs $LFS/sources")

    assert engine.story_engine.current_quest.id == "Q4_STERILE_ENVIRONMENT"

    # Complete sterile environment requirements
    engine.run_command("su - lfs")
    engine.run_command("export LFS=/mnt/lfs")
    engine.run_command("export LC_ALL=POSIX")
    engine.run_command("export LFS_TGT=x86_64-lfs-linux-gnu")
    engine.run_command("export PATH=/usr/bin:/bin")

    assert engine.story_engine.flags.get("act1_celebrated")
    assert engine.char.level >= 4
