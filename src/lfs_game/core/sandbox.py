"""Sandbox / Test Navigation Mode for jumping directly between Acts and Chapters."""

from __future__ import annotations
from dataclasses import dataclass
import posixpath
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .virtual_fs import VirtualFS
from ..data.lfs_manifest import (
    TOOLCHAIN_CATALOG,
    get_md5sums_text,
    get_system_packages,
    list_packages,
)
from ..rpg.character import HackerCharacter
from ..rpg.combat import AnomalyManager
from ..rpg.story_engine import DialogueMessage, StoryEngine

if TYPE_CHECKING:
    from .engine import GameEngine


@dataclass(frozen=True)
class SandboxTarget:
    """Metadata describing an Act/Chapter jump destination."""
    key: str
    aliases: Tuple[str, ...]
    label: str
    chapter: str
    description: str


SANDBOX_TARGETS: List[SandboxTarget] = [
    SandboxTarget(
        key="prologue",
        aliases=("0", "ch1"),
        label="Prólogo — Estação Hera",
        chapter="Cap. 1",
        description="Início absoluto (Prólogo na Estação Hera, diálogo inicial da K.E.R.N.E.L.).",
    ),
    SandboxTarget(
        key="1",
        aliases=("ato1", "ch2"),
        label="Ato 1 — Cap. 2: Particionamento & Montagem",
        chapter="Cap. 2",
        description="Início do Ato 1 (prólogo concluído, pronto para $LFS, mkfs.ext4, swap e mount).",
    ),
    SandboxTarget(
        key="ch3",
        aliases=(),
        label="Ato 1 — Cap. 3: Pacotes e Remendos",
        chapter="Cap. 3",
        description="Partições formatadas e $LFS montado, pronto para baixar fontes e md5sum.",
    ),
    SandboxTarget(
        key="ch4",
        aliases=(),
        label="Ato 1 — Cap. 4: Preparações Finais",
        chapter="Cap. 4",
        description="Fontes em $LFS/sources verificadas, pronto para criar $LFS/tools e usuário lfs.",
    ),
    SandboxTarget(
        key="2",
        aliases=("ato2", "ch5"),
        label="Ato 2 — Cap. 5: Cross-Toolchain (Pass 1)",
        chapter="Cap. 5",
        description="Usuário 'lfs' com ambiente estéril pronto para Binutils/GCC Pass 1 & Glibc.",
    ),
    SandboxTarget(
        key="ch6",
        aliases=(),
        label="Ato 2 — Cap. 6: Ferramentas Temporárias & Pass 2",
        chapter="Cap. 6",
        description="Cross-toolchain + sanity check concluídos, pronto para ferramentas temporárias e Passagem 2.",
    ),
    SandboxTarget(
        key="3",
        aliases=("ato3", "ch7"),
        label="Ato 3 — Cap. 7: Preparação do Chroot",
        chapter="Cap. 7",
        description="Ato 2 concluído, de volta como root no host, pronto para chown e mounts virtuais do chroot.",
    ),
    SandboxTarget(
        key="chroot",
        aliases=(),
        label="Ato 3 — Dentro do Chroot",
        chapter="Cap. 7.4",
        description="Sistemas virtuais montados, dentro de '(lfs chroot) root:/# ', pronto para árvore FHS e ferramentas Cap. 7.",
    ),
    SandboxTarget(
        key="4",
        aliases=("ato4", "ch8"),
        label="Ato 4 — Cap. 8: Sistema Definitivo (Tiers 1–4)",
        chapter="Cap. 8",
        description="Tudo do Cap. 7 concluído e limpo, pronto para Tier 1..4 do sistema definitivo.",
    ),
    SandboxTarget(
        key="5",
        aliases=("ato5", "ch9"),
        label="Ato 5 — Cap. 9: Bootscripts, Rede & Sysconfig",
        chapter="Cap. 9",
        description="Todos os 81 pacotes do Cap. 8 compilados, tests/localedef/shadow/udev/strip feitos, pronto para bootscripts, rede e sysconfig.",
    ),
    SandboxTarget(
        key="ch10",
        aliases=("kernel", "5.2"),
        label="Ato 5 — Cap. 10: /etc/fstab, Kernel 7.1.8 & GRUB",
        chapter="Cap. 10",
        description="Cap. 9 configurado, pronto para /etc/fstab, make menuconfig, Kernel 7.1.8 e GRUB.",
    ),
    SandboxTarget(
        key="ready",
        aliases=("5.end", "boot-ready"),
        label="Ato 5 Concluído — Pronto para o Boot",
        chapter="Cap. 10+",
        description="Ato 5 100% concluído (Kernel 7.1.8 e GRUB instalados no /dev/sda, título 'Forjador do Kernel').",
    ),
]


