"""Core subsystems: virtual filesystem, shell parser, and game engine."""
from .virtual_fs import VirtualFS, VirtualInode, VirtualFile, VirtualDirectory, Partition
from .parser import ShellParser, CommandResult
from .engine import GameEngine

__all__ = [
    "VirtualFS",
    "VirtualInode",
    "VirtualFile",
    "VirtualDirectory",
    "Partition",
    "ShellParser",
    "CommandResult",
    "GameEngine",
]
