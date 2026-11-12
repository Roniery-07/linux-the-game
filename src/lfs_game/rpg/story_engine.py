"""Cyberpunk Story and Quest Engine for Act 1 (LFS 13.1)."""

from __future__ import annotations
from dataclasses import dataclass, field
import posixpath
from typing import Any, Dict, List, Optional
from ..core.virtual_fs import VirtualFS
from .character import HackerCharacter


@dataclass
class DialogueMessage:
    """A broadcast transmission or AI dialogue."""
    speaker: str
    text: str
    mood: str = "normal"  # normal, sarcastic, alert, triumph, glitch
    choices: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "mood": self.mood,
            "choices": self.choices,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DialogueMessage:
        return cls(**data)


@dataclass
class Quest:
    """A quest or chapter milestone."""
    id: str
    chapter: int
    title: str
    description: str
    objectives: List[str]
    hints: List[str]
    completed: bool = False
    xp_reward: int = 150

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "title": self.title,
            "description": self.description,
            "objectives": list(self.objectives),
            "hints": list(self.hints),
            "completed": self.completed,
            "xp_reward": self.xp_reward,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Quest:
        return cls(**data)


class StoryEngine:
    """Manages the cyberpunk narrative, quest graph, and K.E.R.N.E.L. dialogues."""

    def __init__(self):
        self.quests: List[Quest] = self._build_quests()
        self.current_quest_index: int = 0
        self.dialogue_history: List[DialogueMessage] = []
        self.current_dialogue: Optional[DialogueMessage] = None
        self.flags: Dict[str, bool] = {
            "prologue_done": False,
            "sources_downloaded": False,
            "md5_checked": False,
            "act1_celebrated": False,
            "sanity_check_passed": False,
            "temp_tools_compiled": False,
            "act2_celebrated": False,
            "chroot_tools_compiled": False,
            "chroot_cleaned": False,
            "act3_celebrated": False,
            "tier1_compiled": False,
            "tier2_compiled": False,
            "tier3_compiled": False,
            "tier4_compiled": False,
            "act4_celebrated": False,
            "system_configured": False,
            "kernel_forged": False,
            "act5_celebrated": False,
        }
        self._init_prologue()

    def _build_quests(self) -> List[Quest]:
        return [
            Quest(
                id="Q0_PROLOGUE",
                chapter=1,
                title="Despertar na Estação Hera",
                description="Os reatores da Estação Hera estão em colapso. Estabeleça comunicação com a IA K.E.R.N.E.L. e analise o terminal.",
                objectives=[
                    "Responder à transmissão da IA ou inspecionar o status com 'hint' ou 'status'",
                ],
                hints=[
                    "Digite 'hint' para orientações imediatas ou 'status' para inspecionar a telemetria.",
                    "Use 'lfs-book 1' para ler as diretrizes do Capítulo 1.",
                ],
                xp_reward=50,
            ),
            Quest(
                id="Q1_PARTITION_AND_MOUNT",
                chapter=2,
                title="Ato 1 - Cap. 2: Preparando o Hospedeiro",
                description="Configure a variável $LFS, prepare as partições do disco /dev/sda, formate /dev/sda3 com ext4, configure o swap em /dev/sda2 e monte $LFS.",
                objectives=[
                    "Definir a variável de ambiente: export LFS=/mnt/lfs",
                    "Formatar /dev/sda3 em ext4: mkfs.ext4 /dev/sda3",
                    "Formatar e ativar o swap: mkswap /dev/sda2 && swapon /dev/sda2",
                    "Criar ponto de montagem: mkdir -pv $LFS",
                    "Montar /dev/sda3 em $LFS: mount -v -t ext4 /dev/sda3 $LFS",
                ],
                hints=[
                    "Primeiro execute: export LFS=/mnt/lfs",
                    "Inspecione as partições existentes com: fdisk /dev/sda",
                    "Formate a partição de dados: mkfs.ext4 /dev/sda3",
                    "Ative o swap: mkswap /dev/sda2 && swapon /dev/sda2",
                    "Crie o diretório com: mkdir -pv $LFS e monte com: mount -v -t ext4 /dev/sda3 $LFS",
                ],
                xp_reward=200,
            ),
            Quest(
                id="Q2_PACKAGES_AND_PATCHES",
                chapter=3,
                title="Ato 1 - Cap. 3: Pacotes e Remendos",
                description="Crie o diretório sagrado $LFS/sources, ajuste as permissões pegajosas com chmod a+wt, adquira os tarballs de fontes e valide as somas com md5sum -c md5sums.",
                objectives=[
                    "Criar diretório de fontes: mkdir -v $LFS/sources",
                    "Ajustar permissões: chmod -v a+wt $LFS/sources",
                    "Adquirir pacotes (use 'lfs-get-sources' ou espere a varredura da IA)",
                    "Validar integridade dos arquivos: md5sum -c md5sums (ou dentro de $LFS/sources)",
                ],
                hints=[
                    "Crie o diretório de fontes: mkdir -v $LFS/sources",
                    "Defina o sticky bit com: chmod -v a+wt $LFS/sources",
                    "Use o comando de recuperação da estação: lfs-get-sources",
                    "Mude para o diretório com: cd $LFS/sources e rode: md5sum -c md5sums",
                ],
                xp_reward=250,
            ),
            Quest(
                id="Q3_FINAL_PREPARATIONS",
                chapter=4,
                title="Ato 1 - Cap. 4: Preparações Finais",
                description="Crie o diretório de ferramentas temporárias $LFS/tools, crie o grupo e usuário isolado 'lfs', e conceda a ele a propriedade do ambiente.",
                objectives=[
                    "Criar o diretório temporário: mkdir -pv $LFS/tools",
                    "Criar o grupo: groupadd lfs",
                    "Criar o usuário: useradd -s /bin/bash -g lfs -m -k /dev/null lfs",
                    "Transferir posse para lfs: chown -v lfs $LFS/{usr{,/*},lib,var,etc,bin,sbin,tools,sources}",
                ],
                hints=[
                    "Crie a pasta tools: mkdir -pv $LFS/tools",
                    "Crie o grupo e usuário com: groupadd lfs e useradd -s /bin/bash -g lfs -m -k /dev/null lfs",
                    "Transfira a propriedade das ferramentas e fontes com: chown -v lfs $LFS/tools e chown -v lfs $LFS/sources",
                ],
                xp_reward=300,
            ),
            Quest(
                id="Q4_STERILE_ENVIRONMENT",
                chapter=4,
                title="Ato 1 - Cap. 4: O Ambiente Estéril",
                description="Alterne para o usuário lfs com login limpo (su - lfs), configure .bash_profile e .bashrc para isolar $LFS_TGT e manter o $PATH puro.",
                objectives=[
                    "Mudar para o usuário lfs: su - lfs",
                    "Garantir $LFS_TGT=x86_64-lfs-linux-gnu",
                    "Garantir ambiente estéril ($LC_ALL=POSIX e $PATH isolado)",
                ],
                hints=[
                    "Alterne para a sessão limpa: su - lfs",
                    "Você pode definir o ambiente no terminal ou via ~/.bashrc:",
                    "export LFS=/mnt/lfs",
                    "export LC_ALL=POSIX",
                    "export LFS_TGT=x86_64-lfs-linux-gnu",
                    "export PATH=/usr/bin:/bin",
                ],
                xp_reward=400,
            ),
            Quest(
                id="Q5_CROSS_TOOLCHAIN_CORE",
                chapter=5,
                title="Ato 2 - Cap. 5: O Núcleo da Cross-Toolchain",
                description="Compile o Binutils (Passagem 1) e o GCC (Passagem 1) com destino a $LFS/tools. Forje o compilador cruzado isolado $LFS_TGT-gcc.",
                objectives=[
                    "Compilar e instalar Binutils Passagem 1 com destino a $LFS/tools",
                    "Compilar e instalar GCC Passagem 1 com suporte C/C++ em $LFS/tools",
                    "Verificar presença do compilador cruzado $LFS/tools/bin/$LFS_TGT-gcc",
                ],
                hints=[
                    "Para o Binutils: ../configure --prefix=$LFS/tools --with-sysroot=$LFS --target=$LFS_TGT --disable-nls && make && make install",
                    "Para o GCC: configure com --target=$LFS_TGT --prefix=$LFS/tools --with-sysroot=$LFS ... e rode make && make install",
                    "Verifique o checklist de ferramentas com 'lfs-status-tools'.",
                ],
                xp_reward=450,
            ),
            Quest(
                id="Q6_LINUX_HEADERS_AND_GLIBC",
                chapter=5,
                title="Ato 2 - Cap. 5: Cabeçalhos da API Linux & Glibc",
                description="Instale os cabeçalhos da API do Linux 6.14.7 em $LFS/usr, compile a biblioteca C (Glibc 2.44) e realize o Teste de Sanidade com $LFS_TGT-gcc e readelf.",
                objectives=[
                    "Instalar cabeçalhos de API do Linux: make headers && cp -rv usr/include $LFS/usr",
                    "Compilar e instalar Glibc 2.44 em $LFS",
                    "Executar o Teste de Sanidade: echo 'int main(){}' | $LFS_TGT-gcc -xc - && readelf -l a.out | grep ld-linux",
                ],
                hints=[
                    "Execute make headers no código do kernel e copie com: cp -rv usr/include $LFS/usr",
                    "Para a Glibc: configure com --prefix=/usr --host=$LFS_TGT libc_cv_slibdir=/usr/lib e instale com: make DESTDIR=$LFS install",
                    "Valide o compilador cruzado: echo 'int main(){}' | $LFS_TGT-gcc -xc - e verifique com readelf -l a.out | grep ld-linux",
                ],
                xp_reward=500,
            ),
            Quest(
                id="Q7_LIBSTDCXX",
                chapter=5,
                title="Ato 2 - Cap. 5: Libstdc++ da Passagem 1",
                description="Compile e instale a biblioteca padrão C++ (Libstdc++-v3) em $LFS/usr para habilitar suporte à compilação de ferramentas em C++.",
                objectives=[
                    "Configurar ../libstdc++-v3/configure --host=$LFS_TGT --prefix=/usr",
                    "Compilar e instalar com: make DESTDIR=$LFS install",
                ],
                hints=[
                    "Configure o subdiretório libstdc++-v3 com --host=$LFS_TGT e --prefix=/usr",
                    "Instale com: make DESTDIR=$LFS install",
                    "Consulte 'lfs-book 5' para os detalhes da Libstdc++.",
                ],
                xp_reward=350,
            ),
            Quest(
                id="Q8_TEMP_TOOLS",
                chapter=6,
                title="Ato 2 - Cap. 6: Forjando as Ferramentas Temporárias",
                description="Compile o conjunto de utilitários temporários do Capítulo 6 (M4, Ncurses, Bash, Coreutils, etc.) para isolar completamente o ambiente de compilação.",
                objectives=[
                    "Compilar e instalar pelo menos 10 ferramentas temporárias em $LFS/usr/bin",
                    "Utilize compilação individual ou em lote via 'lfs-compile-tools all'",
                ],
                hints=[
                    "Use o comando de automação da estação: lfs-compile-tools all",
                    "Ou compile ferramentas específicas: lfs-compile-tools m4, lfs-compile-tools bash, etc.",
                    "Acompanhe o status com 'lfs-status-tools'.",
                ],
                xp_reward=600,
            ),
            Quest(
                id="Q9_PASS2_AND_CLIMAX",
                chapter=6,
                title="Ato 2 - Cap. 6: A Segunda Passagem e a Libertação da Toolchain",
                description="A Boss Fight do Ato 2! Compile Binutils Passagem 2 e GCC Passagem 2. Neutralize anomalias de compilação e conquiste uma toolchain totalmente autossuficiente!",
                objectives=[
                    "Compilar e instalar Binutils Passagem 2 com vinculação nativa",
                    "Compilar e instalar GCC Passagem 2 com suporte completo a C++",
                    "Resolver as anomalias térmicas e de linker que ameaçam o reator",
                ],
                hints=[
                    "Configure e compile o Binutils Passagem 2 com make && make DESTDIR=$LFS install",
                    "Encare a Boss Fight do GCC Passagem 2: make && make DESTDIR=$LFS install",
                    "Se o alarme térmico soar, use as ações corretivas recomendadas pela IA!",
                ],
                xp_reward=800,
            ),
            Quest(
                id="Q10_CHROOT_PREPARATION",
                chapter=7,
                title="Ato 3 - Cap. 7: Preparação e Montagem do Kernel Virtual",
                description="Alterne a propriedade da árvore $LFS para root:root (chown --from lfs -R root:root), crie os pontos de montagem e monte os sistemas de arquivos virtuais do núcleo (dev, proc, sys, run).",
                objectives=[
                    "Mudar propriedade para root: chown --from lfs -R root:root $LFS/{usr,var,etc,tools}",
                    "Criar pastas virtuais: mkdir -pv $LFS/{dev,proc,sys,run}",
                    "Montar /dev vinculado: mount -v --bind /dev $LFS/dev",
                    "Montar /dev/pts: mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts",
                    "Montar /proc, /sys e /run: mount -vt proc proc $LFS/proc && mount -vt sysfs sysfs $LFS/sys && mount -vt tmpfs tmpfs $LFS/run",
                ],
                hints=[
                    "Lembre-se de retornar ou operar como superusuário root!",
                    "Mude a posse com: chown --from lfs -R root:root $LFS/{usr,var,etc,tools}",
                    "Crie as pastas com: mkdir -pv $LFS/{dev,proc,sys,run}",
                    "Monte os sistemas virtuais: mount -v --bind /dev $LFS/dev, mount -vt proc proc $LFS/proc, mount -vt sysfs sysfs $LFS/sys e mount -vt tmpfs tmpfs $LFS/run",
                ],
                xp_reward=500,
            ),
            Quest(
                id="Q11_ENTERING_CHROOT",
                chapter=7,
                title="Ato 3 - Cap. 7: O Ritual do Chroot",
                description="Execute o comando sagrado 'chroot \"$LFS\" /usr/bin/env -i ... /bin/bash --login' para cortar o cordão com o hospedeiro e adentrar o ambiente isolado.",
                objectives=[
                    "Entrar no ambiente chroot em $LFS",
                    "Confirmar a transição de prompt para '(lfs chroot) root:/# '",
                ],
                hints=[
                    "Execute: chroot \"$LFS\" /usr/bin/env -i HOME=/root TERM=\"$TERM\" PS1='(lfs chroot) \\u:\\w\\$ ' PATH=/usr/bin:/usr/sbin /bin/bash --login",
                    "Ou de forma direta: chroot $LFS",
                ],
                xp_reward=600,
            ),
            Quest(
                id="Q12_CHROOT_BASE_DIRECTORIES",
                chapter=7,
                title="Ato 3 - Cap. 7: A Fundação da Árvore de Diretórios",
                description="Dentro do chroot, construa a estrutura completa de diretórios padrão (FHS) e configure arquivos vitais como /etc/mtab, /etc/passwd e /etc/group.",
                objectives=[
                    "Criar diretórios padrão: mkdir -pv /{boot,home,mnt,opt,srv} e subpastas em /etc, /lib, /usr e /var",
                    "Configurar /root e /tmp com install: install -dv -m 0750 /root && install -dv -m 1777 /tmp /var/tmp",
                    "Criar link do mtab: ln -sfv /proc/self/mounts /etc/mtab",
                    "Garantir existência de /etc/passwd e /etc/group",
                ],
                hints=[
                    "Consulte 'lfs-book 7' para ver a lista de diretórios recomendados pelo FHS.",
                    "Crie os diretórios seguros com: install -dv -m 0750 /root e install -dv -m 1777 /tmp /var/tmp",
                    "Crie o link simbólico: ln -sfv /proc/self/mounts /etc/mtab",
                ],
                xp_reward=550,
            ),
            Quest(
                id="Q13_CHROOT_TEMP_TOOLS",
                chapter=7,
                title="Ato 3 - Cap. 7: Forjando as Ferramentas Finais do Chroot",
                description="Compile os pacotes temporários finais dentro do chroot: Gettext, Bison, Perl, Python 3, Texinfo e Util-linux.",
                objectives=[
                    "Compilar as 6 ferramentas temporárias do chroot (Gettext, Bison, Perl, Python, Texinfo, Util-linux)",
                    "Utilize compilação individual ou em lote via 'lfs-compile-chroot all'",
                ],
                hints=[
                    "Use 'lfs-compile-chroot all' para acelerar a compilação de todas as ferramentas do chroot.",
                    "Ou compile individualmente com: lfs-compile-chroot gettext, lfs-compile-chroot bison, etc.",
                    "Inspecione a telemetria com 'lfs-status-chroot'.",
                ],
                xp_reward=700,
            ),
            Quest(
                id="Q14_CLEANUP_AND_STRIP",
                chapter=7,
                title="Ato 3 - Cap. 7: Purificação e Conquista do Chroot",
                description="Realize a limpeza dos arquivos de documentação redundantes, elimine os arquivos .la e descarte a pasta /tools temporária, conquistando a independência do sistema!",
                objectives=[
                    "Limpar documentação e caches desnecessários: rm -rf /usr/share/{info,man,doc}/*",
                    "Remover arquivos .la da libtool: find /usr/{lib,libexec} -name *.la -delete",
                    "Remover o diretório temporário /tools: rm -rf /tools",
                    "Desbloquear o título: 'Pioneiro do Chroot'",
                ],
                hints=[
                    "Execute: rm -rf /usr/share/{info,man,doc}/*",
                    "Remova os arquivos .la com: find /usr/lib /usr/libexec -name '*.la' -delete",
                    "Exclua as ferramentas temporárias com: rm -rf /tools",
                ],
                xp_reward=850,
            ),
            Quest(
                id="Q15_SYSTEM_TIER1_GLIBC",
                chapter=8,
                title="Ato 4 - Cap. 8 (Tier 1): A Fundação da Glibc e Compressão",
                description=(
                    "Compile os 19 pacotes do Tier 1 dentro do chroot (Man-pages, Iana-Etc, Glibc definitiva, "
                    "bibliotecas de compressão, Tcl, Expect, DejaGNU, Ninja e Pkgconf), execute a suíte de testes "
                    "da Glibc ('make check') e configure os locales UTF-8 ('localedef')."
                ),
                objectives=[
                    "Compilar todos os pacotes do Tier 1: lfs-compile-system tier1",
                    "Validar a Glibc definitiva: make check",
                    "Configurar localidades UTF-8: localedef -i pt_BR -f UTF-8 pt_BR.UTF-8",
                ],
                hints=[
                    "Use 'lfs-compile-system tier1' para compilar os 19 pacotes fundamentais do Tier 1.",
                    "Execute 'make check' para validar a suíte de testes da Glibc 2.44.",
                    "Compile as localidades com: localedef -i pt_BR -f UTF-8 pt_BR.UTF-8",
                    "Acompanhe o progresso do Capítulo 8 com 'lfs-status-system'.",
                ],
                xp_reward=800,
            ),
            Quest(
                id="Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW",
                chapter=8,
                title="Ato 4 - Cap. 8 (Tier 2): Toolchain Nativa, Shadow e Shell",
                description=(
                    "Compile os 19 pacotes do Tier 2 (Binutils 2.47, GMP, MPFR, MPC, Shadow, GCC 16.2.0 definitivo, "
                    "Ncurses, Bash 5.3, etc.), ative as senhas criptografadas (/etc/shadow), defina a senha de root "
                    "e reinicie o shell com o novo Bash."
                ),
                objectives=[
                    "Compilar todos os pacotes do Tier 2: lfs-compile-system tier2",
                    "Ativar senhas Shadow e definir senha de root: pwconv && passwd root",
                    "Reiniciar o shell nativo definitivo: exec /usr/bin/bash --login",
                ],
                hints=[
                    "Compile o Tier 2 com: lfs-compile-system tier2",
                    "Recomendado validar o GCC definitivo com: make -k check",
                    "Configure Shadow e senha de root: pwconv && grpconv && passwd root",
                    "Reinicie o shell para usar o novo Bash 5.3: exec /usr/bin/bash --login",
                ],
                xp_reward=950,
            ),
            Quest(
                id="Q17_SYSTEM_TIER3_CRYPTO_PYTHON",
                chapter=8,
                title="Ato 4 - Cap. 8 (Tier 3): Criptografia, Python, Meson e Kmod",
                description=(
                    "Compile os 20 pacotes do Tier 3: OpenSSL 4.0, Perl definitivo, Autoconf, Automake, Libelf, "
                    "SQLite, Python 3.14 definitivo, ferramentas Wheel/Setuptools, Meson e Kmod."
                ),
                objectives=[
                    "Compilar todos os 20 pacotes do Tier 3: lfs-compile-system tier3",
                ],
                hints=[
                    "Execute: lfs-compile-system tier3",
                    "Inspecione os pacotes do Tier 3 com: lfs-status-system tier3",
                ],
                xp_reward=850,
            ),
            Quest(
                id="Q18_SYSTEM_TIER4_UTILS_INIT",
                chapter=8,
                title="Ato 4 - Cap. 8 (Tier 4): Utilitários Core, GRUB, Udev e SysVinit",
                description=(
                    "Compile os 23 pacotes finais do Tier 4 (Coreutils, GRUB 2.14, IPRoute2, Vim, Udev, Man-DB, "
                    "Procps-ng, Util-linux, E2fsprogs, Sysklogd e SysVinit) e atualize o banco de dispositivos hardware."
                ),
                objectives=[
                    "Compilar todos os 23 pacotes do Tier 4: lfs-compile-system tier4",
                    "Compilar o banco binário de hardware do Udev: udev-hwdb update",
                ],
                hints=[
                    "Execute: lfs-compile-system tier4",
                    "Atualize o banco de dispositivos com: udev-hwdb update",
                ],
                xp_reward=1000,
            ),
            Quest(
                id="Q19_STRIPPING_AND_ACT4_CLIMAX",
                chapter=8,
                title="Ato 4 - Cap. 8 (Clímax): Stripping e Alma do Sistema",
                description=(
                    "Realize o stripping dos símbolos de depuração DWARF (Seção 8.85) para purificar e enxugar "
                    "o sistema operacional recém-compilado, conquistando o título de 'Arquiteto do Sistema'!"
                ),
                objectives=[
                    "Remover símbolos de depuração e limpar caches temporários: lfs-strip (ou strip)",
                    "Desbloquear o título: 'Arquiteto do Sistema'",
                ],
                hints=[
                    "Execute 'lfs-strip' (ou 'strip --strip-debug') dentro do chroot para finalizar o Capítulo 8.",
                ],
                xp_reward=1200,
            ),
            Quest(
                id="Q20_SYSTEM_CONFIG_NETWORK",
                chapter=9,
                title="Ato 5 - Cap. 9: Bootscripts, Rede e Configuração do Sistema",
                description=(
                    "Instale os scripts LFS-Bootscripts 20250827 (/etc/rc.d/*), configure a rede estática "
                    "(/etc/hostname, /etc/hosts, /etc/resolv.conf, /etc/sysconfig/ifconfig.eth0) e os arquivos "
                    "vitais do SysVinit e shell (/etc/inittab, /etc/profile, /etc/inputrc, /etc/shells)."
                ),
                objectives=[
                    "Instalar LFS-Bootscripts: lfs-install-bootscripts (ou make install)",
                    "Configurar rede: lfs-config-network (ou escrever /etc/hostname, /etc/hosts, /etc/resolv.conf, /etc/sysconfig/ifconfig.eth0)",
                    "Configurar SysVinit e shell: lfs-config-system (ou escrever /etc/inittab, /etc/profile, /etc/inputrc, /etc/shells)",
                ],
                hints=[
                    "Consulte 'lfs-book 9' para as instruções completas do Capítulo 9.",
                    "Execute 'lfs-install-bootscripts', 'lfs-config-network hera-lfs' e 'lfs-config-system' (ou crie cada arquivo manualmente com cat << \"EOF\").",
                    "Audite a configuração a qualquer momento com 'lfs-check-config'.",
                ],
                xp_reward=900,
            ),
            Quest(
                id="Q21_FSTAB_AND_KERNEL_CONFIG",
                chapter=10,
                title="Ato 5 - Cap. 10: Tabela /etc/fstab e Configuração do Kernel 7.1.8",
                description=(
                    "Crie o arquivo /etc/fstab montando /dev/sda3 em '/' (ext4) e ativando /dev/sda2 como swap, "
                    "depois configure o Kernel Linux 7.1.8 com suporte built-in [y] via 'make menuconfig' ou 'lfs-kernel-config'."
                ),
                objectives=[
                    "Criar /etc/fstab válido com /dev/sda3 em '/' e /dev/sda2 swap",
                    "Configurar o Kernel Linux 7.1.8: make menuconfig (ou make defconfig / lfs-kernel-config apply)",
                    "Garantir flags built-in [y] vitais: CONFIG_EXT4_FS=y, CONFIG_DEVTMPFS=y, CONFIG_BINFMT_ELF=y",
                ],
                hints=[
                    "Crie /etc/fstab usando heredoc: cat > /etc/fstab << \"EOF\" ... EOF (veja 'lfs-book 10').",
                    "Entre em /sources/linux-7.1.8 e execute 'make mrproper && make menuconfig'.",
                    "Inspecione ou ajuste subsistemas com 'lfs-kernel-config' e aplique com 'lfs-kernel-config apply'.",
                ],
                xp_reward=1000,
            ),
            Quest(
                id="Q22_KERNEL_FORGE",
                chapter=10,
                title="Ato 5 - Cap. 10: A Forja do Kernel Linux 7.1.8",
                description=(
                    "Compile o núcleo Linux 7.1.8 ('make -j4' ou 'lfs-compile-kernel'), instale os módulos "
                    "('make modules_install') e copie a imagem gerada para /boot/vmlinuz-7.1.8-lfs-13.1."
                ),
                objectives=[
                    "Compilar o Kernel Linux 7.1.8: make -j4 (ou lfs-compile-kernel)",
                    "Instalar módulos do kernel: make modules_install",
                    "Instalar imagem em /boot: cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1",
                ],
                hints=[
                    "Dentro de /sources/linux-7.1.8 execute: make -j4",
                    "Instale os módulos com: make modules_install",
                    "Copie a imagem e os mapas: cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1",
                ],
                xp_reward=1200,
            ),
            Quest(
                id="Q23_GRUB_BOOTLOADER",
                chapter=10,
                title="Ato 5 - Cap. 10 (Clímax): O Bootloader GRUB e Prontidão de Boot",
                description=(
                    "Instale o carregador de inicialização GRUB no setor de boot de /dev/sda ('grub-install /dev/sda') "
                    "e crie o arquivo /boot/grub/grub.cfg apontando para vmlinuz-7.1.8-lfs-13.1 e root=/dev/sda3."
                ),
                objectives=[
                    "Instalar o GRUB no MBR de /dev/sda: grub-install /dev/sda",
                    "Gerar /boot/grub/grub.cfg: grub-mkconfig -o /boot/grub/grub.cfg (ou lfs-config-grub / cat << \"EOF\")",
                    "Desbloquear o título: 'Forjador do Kernel'",
                ],
                hints=[
                    "Execute: grub-install /dev/sda",
                    "Gere o menu com: grub-mkconfig -o /boot/grub/grub.cfg (ou lfs-config-grub)",
                    "Verifique tudo com 'lfs-check-config'.",
                ],
                xp_reward=1500,
            ),
        ]

    def _init_prologue(self):
        msg = DialogueMessage(
            speaker="K.E.R.N.E.L.",
            text=(
                "ALERTA CRÍTICO: Pressão atmosférica na Estação Hera em 42%. "
                "O firmware central foi corrompido pela tempestade de radiação de Júpiter. "
                "Nossos antigos sistemas binários proprietários falharam miseravelmente. "
                "Você é o único operador consciente nos setores de manutenção. "
                "Se quiser respirar amanhã, precisamos construir um sistema Linux puro, do zero absoluto, a partir do código-fonte. "
                "Não cometa erros. Eu odeio morrer com incompetência humana."
            ),
            mood="alert",
            choices=[
                {"key": "1", "label": "Quem é você e o que aconteceu aqui?", "reply": "Sou a K.E.R.N.E.L. - Kernel Emulation and Radiation Neutralization Executive Layer. E você acabou de sobreviver à maior pane de subsistemas do século."},
                {"key": "2", "label": "Por que precisamos compilar tudo do zero?", "reply": "Porque os binários pré-compilados do hospedeiro contêm links simbólicos envenenados pela radiação. Apenas um ambiente estéril construído com compilação cruzada nos salvará."},
                {"key": "3", "label": "Estou pronto. O que fazemos primeiro?", "reply": "Excelente. Menos conversa fiada e mais particionamento. Abra o manual com 'lfs-book 2' ou siga meus comandos de hospedeiro."},
            ]
        )
        self.current_dialogue = msg
        self.dialogue_history.append(msg)

    @property
    def current_quest(self) -> Quest:
        if self.current_quest_index < len(self.quests):
            return self.quests[self.current_quest_index]
        return self.quests[-1]

    def handle_choice(self, key: str) -> Optional[DialogueMessage]:
        """Processes player's dialogue option choice."""
        if not self.current_dialogue or not self.current_dialogue.choices:
            return None

        choice_found = None
        for c in self.current_dialogue.choices:
            if c.get("key") == key.strip():
                choice_found = c
                break

        if not choice_found:
            return None

        reply_msg = DialogueMessage(
            speaker="K.E.R.N.E.L.",
            text=choice_found.get("reply", "..."),
            mood="normal"
        )
        self.dialogue_history.append(reply_msg)
        self.current_dialogue = reply_msg

        if not self.flags.get("prologue_done"):
            self.flags["prologue_done"] = True

        return reply_msg

    def check_progress(self, fs: VirtualFS, char: HackerCharacter) -> List[DialogueMessage]:
        """Evaluates quests conditions against VirtualFS and updates state."""
        messages: List[DialogueMessage] = []
        while self.current_quest_index < len(self.quests):
            prev_index = self.current_quest_index
            quest = self.quests[self.current_quest_index]

            # Q0: Prologue
            if quest.id == "Q0_PROLOGUE":
                if self.flags.get("prologue_done"):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text="Conexão neural sincronizada. Iniciando protocolo de reconstrução: ATO 1, CAPÍTULO 2.",
                        mood="encouraging"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q1: Partition & Mount
            elif quest.id == "Q1_PARTITION_AND_MOUNT":
                lfs_var = fs.env.get("LFS", "")
                sda3 = fs.partitions.get("/dev/sda3")
                sda2 = fs.partitions.get("/dev/sda2")
                lfs_mount_dev = fs.mounts.get("/mnt/lfs") or (fs.mounts.get(lfs_var) if lfs_var else None)

                is_sda3_formatted = sda3 and sda3.filesystem == "ext4"
                is_swap_active = sda2 and sda2.is_swap_active
                is_mounted = lfs_mount_dev == "/dev/sda3"

                if lfs_var == "/mnt/lfs" and is_sda3_formatted and is_swap_active and is_mounted:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Excelente trabalho de base, Operador! O disco /dev/sda3 está formatado em ext4 e montado em $LFS. "
                            "O espaço de swap está ativo nos registradores de memória da estação. "
                            "Avançando para o CAPÍTULO 3: Aquisição de Pacotes e Remendos sagrados!"
                        ),
                        mood="triumph",
                        choices=[
                            {"key": "1", "label": "Onde estão os arquivos de código-fonte?", "reply": "Eles estão isolados no banco de dados de sobrevivência. Crie $LFS/sources e execute 'lfs-get-sources' para recuperá-los."},
                        ]
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q2: Packages & Patches
            elif quest.id == "Q2_PACKAGES_AND_PATCHES":
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                sources_dir = f"{lfs_var}/sources"
                has_sources_dir = fs.is_dir(sources_dir)
                has_md5_file = fs.is_file(f"{sources_dir}/md5sums")

                if has_sources_dir and has_md5_file and self.flags.get("md5_checked"):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Somas de verificação MD5 100% íntegras! Todos os 98 tarballs e remendos oficiais do LFS 13.1 estão prontos. "
                            "Sem nenhum byte contaminado. Agora precisamos blindar a montagem: CAPÍTULO 4 - Preparações Finais."
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q3: Final Preparations (Tools & User lfs)
            elif quest.id == "Q3_FINAL_PREPARATIONS":
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                tools_dir = f"{lfs_var}/tools"
                has_tools = fs.is_dir(tools_dir)
                has_group_lfs = "lfs" in fs.groups
                has_user_lfs = "lfs" in fs.users

                tools_node = fs._resolve_node(tools_dir)
                tools_owned = tools_node and tools_node.owner == "lfs"

                if has_tools and has_group_lfs and has_user_lfs and tools_owned:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Usuário 'lfs' registrado nos circuitos de controle. "
                            "Diretório $LFS/tools alocado e sob posse do usuário desprivilegiado. "
                            "Última etapa do Ato 1: Logar com 'su - lfs' e garantir o Ambiente Estéril!"
                        ),
                        mood="encouraging"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q4: Clean Environment
            elif quest.id == "Q4_STERILE_ENVIRONMENT":
                is_lfs_user = fs.current_user == "lfs"
                tgt = fs.env.get("LFS_TGT", "")
                lc = fs.env.get("LC_ALL", "")
                path_val = fs.env.get("PATH", "")

                # Sterile env requires LFS_TGT=x86_64-lfs-linux-gnu and LC_ALL=POSIX or clean PATH
                if is_lfs_user and tgt == "x86_64-lfs-linux-gnu" and (lc == "POSIX" or "tools" in path_val or "/usr/bin:/bin" in path_val):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["act1_celebrated"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ ATO 1 CONCLUÍDO COM DISTINÇÃO! ★\n"
                            "Ambiente Estéril ativado. $LFS_TGT = x86_64-lfs-linux-gnu.\n"
                            "A contaminação do hospedeiro foi anulada. "
                            "Os subsistemas de oxigênio estabilizaram em nível de emergência seguro.\n"
                            "Você acaba de dominar as fundações do Linux From Scratch 13.1!\n"
                            "Aguarde o Ato 2 para a forja da Cross-Toolchain (Binutils e GCC Pass 1)."
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q5: Cross-Toolchain Core (Binutils 1 & GCC 1)
            elif quest.id == "Q5_CROSS_TOOLCHAIN_CORE":
                tgt = fs.env.get("LFS_TGT", "x86_64-lfs-linux-gnu")
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                has_binutils = fs.is_package_compiled("binutils-pass1")
                has_gcc = fs.is_package_compiled("gcc-pass1")
                has_gcc_bin = (
                    fs.exists(f"{lfs_var}/tools/bin/{tgt}-gcc")
                    or fs.exists(f"{lfs_var}/tools/bin/x86_64-lfs-linux-gnu-gcc")
                    or "x86_64-lfs-linux-gnu-gcc" in fs.installed_tools
                    or "$LFS_TGT-gcc" in fs.installed_tools
                )

                if has_binutils and has_gcc and has_gcc_bin:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "O compilador cruzado $LFS_TGT-gcc está forjado e funcional em $LFS/tools/bin! "
                            "Demos o primeiro passo vital para nos libertarmos do binário corrompido da estação. "
                            "Próximo objetivo: Instalar os cabeçalhos do núcleo Linux 6.14.7 e compilar a sagrada Glibc 2.44!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q6: Linux Headers, Glibc & Sanity Check
            elif quest.id == "Q6_LINUX_HEADERS_AND_GLIBC":
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                has_headers = fs.is_package_compiled("linux-headers") or fs.exists(f"{lfs_var}/usr/include")
                has_glibc = (
                    fs.is_package_compiled("glibc")
                    or fs.exists(f"{lfs_var}/lib64/ld-linux-x86-64.so.2")
                    or fs.exists(f"{lfs_var}/lib/ld-linux-x86-64.so.2")
                    or fs.exists(f"{lfs_var}/usr/lib/libc.so.6")
                )
                has_sanity = (
                    self.flags.get("sanity_check_passed")
                    or fs.exists("a.out")
                    or fs.exists(posixpath.join(fs.cwd, "a.out"))
                )

                if has_headers and has_glibc and has_sanity:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Teste de Sanidade validado com louvor! O interpretador dinâmico responde perfeitamente por /lib/ld-linux-x86-64.so.2. "
                            "A Glibc 2.44 está ancorada no sistema hospedeiro gerando chamadas puras. "
                            "Agora compile a biblioteca Libstdc++-v3 para encerrar o Capítulo 5!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q7: Libstdc++
            elif quest.id == "Q7_LIBSTDCXX":
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                has_libstdcpp = (
                    fs.is_package_compiled("libstdc++")
                    or fs.exists(f"{lfs_var}/usr/lib/libstdc++.so")
                    or fs.exists(f"{lfs_var}/usr/lib/libstdc++.so.6")
                )

                if has_libstdcpp:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ CAPÍTULO 5 FINALIZADO! A Cross-Toolchain está completa. ★\n"
                            "Avançando para o CAPÍTULO 6: Ferramentas Temporárias Cruzadas.\n"
                            "Precisamos compilar os utilitários essenciais (M4, Ncurses, Bash, Coreutils, etc.) em $LFS/usr/bin.\n"
                            "Você pode compilá-los passo a passo ou usar 'lfs-compile-tools all' para acelerar a forja!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q8: Temporary Tools
            elif quest.id == "Q8_TEMP_TOOLS":
                ch6_tools = {"m4", "ncurses", "bash", "coreutils", "diffutils", "file", "findutils", "gawk", "grep", "gzip", "make", "patch", "sed", "tar", "xz"}
                compiled_count = len(ch6_tools.intersection(fs.compiled_packages))

                if compiled_count >= 10 or self.flags.get("temp_tools_compiled"):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            f"Arsenal temporário estabelecido ({compiled_count}/15 ferramentas prontas)! "
                            "O sistema LFS ganha comandos fundamentais em $LFS/usr/bin. "
                            "Agora o desafio supremo: Binutils Passagem 2 e GCC Passagem 2. "
                            "A Boss Fight do Ato 2 começou! Monitore os alertas de temperatura e anomalias de vinculação."
                        ),
                        mood="alert"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q9: Pass 2 & Climax
            elif quest.id == "Q9_PASS2_AND_CLIMAX":
                has_binutils2 = fs.is_package_compiled("binutils-pass2")
                has_gcc2 = fs.is_package_compiled("gcc-pass2")

                if has_binutils2 and has_gcc2:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["act2_celebrated"] = True
                    char.title = "Mestre da Toolchain Cruzada"
                    if "Mestre da Toolchain Cruzada" not in char.unlocked_titles:
                        char.unlocked_titles.append("Mestre da Toolchain Cruzada")
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ ATO 2 CONCLUÍDO COM SUCESSO ABSOLUTO! ★\n"
                            "A Cross-Toolchain e as Ferramentas Temporárias do LFS 13.1 estão consolidadas!\n"
                            "O compilador cruzado e a segunda passagem cortaram todos os laços com o hospedeiro contaminado.\n"
                            "Suporte de vida da Estação Hera reenergizado: oxigênio expandido para nível seguro (85%)!\n"
                            "Você foi condecorado com o título: 'Mestre da Toolchain Cruzada'.\n"
                            "Próxima fronteira: Ato 3 - O Isolamento Chroot e a Construção do Sistema Definitivo."
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q10: Chroot Preparation & Virtual Filesystems
            elif quest.id == "Q10_CHROOT_PREPARATION":
                lfs_var = fs.env.get("LFS", "/mnt/lfs")
                tools_node = fs._resolve_node(f"{lfs_var}/tools") or fs._resolve_host_node("/mnt/lfs/tools")
                tools_owned_by_root = tools_node and tools_node.owner == "root"

                mounts = fs.mounts
                has_dev = any(m.endswith("/dev") or m == "/dev" for m in mounts)
                has_proc = any(m.endswith("/proc") or m == "/proc" for m in mounts)
                has_sys = any(m.endswith("/sys") or m == "/sys" for m in mounts)
                has_run = any(m.endswith("/run") or m == "/run" for m in mounts)

                if tools_owned_by_root and has_dev and has_proc and has_sys and has_run:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Sistemas virtuais do núcleo devidamente montados e vinculados! "
                            "A posse da árvore $LFS foi transferida para root:root. "
                            "Estamos prontos para o momento solene: O Ritual do Chroot (Capítulo 7.4). "
                            "Corte o cordão com o anfitrião executando 'chroot \"$LFS\" /usr/bin/env -i ... /bin/bash --login'!"
                        ),
                        mood="triumph",
                        choices=[
                            {"key": "1", "label": "Por que o chroot é chamado de ritual?", "reply": "Porque a partir deste instante, o universo do terminal passa a ter seu centro de gravidade em $LFS. O sistema anfitrião deixa de existir para nós."},
                        ]
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q11: Entering Chroot
            elif quest.id == "Q11_ENTERING_CHROOT":
                if fs.in_chroot and fs.current_user == "root":
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "TRANSLAÇÃO CONCLUÍDA! O prompt confirma: (lfs chroot) root:/# \n"
                            "Você está operando diretamente no coração puro do Linux From Scratch. "
                            "Nenhuma chamada de sistema tocará os discos corrompidos do hospedeiro. "
                            "Próxima missão: forjar a estrutura de diretórios padrão (FHS) e os arquivos essenciais!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q12: Chroot Base Directories & Essential Files
            elif quest.id == "Q12_CHROOT_BASE_DIRECTORIES":
                has_boot = fs.exists("/boot") or fs.exists("/mnt/lfs/boot")
                has_etc = fs.exists("/etc") or fs.exists("/mnt/lfs/etc")
                has_tmp = fs.exists("/tmp") or fs.exists("/mnt/lfs/tmp")
                has_var = fs.exists("/var") or fs.exists("/mnt/lfs/var")
                has_mtab = fs.exists("/etc/mtab") or fs.exists("/mnt/lfs/etc/mtab")
                has_passwd = fs.exists("/etc/passwd") or fs.exists("/mnt/lfs/etc/passwd")

                if has_boot and has_etc and has_tmp and has_var and (has_mtab or has_passwd):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "A espinha dorsal do sistema de arquivos está erguida! "
                            "Pastas padrão do FHS alocadas, /root com permissão restrita 0750 e /tmp com sticky bit 1777. "
                            "Arquivo /etc/mtab vinculado. "
                            "Agora construa o esquadrão final de ferramentas do chroot: Gettext, Bison, Perl, Python 3, Texinfo e Util-linux!"
                        ),
                        mood="encouraging"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q13: Chroot Additional Tools
            elif quest.id == "Q13_CHROOT_TEMP_TOOLS":
                ch7_pkgs = {"gettext", "bison", "perl", "python", "texinfo", "util-linux"}
                compiled_count = len(ch7_pkgs.intersection(fs.compiled_packages))

                if compiled_count >= 5 or self.flags.get("chroot_tools_compiled"):
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            f"Ferramentas do chroot totalmente compiladas e testadas ({compiled_count}/6 prontas)! "
                            "Perl, Python 3, Bison e Util-linux estão nos registros de /usr/bin. "
                            "Último passo do Ato 3: Limpeza da documentação e remoção definitiva da pasta temporária /tools!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q14: Cleanup, Strip & Climax
            elif quest.id == "Q14_CLEANUP_AND_STRIP":
                tools_removed = (
                    not fs.exists("/tools")
                    and not fs.exists("/mnt/lfs/tools")
                )
                is_cleaned = tools_removed or self.flags.get("chroot_cleaned")

                if is_cleaned:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["act3_celebrated"] = True
                    char.title = "Pioneiro do Chroot"
                    if "Pioneiro do Chroot" not in char.unlocked_titles:
                        char.unlocked_titles.append("Pioneiro do Chroot")
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ ATO 3 CONCLUÍDO COM DISTINÇÃO SUPREMA! ★\n"
                            "O Ritual do Chroot foi consumado e o diretório /tools foi descartado!\n"
                            "A Estação Hera opera agora sob um ambiente de compilação 100% autocontido.\n"
                            "Os subsistemas vitais estabilizaram em 95% de oxigênio.\n"
                            "Você desbloqueou a comenda máxima: 'Pioneiro do Chroot'!\n"
                            "Prepare-se para o Ato 4: A Construção do Sistema LFS Definitivo (Capítulo 8)!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q15: Act 4 - Tier 1 + Glibc make check + Locales
            elif quest.id == "Q15_SYSTEM_TIER1_GLIBC":
                from ..data.lfs_manifest import get_system_packages
                tier1_pkgs = get_system_packages(tier=1)
                tier1_done = all(fs.is_package_compiled(p.id) for p in tier1_pkgs)
                glibc_checked = "glibc" in fs.system_checks_passed

                if tier1_done and fs.locales_configured and glibc_checked:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["tier1_compiled"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Tier 1 consolidado! A Glibc 2.44 definitiva passou 100% na suíte 'make check' "
                            "e as localidades UTF-8 estão compiladas em /usr/lib/locale/locale-archive.\n"
                            "Próxima etapa (Tier 2): Compile Binutils, GCC 16.2.0 definitivo, Shadow e Bash 5.3! "
                            "Não esqueça de ativar /etc/shadow ('pwconv'), definir a senha de root ('passwd root') "
                            "e reiniciar o shell ('exec /usr/bin/bash --login')."
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q16: Act 4 - Tier 2 + Shadow + Root Password + Exec Bash
            elif quest.id == "Q16_SYSTEM_TIER2_TOOLCHAIN_SHADOW":
                from ..data.lfs_manifest import get_system_packages
                tier2_pkgs = get_system_packages(tier=2)
                tier2_done = all(fs.is_package_compiled(p.id) for p in tier2_pkgs)

                if tier2_done and fs.shadow_configured and fs.root_password_set and fs.bash_restarted:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["tier2_compiled"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Toolchain nativa definitiva e camada de segurança Shadow operacionais! "
                            "GCC 16.2.0 e Binutils 2.47 agora são nativos do novo sistema, /etc/shadow protege as credenciais "
                            "e o novo Bash 5.3 assumiu o processo do terminal.\n"
                            "Avançando para o Tier 3: OpenSSL 4.0, Perl, Python 3.14, Meson e Kmod!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q17: Act 4 - Tier 3 (OpenSSL, Python, Meson, Kmod)
            elif quest.id == "Q17_SYSTEM_TIER3_CRYPTO_PYTHON":
                from ..data.lfs_manifest import get_system_packages
                tier3_pkgs = get_system_packages(tier=3)
                tier3_done = all(fs.is_package_compiled(p.id) for p in tier3_pkgs)

                if tier3_done:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["tier3_compiled"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Tier 3 finalizado! Criptografia OpenSSL 4.0, Python 3.14 definitivo, Meson e Kmod "
                            "estão integrados ao sistema.\n"
                            "Partindo para o Tier 4: Coreutils, GRUB 2.14, Vim, Udev e SysVinit! "
                            "Após compilar o Tier 4, atualize o banco de dispositivos com 'udev-hwdb update'."
                        ),
                        mood="encouraging"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q18: Act 4 - Tier 4 (Coreutils, GRUB, Vim, Udev, SysVinit) + udev-hwdb update
            elif quest.id == "Q18_SYSTEM_TIER4_UTILS_INIT":
                from ..data.lfs_manifest import get_system_packages
                tier4_pkgs = get_system_packages(tier=4)
                tier4_done = all(fs.is_package_compiled(p.id) for p in tier4_pkgs)

                if tier4_done and fs.udev_updated:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["tier4_compiled"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Todos os 81 pacotes do Capítulo 8 foram forjados e o banco /etc/udev/hwdb.bin foi compilado! "
                            "Falta apenas o toque final da Seção 8.85: remova os símbolos de depuração com 'lfs-strip' (ou 'strip') "
                            "para selar o Ato 4!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q19: Act 4 Climax - Stripping & Title Unlock
            elif quest.id == "Q19_STRIPPING_AND_ACT4_CLIMAX":
                if fs.debug_stripped:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["act4_celebrated"] = True
                    char.title = "Arquiteto do Sistema"
                    if "Arquiteto do Sistema" not in char.unlocked_titles:
                        char.unlocked_titles.append("Arquiteto do Sistema")
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ ATO 4 CONCLUÍDO COM MAESTRIA ABSOLUTA! ★\n"
                            "A Edificação da Alma do Sistema está completa: todos os 81 pacotes definitivos do Capítulo 8 "
                            "foram compilados, testados, protegidos com Shadow e enxugados com Stripping!\n"
                            "Os sistemas principais da Estação Hera operam com 100% de estabilidade.\n"
                            "Você conquistou o título supremo: 'Arquiteto do Sistema'!\n"
                            "O sistema está pronto para o Ato 5 (Capítulos 9–11): Configuração de Rede, Compilação do Kernel Linux e Boot!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q20: Act 5 - Chapter 9 Bootscripts, Network & SysVinit/Shell Config
            elif quest.id == "Q20_SYSTEM_CONFIG_NETWORK":
                if fs.in_chroot:
                    fs.sync_act5_state()
                net_ready = fs.network_configured or fs.has_valid_network_config()
                sys_ready = fs.sysconfig_configured or fs.has_valid_sysconfig()

                if fs.bootscripts_installed and net_ready and sys_ready:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["system_configured"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ CAPÍTULO 9 CONCLUÍDO! ★\n"
                            "Os LFS-Bootscripts, a pilha de rede e a tabela /etc/inittab estão ancorados no sistema.\n"
                            "Avançando para o CAPÍTULO 10: Crie o arquivo /etc/fstab (montando /dev/sda3 em '/' e /dev/sda2 como swap) "
                            "e configure o Kernel Linux 7.1.8 com 'make menuconfig' ou 'lfs-kernel-config'!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q21: Act 5 - /etc/fstab & Linux 7.1.8 Kernel Configuration
            elif quest.id == "Q21_FSTAB_AND_KERNEL_CONFIG":
                if fs.in_chroot:
                    fs.sync_act5_state()
                fstab_ready = fs.fstab_configured or fs.has_valid_fstab()
                kconfig_valid = (
                    fs.kernel_configured
                    and fs.kernel_config.get("CONFIG_EXT4_FS") == "y"
                    and fs.kernel_config.get("CONFIG_DEVTMPFS") == "y"
                    and fs.kernel_config.get("CONFIG_BINFMT_ELF") == "y"
                )

                if fstab_ready and kconfig_valid:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "Tabela /etc/fstab validada e .config do Kernel Linux 7.1.8 selado com drivers críticos built-in [y]!\n"
                            "Chegou a hora da verdade: entre em /sources/linux-7.1.8 e forje o núcleo com 'make -j4', "
                            "'make modules_install' e copie arch/x86/boot/bzImage para /boot/vmlinuz-7.1.8-lfs-13.1!"
                        ),
                        mood="encouraging"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q22: Act 5 - Kernel Compilation & Installation to /boot
            elif quest.id == "Q22_KERNEL_FORGE":
                if fs.in_chroot:
                    fs.sync_act5_state()
                kernel_img_ready = fs.kernel_installed or fs.has_valid_kernel_installed()
                modules_ready = fs.is_package_compiled("linux-modules") or fs.exists("/lib/modules/7.1.8/modules.dep")

                if fs.kernel_compiled and modules_ready and kernel_img_ready:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["kernel_forged"] = True
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "O CORAÇÃO DO SISTEMA BATE! /boot/vmlinuz-7.1.8-lfs-13.1 e seus módulos estão instalados!\n"
                            "Última etapa do Ato 5: Grave o carregador de inicialização com 'grub-install /dev/sda' "
                            "e crie /boot/grub/grub.cfg apontando para vmlinuz-7.1.8-lfs-13.1 e root=/dev/sda3!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            # Q23: Act 5 Climax - GRUB Bootloader & Readiness for Act 6
            elif quest.id == "Q23_GRUB_BOOTLOADER":
                if fs.in_chroot:
                    fs.sync_act5_state()
                grub_cfg_ready = fs.grub_cfg_created or fs.has_valid_grub_cfg()

                if fs.grub_mbr_installed and grub_cfg_ready:
                    quest.completed = True
                    char.add_xp(quest.xp_reward)
                    self.current_quest_index += 1
                    self.flags["act5_celebrated"] = True
                    char.title = "Forjador do Kernel"
                    if "Forjador do Kernel" not in char.unlocked_titles:
                        char.unlocked_titles.append("Forjador do Kernel")
                    msg = DialogueMessage(
                        speaker="K.E.R.N.E.L.",
                        text=(
                            "★ ATO 5 CONCLUÍDO COM GLÓRIA SUPREMA! ★\n"
                            "O Kernel Linux 7.1.8 foi forjado, o sistema SysVinit configurado e o GRUB 2.14 gravado em /dev/sda!\n"
                            "A Estação Orbital Hera está 100% pronta para o Primeiro Boot independente!\n"
                            "Você foi consagrado com o título máximo: 'Forjador do Kernel'!\n"
                            "Prepare-se para o Ato 6: Desmontagem segura, 'reboot' e Primeiro Boot no Linux From Scratch 13.1!"
                        ),
                        mood="triumph"
                    )
                    self.dialogue_history.append(msg)
                    self.current_dialogue = msg
                    messages.append(msg)

            if self.current_quest_index == prev_index:
                break

        return messages

    def get_hint(self) -> str:
        """Returns contextual guidance based on active quest."""
        q = self.current_quest
        if q.hints:
            return f"[cyan]{q.title}[/cyan]\n" + "\n".join([f"• {h}" for h in q.hints])
        return "[yellow]Nenhuma dica disponível no momento. Prossiga com cuidado.[/yellow]"

    def to_dict(self) -> dict:
        return {
            "quests": [q.to_dict() for q in self.quests],
            "current_quest_index": self.current_quest_index,
            "dialogue_history": [d.to_dict() for d in self.dialogue_history],
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StoryEngine:
        engine = cls()
        default_quests = engine._build_quests()
        default_flags = dict(engine.flags)

        saved_quests = [Quest.from_dict(q) for q in data.get("quests", [])]
        if saved_quests:
            saved_map = {q.id: q for q in saved_quests}
            default_ids = {dq.id for dq in default_quests}
            ordered_quests = [saved_map.get(dq.id, dq) for dq in default_quests]
            for sq in saved_quests:
                if sq.id not in default_ids:
                    ordered_quests.append(sq)
            engine.quests = ordered_quests

        engine.current_quest_index = data.get("current_quest_index", 0)
        engine.dialogue_history = [DialogueMessage.from_dict(d) for d in data.get("dialogue_history", [])]
        engine.current_dialogue = engine.dialogue_history[-1] if engine.dialogue_history else None
        saved_flags = data.get("flags", {})
        default_flags.update(saved_flags)
        engine.flags = default_flags
        return engine