def resolve_target(query: str) -> Optional[SandboxTarget]:
    """Resolves a target key or alias (case-insensitive) to its SandboxTarget."""
    q = query.strip().lower()
    if not q:
        return None
    for target in SANDBOX_TARGETS:
        if target.key.lower() == q or q in (a.lower() for a in target.aliases):
            return target
    return None


def list_targets_table() -> str:
    """Returns a Rich-formatted guide listing all sandbox jump targets and aliases."""
    lines = [
        "[bold cyan]╔══════════════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
        "[bold cyan]║ MODO SANDBOX / TESTE — TELEPORTE ENTRE ATOS E CAPÍTULOS (LFS 13.1 pt_BR)            ║[/bold cyan]",
        "[bold cyan]╚══════════════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
        f"{'ALVO':<10} {'CAP.':<9} {'ALIASES':<18} {'DESCRIÇÃO'}",
        "─" * 88,
    ]
    for t in SANDBOX_TARGETS:
        alias_str = ", ".join(t.aliases) if t.aliases else "-"
        lines.append(
            f"[bold green]{t.key:<10}[/bold green] [cyan]{t.chapter:<9}[/cyan] [dim]{alias_str:<18}[/dim] {t.description}"
        )
    lines.extend([
        "─" * 88,
        "[yellow]Uso no terminal:[/yellow] [bold green]lfs-jump <alvo>[/bold green] (ou [bold green]jump <alvo>[/bold green]) | [yellow]Atalho TUI:[/yellow] [bold cyan]F4[/bold cyan]",
        "[yellow]Uso na linha de comando:[/yellow] [bold green]lfs-game --act <alvo>[/bold green] ou [bold green]--test-mode[/bold green]",
    ])
    return "\n".join(lines)


def _complete_quests_up_to(story: StoryEngine, char: HackerCharacter, target_index: int) -> None:
    """Marks quests 0..target_index-1 as completed and awards their quest XP."""
    for idx in range(min(target_index, len(story.quests))):
        q = story.quests[idx]
        q.completed = True
        char.add_xp(q.xp_reward)
    story.current_quest_index = target_index


def _set_teleport_dialogue(
    story: StoryEngine,
    text: str,
    mood: str = "encouraging",
) -> None:
    """Sets a K.E.R.N.E.L. teleport briefing dialogue as the current transmission."""
    msg = DialogueMessage(
        speaker="K.E.R.N.E.L.",
        text=text,
        mood=mood,
    )
    story.current_dialogue = msg
    story.dialogue_history.append(msg)


def _provision_ch3(engine: GameEngine) -> None:
    """Partitions formatted, swap active, $LFS=/mnt/lfs mounted."""
    fs = engine.fs
    fs.env["LFS"] = "/mnt/lfs"
    fs.format_partition("/dev/sda3", "ext4")
    fs.make_swap("/dev/sda2")
    fs.swapon("/dev/sda2")
    fs.mkdir("/mnt/lfs", parents=True)
    fs.mount("/dev/sda3", "/mnt/lfs", fstype="ext4")


def _provision_ch4(engine: GameEngine) -> None:
    """$LFS/sources populated with official tarballs and md5sums verified."""
    _provision_ch3(engine)
    fs = engine.fs
    sources_dir = "/mnt/lfs/sources"
    fs.mkdir(sources_dir, parents=True)
    fs.chmod(sources_dir, "a+wt")
    for p in list_packages():
        fs.write_file(posixpath.join(sources_dir, p.tarball), f"# Tarball binário simulado para {p.name} {p.version}\n")
    fs.write_file(posixpath.join(sources_dir, "md5sums"), get_md5sums_text())
    engine.story_engine.flags["sources_downloaded"] = True
    engine.story_engine.flags["md5_checked"] = True


