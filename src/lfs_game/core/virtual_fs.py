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

        self._init_standard_tree()

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

    def expand_vars(self, text: str) -> str:
        """Expands environment variables like $LFS or ${LFS}."""
        def repl(m: re.Match) -> str:
            var_name = m.group(1) or m.group(2)
            return self.env.get(var_name, "")

        pattern = re.compile(r"\$(?:\{([a-zA-Z_][a-zA-Z0-9_]*)\}|([a-zA-Z_][a-zA-Z0-9_]*))")
        return pattern.sub(repl, text)

    def _get_parent_and_basename(self, abs_path: str) -> Tuple[Optional[VirtualDirectory], str]:
        """Returns parent VirtualDirectory and final component name."""
        if abs_path == "/":
            return None, ""
        parent_path, basename = posixpath.split(abs_path)
        parent_node = self._resolve_node(parent_path)
        if isinstance(parent_node, VirtualDirectory):
            return parent_node, basename
        return None, basename

    def _resolve_node(self, abs_path: str) -> Optional[VirtualInode]:
        """Finds node at absolute path."""
        abs_path = posixpath.normpath(abs_path)
        if abs_path in ("", "/"):
            return self.root

        parts = [p for p in abs_path.split("/") if p]
        curr = self.root
        for part in parts:
            if not isinstance(curr, VirtualDirectory):
                return None
            if part not in curr.children:
                return None
            curr = curr.children[part]
        return curr

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

        parts = [p for p in abs_path.split("/") if p]
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
                created_paths.append(accum)

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
        return True, ""

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

    def chown(self, path: str, owner_group: str, recursive: bool = False, verbose: bool = False) -> Tuple[bool, str]:
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
        """Changes mode permissions (e.g. 'a+wt', '755', '644')."""
        abs_path = self.resolve_path(path)
        node = self._resolve_node(abs_path)
        if not node:
            return False, f"chmod: não foi possível acessar '{path}': Arquivo ou diretório inexistente"

        if self.current_user != "root" and node.owner != self.current_user:
            return False, f"chmod: alterando as permissões de '{path}': Operação não permitida"

        new_mode: Optional[int] = None
        if mode_expr.isdigit():
            try:
                new_mode = int(mode_expr, 8)
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

    def mount(self, device: str, mount_point: str, fstype: str = "ext4", verbose: bool = False) -> Tuple[bool, str]:
        """Mounts a filesystem partition to a mount point."""
        if self.current_user != "root":
            return False, "mount: apenas o superusuário pode executar 'mount'."

        norm_mp = self.resolve_path(mount_point)
        if not self.exists(norm_mp):
            return False, f"mount: ponto de montagem '{mount_point}' não existe"

        if not self.is_dir(norm_mp):
            return False, f"mount: '{mount_point}' não é um diretório"

        if device not in self.partitions:
            return False, f"mount: dispositivo especial '{device}' não existe"

        part = self.partitions[device]
        if not part.filesystem:
            return False, f"mount: tipo de sistema de arquivos incorreto, opção inválida, superbloco inválido em {device}"

        if norm_mp in self.mounts:
            return False, f"mount: {norm_mp} já está montado"

        self.mounts[norm_mp] = device
        part.mount_point = norm_mp
        msg = f"mount: {device} montado em {norm_mp}." if verbose else ""
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
