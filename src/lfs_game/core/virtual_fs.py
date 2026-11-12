"""In-Memory Virtual Filesystem for LFS Simulator."""

from __future__ import annotations
from dataclasses import dataclass, field
import posixpath
import re
import stat
import time
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Partition:
    """Represents a virtual disk partition on the station drive."""
    device: str
    size_mb: int
    part_type: str
    filesystem: Optional[str] = None
    is_swap_active: bool = False
    mount_point: Optional[str] = None

    @property
    def size_human(self) -> str:
        if self.size_mb >= 1024:
            return f"{self.size_mb / 1024:.1f}G"
        return f"{self.size_mb}M"

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "size_mb": self.size_mb,
            "part_type": self.part_type,
            "filesystem": self.filesystem,
            "is_swap_active": self.is_swap_active,
            "mount_point": self.mount_point,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Partition:
        return cls(**data)


@dataclass
class VirtualInode:
    """Base Inode structure."""
    name: str
    is_directory: bool
    owner: str = "root"
    group: str = "root"
    mode: int = 0o755
    mtime: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "is_directory": self.is_directory,
            "owner": self.owner,
            "group": self.group,
            "mode": self.mode,
            "mtime": self.mtime,
        }


@dataclass
class VirtualFile(VirtualInode):
    """File inode containing text or binary data."""
    content: str = ""
    is_tarball: bool = False
    size_bytes: int = 0

    def __post_init__(self):
        self.is_directory = False
        if not self.size_bytes:
            self.size_bytes = len(self.content.encode("utf-8"))

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "content": self.content,
            "is_tarball": self.is_tarball,
            "size_bytes": self.size_bytes,
        })
        return d

    @classmethod
    def from_dict(cls, d: dict) -> VirtualFile:
        return cls(
            name=d["name"],
            is_directory=False,
            owner=d.get("owner", "root"),
            group=d.get("group", "root"),
            mode=d.get("mode", 0o644),
            mtime=d.get("mtime", time.time()),
            content=d.get("content", ""),
            is_tarball=d.get("is_tarball", False),
            size_bytes=d.get("size_bytes", len(d.get("content", "").encode("utf-8"))),
        )


@dataclass
class VirtualDirectory(VirtualInode):
    """Directory inode containing child inodes."""
    children: Dict[str, VirtualInode] = field(default_factory=dict)

    def __post_init__(self):
        self.is_directory = True

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> VirtualDirectory:
        dir_obj = cls(
            name=d["name"],
            is_directory=True,
            owner=d.get("owner", "root"),
            group=d.get("group", "root"),
            mode=d.get("mode", 0o755),
            mtime=d.get("mtime", time.time()),
        )
        for k, v in d.get("children", {}).items():
            if v.get("is_directory"):
                dir_obj.children[k] = VirtualDirectory.from_dict(v)
            else:
                dir_obj.children[k] = VirtualFile.from_dict(v)
        return dir_obj