def _provision_act2(engine: GameEngine) -> None:
    """Tools directory, lfs user, sterile environment (su - lfs), Act 1 complete."""
    _provision_ch4(engine)
    fs = engine.fs
    for d in ("tools", "etc", "var", "usr", "lib", "lib64", "bin", "sbin"):
        fs.mkdir(f"/mnt/lfs/{d}", parents=True)
    fs.groupadd("lfs")
    fs.useradd("lfs", group="lfs", home="/home/lfs", shell="/bin/bash", create_home=True)

    for d in ("tools", "sources", "etc", "var", "usr", "lib", "lib64", "bin", "sbin"):
        fs.chown(f"/mnt/lfs/{d}", "lfs", recursive=True)

    fs.write_file(
        "/home/lfs/.bash_profile",
        "exec env -i HOME=$HOME TERM=$TERM PS1='\\u:\\w\\$ ' /bin/bash\n",
    )
    fs.write_file(
        "/home/lfs/.bashrc",
        (
            "set +h\n"
            "umask 022\n"
            "LFS=/mnt/lfs\n"
            "LC_ALL=POSIX\n"
            "LFS_TGT=x86_64-lfs-linux-gnu\n"
            "PATH=/usr/bin:/bin\n"
            "export LFS LC_ALL LFS_TGT PATH\n"
        ),
    )
    fs.chown("/home/lfs", "lfs:lfs", recursive=True)

    # Ensure root's saved env preserves LFS=/mnt/lfs before switching to lfs
    fs.env["LFS"] = "/mnt/lfs"
    fs.su("lfs", login=True)
    fs.env["LFS"] = "/mnt/lfs"
    fs.env["LC_ALL"] = "POSIX"
    fs.env["LFS_TGT"] = "x86_64-lfs-linux-gnu"
    fs.env["PATH"] = "/usr/bin:/bin"

    engine.story_engine.flags["act1_celebrated"] = True
    engine.telemetry.oxygen = 65.0


def _provision_ch6(engine: GameEngine) -> None:
    """Chapter 5 cross-toolchain (Binutils1, GCC1, Headers, Glibc, sanity check, Libstdc++) complete."""
    _provision_act2(engine)
    fs = engine.fs
    tgt = fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu")
    lfs_dir = "/mnt/lfs"

    for tool_id in ("binutils-pass1", "gcc-pass1"):
        pkg = TOOLCHAIN_CATALOG[tool_id]
        fs.record_package_compiled(tool_id)
        for b in pkg.binaries:
            b_clean = b.replace("$LFS_TGT", tgt)
            fs.install_tool(b_clean, f"{lfs_dir}/tools/bin/{b_clean}")

    fs.mkdir(f"{lfs_dir}/usr/include/linux", parents=True)
    fs.write_file(f"{lfs_dir}/usr/include/linux/version.h", "#define LINUX_VERSION_CODE 396807\n")
    fs.record_package_compiled("linux-headers")

    fs.mkdir(f"{lfs_dir}/lib64", parents=True)
    fs.mkdir(f"{lfs_dir}/lib", parents=True)
    fs.mkdir(f"{lfs_dir}/usr/lib", parents=True)
    fs.mkdir(f"{lfs_dir}/usr/bin", parents=True)
    fs.install_tool("ld-linux-x86-64.so.2", f"{lfs_dir}/lib64/ld-linux-x86-64.so.2")
    fs.install_tool("ld-linux.so.2", f"{lfs_dir}/lib/ld-linux-x86-64.so.2")
    fs.install_tool("libc.so.6", f"{lfs_dir}/usr/lib/libc.so.6")
    fs.install_tool("ldd", f"{lfs_dir}/usr/bin/ldd")
    fs.record_package_compiled("glibc")

    fs.write_file(f"{lfs_dir}/sources/a.out", "\x7fELF (x86_64 LFS 13.1 Sanity Check Binary)\n")
    engine.story_engine.flags["sanity_check_passed"] = True

    fs.install_tool("libstdc++.so", f"{lfs_dir}/usr/lib/libstdc++.so")
    fs.install_tool("libstdc++.so.6", f"{lfs_dir}/usr/lib/libstdc++.so.6")
    fs.record_package_compiled("libstdc++")


def _provision_act3(engine: GameEngine) -> None:
    """Chapter 6 temp tools + Pass 2 complete; returned to host root ready for chown & virtual mounts."""
    _provision_ch6(engine)
    fs = engine.fs
    lfs_dir = "/mnt/lfs"
    tgt = fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu")

    ch6_order = [
        "m4", "ncurses", "bash", "coreutils", "diffutils",
        "file", "findutils", "gawk", "grep", "gzip",
        "make", "patch", "sed", "tar", "xz",
    ]
    for tool_id in ch6_order:
        pkg = TOOLCHAIN_CATALOG[tool_id]
        fs.record_package_compiled(tool_id)
        fs.install_tool(tool_id, f"{lfs_dir}/usr/bin/{tool_id}")
        for b in pkg.binaries:
            b_clean = b.replace("$LFS_TGT", tgt)
            fs.install_tool(b_clean, f"{lfs_dir}/usr/bin/{b_clean}")
            fs.record_package_compiled(b_clean)

    engine.story_engine.flags["temp_tools_compiled"] = True

    for tool_id in ("binutils-pass2", "gcc-pass2"):
        pkg = TOOLCHAIN_CATALOG[tool_id]
        fs.record_package_compiled(tool_id)
        for b in pkg.binaries:
            fs.install_tool(b, f"{lfs_dir}/usr/bin/{b}")

    engine.anomaly_manager.resolved_history.append("CPU_OVERHEAT")
    engine.story_engine.flags["act2_celebrated"] = True

    # Exit back to host root with $LFS preserved
    fs.exit_user()
    fs.cd("/root")
    fs.env["LFS"] = "/mnt/lfs"
    engine.telemetry.oxygen = 85.0


def _provision_chroot(engine: GameEngine) -> None:
    """Ownership transferred to root, virtual kernel filesystems mounted, inside chroot jail."""
    _provision_act3(engine)
    fs = engine.fs
    for d in ("usr", "var", "etc", "tools", "lib", "lib64", "bin", "sbin", "sources"):
        fs.chown(f"/mnt/lfs/{d}", "root:root", recursive=True, from_owner="lfs")

    for vfs in ("dev", "proc", "sys", "run"):
        fs.mkdir(f"/mnt/lfs/{vfs}", parents=True)

    fs.mount("/dev", "/mnt/lfs/dev", fstype="bind", is_bind=True)
    fs.mount("devpts", "/mnt/lfs/dev/pts", fstype="devpts", options="gid=5,mode=0620")
    fs.mount("proc", "/mnt/lfs/proc", fstype="proc")
    fs.mount("sysfs", "/mnt/lfs/sys", fstype="sysfs")
    fs.mount("tmpfs", "/mnt/lfs/run", fstype="tmpfs")

    fs.enter_chroot("/mnt/lfs")


def _provision_act4(engine: GameEngine) -> None:
    """Chroot FHS tree, Chapter 7 tools compiled, /tools removed, ready for Chapter 8 Tiers 1-4."""
    _provision_chroot(engine)
    fs = engine.fs

    fhs_dirs = [
        "/boot", "/home", "/mnt", "/opt", "/srv",
        "/etc/opt", "/etc/sysconfig", "/lib/firmware",
        "/media/floppy", "/media/cdrom",
        "/usr/bin", "/usr/include", "/usr/lib", "/usr/sbin", "/usr/src",
        "/usr/local/bin", "/usr/local/include", "/usr/local/lib", "/usr/local/sbin", "/usr/local/src",
        "/usr/share/color", "/usr/share/dict", "/usr/share/doc", "/usr/share/info",
        "/usr/share/locale", "/usr/share/man",
        "/var/cache", "/var/local", "/var/log", "/var/mail", "/var/opt", "/var/spool",
        "/var/lib/color", "/var/lib/misc", "/var/lib/locate",
    ]
    for d in fhs_dirs:
        fs.mkdir(d, parents=True)

    fs.install(["/root"], dir_mode=True, mode=0o750)
    fs.install(["/tmp", "/var/tmp"], dir_mode=True, mode=0o1777)
    fs.write_file("/etc/mtab", "# Symlink to /proc/self/mounts\n")
    fs.write_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n")
    fs.write_file("/etc/group", "root:x:0:\n")

    ch7_order = ["gettext", "bison", "perl", "python", "texinfo", "util-linux"]
    for tool_id in ch7_order:
        pkg = TOOLCHAIN_CATALOG[tool_id]
        fs.record_package_compiled(tool_id)
        fs.install_tool(tool_id, f"/usr/bin/{tool_id}")
        for b in pkg.binaries:
            fs.install_tool(b, f"/usr/bin/{b}")
            fs.record_package_compiled(b)

    engine.story_engine.flags["chroot_tools_compiled"] = True

    fs.rm("/tools", recursive=True, force=True)
    engine.story_engine.flags["chroot_cleaned"] = True
    engine.story_engine.flags["act3_celebrated"] = True
    engine.telemetry.oxygen = 95.0