class VirtualFS:
    """Simulated Unix Filesystem with mount points, environment and permissions."""

    def __init__(self):
        self.root = VirtualDirectory(name="", is_directory=True, owner="root", group="root", mode=0o755)
        self.cwd: str = "/root"
        self.current_user: str = "root"
        self.user_stack: List[str] = []

        # Users & Groups
        self.users: Dict[str, dict] = {
            "root": {"uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"},
        }
        self.groups: Dict[str, dict] = {
            "root": {"gid": 0, "members": ["root"]},
        }

        # Environments
        self.env: Dict[str, str] = {
            "USER": "root",
            "LOGNAME": "root",
            "HOME": "/root",
            "SHELL": "/bin/bash",
            "PATH": "/bin:/usr/bin:/sbin:/usr/sbin",
            "TERM": "xterm-256color",
            "PWD": "/root",
        }
        self.user_saved_envs: Dict[str, Dict[str, str]] = {}

        # Partitions
        self.partitions: Dict[str, Partition] = {
            "/dev/sda1": Partition(device="/dev/sda1", size_mb=512, part_type="EFI System", filesystem="vfat"),
            "/dev/sda2": Partition(device="/dev/sda2", size_mb=4096, part_type="Linux swap", filesystem=None),
            "/dev/sda3": Partition(device="/dev/sda3", size_mb=51200, part_type="Linux filesystem", filesystem=None),
        }

        # Mounts: mount_point -> Partition device
        self.mounts: Dict[str, str] = {}

        # Act 2 Toolchain State Tracking
        self.installed_tools: Dict[str, str] = {}
        self.compiled_packages: Set[str] = set()
        self.configured_packages: Dict[str, dict] = {}

        # Act 3 Chroot State Tracking
        self.in_chroot: bool = False
        self.chroot_dir: str = "/mnt/lfs"
        self.chroot_saved_host_state: Optional[dict] = None

        # Act 4 System Build & Configuration State Tracking
        self.locales_configured: bool = False
        self.shadow_configured: bool = False
        self.root_password_set: bool = False
        self.bash_restarted: bool = False
        self.udev_updated: bool = False
        self.debug_stripped: bool = False
        self.system_checks_passed: Set[str] = set()

        # Act 5 System Configuration, Kernel 7.1.8 & GRUB State Tracking
        self.bootscripts_installed: bool = False
        self.network_configured: bool = False
        self.sysconfig_configured: bool = False
        self.fstab_configured: bool = False
        self.kernel_config: Dict[str, str] = self._default_kernel_config()
        self.kernel_configured: bool = False
        self.kernel_compiled: bool = False
        self.kernel_installed: bool = False
        self.grub_mbr_installed: bool = False
        self.grub_cfg_created: bool = False

        self._init_standard_tree()

    @staticmethod
    def _default_kernel_config() -> Dict[str, str]:
        """Returns the default critical kernel configuration flags for LFS 13.1."""
        return {
            "CONFIG_64BIT": "y",
            "CONFIG_DEVTMPFS": "y",
            "CONFIG_DEVTMPFS_MOUNT": "y",
            "CONFIG_EXT4_FS": "y",
            "CONFIG_SATA_AHCI": "y",
            "CONFIG_BINFMT_ELF": "y",
            "CONFIG_NET": "y",
        }

    def _init_standard_tree(self):
        """Initializes standard Unix root hierarchy."""
        base_dirs = [
            "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/mnt",
            "/opt", "/proc", "/root", "/sbin", "/sys", "/tmp", "/usr", "/var"
        ]
        for d in base_dirs:
            self.mkdir(d, parents=True)

        # Standard devices
        for p in self.partitions.keys():
            self.touch(p)
        self.touch("/dev/null")
        self.touch("/dev/zero")
        self.touch("/dev/console")
        self.touch("/dev/ptmx")
        self.mkdir("/dev/pts", parents=True)
        self.mkdir("/dev/shm", parents=True)

        # /etc/passwd and /etc/group placeholders
        self.write_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n")
        self.write_file("/etc/group", "root:x:0:\n")

        # Set /root permissions
        root_dir = self._resolve_node("/root")
        if root_dir:
            root_dir.mode = 0o700

    def resolve_path(self, path: str) -> str:
        """Resolves path relative to cwd, expanding ~ and canonicalizing."""
        if not path:
            return self.cwd
        path = path.strip()
        if path.startswith("~"):
            home = self.users.get(self.current_user, {}).get("home", "/root")
            path = home + path[1:]
        if not path.startswith("/"):
            path = posixpath.join(self.cwd, path)
        norm = posixpath.normpath(path)
        return "/" if norm == "/" else norm

    def _to_real_path(self, path: str) -> str:
        """Translates a virtual path into the host root coordinate system."""
        norm = posixpath.normpath(path)
        if not self.in_chroot:
            return norm

        chroot_base = posixpath.normpath(self.chroot_dir)
        if norm == chroot_base or norm.startswith(chroot_base + "/"):
            return norm

        if norm == "/":
            return chroot_base

        return posixpath.normpath(posixpath.join(chroot_base, norm.lstrip("/")))

    def expand_vars(self, text: str) -> str:
        """Expands environment variables like $LFS or ${LFS}."""
        def repl(m: re.Match) -> str:
            var_name = m.group(1) or m.group(2)
            return self.env.get(var_name, "")

        pattern = re.compile(r"\$(?:\{([a-zA-Z_][a-zA-Z0-9_]*)\}|([a-zA-Z_][a-zA-Z0-9_]*))")
        return pattern.sub(repl, text)

    def _resolve_host_node(self, real_path: str) -> Optional[VirtualInode]:
        """Finds node at host absolute path directly from root."""
        real_path = posixpath.normpath(real_path)
        if real_path in ("", "/"):
            return self.root

        parts = [p for p in real_path.split("/") if p]
        curr = self.root
        for part in parts:
            if not isinstance(curr, VirtualDirectory):
                return None
            if part not in curr.children:
                return None
            curr = curr.children[part]
        return curr

    def _resolve_node(self, abs_path: str) -> Optional[VirtualInode]:
        """Finds node at absolute path, taking chroot jail into account."""
        real_path = self._to_real_path(abs_path)
        return self._resolve_host_node(real_path)

    def _get_parent_and_basename(self, abs_path: str) -> Tuple[Optional[VirtualDirectory], str]:
        """Returns parent VirtualDirectory and final component name."""
        if abs_path == "/" or (self.in_chroot and abs_path == "/"):
            return None, ""
        real_path = self._to_real_path(abs_path)
        if real_path == "/":
            return None, ""
        parent_real, basename = posixpath.split(real_path)
        parent_node = self._resolve_host_node(parent_real)
        if isinstance(parent_node, VirtualDirectory):
            return parent_node, basename
        return None, basename

    def _check_perm(self, inode: VirtualInode, req: int) -> bool:
        """Checks if current_user has requested permission (read=4, write=2, exec=1)."""
        if self.current_user == "root":
            return True
        # Check owner
        if inode.owner == self.current_user:
            return bool((inode.mode >> 6) & req)
        # Check group
        user_gid = self.users.get(self.current_user, {}).get("gid")
        user_group = self.users.get(self.current_user, {}).get("group")
        inode_group_info = self.groups.get(inode.group, {})
        is_member = (
            inode.group == user_group
            or inode_group_info.get("gid") == user_gid
            or self.current_user in inode_group_info.get("members", [])
        )
        if is_member:
            return bool((inode.mode >> 3) & req)
        # Other
        return bool(inode.mode & req)

    def exists(self, path: str) -> bool:
        """Checks if file or directory exists."""
        abs_path = self.resolve_path(path)
        return self._resolve_node(abs_path) is not None

    def is_dir(self, path: str) -> bool:
        """Checks if path is a directory."""
        node = self._resolve_node(self.resolve_path(path))
        return isinstance(node, VirtualDirectory)

    def is_file(self, path: str) -> bool:
        """Checks if path is a regular file."""
        node = self._resolve_node(self.resolve_path(path))
        return isinstance(node, VirtualFile)

    def mkdir(self, path: str, parents: bool = False, verbose: bool = False) -> Tuple[bool, str]:
        """Creates a directory."""
        abs_path = self.resolve_path(path)
        if abs_path == "/":
            return True, ""

        if self.exists(abs_path):
            if parents:
                return True, ""
            return False, f"mkdir: não foi possível criar o diretório '{path}': Arquivo existe"

        real_path = self._to_real_path(abs_path)
        parts = [p for p in real_path.split("/") if p]
        curr = self.root
        accum = ""
        created_paths = []

        for i, part in enumerate(parts):
            accum += "/" + part
            if part in curr.children:
                node = curr.children[part]
                if not isinstance(node, VirtualDirectory):
                    return False, f"mkdir: '{accum}' não é um diretório"
                curr = node
            else:
                if not parents and i < len(parts) - 1:
                    return False, f"mkdir: não foi possível criar o diretório '{path}': Arquivo ou diretório inexistente"
                if not self._check_perm(curr, 2):
                    return False, f"mkdir: não foi possível criar o diretório '{path}': Permissão negada"
                new_dir = VirtualDirectory(
                    name=part,
                    is_directory=True,
                    owner=self.current_user,
                    group=self.users.get(self.current_user, {}).get("group", "root")
                )
                curr.children[part] = new_dir
                curr = new_dir

                display_p = accum
                if self.in_chroot:
                    chroot_base = posixpath.normpath(self.chroot_dir)
                    if accum == chroot_base:
                        display_p = "/"
                    elif accum.startswith(chroot_base + "/"):
                        rel = accum[len(chroot_base):]
                        display_p = rel if rel.startswith("/") else "/" + rel
                created_paths.append(display_p)

        msg = ""
        if verbose and created_paths:
            msg = "\n".join([f"mkdir: criado o diretório '{p}'" for p in created_paths])
        return True, msg

    def touch(self, path: str) -> Tuple[bool, str]:
        """Creates an empty file or updates its mtime."""
        abs_path = self.resolve_path(path)
        node = self._resolve_node(abs_path)
        if node:
            if not self._check_perm(node, 2):
                return False, f"touch: não foi possível tocar '{path}': Permissão negada"
            node.mtime = time.time()
            return True, ""

        parent, basename = self._get_parent_and_basename(abs_path)
        if not parent:
            return False, f"touch: não foi possível tocar '{path}': Diretório inexistente"
        if not self._check_perm(parent, 2):
            return False, f"touch: não foi possível tocar '{path}': Permissão negada"

        new_file = VirtualFile(
            name=basename,
            is_directory=False,
            owner=self.current_user,
            group=self.users.get(self.current_user, {}).get("group", "root"),
            mode=0o644,
            content=""
        )
        parent.children[basename] = new_file
        return True, ""

    def write_file(self, path: str, content: str, append: bool = False) -> Tuple[bool, str]:
        """Writes or appends content to a file."""
        abs_path = self.resolve_path(path)
        node = self._resolve_node(abs_path)
        if node:
            if isinstance(node, VirtualDirectory):
                return False, f"bash: {path}: É um diretório"
            if not self._check_perm(node, 2):
                return False, f"bash: {path}: Permissão negada"
            if append:
                node.content += content
            else:
                node.content = content
            node.size_bytes = len(node.content.encode("utf-8"))
            node.mtime = time.time()
            self._refresh_act5_file_flags(abs_path)
            return True, ""

        parent, basename = self._get_parent_and_basename(abs_path)
        if not parent:
            return False, f"bash: {path}: Arquivo ou diretório inexistente"
        if not self._check_perm(parent, 2):
            return False, f"bash: {path}: Permissão negada"

        new_file = VirtualFile(
            name=basename,
            is_directory=False,
            owner=self.current_user,
            group=self.users.get(self.current_user, {}).get("group", "root"),
            mode=0o644,
            content=content,
            size_bytes=len(content.encode("utf-8"))
        )
        parent.children[basename] = new_file
        self._refresh_act5_file_flags(abs_path)
        return True, ""

    def _read_chroot_file(self, chroot_path: str) -> Optional[str]:
        """Reads a file inside the LFS system (resolved via chroot_dir if not currently in chroot)."""
        real_path = chroot_path if self.in_chroot else posixpath.join(posixpath.normpath(self.chroot_dir), chroot_path.lstrip("/"))
        node = self._resolve_node(chroot_path) if self.in_chroot else self._resolve_host_node(real_path)
        if isinstance(node, VirtualFile):
            return node.content
        return None

    def has_valid_network_config(self) -> bool:
        """Checks whether /etc/hostname, /etc/hosts, /etc/sysconfig/ifconfig.eth0, and /etc/resolv.conf are valid."""
        hostname = self._read_chroot_file("/etc/hostname")
        hosts = self._read_chroot_file("/etc/hosts")
        ifconfig = self._read_chroot_file("/etc/sysconfig/ifconfig.eth0")
        resolv = self._read_chroot_file("/etc/resolv.conf")
        if not all(x is not None for x in (hostname, hosts, ifconfig, resolv)):
            return False
        assert hostname is not None and hosts is not None and ifconfig is not None and resolv is not None
        if not hostname.strip():
            return False
        if "127.0.0.1" not in hosts or "localhost" not in hosts:
            return False
        if not any(tok in ifconfig for tok in ("ONBOOT", "IP=", "SERVICE=", "IFACE=")):
            return False
        if "nameserver" not in resolv:
            return False
        return True

    def has_valid_sysconfig(self) -> bool:
        """Checks whether /etc/inittab, /etc/profile, /etc/inputrc, and /etc/shells are valid."""
        inittab = self._read_chroot_file("/etc/inittab")
        profile = self._read_chroot_file("/etc/profile")
        inputrc = self._read_chroot_file("/etc/inputrc")
        shells = self._read_chroot_file("/etc/shells")
        if not all(x is not None for x in (inittab, profile, inputrc, shells)):
            return False
        assert inittab is not None and profile is not None and inputrc is not None and shells is not None
        if "initdefault" not in inittab:
            return False
        if not profile.strip() or not inputrc.strip():
            return False
        if "/bin/bash" not in shells:
            return False
        return True

    def has_valid_fstab(self) -> bool:
        """Validates that /etc/fstab mounts /dev/sda3 on '/' and configures /dev/sda2 as swap."""
        fstab = self._read_chroot_file("/etc/fstab")
        if not fstab:
            return False
        has_root = False
        has_swap = False
        for raw_line in fstab.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split()
            if len(cols) >= 2 and cols[0] == "/dev/sda3" and cols[1] == "/":
                has_root = True
            if len(cols) >= 3 and cols[0] == "/dev/sda2" and (cols[2] == "swap" or cols[1] == "swap"):
                has_swap = True
        return has_root and has_swap

    def has_valid_kernel_installed(self) -> bool:
        """Checks whether /boot/vmlinuz-7.1.8-lfs-13.1 exists in the LFS system."""
        return self._read_chroot_file("/boot/vmlinuz-7.1.8-lfs-13.1") is not None

    def has_valid_grub_cfg(self) -> bool:
        """Checks whether /boot/grub/grub.cfg references vmlinuz-7.1.8-lfs-13.1 and root=/dev/sda3."""
        grub_cfg = self._read_chroot_file("/boot/grub/grub.cfg")
        if not grub_cfg:
            return False
        return "vmlinuz-7.1.8-lfs-13.1" in grub_cfg and "root=/dev/sda3" in grub_cfg

    def sync_act5_state(self) -> None:
        """Synchronizes Act 5 boolean flags from actual files present in VirtualFS."""
        if not self.bootscripts_installed and self._read_chroot_file("/etc/rc.d/init.d/rc") is not None:
            self.bootscripts_installed = True
        if self.has_valid_network_config():
            self.network_configured = True
        if self.has_valid_sysconfig():
            self.sysconfig_configured = True
        if self.has_valid_fstab():
            self.fstab_configured = True
        if self.has_valid_kernel_installed():
            self.kernel_installed = True
        if self.has_valid_grub_cfg():
            self.grub_cfg_created = True

    def _refresh_act5_file_flags(self, abs_path: str) -> None:
        """Updates Act 5 flags immediately when relevant configuration or boot files are written inside chroot."""
        if not self.in_chroot:
            return
        if abs_path in ("/etc/hostname", "/etc/hosts", "/etc/sysconfig/ifconfig.eth0", "/etc/resolv.conf"):
            if self.has_valid_network_config():
                self.network_configured = True
        elif abs_path in ("/etc/inittab", "/etc/profile", "/etc/inputrc", "/etc/shells"):
            if self.has_valid_sysconfig():
                self.sysconfig_configured = True
        elif abs_path == "/etc/fstab":
            if self.has_valid_fstab():
                self.fstab_configured = True
        elif abs_path == "/boot/vmlinuz-7.1.8-lfs-13.1":
            if self.has_valid_kernel_installed():
                self.kernel_installed = True
        elif abs_path == "/boot/grub/grub.cfg":
            if self.has_valid_grub_cfg():
                self.grub_cfg_created = True

    def read_file(self, path: str) -> Tuple[bool, str]:
        """Reads content from a file."""
        abs_path = self.resolve_path(path)
        parent, basename = self._get_parent_and_basename(abs_path)
        if parent and not self._check_perm(parent, 1):
            return False, f"cat: {path}: Permissão negada"

        node = self._resolve_node(abs_path)
        if not node:
            return False, f"cat: {path}: Arquivo ou diretório inexistente"
        if isinstance(node, VirtualDirectory):
            return False, f"cat: {path}: É um diretório"
        if not self._check_perm(node, 4):
            return False, f"cat: {path}: Permissão negada"

        if isinstance(node, VirtualFile) and node.content.startswith("# Symlink to "):
            target_link = node.content.split("# Symlink to ", 1)[1].strip()
            if target_link not in (path, abs_path):
                ok_link, link_content = self.read_file(target_link)
                if ok_link:
                    return True, link_content

        return True, node.content

    def rm(self, path: str, recursive: bool = False, force: bool = False) -> Tuple[bool, str]:
        """Removes a file or directory."""
        abs_path = self.resolve_path(path)
        if abs_path == "/":
            return False, "rm: é perigoso operar recursivamente em '/'"

        parent, basename = self._get_parent_and_basename(abs_path)
        if not parent or basename not in parent.children:
            if force:
                return True, ""
            return False, f"rm: não foi possível remover '{path}': Arquivo ou diretório inexistente"

        if not self._check_perm(parent, 2):
            return False, f"rm: não foi possível remover '{path}': Permissão negada"

        node = parent.children[basename]
        if isinstance(node, VirtualDirectory):
            if not recursive:
                return False, f"rm: não foi possível remover '{path}': É um diretório"
        del parent.children[basename]
        return True, ""

    def cd(self, path: str) -> Tuple[bool, str]:
        """Changes current working directory."""
        if not path or path == "~":
            target = self.users.get(self.current_user, {}).get("home", "/root")
        else:
            target = self.resolve_path(path)

        node = self._resolve_node(target)
        if not node:
            return False, f"bash: cd: {path}: Arquivo ou diretório inexistente"
        if not isinstance(node, VirtualDirectory):
            return False, f"bash: cd: {path}: Não é um diretório"
        if not self._check_perm(node, 1):
            return False, f"bash: cd: {path}: Permissão negada"

        self.cwd = target
        self.env["PWD"] = target
        return True, ""

    def pwd(self) -> str:
        """Returns current working directory."""
        return self.cwd

    def ls(self, path: Optional[str] = None, detailed: bool = False, all_files: bool = False) -> Tuple[bool, str]:
        """Lists directory contents."""
        target = self.resolve_path(path) if path else self.cwd
        node = self._resolve_node(target)
        if not node:
            return False, f"ls: não foi possível acessar '{path or target}': Arquivo ou diretório inexistente"

        if not self._check_perm(node, 4):
            return False, f"ls: não foi possível abrir o diretório '{path or target}': Permissão negada"

        if isinstance(node, VirtualFile):
            if detailed:
                return True, self._format_inode_detailed(node, node.name)
            return True, node.name

        assert isinstance(node, VirtualDirectory)
        names = sorted(node.children.keys())
        if not all_files:
            names = [n for n in names if not n.startswith(".")]

        if not detailed:
            return True, "  ".join(names)

        lines = []
        for n in names:
            child = node.children[n]
            lines.append(self._format_inode_detailed(child, n))
        return True, "\n".join(lines)

    def _format_inode_detailed(self, inode: VirtualInode, display_name: str) -> str:
        """Formats an inode in 'ls -l' style."""
        kind = "d" if inode.is_directory else "-"
        mode_str = stat.filemode(inode.mode)[1:] if hasattr(stat, "filemode") else "rwxr-xr-x"
        size = getattr(inode, "size_bytes", 4096 if inode.is_directory else 0)
        date_str = time.strftime("%b %d %H:%M", time.localtime(inode.mtime))
        return f"{kind}{mode_str} 1 {inode.owner} {inode.group} {size:>8} {date_str} {display_name}"

    def chown(
        self,
        path: str,
        owner_group: str,
        recursive: bool = False,
        verbose: bool = False,
        from_owner: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Changes owner and group of file or directory (e.g. 'lfs' or 'lfs:lfs')."""
        if self.current_user != "root":
            return False, f"chown: alterando o proprietário de '{path}': Operação não permitida"

        if ":" in owner_group:
            new_owner, new_group = owner_group.split(":", 1)
        elif "." in owner_group:
            new_owner, new_group = owner_group.split(".", 1)
        else:
            new_owner, new_group = owner_group, None

        abs_path = self.resolve_path(path)
        node = self._resolve_node(abs_path)
        if not node:
            return False, f"chown: não foi possível acessar '{path}': Arquivo ou diretório inexistente"

        modified = []

        def apply_chown(curr_node: VirtualInode, curr_path: str):
            if from_owner is not None and curr_node.owner != from_owner:
                pass
            else:
                if new_owner:
                    curr_node.owner = new_owner
                if new_group:
                    curr_node.group = new_group
                elif new_owner and not new_group:
                    curr_node.group = self.users.get(new_owner, {}).get("group", new_owner)
                modified.append(f"propriedade de '{curr_path}' alterada para {curr_node.owner}:{curr_node.group}")
            if recursive and isinstance(curr_node, VirtualDirectory):
                for child_name, child in curr_node.children.items():
                    apply_chown(child, posixpath.join(curr_path, child_name))

        apply_chown(node, abs_path)
        msg = "\n".join([f"chown: {m}" for m in modified]) if verbose else ""
        return True, msg

    def chmod(self, path: str, mode_expr: str, recursive: bool = False, verbose: bool = False) -> Tuple[bool, str]:
        """Changes mode permissions (e.g. 'a+wt', '755', '644', '0750')."""
        abs_path = self.resolve_path(path)
        node = self._resolve_node(abs_path)
        if not node:
            return False, f"chmod: não foi possível acessar '{path}': Arquivo ou diretório inexistente"

        if self.current_user != "root" and node.owner != self.current_user:
            return False, f"chmod: alterando as permissões de '{path}': Operação não permitida"

        new_mode: Optional[int] = None
        clean_expr = mode_expr.strip()
        if clean_expr.startswith("0o"):
            clean_expr = clean_expr[2:]
        if clean_expr.isdigit():
            try:
                new_mode = int(clean_expr, 8)
            except ValueError:
                return False, f"chmod: modo inválido: '{mode_expr}'"
        elif "a+wt" in mode_expr or "+t" in mode_expr:
            # Sticky bit + write for all (LFS sources standard: 01777)
            new_mode = 0o1777
        elif "+x" in mode_expr:
            new_mode = 0o755

        if new_mode is None:
            new_mode = 0o755

        modified = []

        def apply_chmod(curr_node: VirtualInode, curr_path: str):
            curr_node.mode = new_mode
            modified.append(f"modo de '{curr_path}' alterado para {oct(new_mode)}")
            if recursive and isinstance(curr_node, VirtualDirectory):
                for child_name, child in curr_node.children.items():
                    apply_chmod(child, posixpath.join(curr_path, child_name))

        apply_chmod(node, abs_path)
        msg = "\n".join([f"chmod: {m}" for m in modified]) if verbose else ""
        return True, msg

    # Disks, Partitions & Mounts
    def format_partition(self, device: str, fstype: str = "ext4") -> Tuple[bool, str]:
        """Formats a partition device (e.g. mkfs.ext4 /dev/sda3)."""
        if self.current_user != "root":
            return False, f"mkfs.{fstype}: Permissão negada. Apenas superusuário pode formatar partições."

        if device not in self.partitions:
            return False, f"mkfs.{fstype}: {device}: Arquivo ou diretório inexistente"

        part = self.partitions[device]
        if part.mount_point:
            return False, f"mkfs.{fstype}: /dev/{device} está montado; não será construído um sistema de arquivos aqui!"

        part.filesystem = fstype
        return True, f"mke2fs 1.47.4 (2-Feb-2026)\nCriando sistema de arquivos {fstype} em {device} ({part.size_human})...\nSuperblocos e cabeçalhos gravados com sucesso."

    def make_swap(self, device: str) -> Tuple[bool, str]:
        """Initializes a swap area (mkswap /dev/sda2)."""
        if self.current_user != "root":
            return False, f"mkswap: {device}: Permissão negada."

        if device not in self.partitions:
            return False, f"mkswap: erro: {device}: Arquivo ou diretório inexistente"

        part = self.partitions[device]
        part.filesystem = "swap"
        return True, f"Configurando o espaço de swap versão 1, tamanho = {part.size_human}\nsem rótulo, UUID=8a7c22e4-9842-4f91-a1b2-11c5e93df7a1"

    def swapon(self, device: str) -> Tuple[bool, str]:
        """Activates swap space."""
        if self.current_user != "root":
            return False, f"swapon: {device}: Operação não permitida."

        if device not in self.partitions:
            return False, f"swapon: não foi possível encontrar a partição {device}"
        part = self.partitions[device]
        if part.filesystem != "swap":
            return False, f"swapon: {device}: assinatura de swap inválida."
        if part.is_swap_active:
            return False, f"swapon: {device}: dispositivo ou recurso ocupado"
        part.is_swap_active = True
        return True, ""

    def swapoff(self, device: str) -> Tuple[bool, str]:
        """Deactivates swap space."""
        if self.current_user != "root":
            return False, f"swapoff: {device}: Operação não permitida."

        if device not in self.partitions:
            return False, f"swapoff: {device}: Arquivo ou diretório inexistente"
        part = self.partitions[device]
        part.is_swap_active = False
        return True, ""

    def _generate_mounts_file(self) -> str:
        """Generates mock contents of /proc/self/mounts."""
        lines = [
            "rootfs / rootfs rw 0 0",
            "/dev/sda3 / ext4 rw,relatime 0 0",
            "proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0",
            "sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0",
            "tmpfs /run tmpfs rw,nosuid,nodev,relatime,mode=755 0 0",
            "devpts /dev/pts devpts rw,nosuid,noexec,relatime,gid=5,mode=620 0 0",
        ]
        return "\n".join(lines) + "\n"

    def mount(
        self,
        device: str,
        mount_point: str,
        fstype: str = "ext4",
        verbose: bool = False,
        is_bind: bool = False,
        options: str = ""
    ) -> Tuple[bool, str]:
        """Mounts a filesystem partition, bind mount, or kernel virtual filesystem."""
        if self.current_user != "root":
            return False, "mount: apenas o superusuário pode executar 'mount'."

        norm_mp = self.resolve_path(mount_point)
        real_mp = self._to_real_path(norm_mp)

        mp_node = self._resolve_host_node(real_mp)
        if not mp_node:
            return False, f"mount: ponto de montagem '{mount_point}' não existe"

        if not isinstance(mp_node, VirtualDirectory):
            return False, f"mount: '{mount_point}' não é um diretório"

        if real_mp in self.mounts or norm_mp in self.mounts:
            return False, f"mount: {mount_point} já está montado"

        # 1. Bind mount (e.g. mount --bind /dev $LFS/dev)
        if is_bind or fstype == "bind":
            norm_dev = self.resolve_path(device)
            real_dev = self._to_real_path(norm_dev)
            src_node = self._resolve_host_node(real_dev) or self._resolve_host_node(norm_dev)
            if not src_node:
                self.mkdir(device, parents=True)
                src_node = self._resolve_host_node(real_dev) or self._resolve_host_node(norm_dev)

            if isinstance(src_node, VirtualDirectory) and isinstance(mp_node, VirtualDirectory):
                for child_name, child_node in src_node.children.items():
                    mp_node.children[child_name] = child_node

            self.mounts[real_mp] = device
            self.mounts[norm_mp] = device
            msg = f"mount: {device} montado em {mount_point} (montagem vinculada)." if verbose else ""
            return True, msg

        # 2. Kernel Virtual Filesystems (proc, sysfs, tmpfs, devpts)
        virtual_types = {"proc", "sysfs", "tmpfs", "devpts", "devtmpfs", "ramfs"}
        if fstype in virtual_types or device in virtual_types:
            actual_type = fstype if fstype in virtual_types else device
            if isinstance(mp_node, VirtualDirectory):
                if actual_type == "proc":
                    self.touch(f"{norm_mp}/cpuinfo")
                    self.touch(f"{norm_mp}/meminfo")
                    self.mkdir(f"{norm_mp}/self", parents=True)
                    self.write_file(f"{norm_mp}/self/mounts", self._generate_mounts_file())
                elif actual_type == "sysfs":
                    self.mkdir(f"{norm_mp}/devices", parents=True)
                    self.mkdir(f"{norm_mp}/block", parents=True)
                    self.mkdir(f"{norm_mp}/bus", parents=True)
                elif actual_type == "devpts":
                    self.touch(f"{norm_mp}/ptmx")
                elif actual_type == "tmpfs":
                    pass

            self.mounts[real_mp] = device
            self.mounts[norm_mp] = device
            msg = f"mount: {device} montado em {mount_point} (tipo {actual_type})." if verbose else ""
            return True, msg

        # 3. Partition block device
        if device not in self.partitions:
            return False, f"mount: dispositivo especial '{device}' não existe"

        part = self.partitions[device]
        if not part.filesystem:
            return False, f"mount: tipo de sistema de arquivos incorreto, opção inválida, superbloco inválido em {device}"

        self.mounts[real_mp] = device
        self.mounts[norm_mp] = device
        part.mount_point = norm_mp
        msg = f"mount: {device} montado em {mount_point}." if verbose else ""
        return True, msg

    def umount(self, target: str, verbose: bool = False) -> Tuple[bool, str]:
        """Unmounts filesystem."""
        if self.current_user != "root":
            return False, "umount: apenas o superusuário pode executar 'umount'."

        norm_target = self.resolve_path(target)
        found_mp = None
        if norm_target in self.mounts:
            found_mp = norm_target
        else:
            for mp, dev in self.mounts.items():
                if dev == target or dev == norm_target:
                    found_mp = mp
                    break

        if not found_mp:
            return False, f"umount: {target}: não montado."

        dev = self.mounts.pop(found_mp)
        if dev in self.partitions:
            self.partitions[dev].mount_point = None
        msg = f"umount: {found_mp} desmontado." if verbose else ""
        return True, msg

    def df(self) -> str:
        """Returns df output of virtual filesystem."""
        lines = [
            f"{'Sistema de Arq.':<18} {'Tam.':>8} {'Usado':>8} {'Disp.':>8} {'Uso%':>5} {'Montado em':<15}",
            f"{'udev':<18} {'3.8G':>8} {'0':>8} {'3.8G':>8} {'0%':>5} {'/dev':<15}",
            f"{'tmpfs':<18} {'788M':>8} {'1.8M':>8} {'786M':>8} {'1%':>5} {'/run':<15}",
            f"{'/dev/nvme0n1p2':<18} {'98G':>8} {'22G':>8} {'71G':>8} {'24%':>5} {'/':<15}",
        ]
        for mp, dev in self.mounts.items():
            part = self.partitions.get(dev)
            if part:
                lines.append(f"{dev:<18} {part.size_human:>8} {'128M':>8} {part.size_human:>8} {'1%':>5} {mp:<15}")
        return "\n".join(lines)

    # Users and Groups
    def groupadd(self, groupname: str) -> Tuple[bool, str]:
        """Adds a group."""
        if self.current_user != "root":
            return False, "groupadd: Permissão negada."

        if groupname in self.groups:
            return False, f"groupadd: o grupo '{groupname}' já existe"
        gid = max([g["gid"] for g in self.groups.values()], default=999) + 1
        if gid < 1000:
            gid = 1000
        self.groups[groupname] = {"gid": gid, "members": []}
        # Update /etc/group
        grp_content = f"{groupname}:x:{gid}:\n"
        self.write_file("/etc/group", grp_content, append=True)
        return True, ""

    def useradd(self, username: str, group: Optional[str] = None, home: Optional[str] = None, shell: str = "/bin/bash", create_home: bool = True) -> Tuple[bool, str]:
        """Adds a user."""
        if self.current_user != "root":
            return False, "useradd: Permissão negada."

        if username in self.users:
            return False, f"useradd: o usuário '{username}' já existe"

        primary_group = group if group else username
        if primary_group not in self.groups:
            self.groupadd(primary_group)

        uid = max([u["uid"] for u in self.users.values()], default=999) + 1
        if uid < 1000:
            uid = 1000
        gid = self.groups[primary_group]["gid"]
        user_home = home if home else f"/home/{username}"

        self.users[username] = {
            "uid": uid,
            "gid": gid,
            "group": primary_group,
            "home": user_home,
            "shell": shell
        }
        self.groups[primary_group]["members"].append(username)

        # Update /etc/passwd
        passwd_line = f"{username}:x:{uid}:{gid}:{username}:{user_home}:{shell}\n"
        self.write_file("/etc/passwd", passwd_line, append=True)

        if create_home:
            self.mkdir(user_home, parents=True)
            self.chown(user_home, f"{username}:{primary_group}")

        return True, ""

    def su(self, username: str = "root", login: bool = False) -> Tuple[bool, str]:
        """Switches current user."""
        if username not in self.users:
            return False, f"su: usuário {username} não existe ou a chave de acesso foi revogada."

        # Save previous user env
        self.user_saved_envs[self.current_user] = dict(self.env)
        self.user_stack.append(self.current_user)

        self.current_user = username
        user_data = self.users[username]

        if login:
            # Sterile clean environment as per Chapter 4
            self.env = {
                "USER": username,
                "LOGNAME": username,
                "HOME": user_data["home"],
                "SHELL": user_data["shell"],
                "TERM": "xterm-256color",
                "PWD": user_data["home"],
            }
            self.cwd = user_data["home"]

            # Execute .bash_profile and .bashrc if they exist in user home
            profile_path = posixpath.join(user_data["home"], ".bash_profile")
            bashrc_path = posixpath.join(user_data["home"], ".bashrc")

            if self.exists(profile_path):
                ok, profile_content = self.read_file(profile_path)
                if ok:
                    self._eval_simple_bash_env(profile_content)

            if self.exists(bashrc_path):
                ok, rc_content = self.read_file(bashrc_path)
                if ok:
                    self._eval_simple_bash_env(rc_content)
        else:
            self.env["USER"] = username
            self.env["LOGNAME"] = username

        return True, ""

    def exit_user(self) -> Tuple[bool, str]:
        """Exits current sub-shell user back to previous user."""
        if not self.user_stack:
            return False, "exit: nenhuma sessão anterior no terminal"
        prev_user = self.user_stack.pop()
        self.current_user = prev_user
        if prev_user in self.user_saved_envs:
            self.env = self.user_saved_envs[prev_user]
            self.cwd = self.env.get("PWD", self.users[prev_user]["home"])
        return True, f"logout (retornando a {self.current_user})"

    def _eval_simple_bash_env(self, script: str):
        """Simple evaluator for assignments and exports in bash profile/rc."""
        for line in script.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle semicolons
            statements = [s.strip() for s in line.split(";") if s.strip()]
            for stmt in statements:
                if stmt.startswith("export "):
                    stmt = stmt[7:].strip()
                    # e.g. export LFS LC_ALL LFS_TGT PATH or export LFS=/mnt/lfs
                    tokens = stmt.split()
                    for tok in tokens:
                        if "=" in tok:
                            k, v = tok.split("=", 1)
                            self.env[k] = self.expand_vars(v.strip("\"'"))
                elif "=" in stmt and not stmt.startswith("exec "):
                    k, v = stmt.split("=", 1)
                    k = k.strip()
                    v = self.expand_vars(v.strip().strip("\"'"))
                    self.env[k] = v

    def enter_chroot(self, target_path: str = "/mnt/lfs") -> Tuple[bool, str]:
        """Enters chroot environment rooted at target_path."""
        if self.in_chroot:
            return False, "chroot: já está operando dentro de um ambiente chroot ativo"

        abs_target = self.resolve_path(target_path)
        node = self._resolve_node(abs_target)
        if not node:
            return False, f"chroot: não foi possível mudar o diretório raiz para '{target_path}': Arquivo ou diretório inexistente"
        if not isinstance(node, VirtualDirectory):
            return False, f"chroot: não foi possível mudar o diretório raiz para '{target_path}': Não é um diretório"

        self.chroot_saved_host_state = {
            "current_user": self.current_user,
            "cwd": self.cwd,
            "env": dict(self.env),
            "user_stack": list(self.user_stack),
        }
        self.chroot_dir = abs_target
        self.in_chroot = True
        self.current_user = "root"
        self.cwd = "/"
        self.user_stack = []

        self.env = {
            "HOME": "/root",
            "TERM": self.env.get("TERM", "xterm-256color"),
            "PS1": "(lfs chroot) \\u:\\w\\$ ",
            "PATH": "/usr/bin:/usr/sbin",
            "USER": "root",
            "LOGNAME": "root",
            "PWD": "/",
        }

        # Check for virtual kernel filesystems (/dev, /proc, /sys)
        missing_mounts = []
        for vfs in ["dev", "proc", "sys"]:
            expected_mp = posixpath.join(abs_target, vfs)
            if expected_mp not in self.mounts and not any(m == expected_mp or m.endswith(f"/{vfs}") for m in self.mounts):
                missing_mounts.append(f"/{vfs}")

        warn_msg = ""
        if missing_mounts:
            warn_msg = (
                f"\n[bold yellow]⚠ ALERTA (K.E.R.N.E.L.): Montagens virtuais essenciais ausentes: {', '.join(missing_mounts)}![/bold yellow]\n"
                f"[yellow]O ambiente chroot foi isolado sem as interfaces do kernel (/dev, /proc, /sys).\n"
                f"Comandos que dependem de descritores de dispositivos ou inspeção de processos podem falhar.[/yellow]"
            )

        return True, (
            f"[bold green]Adentrando o ambiente chroot em '{target_path}'...[/bold green]\n"
            f"[dim]O cordão umbilical com o sistema anfitrião foi cortado.\n"
            f"Nova raiz '/': {abs_target}\n"
            f"Usuário: root | PATH: /usr/bin:/usr/sbin[/dim]{warn_msg}"
        )

    def exit_chroot(self) -> Tuple[bool, str]:
        """Exits chroot environment back to host system."""
        if not self.in_chroot:
            return False, "exit: nenhuma sessão chroot ativa"

        self.in_chroot = False
        saved = getattr(self, "chroot_saved_host_state", None)
        if saved:
            self.current_user = saved.get("current_user", "root")
            self.cwd = saved.get("cwd", self.chroot_dir)
            self.env = saved.get("env", {})
            self.user_stack = saved.get("user_stack", [])
        else:
            self.current_user = "root"
            self.cwd = self.chroot_dir

        return True, f"logout (saindo do ambiente chroot para o sistema hospedeiro em {self.cwd})"

    def install(
        self,
        targets: List[str],
        dir_mode: bool = False,
        mode: Optional[int] = None,
        verbose: bool = False
    ) -> Tuple[bool, str]:
        """Simulates Unix 'install' utility."""
        if not targets:
            return False, "install: operandos ausentes"

        msgs = []
        if dir_mode:
            for t in targets:
                ok, m = self.mkdir(t, parents=True)
                if not ok:
                    return False, m
                if mode is not None:
                    self.chmod(t, format(mode, "o"))
                msgs.append(f"install: criando diretório '{t}'")
            return True, "\n".join(msgs) if verbose else ""
        else:
            if len(targets) == 1:
                return False, f"install: operando de arquivo de destino ausente após '{targets[0]}'"
            srcs = targets[:-1]
            dest = targets[-1]
            for s in srcs:
                content = ""
                if self.exists(s):
                    _, content = self.read_file(s)
                dst_path = posixpath.join(dest, posixpath.basename(s)) if self.is_dir(dest) else dest
                self.write_file(dst_path, content)
                if mode is not None:
                    self.chmod(dst_path, format(mode, "o"))
                msgs.append(f"'{s}' -> '{dst_path}'")
            return True, "\n".join(msgs) if verbose else ""

    def to_dict(self) -> dict:
        """Serializes filesystem state to dict."""
        return {
            "root": self.root.to_dict(),
            "cwd": self.cwd,
            "current_user": self.current_user,
            "user_stack": self.user_stack,
            "users": self.users,
            "groups": self.groups,
            "env": self.env,
            "user_saved_envs": self.user_saved_envs,
            "partitions": {k: p.to_dict() for k, p in self.partitions.items()},
            "mounts": self.mounts,
            "installed_tools": dict(self.installed_tools),
            "compiled_packages": list(self.compiled_packages),
            "configured_packages": self.configured_packages,
            "in_chroot": self.in_chroot,
            "chroot_dir": self.chroot_dir,
            "chroot_saved_host_state": self.chroot_saved_host_state,
            "locales_configured": self.locales_configured,
            "shadow_configured": self.shadow_configured,
            "root_password_set": self.root_password_set,
            "bash_restarted": self.bash_restarted,
            "udev_updated": self.udev_updated,
            "debug_stripped": self.debug_stripped,
            "system_checks_passed": sorted(self.system_checks_passed),
            "bootscripts_installed": self.bootscripts_installed,
            "network_configured": self.network_configured,
            "sysconfig_configured": self.sysconfig_configured,
            "fstab_configured": self.fstab_configured,
            "kernel_config": dict(self.kernel_config),
            "kernel_configured": self.kernel_configured,
            "kernel_compiled": self.kernel_compiled,
            "kernel_installed": self.kernel_installed,
            "grub_mbr_installed": self.grub_mbr_installed,
            "grub_cfg_created": self.grub_cfg_created,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VirtualFS:
        """Deserializes filesystem state from dict."""
        fs = cls()
        fs.root = VirtualDirectory.from_dict(data["root"])
        fs.cwd = data.get("cwd", "/root")
        fs.current_user = data.get("current_user", "root")
        fs.user_stack = data.get("user_stack", [])
        fs.users = data.get("users", fs.users)
        fs.groups = data.get("groups", fs.groups)
        fs.env = data.get("env", fs.env)
        fs.user_saved_envs = data.get("user_saved_envs", {})
        fs.partitions = {k: Partition.from_dict(v) for k, v in data.get("partitions", {}).items()}
        fs.mounts = data.get("mounts", {})
        fs.installed_tools = data.get("installed_tools", {})
        fs.compiled_packages = set(data.get("compiled_packages", []))
        fs.configured_packages = data.get("configured_packages", {})
        fs.in_chroot = data.get("in_chroot", False)
        fs.chroot_dir = data.get("chroot_dir", "/mnt/lfs")
        fs.chroot_saved_host_state = data.get("chroot_saved_host_state", None)
        fs.locales_configured = data.get("locales_configured", False)
        fs.shadow_configured = data.get("shadow_configured", False)
        fs.root_password_set = data.get("root_password_set", False)
        fs.bash_restarted = data.get("bash_restarted", False)
        fs.udev_updated = data.get("udev_updated", False)
        fs.debug_stripped = data.get("debug_stripped", False)
        fs.system_checks_passed = set(data.get("system_checks_passed", []))
        fs.bootscripts_installed = data.get("bootscripts_installed", False)
        fs.network_configured = data.get("network_configured", False)
        fs.sysconfig_configured = data.get("sysconfig_configured", False)
        fs.fstab_configured = data.get("fstab_configured", False)
        default_kconfig = cls._default_kernel_config()
        saved_kconfig = data.get("kernel_config")
        if isinstance(saved_kconfig, dict) and saved_kconfig:
            default_kconfig.update(saved_kconfig)
        fs.kernel_config = default_kconfig
        fs.kernel_configured = data.get("kernel_configured", False)
        fs.kernel_compiled = data.get("kernel_compiled", False)
        fs.kernel_installed = data.get("kernel_installed", False)
        fs.grub_mbr_installed = data.get("grub_mbr_installed", False)
        fs.grub_cfg_created = data.get("grub_cfg_created", False)
        return fs

    def install_tool(self, name: str, path: str, content: str = "#!/bin/sh\n# LFS virtual binary\n", mode: int = 0o755) -> bool:
        """Installs a virtual binary and registers it in installed_tools."""
        abs_p = self.resolve_path(path)
        parent_dir = posixpath.dirname(abs_p)
        if not self.exists(parent_dir):
            parts = [p for p in parent_dir.split("/") if p]
            curr = self.root
            for part in parts:
                if part not in curr.children:
                    new_dir = VirtualDirectory(
                        name=part,
                        is_directory=True,
                        owner=self.current_user,
                        group=self.users.get(self.current_user, {}).get("group", "root"),
                        mode=0o755
                    )
                    curr.children[part] = new_dir
                    curr = new_dir
                else:
                    curr = curr.children[part]

        ok, _ = self.write_file(abs_p, content)
        if ok:
            node = self._resolve_node(abs_p)
            if node:
                node.mode = mode
                node.owner = self.current_user
            self.installed_tools[name] = abs_p
        return ok

    def record_package_compiled(self, pkg_id: str):
        """Records a package as successfully compiled."""
        self.compiled_packages.add(pkg_id.strip().lower())

    def is_package_compiled(self, pkg_id: str) -> bool:
        """Checks if a package has been compiled."""
        return pkg_id.strip().lower() in self.compiled_packages

    def inspect_elf(self, path: str) -> Optional[str]:
        """Simulates ELF program headers inspection (as output by readelf -l)."""
        abs_p = self.resolve_path(path)
        if not self.exists(abs_p) or self.is_dir(abs_p):
            return None

        ok, content = self.read_file(abs_p)
        is_elf = (
            (ok and content.startswith("\x7fELF"))
            or abs_p in self.installed_tools.values()
            or any(t in abs_p for t in ["/tools/bin/", "/usr/bin/", "/lib64/", "/usr/lib/"])
        )
        if not is_elf:
            return None

        return (
            "Elf file type is EXEC (Executable file)\n"
            "Entry point 0x401000\n"
            "There are 4 program headers, starting at offset 64\n\n"
            "Program Headers:\n"
            "  Type           Offset             VirtAddr           PhysAddr\n"
            "                 FileSiz            MemSiz              Flags  Align\n"
            "  PHDR           0x0000000000000040 0x0000000000400040 0x0000000000400040\n"
            "                 0x00000000000001f8 0x00000000000001f8  R      0x8\n"
            "  INTERP         0x0000000000000238 0x0000000000400238 0x0000000000400238\n"
            "                 0x000000000000001c 0x000000000000001c  R      0x1\n"
            "      [Requesting program interpreter: /lib/ld-linux-x86-64.so.2]\n"
            "  LOAD           0x0000000000000000 0x0000000000400000 0x0000000000400000\n"
            "                 0x00000000000005a0 0x00000000000005a0  R E    0x1000\n"
            "  LOAD           0x00000000000005a0 0x00000000004015a0 0x00000000004015a0\n"
            "                 0x0000000000000210 0x0000000000000210  RW     0x1000\n"
        )