def _provision_act5(engine: GameEngine) -> None:
    """All 81 Chapter 8 packages compiled, tests/locales/shadow/udev/strip done, ready for Chapter 9."""
    _provision_act4(engine)
    fs = engine.fs

    for pkg in get_system_packages():
        fs.record_package_compiled(pkg.id)
        if pkg.binaries:
            for b in pkg.binaries:
                if b.startswith("lib") or ".so" in b or b.endswith(".a"):
                    dest_dir = "/usr/lib"
                elif pkg.install_path in ("/usr/sbin", "/sbin"):
                    dest_dir = "/usr/sbin"
                else:
                    dest_dir = "/usr/bin"
                fs.install_tool(b, f"{dest_dir}/{b}")
        elif pkg.install_path == "/etc":
            fs.write_file("/etc/services", "# IANA network services\nssh\t22/tcp\nhttps\t443/tcp\n")
            fs.write_file("/etc/protocols", "# IANA internet protocols\ntcp\t6\tTCP\nudp\t17\tUDP\n")

    for t in (1, 2, 3, 4):
        engine.story_engine.flags[f"tier{t}_compiled"] = True

    fs.system_checks_passed.update({"glibc", "binutils", "gcc"})

    fs.mkdir("/usr/lib/locale", parents=True)
    fs.write_file("/usr/lib/locale/locale-archive", "# Compiled locale archive\npt_BR.UTF-8\n")
    fs.locales_configured = True

    shadow_hash = "$y$j9T$HeraStation2142QuantumSalt$8xK9vP2mL4nQ7rT1wZ5yB3cF6hJ0kM"
    fs.write_file("/etc/shadow", f"root:{shadow_hash}:20100:0:99999:7:::\n")
    fs.chmod("/etc/shadow", "0600")
    fs.write_file("/etc/gshadow", "root:*::\n")
    fs.chmod("/etc/gshadow", "0600")
    fs.shadow_configured = True
    fs.root_password_set = True

    fs.env["SHELL"] = "/usr/bin/bash"
    fs.env["PATH"] = "/usr/bin:/usr/sbin"
    fs.bash_restarted = True

    fs.mkdir("/etc/udev", parents=True)
    fs.write_file("/etc/udev/hwdb.bin", "# Binary udev hardware database (LFS 13.1)\n")
    fs.udev_updated = True

    fs.debug_stripped = True
    engine.story_engine.flags["act4_celebrated"] = True
    engine.telemetry.oxygen = 100.0


def _provision_ch10(engine: GameEngine) -> None:
    """Chapter 9 bootscripts, network, and SysVinit/shell config complete; ready for fstab, Kernel 7.1.8 & GRUB."""
    _provision_act5(engine)
    fs = engine.fs

    for d in ("/etc/rc.d/init.d", "/etc/rc.d/rc0.d", "/etc/rc.d/rc3.d", "/etc/rc.d/rcS.d", "/lib/services"):
        fs.mkdir(d, parents=True)
    for script in ("rc", "functions", "network", "mountfs", "udev", "sysklogd"):
        fs.write_file(f"/etc/rc.d/init.d/{script}", f"#!/bin/sh\n# LFS-Bootscripts 20250827 {script}\n")
    fs.write_file("/lib/services/ipv4-static", "#!/bin/sh\n# LFS static IPv4 network service\n")
    fs.bootscripts_installed = True
    fs.record_package_compiled("lfs-bootscripts")

    fs.write_file("/etc/hostname", "hera-lfs\n")
    fs.write_file(
        "/etc/hosts",
        "# Begin /etc/hosts\n127.0.0.1 localhost.localdomain localhost\n127.0.1.1 hera-lfs.hera.local hera-lfs\n::1 localhost\n# End /etc/hosts\n",
    )
    fs.write_file("/etc/resolv.conf", "# Begin /etc/resolv.conf\nnameserver 10.0.2.3\nnameserver 1.1.1.1\n# End /etc/resolv.conf\n")
    fs.write_file(
        "/etc/sysconfig/ifconfig.eth0",
        "ONBOOT=yes\nIFACE=eth0\nSERVICE=ipv4-static\nIP=192.168.1.2\nGATEWAY=192.168.1.1\nPREFIX=24\nBROADCAST=192.168.1.255\n",
    )
    fs.network_configured = True

    fs.write_file(
        "/etc/inittab",
        "# Begin /etc/inittab\nid:3:initdefault:\nsi::sysinit:/etc/rc.d/init.d/rc S\n1:2345:respawn:/sbin/agetty --noclear tty1 9600\n# End /etc/inittab\n",
    )
    fs.write_file("/etc/sysconfig/clock", "# Begin /etc/sysconfig/clock\nUTC=1\n# End /etc/sysconfig/clock\n")
    fs.write_file("/etc/sysconfig/console", "# Begin /etc/sysconfig/console\nKEYMAP=\"br-abnt2\"\nFONT=\"Lat2-Terminus16\"\n# End /etc/sysconfig/console\n")
    fs.write_file("/etc/profile", "# Begin /etc/profile\nexport LANG=pt_BR.UTF-8\nexport PATH=/usr/bin:/usr/sbin\n# End /etc/profile\n")
    fs.write_file("/etc/inputrc", "# Begin /etc/inputrc\nset horizontal-scroll-mode Off\nset meta-flag On\n# End /etc/inputrc\n")
    fs.write_file("/etc/shells", "# Begin /etc/shells\n/bin/sh\n/bin/bash\n# End /etc/shells\n")
    fs.sysconfig_configured = True

    fs.mkdir("/sources/linux-7.1.8", parents=True)
    engine.story_engine.flags["system_configured"] = True


def _provision_ready(engine: GameEngine) -> None:
    """Act 5 100% complete: /etc/fstab, Kernel 7.1.8, modules, GRUB MBR & grub.cfg."""
    _provision_ch10(engine)
    fs = engine.fs

    fs.write_file(
        "/etc/fstab",
        (
            "# Begin /etc/fstab\n"
            "/dev/sda3   /      ext4   defaults            1   1\n"
            "/dev/sda2   swap   swap   pri=1               0   0\n"
            "# End /etc/fstab\n"
        ),
    )
    fs.fstab_configured = True

    fs.kernel_config = fs._default_kernel_config()
    fs.kernel_configured = True
    dot_config_lines = ["# Automatically generated Linux 7.1.8 Kernel Configuration (LFS 13.1)"]
    for flag, val in fs.kernel_config.items():
        dot_config_lines.append(f"{flag}={val}")
    fs.write_file("/sources/linux-7.1.8/.config", "\n".join(dot_config_lines) + "\n")

    fs.mkdir("/sources/linux-7.1.8/arch/x86/boot", parents=True)
    fs.write_file("/sources/linux-7.1.8/arch/x86/boot/bzImage", "ELF/bzImage Linux 7.1.8-lfs-13.1\n")
    fs.write_file("/sources/linux-7.1.8/System.map", "ffffffff81000000 T _text\n")
    fs.kernel_compiled = True
    fs.record_package_compiled("linux-kernel")

    fs.mkdir("/lib/modules/7.1.8/kernel/fs", parents=True)
    fs.write_file("/lib/modules/7.1.8/modules.dep", "# Linux 7.1.8 module dependency map\n")
    fs.record_package_compiled("linux-modules")

    fs.write_file("/boot/vmlinuz-7.1.8-lfs-13.1", "ELF/bzImage Linux 7.1.8-lfs-13.1\n")
    fs.write_file("/boot/System.map-7.1.8", "ffffffff81000000 T _text\n")
    fs.write_file("/boot/config-7.1.8", "\n".join(dot_config_lines) + "\n")
    fs.kernel_installed = True

    fs.mkdir("/boot/grub/i386-pc", parents=True)
    fs.write_file("/boot/grub/i386-pc/core.img", "# GRUB 2.14 core image\n")
    fs.grub_mbr_installed = True

    fs.write_file(
        "/boot/grub/grub.cfg",
        (
            "# Begin /boot/grub/grub.cfg\n"
            "set default=0\n"
            "set timeout=5\n\n"
            "insmod part_gpt\n"
            "insmod ext2\n"
            "set root=(hd0,3)\n\n"
            "menuentry \"GNU/Linux, Linux 7.1.8-lfs-13.1 (Estacao Hera)\" {\n"
            "        linux   /boot/vmlinuz-7.1.8-lfs-13.1 root=/dev/sda3 ro\n"
            "}\n"
        ),
    )
    fs.grub_cfg_created = True

    engine.story_engine.flags["kernel_forged"] = True
    engine.story_engine.flags["act5_celebrated"] = True


# Mapping from canonical target key -> (provision_fn, target_quest_index, title_override, dialogue_text, mood)
_TARGET_SPECS: Dict[str, Tuple] = {
    "prologue": (
        None,
        0,
        None,
        "",
        "alert",
    ),
    "1": (
        None,
        1,
        None,
        (
            "[TELEPORTE SANDBOX: ATO 1 - CAPÍTULO 2]\n"
            "Prólogo concluído. Você está como root na Estação Hera.\n"
            "Próximos passos: 'export LFS=/mnt/lfs', 'mkfs.ext4 /dev/sda3', 'mkswap /dev/sda2 && swapon /dev/sda2', "
            "'mkdir -pv $LFS' e 'mount -v -t ext4 /dev/sda3 $LFS'."
        ),
        "encouraging",
    ),
    "ch3": (
        _provision_ch3,
        2,
        None,
        (
            "[TELEPORTE SANDBOX: ATO 1 - CAPÍTULO 3]\n"
            "Partições /dev/sda3 (ext4) e /dev/sda2 (swap) configuradas e $LFS=/mnt/lfs montado.\n"
            "Próximos passos: 'mkdir -v $LFS/sources', 'chmod -v a+wt $LFS/sources', 'lfs-get-sources' e 'cd $LFS/sources && md5sum -c md5sums'."
        ),
        "encouraging",
    ),
    "ch4": (
        _provision_ch4,
        3,
        None,
        (
            "[TELEPORTE SANDBOX: ATO 1 - CAPÍTULO 4]\n"
            "Todos os 98 pacotes e remendos estão em $LFS/sources com somas MD5 validadas.\n"
            "Próximos passos: 'mkdir -pv $LFS/tools', 'groupadd lfs', 'useradd -s /bin/bash -g lfs -m -k /dev/null lfs' e 'chown -v lfs $LFS/{tools,sources}'."
        ),
        "encouraging",
    ),
    "2": (
        _provision_act2,
        5,
        None,
        (
            "[TELEPORTE SANDBOX: ATO 2 - CAPÍTULO 5]\n"
            "Ato 1 concluído! Você está operando como usuário 'lfs' em ambiente estéril ($LFS_TGT=x86_64-lfs-linux-gnu).\n"
            "Próximos passos: Compilar Binutils Pass 1, GCC Pass 1, Linux API Headers, Glibc 2.44 + Sanity Check e Libstdc++."
        ),
        "encouraging",
    ),
    "ch6": (
        _provision_ch6,
        8,
        None,
        (
            "[TELEPORTE SANDBOX: ATO 2 - CAPÍTULO 6]\n"
            "Cross-Toolchain do Capítulo 5 e Teste de Sanidade concluídos!\n"
            "Próximos passos: 'lfs-compile-tools all' para as 15 ferramentas temporárias, depois Binutils Pass 2 e GCC Pass 2."
        ),
        "encouraging",
    ),
    "3": (
        _provision_act3,
        10,
        "Mestre da Toolchain Cruzada",
        (
            "[TELEPORTE SANDBOX: ATO 3 - CAPÍTULO 7 (PREPARAÇÃO)]\n"
            "Ato 2 concluído! Você retornou como 'root' no sistema hospedeiro com $LFS=/mnt/lfs.\n"
            "Próximos passos: 'chown --from lfs -R root:root $LFS/{usr,var,etc,tools}', criar $LFS/{dev,proc,sys,run} e montar os sistemas virtuais!"
        ),
        "encouraging",
    ),
    "chroot": (
        _provision_chroot,
        12,
        "Mestre da Toolchain Cruzada",
        (
            "[TELEPORTE SANDBOX: ATO 3 - DENTRO DO CHROOT]\n"
            "Sistemas virtuais montados e transição concluída para '(lfs chroot) root:/# '.\n"
            "Próximos passos: Criar árvore FHS ('mkdir -pv /{boot,home,mnt,opt,srv}'), 'install -dv -m 0750 /root', "
            "'ln -sfv /proc/self/mounts /etc/mtab', 'lfs-compile-chroot all' e limpar /tools."
        ),
        "encouraging",
    ),
    "4": (
        _provision_act4,
        15,
        "Pioneiro do Chroot",
        (
            "[TELEPORTE SANDBOX: ATO 4 - CAPÍTULO 8]\n"
            "Ato 3 concluído e /tools removido! Você está dentro do chroot pronto para os 81 pacotes do sistema definitivo.\n"
            "Próximos passos: 'lfs-compile-system tier1', 'make check', 'localedef -i pt_BR -f UTF-8 pt_BR.UTF-8', depois Tiers 2, 3, 4 e 'lfs-strip'."
        ),
        "encouraging",
    ),
    "5": (
        _provision_act5,
        20,
        "Arquiteto do Sistema",
        (
            "[TELEPORTE SANDBOX: ATO 5 - CAPÍTULO 9]\n"
            "Ato 4 concluído! Todos os 81 pacotes compilados, Glibc testada, Shadow e Udev configurados e debug stripped.\n"
            "Próximos passos: 'lfs-install-bootscripts', 'lfs-config-network hera-lfs' e 'lfs-config-system'."
        ),
        "encouraging",
    ),
    "ch10": (
        _provision_ch10,
        21,
        "Arquiteto do Sistema",
        (
            "[TELEPORTE SANDBOX: ATO 5 - CAPÍTULO 10 (KERNEL & GRUB)]\n"
            "Capítulo 9 concluído (Bootscripts, rede e SysVinit ativos)!\n"
            "Próximos passos: Criar '/etc/fstab', rodar 'make menuconfig', 'lfs-compile-kernel', 'make modules_install', "
            "copiar bzImage para '/boot/vmlinuz-7.1.8-lfs-13.1', 'grub-install /dev/sda' e 'grub-mkconfig -o /boot/grub/grub.cfg'."
        ),
        "encouraging",
    ),
    "ready": (
        _provision_ready,
        24,
        "Forjador do Kernel",
        (
            "[TELEPORTE SANDBOX: ATO 5 100% CONCLUÍDO]\n"
            "Kernel Linux 7.1.8 forjado e instalado em /boot, GRUB 2.14 gravado em /dev/sda e /boot/grub/grub.cfg configurado!\n"
            "Use 'lfs-check-config' para auditar o sistema pronto para o boot."
        ),
        "triumph",
    ),
}


def provision_target(engine: GameEngine, target_key: str) -> Tuple[bool, str]:
    """Resets engine state and deterministically provisions the requested Act/Chapter target."""
    target = resolve_target(target_key)
    if not target:
        return False, (
            f"[red]lfs-jump: alvo '{target_key}' inválido.[/red]\n"
            f"[yellow]Use 'lfs-jump' sem argumentos para listar os alvos disponíveis.[/yellow]"
        )

    # Cleanly reset core subsystems
    from .engine import Telemetry
    engine.fs = VirtualFS()
    engine.char = HackerCharacter()
    engine.story_engine = StoryEngine()
    engine.anomaly_manager = AnomalyManager()
    engine.telemetry = Telemetry()
    engine.command_history = []
    if hasattr(engine, "parser") and engine.parser is not None:
        engine.parser.dir_stack.clear()
    engine.test_mode = True

    prov_fn, quest_idx, title_override, dlg_text, mood = _TARGET_SPECS[target.key]

    if target.key == "prologue":
        # Keep StoryEngine's fresh initial prologue state
        return True, (
            f"[bold green]⚡ Teleporte Sandbox concluído:[/bold green] {target.label} ({target.chapter})\n"
            f"[dim]Prompt atual: {engine.get_prompt()}[/dim]"
        )

    # Mark prologue done for all targets >= 1
    engine.story_engine.flags["prologue_done"] = True

    if prov_fn is not None:
        prov_fn(engine)

    # Mark prior quests completed and grant XP before setting milestone title
    _complete_quests_up_to(engine.story_engine, engine.char, quest_idx)

    if title_override:
        engine.char.title = title_override
        if title_override not in engine.char.unlocked_titles:
            engine.char.unlocked_titles.append(title_override)

    _set_teleport_dialogue(engine.story_engine, dlg_text, mood=mood)

    quest = engine.story_engine.current_quest
    quest_status = "CONCLUÍDA" if quest.completed else quest.title
    return True, (
        f"[bold green]⚡ Teleporte Sandbox concluído:[/bold green] [bold cyan]{target.label}[/bold cyan] ({target.chapter})\n"
        f"[dim]Missão ativa: {quest_status} | Usuário: {engine.fs.current_user} | Chroot: {engine.fs.in_chroot} | Prompt: {engine.get_prompt()}[/dim]"
    )
