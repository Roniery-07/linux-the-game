"""Didactic Glossary of Linux From Scratch (LFS 13.1) commands and concepts.

Provides comprehensive educational explanations for commands, variables,
compiler flags, and architectural concepts used throughout the LFS build process.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional


@dataclass
class GlossaryEntry:
    """A didactic entry explaining a Linux/LFS command, variable, or concept."""
    term: str
    name: str
    category: str
    syntax: str
    what_it_does: str
    why_in_lfs: str
    danger_if_missed: str
    related_terms: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


# Categories in presentation order
CATEGORIES = [
    "Básico & Hospedeiro",
    "Discos & Montagens",
    "Pacotes & Verificação",
    "Variáveis LFS",
    "Toolchain & Compiladores",
    "Conceitos do Sistema & Chroot",
]


GLOSSARY_ENTRIES: List[GlossaryEntry] = [
    # -------------------------------------------------------------------------
    # Básico & Hospedeiro
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="export",
        name="export - Exportação de Variáveis de Ambiente",
        category="Básico & Hospedeiro",
        syntax="export VARIAVEL=VALOR",
        what_it_does=(
            "Marca uma variável do shell para ser exportada automaticamente para o ambiente "
            "de quaisquer processos-filhos (subshells, scripts de compilação, Makefiles) executados "
            "a partir da sessão atual."
        ),
        why_in_lfs=(
            "No LFS, variáveis críticas como $LFS e $LFS_TGT precisam ser lidas por inúmeros scripts "
            "e subshells gerados pelo 'make' e './configure'. Sem o 'export', a variável existiria apenas "
            "na memória do shell interativo e desapareceria assim que um subprocesso de build fosse invocado."
        ),
        danger_if_missed=(
            "Se você definir 'LFS=/mnt/lfs' sem 'export', qualquer subshell verá $LFS como vazio (''). "
            "Comandos como 'mkdir -pv $LFS/sources' tentarão criar '/sources' diretamente na raiz do seu "
            "sistema hospedeiro, ou pior: 'rm -rf $LFS/*' tentará apagar a raiz '/' do hospedeiro!"
        ),
        related_terms=["env", "echo", "$LFS", "$LFS_TGT", "PATH"],
        aliases=["exportar"],
    ),
    GlossaryEntry(
        term="env",
        name="env - Exibir ou Executar em Ambiente Modificado",
        category="Básico & Hospedeiro",
        syntax="env [OPÇÕES] [COMANDO]",
        what_it_does=(
            "Sem argumentos, lista todas as variáveis de ambiente ativas. Com a opção '-i' "
            "(ignore-environment), executa um comando iniciando com um ambiente 100% limpo, "
            "descartando todas as variáveis herdadas da sessão anterior."
        ),
        why_in_lfs=(
            "Utilizado na transição crucial para o usuário de compilação 'lfs' (via 'env -i'). Isso assegura "
            "que nenhuma variável tóxica do hospedeiro (como CFLAGS, CXXFLAGS ou caminhos de bibliotecas "
            "em /usr/local) contamine o processo de compilação das ferramentas temporárias."
        ),
        danger_if_missed=(
            "Se variáveis da distribuição hospedeira vazarem para a compilação do LFS, o compilador pode "
            "vincular bibliotecas locais do host nos novos binários, criando um sistema contaminado que "
            "falhará catastrófica e misteriosamente ao tentar inicializar de forma independente."
        ),
        related_terms=["export", "su", "PATH", "LC_ALL=POSIX"],
        aliases=["printenv"],
    ),
    GlossaryEntry(
        term="echo",
        name="echo - Impressão de Linhas de Texto e Variáveis",
        category="Básico & Hospedeiro",
        syntax="echo [OPÇÕES] [TEXTO / $VARIAVEL]",
        what_it_does=(
            "Escreve seus argumentos na saída padrão (stdout) seguidos por uma nova linha. "
            "Quando combinado com operadores de redirecionamento (> ou >>), permite escrever ou anexar "
            "conteúdo diretamente em arquivos sem necessidade de editores de texto."
        ),
        why_in_lfs=(
            "É o principal instrumento de verificação rápida das variáveis do LFS (ex: 'echo $LFS', 'echo $LFS_TGT'). "
            "Também é empregado na criação automatizada de arquivos de ambiente essenciais como ~/.bashrc "
            "e ~/.bash_profile para o usuário 'lfs'."
        ),
        danger_if_missed=(
            "Não verificar os valores de variáveis com 'echo' antes de iniciar horas de compilação "
            "costuma resultar em pacotes instalados em locais errados sem que o operador perceba o desvio."
        ),
        related_terms=["cat", "export", "$LFS"],
        aliases=[],
    ),
    GlossaryEntry(
        term="mkdir",
        name="mkdir - Criação de Diretórios",
        category="Básico & Hospedeiro",
        syntax="mkdir [OPÇÕES] DIRETÓRIO...",
        what_it_does=(
            "Cria diretórios no sistema de arquivos. O parâmetro '-p' (--parents) cria todos os diretórios "
            "ancestrais necessários que ainda não existam sem emitir erro, e '-v' (--verbose) imprime "
            "uma mensagem confirmando cada diretório criado."
        ),
        why_in_lfs=(
            "O Linux From Scratch é construído sobre a hierarquia padrão FHS (Filesystem Hierarchy Standard). "
            "Comandos como 'mkdir -pv $LFS/{bin,etc,lib,sbin,usr,var,tools,sources}' erguem o esqueleto "
            "completo do novo sistema operacional antes do início da compilação dos pacotes."
        ),
        danger_if_missed=(
            "Sem criar os diretórios de antemão, scripts de compilação e comandos 'make install' falharão "
            "imediatamente com o clássico erro 'No such file or directory' ao tentar descarregar bibliotecas."
        ),
        related_terms=["cd", "rm", "ls"],
        aliases=["mkdir -pv", "mkdir -p"],
    ),
    GlossaryEntry(
        term="cd",
        name="cd - Troca de Diretório de Trabalho (Change Directory)",
        category="Básico & Hospedeiro",
        syntax="cd [DIRETÓRIO]",
        what_it_does=(
            "Altera o diretório de trabalho atual do processo da shell para o caminho especificado. "
            "Se nenhum argumento for passado, move para o diretório pessoal (HOME) do usuário atual."
        ),
        why_in_lfs=(
            "A metodologia de compilação do LFS baseia-se em: descompactar o tarball em $LFS/sources, "
            "entrar na pasta ('cd pacote-versao'), criar um diretório isolado de build ('mkdir build && cd build') "
            "e disparar o './configure' ou '../configure'. Estar no diretório correto é mandatório."
        ),
        danger_if_missed=(
            "Executar um script de build dentro do diretório errado polui diretórios anteriores ou compila "
            "fontes de pacotes diferentes, gerando falhas de linking difíceis de depurar."
        ),
        related_terms=["pwd", "mkdir", "pushd", "popd"],
        aliases=[],
    ),
    GlossaryEntry(
        term="ls",
        name="ls - Listagem de Conteúdo de Diretórios",
        category="Básico & Hospedeiro",
        syntax="ls [OPÇÕES] [CAMINHO...]",
        what_it_does=(
            "Lista arquivos e diretórios. Com as opções '-la' (long format + all), exibe permissões, "
            "número de links, proprietário, grupo, tamanho em bytes, data de modificação e arquivos ocultos."
        ),
        why_in_lfs=(
            "Permite inspecionar a integridade de diretórios críticos, confirmar se arquivos foram "
            "descompactados, auditar se permissões e donos estão corretos e validar a existência de "
            "links simbólicos vitais (como /tools/lib64 -> lib)."
        ),
        danger_if_missed=(
            "Sem o 'ls', você opera às cegas, correndo o risco de compilar pastas incompletas ou não notar "
            "que um arquivo importante não foi gerado pelo processo de instalação."
        ),
        related_terms=["cd", "cat", "find"],
        aliases=["ls -la", "ls -l"],
    ),
    GlossaryEntry(
        term="cat",
        name="cat - Concatenação e Exibição de Arquivos",
        category="Básico & Hospedeiro",
        syntax="cat [OPÇÕES] [ARQUIVO...]",
        what_it_does=(
            "Lê arquivos em sequência e imprime seu conteúdo na saída padrão. Usado com '<< EOF' (Heredoc) "
            "para criar ou sobrescrever arquivos de texto inteiros diretamente a partir de scripts ou terminal."
        ),
        why_in_lfs=(
            "É o método canônico do livro LFS para gerar arquivos de inicialização (como ~/.bashrc, "
            "~/.bash_profile, /etc/passwd, /etc/fstab) de maneira automatizada, garantindo que o conteúdo "
            "seja idêntico ao exigido pelo padrão sem depender de editores como nano ou vim."
        ),
        danger_if_missed=(
            "Se aspas forem omitidas no cabeçalho do Heredoc ('cat > file << EOF' em vez de '<< \"EOF\"'), "
            "variáveis como $PATH ou $LFS serão expandidas no momento da gravação com valores do host, "
            "sabotando os arquivos de configuração do novo sistema."
        ),
        related_terms=["echo", "touch", "sed"],
        aliases=["heredoc"],
    ),
    GlossaryEntry(
        term="rm",
        name="rm - Remoção de Arquivos e Diretórios",
        category="Básico & Hospedeiro",
        syntax="rm [OPÇÕES] ALVO...",
        what_it_does=(
            "Remove arquivos ou diretórios permanentemente do sistema de arquivos. O modificador '-r' "
            "executa remoção recursiva de diretórios, e '-f' ignora confirmações e erros de arquivos inexistentes."
        ),
        why_in_lfs=(
            "Após compilar e instalar com sucesso cada pacote, o livro LFS orienta a remoção imediata da "
            "pasta de fontes extraída ('rm -rf $LFS/sources/pacote-*') para liberar espaço em disco, "
            "já que manter todos os fontes compilados esgotaria rapidamente dezenas de gigabytes."
        ),
        danger_if_missed=(
            "O comando 'rm -rf' é uma lâmina sem trava de segurança: executar 'rm -rf $LFS/*' quando $LFS "
            "estiver acidentalmente vazio resulta em 'rm -rf /*', destruindo toda a instalação do seu Linux hospedeiro!"
        ),
        related_terms=["mkdir", "touch", "$LFS"],
        aliases=["rm -rf", "remover"],
    ),
    GlossaryEntry(
        term="touch",
        name="touch - Atualização de Timestamps ou Criação de Arquivos Vazios",
        category="Básico & Hospedeiro",
        syntax="touch ARQUIVO...",
        what_it_does=(
            "Atualiza os registros de data e hora de último acesso e modificação de um arquivo. "
            "Caso o arquivo ainda não exista, cria um arquivo regular vazio."
        ),
        why_in_lfs=(
            "Makefiles do GNU Make decidem o que recompilar comparando a data dos códigos-fonte contra "
            "a data dos arquivos gerados. No LFS, 'touch' é usado para contornar problemas onde fontes descompactados "
            "possuem datas futuras ou passadas, evitando recompilações acidentais de documentação ou geradores ausentes."
        ),
        danger_if_missed=(
            "Arquivos com timestamps desregulados podem forçar o Makefile a invocar ferramentas obsoletas "
            "como automake, bison ou makeinfo que não existem no ambiente mínimo do LFS, quebrando o build."
        ),
        related_terms=["cat", "mkdir", "make"],
        aliases=[],
    ),
    GlossaryEntry(
        term="chown",
        name="chown - Alteração de Proprietário e Grupo (Change Owner)",
        category="Básico & Hospedeiro",
        syntax="chown [OPÇÕES] USUÁRIO[:GRUPO] CAMINHO...",
        what_it_does=(
            "Muda o proprietário (UID) e, opcionalmente, o grupo (GID) de arquivos e diretórios. "
            "O parâmetro '-R' aplica a alteração de forma recursiva a toda a árvore subordinada."
        ),
        why_in_lfs=(
            "No Capítulo 5, executamos 'chown -v -R lfs $LFS/tools $LFS/sources'. Isso concede ao usuário "
            "sem privilégios 'lfs' a posse dos diretórios de construção, permitindo que ele extraia tarballs "
            "e instale ferramentas temporárias sem precisar de acesso de superusuário (root)."
        ),
        danger_if_missed=(
            "Se as pastas continuarem pertencendo ao 'root', o usuário 'lfs' receberá erros imediatos de "
            "'Permission denied' ao tentar extrair pacotes ou rodar 'make install', bloqueando o progresso."
        ),
        related_terms=["chmod", "su", "useradd", "whoami"],
        aliases=["chown -v -R", "dono"],
    ),
    GlossaryEntry(
        term="chmod",
        name="chmod - Alteração de Permissões de Acesso (Change Mode)",
        category="Básico & Hospedeiro",
        syntax="chmod [OPÇÕES] MODO ARQUIVO...",
        what_it_does=(
            "Altera os bits de permissão de leitura (r), escrita (w) e execução (x) para dono, grupo "
            "e outros usuários, utilizando notação simbólica (ex: '+x', 'u+w') ou octal (ex: 755, 644)."
        ),
        why_in_lfs=(
            "Garante que scripts de compilação recém-criados possam ser executados (+x), que diretórios "
            "do sistema sejam legíveis por todos (755) e que arquivos de senhas (/etc/shadow) fiquem "
            "estritamente protegidos contra leitura não autorizada (600)."
        ),
        danger_if_missed=(
            "Esquecer de conceder permissão de execução a scripts do configure ou a binários temporários "
            "resulta em falhas de 'Permission denied'. Deixar permissões abertas em arquivos críticos "
            "cria brechas graves de segurança no sistema final."
        ),
        related_terms=["chown", "su"],
        aliases=["permissoes"],
    ),
    GlossaryEntry(
        term="su",
        name="su - Troca de Usuário (Substitute User / Switch User)",
        category="Básico & Hospedeiro",
        syntax="su [OPÇÕES] [USUÁRIO]",
        what_it_does=(
            "Permite assumir a identidade de outra conta de usuário durante a sessão atual. "
            "O hífen '-' (equivalente a '-l' ou '--login') inicializa a nova sessão como um shell de login completo, "
            "redefinindo todas as variáveis de ambiente de acordo com a conta de destino."
        ),
        why_in_lfs=(
            "A troca com 'su - lfs' é uma das operações de segurança mais vitais do LFS. O hífen é obrigatório "
            "porque limpa completamente o ambiente do root do host, garantindo que o usuário 'lfs' inicie "
            "apenas com as variáveis limpas e isoladas definidas em seu ~/.bash_profile e ~/.bashrc."
        ),
        danger_if_missed=(
            "Executar apenas 'su lfs' (sem o hífen '-') mantém o PATH, as variáveis e os aliases do root do host! "
            "Isso contamina o ambiente de compilação com bibliotecas do hospedeiro e invalida o isolamento da toolchain."
        ),
        related_terms=["whoami", "useradd", "env", "export"],
        aliases=["su - lfs", "su -"],
    ),
    GlossaryEntry(
        term="useradd",
        name="useradd - Criação de Novo Usuário no Sistema",
        category="Básico & Hospedeiro",
        syntax="useradd [OPÇÕES] NOME_DO_USUÁRIO",
        what_it_does=(
            "Cria uma nova conta de usuário no sistema, registrando-a nos arquivos /etc/passwd e /etc/shadow, "
            "e definindo seu grupo primário, diretório home e shell de login padrão."
        ),
        why_in_lfs=(
            "O comando 'useradd -s /bin/bash -k /dev/null -m lfs' cria o operador de compilação 'lfs'. "
            "A opção '-k /dev/null' impede que o sistema copie arquivos de template do /etc/skel do hospedeiro, "
            "assegurando uma home totalmente limpa para receber os scripts canônicos do LFS."
        ),
        danger_if_missed=(
            "Compilar pacotes como superusuário 'root' é extremamente perigoso: qualquer bug em um Makefile "
            "de terceiros que execute comandos destrutivos sobrescreverá ou apagará o sistema hospedeiro."
        ),
        related_terms=["groupadd", "su", "chown"],
        aliases=["criar-usuario"],
    ),
    GlossaryEntry(
        term="groupadd",
        name="groupadd - Criação de Novo Grupo de Usuários",
        category="Básico & Hospedeiro",
        syntax="groupadd [OPÇÕES] NOME_DO_GRUPO",
        what_it_does=(
            "Cria um novo grupo de segurança no sistema, alocando um identificador de grupo (GID) único "
            "no arquivo /etc/group."
        ),
        why_in_lfs=(
            "O comando 'groupadd lfs' cria o grupo homônimo que servirá como grupo primário para o usuário 'lfs' "
            "e definirá as permissões compartilhadas dos diretórios de fontes e ferramentas temporárias."
        ),
        danger_if_missed=(
            "Tentar criar o usuário 'useradd -g lfs ...' sem que o grupo 'lfs' exista previamente abortará "
            "com erro informando que o grupo especificado não foi encontrado."
        ),
        related_terms=["useradd", "chown"],
        aliases=["criar-grupo"],
    ),
    GlossaryEntry(
        term="whoami",
        name="whoami - Identificação do Usuário Efetivo Atual",
        category="Básico & Hospedeiro",
        syntax="whoami",
        what_it_does=(
            "Imprime na tela o nome do usuário correspondente ao UID efetivo da sessão atual do shell."
        ),
        why_in_lfs=(
            "Atua como confirmação de segurança contínua no LFS: antes de particionar discos ou entrar no chroot, "
            "você deve ser 'root'. Antes de compilar os pacotes dos Capítulos 5 e 6, você DEVE ser 'lfs'."
        ),
        danger_if_missed=(
            "Executar comandos pertencentes ao usuário 'lfs' como 'root' (ou o oposto) altera permissões "
            "de arquivos compilados e pode causar poluição irreversível do ambiente."
        ),
        related_terms=["su", "env"],
        aliases=["quem-sou-eu"],
    ),

    # -------------------------------------------------------------------------
    # Discos & Montagens
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="fdisk",
        name="fdisk - Utilitário de Particionamento de Discos MBR/GPT",
        category="Discos & Montagens",
        syntax="fdisk [OPÇÕES] DISPOSITIVO",
        what_it_does=(
            "Programa interativo em modo texto para criar, inspecionar, alterar e deletar partições em discos "
            "com tabelas de partição MBR (Master Boot Record) ou GPT (GUID Partition Table)."
        ),
        why_in_lfs=(
            "Usado no Capítulo 2 para estruturar o disco rígido virtual dedicado ao LFS, reservando as fatias "
            "necessárias: a partição de swap (ex: /dev/sda2) e a partição raiz do novo sistema (ex: /dev/sda3)."
        ),
        danger_if_missed=(
            "Sem particionar o disco, não há onde formatar o sistema de arquivos ou instalar o LFS. "
            "Além disso, apontar o fdisk para o disco errado pode apagar acidentalmente o sistema hospedeiro!"
        ),
        related_terms=["cfdisk", "mkfs.ext4", "mkswap", "mount"],
        aliases=["particionar"],
    ),
    GlossaryEntry(
        term="cfdisk",
        name="cfdisk - Particionador Interativo Baseado em Curses",
        category="Discos & Montagens",
        syntax="cfdisk DISPOSITIVO",
        what_it_does=(
            "Fornece uma interface gráfica amigável no próprio terminal para visualizar partições, "
            "alterar tipos de sistema de arquivos e redimensionar discos sem memorizar comandos de uma letra."
        ),
        why_in_lfs=(
            "É uma alternativa mais intuitiva ao fdisk no LFS para selecionar tipos de partição (Linux Filesystem, "
            "Linux Swap) e aplicar as modificações com segurança visual antes de salvar."
        ),
        danger_if_missed=(
            "Esquecer de selecionar a opção 'Write' antes de sair ('Quit') descarta todas as partições criadas, "
            "deixando o disco completamente vazio para as etapas seguintes."
        ),
        related_terms=["fdisk", "mkfs.ext4"],
        aliases=[],
    ),
    GlossaryEntry(
        term="mkfs.ext4",
        name="mkfs.ext4 - Formatação de Sistema de Arquivos EXT4",
        category="Discos & Montagens",
        syntax="mkfs.ext4 [OPÇÕES] DISPOSITIVO_PARTIÇÃO",
        what_it_does=(
            "Escreve as estruturas de metadados do sistema de arquivos EXT4 na partição especificada: superblocos, "
            "tabelas de inodes, grupos de blocos e o log de journaling para recuperação contra falhas."
        ),
        why_in_lfs=(
            "O Linux From Scratch exige um sistema de arquivos nativo POSIX com suporte a permissões estritas, "
            "links simbólicos, hardlinks e atributos estendidos para armazenar com integridade os binários do SO."
        ),
        danger_if_missed=(
            "Tentar montar uma partição que não foi formatada com mkfs.ext4 resultará no erro fatal "
            "'mount: wrong fs type, bad superblock, bad option, missing codepage'."
        ),
        related_terms=["mount", "fdisk", "mkswap"],
        aliases=["mkfs", "formatar", "ext4", "mkfs-ext4"],
    ),
    GlossaryEntry(
        term="mkswap",
        name="mkswap - Inicialização de Partição ou Arquivo de Swap",
        category="Discos & Montagens",
        syntax="mkswap [OPÇÕES] DISPOSITIVO_PARTIÇÃO",
        what_it_does=(
            "Grava a assinatura mágica e a tabela de paginação de memória virtual swap na partição designada, "
            "preparando-a para ser usada como extensão da memória RAM pelo kernel."
        ),
        why_in_lfs=(
            "A compilação de pacotes gigantescos (como GCC Pass 1/2 e Glibc) consome picos de vários gigabytes de RAM. "
            "Ter a partição de swap inicializada previne travamentos causados por esgotamento de memória."
        ),
        danger_if_missed=(
            "Se a máquina ficar sem memória durante a compilação do GCC e a swap não estiver configurada, o kernel "
            "invocará o OOM Killer (Out Of Memory), matando o processo do compilador com erros crípticos."
        ),
        related_terms=["swapon", "swapoff", "fdisk"],
        aliases=["criar-swap", "swap"],
    ),
    GlossaryEntry(
        term="swapon",
        name="swapon - Ativação de Áreas de Swap",
        category="Discos & Montagens",
        syntax="swapon [OPÇÕES] DISPOSITIVO_PARTIÇÃO",
        what_it_does=(
            "Informa ao kernel do Linux que a partição de swap especificada deve ser ativada e colocada "
            "em uso imediato para paginação de memória virtual."
        ),
        why_in_lfs=(
            "Deve ser executado no Capítulo 2 ('swapon -v /dev/sda2') logo após a formatação com mkswap, "
            "assegurando que o ambiente hospedeiro conte com reserva extra de memória durante todas as compilações."
        ),
        danger_if_missed=(
            "Formatar a partição com mkswap mas esquecer o 'swapon' deixa a swap inativa: o kernel não saberá "
            "que pode paginar memória no disco, deixando o sistema vulnerável a travamentos por falta de RAM."
        ),
        related_terms=["mkswap", "swapoff"],
        aliases=["ativar-swap"],
    ),
    GlossaryEntry(
        term="swapoff",
        name="swapoff - Desativação de Áreas de Swap",
        category="Discos & Montagens",
        syntax="swapoff [OPÇÕES] DISPOSITIVO_PARTIÇÃO",
        what_it_does=(
            "Descarrega as páginas de memória armazenadas no disco de volta para a RAM física e desativa "
            "o dispositivo de swap."
        ),
        why_in_lfs=(
            "Utilizado ao desmontar os sistemas de arquivos antes de reiniciar a máquina ou ao reorganizar "
            "as partições da estação de trabalho."
        ),
        danger_if_missed=(
            "Tentar reparticionar ou formatar uma partição de swap que ainda está ativa falhará com erro "
            "'Device or resource busy'."
        ),
        related_terms=["swapon", "mkswap"],
        aliases=["desativar-swap"],
    ),
    GlossaryEntry(
        term="mount",
        name="mount - Montagem de Sistemas de Arquivos",
        category="Discos & Montagens",
        syntax="mount [OPÇÕES] DISPOSITIVO PONTO_DE_MONTAGEM",
        what_it_does=(
            "Conecta o sistema de arquivos contido em uma partição ou dispositivo físico a um ponto específico "
            "(diretório) na árvore de arquivos hierárquica global do sistema operacional."
        ),
        why_in_lfs=(
            "É o elo fundamental do LFS: 'mount -v -t ext4 /dev/sda3 $LFS'. Tudo o que for gravado sob o diretório "
            "$LFS passará a ser escrito fisicamente na partição do novo sistema operacional, e não no hospedeiro."
        ),
        danger_if_missed=(
            "Se você esquecer de executar o 'mount' e começar a criar diretórios e compilar pacotes em $LFS, "
            "todos os dados serão gravados no disco rígido do sistema hospedeiro! Ao reiniciar a máquina, "
            "a partição do LFS estará vazia e todo o trabalho de compilação será perdido!"
        ),
        related_terms=["umount", "df", "mkfs.ext4", "$LFS"],
        aliases=["montar"],
    ),
    GlossaryEntry(
        term="umount",
        name="umount - Desmontagem de Sistemas de Arquivos",
        category="Discos & Montagens",
        syntax="umount [OPÇÕES] DISPOSITIVO_OU_PONTO_DE_MONTAGEM",
        what_it_does=(
            "Desconecta o sistema de arquivos montado, garantindo que todos os dados e metadados pendentes "
            "no cache de memória (dirty buffers) sejam sincronizados e gravados fisicamente no disco."
        ),
        why_in_lfs=(
            "Obrigatório antes de reiniciar a máquina para inicializar o novo sistema operacional, ou ao "
            "desmontar os sistemas de arquivos virtuais (/dev, /proc, /sys) após sair do chroot."
        ),
        danger_if_missed=(
            "Desligar ou reiniciar o computador com sistemas de arquivos montados sem o 'umount' pode "
            "corromper o journal do EXT4 e causar perda ou truncamento de binários recém-instalados."
        ),
        related_terms=["mount", "df"],
        aliases=["desmontar"],
    ),
    GlossaryEntry(
        term="df",
        name="df - Relatório de Espaço Livre em Disco (Disk Free)",
        category="Discos & Montagens",
        syntax="df [OPÇÕES] [CAMINHO...]",
        what_it_does=(
            "Exibe a quantidade de espaço em disco total, utilizado e disponível em todos os sistemas de arquivos "
            "atualmente montados. A opção '-h' formata os números em unidades legíveis (M, G)."
        ),
        why_in_lfs=(
            "Permite confirmar visualmente se a partição do LFS está de fato montada em $LFS e monitorar "
            "se há espaço suficiente disponível para suportar o processo de compilação de novos pacotes."
        ),
        danger_if_missed=(
            "Sem monitorar o espaço com 'df', o disco pode atingir 100% de capacidade durante uma compilação pesada, "
            "corrompendo arquivos instalados parcialmente e abortando o build com falhas enganosas."
        ),
        related_terms=["mount", "umount"],
        aliases=["df -h"],
    ),

    # -------------------------------------------------------------------------
    # Pacotes & Verificação
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="tar",
        name="tar - Manipulador de Arquivos Compactados (Tape Archive)",
        category="Pacotes & Verificação",
        syntax="tar [OPÇÕES] ARQUIVO_TAR",
        what_it_does=(
            "Agrupa múltiplos arquivos e árvores de diretórios em um único arquivo de arquivo (.tar) "
            "e interage com compressores (gzip, bzip2, xz). A combinação '-xf' descompacta e extrai o conteúdo."
        ),
        why_in_lfs=(
            "Todos os 30+ pacotes de código-fonte utilizados na construção do LFS são distribuídos como "
            "arquivos tarballs (.tar.xz ou .tar.gz). O protocolo canônico é: 1. Descompactar com 'tar -xf'; "
            "2. Entrar na pasta; 3. Compilar e instalar; 4. Remover a pasta de fontes extraída."
        ),
        danger_if_missed=(
            "Tentar descompactar fontes diretamente em cima de uma compilação anterior sem limpar a pasta "
            "mistura arquivos de versões distintas, gerando falhas inexplicáveis de compilação."
        ),
        related_terms=["md5sum", "patch"],
        aliases=["tar -xf", "tar -xvf", "tarball"],
    ),
    GlossaryEntry(
        term="md5sum",
        name="md5sum - Verificação Criptográfica de Integridade MD5",
        category="Pacotes & Verificação",
        syntax="md5sum [OPÇÕES] [ARQUIVOS...]",
        what_it_does=(
            "Calcula o hash criptográfico MD5 (Message Digest 5 de 128 bits) de arquivos. A opção '-c md5sums' "
            "lê um arquivo com hashes esperados e valida automaticamente cada arquivo listado."
        ),
        why_in_lfs=(
            "No Capítulo 3, após o download de todos os pacotes em $LFS/sources, rodamos 'md5sum -c md5sums'. "
            "Isso garante matematicamente que nenhum tarball foi corrompido durante a transmissão na rede "
            "e que nenhum arquivo foi adulterado por terceiros com código malicioso."
        ),
        danger_if_missed=(
            "Compilar a partir de um tarball corrompido resulta em falhas de sintaxe e erros misteriosos "
            "no compilador após horas de espera, forçando você a recomeçar do zero."
        ),
        related_terms=["tar", "sha256sum"],
        aliases=["md5", "md5sum -c"],
    ),
    GlossaryEntry(
        term="patch",
        name="patch - Aplicação de Modificações e Correções em Códigos-Fonte",
        category="Pacotes & Verificação",
        syntax="patch [OPÇÕES] < ARQUIVO_PATCH",
        what_it_does=(
            "Lê um arquivo de diferenças unificadas (diff) e aplica modificações cirúrgicas linha a linha "
            "diretamente nos arquivos de código-fonte originais de um programa."
        ),
        why_in_lfs=(
            "Muitos softwares clássicos (como Bash, Coreutils ou Glibc) precisam de pequenos ajustes mantidos "
            "pela comunidade LFS para compilar contra versões mais recentes do kernel ou compilador, "
            "ou para corrigir bugs críticos de compatibilidade identificados após o lançamento daquele pacote."
        ),
        danger_if_missed=(
            "Esquecer de aplicar um patch obrigatório documentado no livro LFS fará a compilação quebrar "
            "com erros de compilação insolúveis ou fará o programa final falhar silenciosamente em tempo de execução."
        ),
        related_terms=["tar", "cat", "sed"],
        aliases=["aplicar-patch"],
    ),

    # -------------------------------------------------------------------------
    # Variáveis LFS
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="$LFS",
        name="$LFS - A Variável do Ponto de Montagem do Novo Sistema",
        category="Variáveis LFS",
        syntax="export LFS=/mnt/lfs",
        what_it_does=(
            "Variável de ambiente que aponta para o diretório raiz sob o qual a partição do novo sistema "
            "operacional Linux From Scratch está montada."
        ),
        why_in_lfs=(
            "É o ponto de ancoragem de todo o livro. Ao utilizar '$LFS' em todos os comandos, os scripts e instruções "
            "tornam-se portáteis e independentes de qual pasta física você escolheu como ponto de montagem."
        ),
        danger_if_missed=(
            "Se $LFS não estiver definida, expressões como '$LFS/sources' viram '/sources'. Comandos de remoção "
            "como 'rm -rf $LFS/*' expandem para 'rm -rf /*', destruindo completamente a máquina do hospedeiro!"
        ),
        related_terms=["export", "mount", "$LFS_TGT", "PATH"],
        aliases=["LFS", "lfs_var", "/mnt/lfs", "mnt/lfs"],
    ),
    GlossaryEntry(
        term="$LFS_TGT",
        name="$LFS_TGT - A Tupla de Arquitetura de Compilação Cruzada",
        category="Variáveis LFS",
        syntax="export LFS_TGT=x86_64-lfs-linux-gnu",
        what_it_does=(
            "Define a tupla canônica de arquitetura (máquina-fornecedor-kernel-sistema operacional) "
            "que será utilizada para instruir a toolchain a produzir binários para a nova plataforma."
        ),
        why_in_lfs=(
            "O grande segredo do LFS: ao colocar '-lfs-' como fornecedor (vendor), o sistema de build do GNU "
            "reconhece que está construindo um cross-compiler (compilador cruzado). Isso força o GCC e o Binutils "
            "a NUNCA procurarem bibliotecas ou cabeçalhos nos diretórios padrão do sistema hospedeiro (/usr/include, /lib)."
        ),
        danger_if_missed=(
            "Se $LFS_TGT não for configurado ou se for idêntico à tupla nativa do host, o GCC assumirá "
            "uma compilação nativa comum e vinculará as bibliotecas da sua distribuição hospedeira, arruinando o isolamento."
        ),
        related_terms=["export", "$LFS_TGT-gcc", "--target", "--host"],
        aliases=["LFS_TGT", "lfs_tgt", "target-tuple", "x86_64-lfs-linux-gnu", "tgt"],
    ),
    GlossaryEntry(
        term="PATH",
        name="$PATH - A Ordem de Busca de Executáveis",
        category="Variáveis LFS",
        syntax="export PATH=$LFS/tools/bin:$PATH",
        what_it_does=(
            "Lista ordenada de diretórios (separados por dois-pontos ':') onde a shell procura executáveis "
            "quando você digita o nome de um comando sem fornecer o caminho absoluto."
        ),
        why_in_lfs=(
            "Ao colocar '$LFS/tools/bin' no INÍCIO do PATH, garantimos que assim que uma ferramenta temporária "
            "for compilada e instalada (como o novo gcc, sed ou bash), o shell a utilize prioritariamente, "
            "substituindo a ferramenta correspondente da distribuição hospedeira."
        ),
        danger_if_missed=(
            "Se /usr/bin ou /bin continuarem na frente de $LFS/tools/bin no PATH, o sistema continuará invocando "
            "os compiladores e utilitários do hospedeiro, ignorando todo o trabalho das ferramentas temporárias."
        ),
        related_terms=["export", "env", "$LFS"],
        aliases=["$PATH"],
    ),
    GlossaryEntry(
        term="LC_ALL=POSIX",
        name="LC_ALL=POSIX - Padronização Canônica de Localidade (Locale)",
        category="Variáveis LFS",
        syntax="export LC_ALL=POSIX",
        what_it_does=(
            "Força o ambiente a adotar a convenção de localidade padrão POSIX/C: codificação ASCII simples, "
            "ordenação estrita de bytes, sem caracteres acentuados e com mensagens de sistema em inglês puro."
        ),
        why_in_lfs=(
            "Muitos scripts de compilação utilizam ferramentas como sort, sed e grep com intervalos de caracteres "
            "(como [a-z]). Em locales modernos UTF-8 (como pt_BR ou en_US), a ordem alfabética inclui maiúsculas "
            "ou caracteres especiais, quebrando scripts de configuração durante a geração de Makefiles."
        ),
        danger_if_missed=(
            "Manter variáveis de locale UTF-8 ativas causa falhas silenciosas na compilação da Glibc e do GCC, "
            "onde arquivos de cabeçalho essenciais deixam de ser gerados devido a erros de ordenação léxica."
        ),
        related_terms=["export", "env"],
        aliases=["LC_ALL", "POSIX", "locale"],
    ),

    # -------------------------------------------------------------------------
    # Toolchain & Compiladores
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="./configure",
        name="./configure / ../configure - Script de Sondagem e Geração de Makefiles",
        category="Toolchain & Compiladores",
        syntax="../configure --prefix=/tools --host=$LFS_TGT [OPÇÕES...]",
        what_it_does=(
            "Script de shell autogerado pelo GNU Autotools que inspeciona o compilador, recursos do hardware "
            "e bibliotecas disponíveis no sistema, montando os arquivos Makefile customizados para o build."
        ),
        why_in_lfs=(
            "É o leme de cada pacote. Nele especificamos onde o programa será instalado (--prefix) e para qual "
            "arquitetura será compilado (--target, --host). No LFS, executamos '../configure' a partir de uma "
            "pasta 'build' separada para não poluir os arquivos de código-fonte originais."
        ),
        danger_if_missed=(
            "Esquecer de passar flags essenciais como '--with-sysroot=$LFS' ou '--prefix=/tools' fará o pacote "
            "ser configurado com valores padrão, instalando arquivos no hospedeiro ou vinculando bibliotecas locais."
        ),
        related_terms=["make", "--prefix", "--host", "--target", "--with-sysroot"],
        aliases=["configure", "../configure"],
    ),
    GlossaryEntry(
        term="--prefix",
        name="--prefix - Diretório Raiz de Instalação do Pacote",
        category="Toolchain & Compiladores",
        syntax="--prefix=/tools (ou --prefix=/usr)",
        what_it_does=(
            "Opção passada ao './configure' que define o diretório raiz sob o qual executáveis (bin/), "
            "bibliotecas (lib/) e documentações (share/) serão instalados pelo comando 'make install'."
        ),
        why_in_lfs=(
            "No Capítulo 5 e 6, passamos '--prefix=/tools' ou '--prefix=$LFS/tools' para isolar as ferramentas "
            "temporárias em seu próprio diretório. No Capítulo 8, quando o sistema definitivo for compilado, "
            "usamos '--prefix=/usr' para que os programas fiquem nos caminhos finais do Linux."
        ),
        danger_if_missed=(
            "O padrão da maioria dos pacotes GNU é '--prefix=/usr/local'. Se você omitir a flag, os programas "
            "serão instalados em /usr/local do sistema hospedeiro, falhando em compor o sistema LFS."
        ),
        related_terms=["./configure", "DESTDIR"],
        aliases=["prefix"],
    ),
    GlossaryEntry(
        term="--host",
        name="--host - A Plataforma Onde o Binário Executará",
        category="Toolchain & Compiladores",
        syntax="--host=$LFS_TGT",
        what_it_does=(
            "Especifica ao './configure' qual é a arquitetura da máquina onde os programas compilados "
            "irão rodar quando estiverem em execução."
        ),
        why_in_lfs=(
            "Ao compilar a Glibc e os pacotes da passagem 2 das ferramentas temporárias, passar '--host=$LFS_TGT' "
            "instrui o build system a utilizar o compilador cruzado recém-criado ($LFS_TGT-gcc) em vez do compilador do host."
        ),
        danger_if_missed=(
            "Se '--host' for omitido, o script configure assumirá uma compilação nativa comum, invocando o compilador "
            "da distribuição hospedeira e vinculando bibliotecas do host em vez da Glibc do LFS."
        ),
        related_terms=["--target", "$LFS_TGT", "./configure"],
        aliases=["host"],
    ),
    GlossaryEntry(
        term="--target",
        name="--target - A Plataforma Para a Qual o Compilador Gerará Código",
        category="Toolchain & Compiladores",
        syntax="--target=$LFS_TGT",
        what_it_does=(
            "Utilizado exclusivamente ao compilar compiladores e ferramentas de montagem (GCC, Binutils). "
            "Define qual arquitetura de hardware os binários gerados por aquele compilador terão como alvo."
        ),
        why_in_lfs=(
            "Na Passagem 1 do Binutils e GCC, passamos '--target=$LFS_TGT'. Isso cria um compilador cruzado que roda "
            "no processador hospedeiro, mas produz binários configurados especificamente para a arquitetura do LFS."
        ),
        danger_if_missed=(
            "O compilador construído gerará executáveis nativos comuns para o hospedeiro, impossibilitando "
            "a separação da toolchain temporária."
        ),
        related_terms=["--host", "$LFS_TGT", "$LFS_TGT-gcc"],
        aliases=["target"],
    ),
    GlossaryEntry(
        term="--with-sysroot",
        name="--with-sysroot - O Diretório Raiz de Bibliotecas e Cabeçalhos",
        category="Toolchain & Compiladores",
        syntax="--with-sysroot=$LFS",
        what_it_does=(
            "Informa ao compilador cruzado e ao linker onde fica o diretório raiz lógico para a busca de "
            "cabeçalhos de cabeçalho C (/usr/include) e bibliotecas dinâmicas (/lib, /usr/lib)."
        ),
        why_in_lfs=(
            "É a muralha de contenção mais importante do LFS: ela força o cross-compiler a buscar dependências "
            "EXCLUSIVAMENTE dentro de $LFS, impedindo fisicamente que qualquer biblioteca da distribuição "
            "hospedeira seja ligada nos novos binários."
        ),
        danger_if_missed=(
            "Sem '--with-sysroot', o GCC consultará as bibliotecas do hospedeiro em '/lib' e '/usr/lib'. "
            "O sistema gerado parecerá funcionar enquanto estiver no host, mas morrerá instantaneamente no boot autônomo."
        ),
        related_terms=["$LFS_TGT-gcc", "./configure", "$LFS"],
        aliases=["with-sysroot", "sysroot"],
    ),
    GlossaryEntry(
        term="--with-headers",
        name="--with-headers - Caminho dos Cabeçalhos da API do Kernel",
        category="Toolchain & Compiladores",
        syntax="--with-headers=$LFS/usr/include",
        what_it_does=(
            "Especifica para a biblioteca C (Glibc) a localização exata dos cabeçalhos sanitizados "
            "da API do Kernel Linux recém-instalados."
        ),
        why_in_lfs=(
            "A biblioteca C fornece a ponte entre os programas e as chamadas de sistema (syscalls) do kernel. "
            "Ela precisa ler os cabeçalhos do novo kernel para saber quais estruturas de dados e chamadas de sistema "
            "estão disponíveis para o novo sistema operacional."
        ),
        danger_if_missed=(
            "A Glibc tentará usar os cabeçalhos do kernel do sistema hospedeiro, o que causará inconsistências "
            "graves de chamadas de sistema caso os kernels possuam versões ou configurações diferentes."
        ),
        related_terms=["./configure", "--with-sysroot"],
        aliases=["with-headers", "headers"],
    ),
    GlossaryEntry(
        term="--disable-nls",
        name="--disable-nls - Desativação de Suporte a Idiomas Nativos (Native Language Support)",
        category="Toolchain & Compiladores",
        syntax="--disable-nls",
        what_it_does=(
            "Desativa o suporte à internacionalização (tradução de mensagens de erro para outros idiomas) "
            "nos utilitários compilados, mantendo apenas as mensagens originais em inglês."
        ),
        why_in_lfs=(
            "Nas ferramentas temporárias dos Capítulos 5 e 6, a prioridade máxima é simplicidade e velocidade "
            "de compilação. Desativar o NLS reduz o tamanho dos binários e elimina a dependência da biblioteca gettext."
        ),
        danger_if_missed=(
            "Aumenta drasticamente o tempo de compilação dos pacotes e pode exigir a presença de utilitários "
            "do hospedeiro como msgfmt, quebrando o isolamento mínimo da fase temporária."
        ),
        related_terms=["./configure"],
        aliases=["disable-nls", "nls"],
    ),
    GlossaryEntry(
        term="make",
        name="make - O Motor de Automação de Compilação",
        category="Toolchain & Compiladores",
        syntax="make [-jN]",
        what_it_does=(
            "Lê arquivos Makefile e determina quais partes de um programa complexo precisam ser recompiladas, "
            "emitindo os comandos apropriados para o compilador e linker. A flag '-j$(nproc)' paraleliza "
            "a compilação em múltiplos núcleos de CPU."
        ),
        why_in_lfs=(
            "É a força motriz do LFS: praticamente todos os pacotes de software são construídos pelo GNU Make. "
            "Ele orquestra a transformação de milhares de linhas de código em linguagem C/C++ em bibliotecas "
            "e binários executáveis."
        ),
        danger_if_missed=(
            "Executar 'make' sem antes ter rodado o './configure' com sucesso falhará imediatamente com "
            "'No targets specified and no makefile found'."
        ),
        related_terms=["./configure", "make install", "DESTDIR"],
        aliases=["compilar"],
    ),
    GlossaryEntry(
        term="make install",
        name="make install - Cópia e Instalação dos Arquivos Compilados",
        category="Toolchain & Compiladores",
        syntax="make install (ou make DESTDIR=$LFS install)",
        what_it_does=(
            "Alvo padrão do Makefile que copia os executáveis, bibliotecas dinâmicas (.so), cabeçalhos (.h) "
            "e manuais compilados para seus respectivos diretórios de destino no sistema de arquivos."
        ),
        why_in_lfs=(
            "É o passo que concretiza a compilação: os arquivos deixam a pasta temporária de fontes e passam "
            "a residir de fato no diretório de ferramentas (/tools) ou no sistema definitivo."
        ),
        danger_if_missed=(
            "Compilar um pacote com 'make' mas esquecer de rodar 'make install' deixa as ferramentas apenas "
            "na pasta de fontes. Quando o próximo pacote tentar compilar, ele falhará por não encontrar o software instalado."
        ),
        related_terms=["make", "DESTDIR", "--prefix"],
        aliases=["make-install", "instalar"],
    ),
    GlossaryEntry(
        term="DESTDIR",
        name="DESTDIR - Redirecionamento da Raiz de Instalação",
        category="Toolchain & Compiladores",
        syntax="make DESTDIR=$LFS install",
        what_it_does=(
            "Variável passada ao 'make install' que prefixa todos os caminhos de instalação com o diretório "
            "informado, sem alterar os caminhos internos fixados dentro dos binários pelo --prefix."
        ),
        why_in_lfs=(
            "Permite instalar pacotes configurados com '--prefix=/usr' fisicamente dentro de '$LFS/usr' antes "
            "de entrarmos no chroot. O programa pensa que mora em '/usr', mas seus arquivos são gravados em '$LFS/usr'."
        ),
        danger_if_missed=(
            "Se você esquecer de passar 'DESTDIR=$LFS' ao instalar um pacote configurado com '--prefix=/usr', "
            "o comando 'make install' sobrescreverá os arquivos do sistema operacional HOSPEDEIRO, corrompendo sua máquina!"
        ),
        related_terms=["make install", "--prefix", "$LFS"],
        aliases=["destdir"],
    ),
    GlossaryEntry(
        term="$LFS_TGT-gcc",
        name="$LFS_TGT-gcc - O Compilador Cruzado do LFS",
        category="Toolchain & Compiladores",
        syntax="$LFS_TGT-gcc [OPÇÕES] FONTE.c -o EXECUTAVEL",
        what_it_does=(
            "O executável do compilador GCC construído com a tupla de arquitetura alvo $LFS_TGT "
            "(ex: x86_64-lfs-linux-gnu-gcc)."
        ),
        why_in_lfs=(
            "É o coração do Capítulo 5: ele executa no hospedeiro mas foi construído para procurar bibliotecas "
            "apenas no sysroot do LFS. É ele quem compila a Glibc e todas as ferramentas temporárias que comporão "
            "o ecossistema do novo sistema operacional."
        ),
        danger_if_missed=(
            "Chamar apenas 'gcc' em vez de '$LFS_TGT-gcc' invocará o compilador comum da distribuição hospedeira, "
            "quebrando imediatamente o isolamento de segurança da compilação cruzada."
        ),
        related_terms=["$LFS_TGT", "readelf", "./configure"],
        aliases=["gcc", "lfs-gcc", "cross-gcc", "$LFS_TGT-gcc"],
    ),
    GlossaryEntry(
        term="readelf",
        name="readelf - Inspetor de Estrutura de Arquivos ELF",
        category="Toolchain & Compiladores",
        syntax="readelf -l EXECUTAVEL | grep ': /tools'",
        what_it_does=(
            "Exibe informações detalhadas sobre cabeçalhos, seções e interpretadores de programas de binários "
            "e bibliotecas no padrão ELF (Executable and Linkable Format) do Linux."
        ),
        why_in_lfs=(
            "É o instrumento sagrado do Teste de Sanidade (Sanity Check). Ao compilar um programa de teste "
            "(dummy.c), usamos 'readelf -l a.out' para verificar qual carregador dinâmico foi gravado no cabeçalho. "
            "Ele DEVE apontar para '/tools/lib64/ld-linux...' comprovando que a toolchain não depende do hospedeiro."
        ),
        danger_if_missed=(
            "Se você não validar com o 'readelf', pode passar horas construindo dezenas de pacotes sem notar "
            "que seus binários continuam presos ao linker do hospedeiro (/lib64/ld-linux...), tornando todo o esforço inútil."
        ),
        related_terms=["ld-linux", "$LFS_TGT-gcc"],
        aliases=["readelf -l", "sanity-check"],
    ),
    GlossaryEntry(
        term="ld-linux",
        name="ld-linux.so - O Carregador e Linker Dinâmico do Linux",
        category="Toolchain & Compiladores",
        syntax="/tools/lib64/ld-linux-x86-64.so.2 (ou /lib64/ld-linux-x86-64.so.2)",
        what_it_does=(
            "O interpretador dinâmico padrão do Linux. Sempre que um executável dinâmico é iniciado, o kernel "
            "carrega primeiro o ld-linux, que se encarrega de mapear na memória todas as bibliotecas compartilhadas (.so)."
        ),
        why_in_lfs=(
            "Controlar qual ld-linux é chamado é o cerne da independência do LFS. Na fase de ferramentas temporárias, "
            "todos os programas devem apontar para '/tools/lib64/ld-linux...'. No sistema final, para '/lib64/ld-linux...'."
        ),
        danger_if_missed=(
            "Se um binário apontar para um caminho de ld-linux que não existe no ambiente atual, o Linux emitirá "
            "o confuso erro 'bash: ./programa: No such file or directory', mesmo que o executável exista fisicamente no disco!"
        ),
        related_terms=["readelf", "limits.h", "$LFS_TGT-gcc"],
        aliases=["ld-linux.so", "ld.so", "dynamic-linker", "interpretador-dinamico"],
    ),
    GlossaryEntry(
        term="limits.h",
        name="limits.h - Cabeçalho do GCC e Correção de Limites da Toolchain",
        category="Toolchain & Compiladores",
        syntax="cat $LFS/tools/lib/gcc/.../include/limits.h",
        what_it_does=(
            "Arquivo de cabeçalho padrão da linguagem C que estabelece constantes de limites fundamentais "
            "do sistema (como INT_MAX, PATH_MAX, CHAR_BIT)."
        ),
        why_in_lfs=(
            "O GCC gera um cabeçalho limits.h interno que complementa o limits.h da biblioteca C do sistema. "
            "Na Passagem 1 do GCC, como a Glibc ainda não existia, o limits.h foi gerado incompleto. "
            "Após instalar a Glibc, o LFS instrui a rodar um script interno do GCC para gerar a versão completa do limits.h."
        ),
        danger_if_missed=(
            "Se o limits.h não for corrigido após a instalação da Glibc, pacotes subsequentes falharão na compilação "
            "alegando que constantes básicas como PATH_MAX ou NAME_MAX estão indefinidas."
        ),
        related_terms=["$LFS_TGT-gcc", "readelf"],
        aliases=["limits"],
    ),

    # -------------------------------------------------------------------------
    # Conceitos do Sistema & Chroot
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="chroot",
        name="chroot - Mudança do Diretório Raiz de Processos (Change Root)",
        category="Conceitos do Sistema & Chroot",
        syntax="chroot \"$LFS\" /usr/bin/env -i HOME=/root TERM=\"$TERM\" PS1='(lfs chroot) \\u:\\w\\$ ' PATH=/usr/bin:/usr/sbin /bin/bash --login",
        what_it_does=(
            "Altera o diretório raiz ('/') aparente para o processo atual e todos os seus processos-filhos. "
            "Um processo confinado em chroot não consegue acessar nenhum arquivo localizado fora da nova raiz delimitada."
        ),
        why_in_lfs=(
            "É o grande ritual e clímax do LFS (Capítulo 7): ao entrar em chroot em $LFS, cortamos definitivamente "
            "o cordão umbilical com a distribuição hospedeira. A partir deste ponto, o diretório $LFS passa a ser "
            "a verdadeira raiz ('/') do terminal, e todas as ferramentas temporárias recém-compiladas passam a construir "
            "o sistema operacional final em isolamento estéril completo."
        ),
        danger_if_missed=(
            "Se você não usar o chroot e tentar compilar os pacotes do Capítulo 8 no terminal comum, os comandos "
            "'make install' sobrescreverão as bibliotecas essenciais (/lib, /usr/lib) da sua própria distribuição "
            "hospedeira, destruindo completamente a máquina onde você está trabalhando!"
        ),
        related_terms=["bind-mount", "procfs", "sysfs", "devtmpfs", "su", "env"],
        aliases=["entrar-chroot", "change-root"],
    ),
    GlossaryEntry(
        term="bind-mount",
        name="bind-mount - Montagem Vinculada de Diretórios (mount --bind)",
        category="Discos & Montagens",
        syntax="mount -v --bind /dev $LFS/dev",
        what_it_does=(
            "Cria uma montagem vinculada (bind mount), que espelha uma subárvore de diretórios existente "
            "em outro local da hierarquia de arquivos sem duplicar o espaço em disco ou copiar dados."
        ),
        why_in_lfs=(
            "No Capítulo 7, usamos 'mount --bind /dev $LFS/dev' para compartilhar os nós de dispositivos "
            "de hardware da máquina anfitriã com o ambiente isolado do chroot, permitindo que processos dentro "
            "do chroot acessem /dev/null, /dev/zero, /dev/console e terminais virtuais sem criar discos extras."
        ),
        danger_if_missed=(
            "Sem o bind mount de /dev, comandos que redirecionam para /dev/null (como quase todo script de build) "
            "falharão com erro fatal, e testes que dependem de pseudoterminais (/dev/pts) serão abortados."
        ),
        related_terms=["mount", "chroot", "/dev", "devtmpfs"],
        aliases=["mount --bind", "--bind", "bind"],
    ),
    GlossaryEntry(
        term="procfs",
        name="procfs - Pseudo-sistema de Arquivos de Processos (/proc)",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -vt proc proc $LFS/proc",
        what_it_does=(
            "Sistema de arquivos virtual gerado dinamicamente na memória RAM pelo kernel Linux. "
            "Funciona como uma interface direta de controle e leitura de processos, memória, CPU e parâmetros do kernel."
        ),
        why_in_lfs=(
            "Montado em $LFS/proc antes de entrar no chroot para que utilitários de diagnóstico (ps, top), montadores de pacotes "
            "e suítes de teste de compiladores consigam consultar estatísticas de CPU e memória em tempo real."
        ),
        danger_if_missed=(
            "Testes de sanidade e suítes de testes do Coreutils, Glibc e Perl abortarão imediatamente caso não encontrem "
            "/proc montado, impedindo a validação da integridade das ferramentas."
        ),
        related_terms=["/proc", "sysfs", "chroot", "mount"],
        aliases=["proc", "/proc"],
    ),
    GlossaryEntry(
        term="sysfs",
        name="sysfs - Árvore de Dispositivos e Drivers do Kernel (/sys)",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -vt sysfs sysfs $LFS/sys",
        what_it_does=(
            "Estrutura hierárquica em memória RAM exposta pelo kernel Linux para representar dispositivos físicos e virtuais, "
            "barramentos (PCI, USB), drivers e subsistemas de hardware do computador."
        ),
        why_in_lfs=(
            "Essencial dentro do chroot para que gerenciadores de dispositivos (udev/eudev) e ferramentas de configuração "
            "de boot e disco (como fdisk, GRUB e util-linux) consigam descobrir e enumerar o hardware da estação."
        ),
        danger_if_missed=(
            "Sem o sysfs montado em $LFS/sys, instaladores de bootloader (GRUB) e detectores de rede não conseguirão "
            "identificar os discos nem as placas de rede do sistema."
        ),
        related_terms=["/sys", "procfs", "devtmpfs", "chroot"],
        aliases=["sys", "/sys"],
    ),
    GlossaryEntry(
        term="devtmpfs",
        name="devtmpfs - Sistema de Arquivos de Nós de Dispositivos (/dev)",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -v --bind /dev $LFS/dev",
        what_it_does=(
            "Instância em memória mantida pelo kernel Linux onde nós de dispositivos especiais (device nodes) "
            "são criados automaticamente conforme placas, discos e interfaces são detectados pelo sistema."
        ),
        why_in_lfs=(
            "Permite aos binários temporários do chroot comunicar-se com o hardware através dos nós em /dev, "
            "incluindo dispositivos fundamentais como /dev/null, /dev/zero, /dev/ptmx e partições /dev/sda."
        ),
        danger_if_missed=(
            "Se o devtmpfs não estiver acessível, nenhum processo conseguirá abrir canais de entrada/saída de dispositivos "
            "ou terminais, paralisando a compilação do sistema."
        ),
        related_terms=["/dev", "bind-mount", "chroot"],
        aliases=["dev", "/dev", "devnodes"],
    ),
    GlossaryEntry(
        term="/dev",
        name="/dev e devtmpfs - Diretório e Nós de Dispositivos",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -v --bind /dev $LFS/dev",
        what_it_does=(
            "Sistema de arquivos virtual preenchido pelo kernel com nós de dispositivos especiais "
            "(/dev/null, /dev/zero, /dev/ptmx, /dev/sda) que servem como ponto de comunicação entre softwares e hardware."
        ),
        why_in_lfs=(
            "Dentro do chroot, compiladores e comandos precisam interagir com dispositivos (ex: ler /dev/null "
            "ou usar terminais virtuais para suítes de teste). Usamos 'mount --bind /dev $LFS/dev' para espelhar "
            "os nós de hardware do hospedeiro para dentro da jaula do LFS."
        ),
        danger_if_missed=(
            "Entrar no chroot sem montar o /dev fará qualquer comando que redirecione saída para '/dev/null' falhar "
            "com erro 'No such file or directory', quebrando imediatamente a maioria dos scripts de shell."
        ),
        related_terms=["/proc", "/sys", "chroot", "mount"],
        aliases=["dev", "devtmpfs", "/dev/null"],
    ),
    GlossaryEntry(
        term="/proc",
        name="/proc - Sistema de Arquivos Virtual de Processos do Kernel",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -v -t proc proc $LFS/proc",
        what_it_does=(
            "Pseudo-sistema de arquivos gerado dinamicamente pelo kernel na memória RAM. Expõe informações "
            "sobre processos em execução, configuração do kernel e recursos de hardware (como /proc/cpuinfo e /proc/meminfo)."
        ),
        why_in_lfs=(
            "Ferramentas de compilação dentro do chroot (como o comando 'ps', montadores e suítes de teste de pacotes) "
            "consultam o /proc para saber o número de núcleos de CPU disponíveis e monitorar processos subordinados."
        ),
        danger_if_missed=(
            "Diversas suítes de teste de pacotes fundamentais (como Coreutils, Glibc e Bash) abortam com falhas "
            "críticas caso o /proc não esteja montado dentro do chroot."
        ),
        related_terms=["/sys", "/dev", "chroot", "mount"],
        aliases=["proc", "procfs"],
    ),
    GlossaryEntry(
        term="/sys",
        name="/sys - Sistema de Arquivos Virtual Sysfs",
        category="Conceitos do Sistema & Chroot",
        syntax="mount -v -t sysfs sysfs $LFS/sys",
        what_it_does=(
            "Estrutura hierárquica em RAM exportada pelo kernel Linux para representar dispositivos, barramentos, "
            "drivers e subsistemas de hardware do computador."
        ),
        why_in_lfs=(
            "O gerenciador de dispositivos udev/eudev e utilitários modernos de gerenciamento de disco precisam do /sys "
            "para descobrir placas de rede, unidades de armazenamento e barramentos dentro do chroot."
        ),
        danger_if_missed=(
            "Configurar o gerenciador de boot (GRUB) ou compilar ferramentas de rede e udev sem o /sys montado "
            "resultará em falhas de detecção de hardware durante a instalação."
        ),
        related_terms=["/proc", "/dev", "chroot", "mount"],
        aliases=["sys", "sysfs"],
    ),

    # -------------------------------------------------------------------------
    # Comandos Complementares Comuns
    # -------------------------------------------------------------------------
    GlossaryEntry(
        term="cp",
        name="cp - Cópia de Arquivos e Diretórios",
        category="Básico & Hospedeiro",
        syntax="cp [OPÇÕES] ORIGEM DESTINO",
        what_it_does=(
            "Copia arquivos ou árvores de diretórios. O parâmetro '-r' realiza cópia recursiva e '-v' exibe "
            "mensagens detalhadas de cada arquivo copiado."
        ),
        why_in_lfs=(
            "Utilizado para copiar os cabeçalhos sanitizados do kernel ('cp -rv usr/include/* $LFS/usr/include') "
            "e duplicar arquivos de configuração padrão para os locais definitivos do sistema."
        ),
        danger_if_missed=(
            "Copiar bibliotecas ou cabeçalhos esquecendo opções de preservação de atributos pode quebrar permissões "
            "ou converter links simbólicos essenciais em cópias físicas duplicadas."
        ),
        related_terms=["rm", "mkdir", "ln"],
        aliases=["copiar"],
    ),
    GlossaryEntry(
        term="ln",
        name="ln - Criação de Links Simbólicos e Rígidos",
        category="Básico & Hospedeiro",
        syntax="ln [OPÇÕES] ALVO NOME_DO_LINK",
        what_it_does=(
            "Cria ligações entre arquivos. A opção '-s' (--symbolic) cria um link simbólico (atalho) que aponta "
            "para o nome de outro arquivo ou diretório."
        ),
        why_in_lfs=(
            "Essencial no LFS para compatibilidade: usamos 'ln -sv bash /bin/sh' para garantir que scripts "
            "que invocam '/bin/sh' usem o Bash, e 'ln -sv lib $LFS/lib64' para unificar pastas de bibliotecas."
        ),
        danger_if_missed=(
            "Sem o link /bin/sh -> bash, quase todos os scripts de configuração e inicialização do sistema "
            "falharão imediatamente com erro 'sh: command not found'."
        ),
        related_terms=["ls", "cp"],
        aliases=["ln -s", "symlink"],
    ),
    GlossaryEntry(
        term="sed",
        name="sed - Editor de Fluxo de Texto (Stream Editor)",
        category="Toolchain & Compiladores",
        syntax="sed [OPÇÕES] 's/padrao/substituto/g' ARQUIVO",
        what_it_does=(
            "Executa transformações automáticas, substituições de expressões regulares e filtragens de texto "
            "diretamente em fluxos de dados ou arquivos, sem requerer editores interativos."
        ),
        why_in_lfs=(
            "Utilizado cirurgicamente nas instruções do livro para ajustar caminhos hardcoded em Makefiles antigos, "
            "redirecionando buscas de bibliotecas de '/lib64' para '/tools/lib64' ou corrigindo bugs pontuais de compilação."
        ),
        danger_if_missed=(
            "Errar uma expressão regular do sed pode corromper a sintaxe de um Makefile, gerando erros crípticos "
            "de compilação ou impedindo a instalação de bibliotecas no destino correto."
        ),
        related_terms=["grep", "cat", "patch"],
        aliases=["stream-editor"],
    ),
    GlossaryEntry(
        term="grep",
        name="grep - Busca de Padrões e Expressões Regulares",
        category="Toolchain & Compiladores",
        syntax="grep [OPÇÕES] PADRÃO [ARQUIVO...]",
        what_it_does=(
            "Examina linhas de texto que combinam com uma expressão regular e as imprime na saída padrão. "
            "A opção '-o' imprime exclusivamente a parte correspondente ao padrão buscado."
        ),
        why_in_lfs=(
            "Utilizado nos testes de sanidade (ex: 'readelf -l a.out | grep \": /tools\"') para filtrar "
            "exatamente a linha do carregador dinâmico em meio a centenas de linhas de cabeçalho ELF."
        ),
        danger_if_missed=(
            "Sem o grep, inspecionar manualmente saídas gigantescas de comandos como readelf ou logs de build "
            "seria lento e altamente propenso a falhas humanas de observação."
        ),
        related_terms=["sed", "cat", "readelf"],
        aliases=[],
    ),
    GlossaryEntry(
        term="find",
        name="find - Busca Hierárquica no Sistema de Arquivos",
        category="Básico & Hospedeiro",
        syntax="find [CAMINHO] [OPÇÕES]",
        what_it_does=(
            "Percorre recursivamente árvores de diretórios localizando arquivos que atendam a critérios "
            "de nome, tipo, tamanho, data de modificação ou permissões."
        ),
        why_in_lfs=(
            "Empregado para inspecionar onde bibliotecas foram instaladas, localizar e remover arquivos de "
            "arquivamento estático (.la) desnecessários ou auditar permissões de binários antes de empacotar."
        ),
        danger_if_missed=(
            "Procurar arquivos manualmente em hierarquias com dezenas de milhares de itens é inviável e lento."
        ),
        related_terms=["ls", "grep"],
        aliases=[],
    ),
    GlossaryEntry(
        term="install",
        name="install - Cópia e Configuração Atômica de Arquivos e Pastas",
        category="Básico & Hospedeiro",
        syntax="install -dv -m 0750 /root && install -dv -m 1777 /tmp /var/tmp",
        what_it_does=(
            "Combina operações de criação de diretórios (mkdir), cópia de arquivos (cp), "
            "definição de dono (chown) e atribuição de permissões (chmod) em uma única operação atômica e segura."
        ),
        why_in_lfs=(
            "No Capítulo 7.5, é empregado para criar os diretórios de segurança do sistema: '/root' com permissão "
            "restrita 0750 (apenas superusuário) e '/tmp' / '/var/tmp' com modo 1777 (sticky bit ativo, permitindo "
            "que todos criem arquivos temporários, mas somente os donos possam apagá-los)."
        ),
        danger_if_missed=(
            "Se /tmp for criado com 'mkdir' padrão (0755) em vez de 'install -m 1777', qualquer usuário ou processo "
            "poderá deletar arquivos temporários de outros usuários, abrindo vulnerabilidades críticas de segurança."
        ),
        related_terms=["mkdir", "chmod", "cp", "chown"],
        aliases=["install -d", "install -m", "instalar"],
    ),
]


class GlossaryManager:
    """Manages searching, retrieving, and formatting didactic glossary entries."""

    def __init__(self, entries: Optional[List[GlossaryEntry]] = None):
        self._entries: List[GlossaryEntry] = entries or GLOSSARY_ENTRIES
        self._term_map: Dict[str, GlossaryEntry] = {}
        self._alias_map: Dict[str, GlossaryEntry] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        for entry in self._entries:
            key = entry.term.strip().lower()
            self._term_map[key] = entry
            # Register aliases
            for alias in entry.aliases:
                self._alias_map[alias.strip().lower()] = entry

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Removes diacritics/accents from text for accent-insensitive search."""
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

    @staticmethod
    def _normalize(term: str) -> str:
        """Normalizes a lookup term by stripping common prefixes and punctuation."""
        import unicodedata
        t = term.strip().lower()
        t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
        # Strip leading $, --, ./, ../, /
        t = re.sub(r"^(\.\./|\./|\$|--|/)", "", t)
        # Strip trailing punctuation
        t = t.rstrip("/.-_")
        return t

    def get(self, term: str) -> Optional[GlossaryEntry]:
        """Looks up a glossary entry by exact term, alias, or normalized key."""
        if not term:
            return None
        raw = term.strip().lower()
        raw_clean = self._strip_accents(raw)

        # 1. Exact match on term
        if raw in self._term_map:
            return self._term_map[raw]
        if raw_clean in self._term_map:
            return self._term_map[raw_clean]

        # 2. Exact match on aliases
        if raw in self._alias_map:
            return self._alias_map[raw]
        if raw_clean in self._alias_map:
            return self._alias_map[raw_clean]

        # 3. Normalized match
        norm = self._normalize(raw)
        for key, entry in self._term_map.items():
            if self._normalize(key) == norm:
                return entry

        for alias, entry in self._alias_map.items():
            if self._normalize(alias) == norm:
                return entry

        # 4. Partial fallback (e.g. "sysroot" -> "--with-sysroot", "lfs_tgt" -> "$LFS_TGT")
        norm_clean = norm.replace("_", "-").replace(" ", "-")
        for key, entry in self._term_map.items():
            clean_key = self._normalize(key).replace("_", "-").replace(" ", "-")
            if norm_clean == clean_key or clean_key.endswith("-" + norm_clean):
                return entry

        return None

    def search(self, query: str) -> List[GlossaryEntry]:
        """Searches glossary entries for a keyword or phrase, returning ranked matches."""
        q = query.strip().lower()
        if not q:
            return []
        q_clean = self._strip_accents(q)

        exact_matches: List[GlossaryEntry] = []
        term_matches: List[GlossaryEntry] = []
        body_matches: List[GlossaryEntry] = []

        for entry in self._entries:
            term_clean = self._strip_accents(entry.term.lower())
            name_clean = self._strip_accents(entry.name.lower())
            aliases_clean = [self._strip_accents(a.lower()) for a in entry.aliases]

            if q_clean == term_clean or q_clean in aliases_clean:
                exact_matches.append(entry)
            elif q_clean in term_clean or any(q_clean in a for a in aliases_clean) or q_clean in name_clean:
                term_matches.append(entry)
            elif (
                q_clean in self._strip_accents(entry.what_it_does.lower())
                or q_clean in self._strip_accents(entry.why_in_lfs.lower())
                or q_clean in self._strip_accents(entry.danger_if_missed.lower())
                or q_clean in self._strip_accents(entry.category.lower())
            ):
                body_matches.append(entry)

        # Combine preserving ranking and uniqueness
        combined: List[GlossaryEntry] = []
        for e in exact_matches + term_matches + body_matches:
            if e not in combined:
                combined.append(e)
        return combined

    def list_by_category(self) -> Dict[str, List[GlossaryEntry]]:
        """Returns entries grouped by canonical category order."""
        result: Dict[str, List[GlossaryEntry]] = {cat: [] for cat in CATEGORIES}
        for entry in self._entries:
            if entry.category in result:
                result[entry.category].append(entry)
            else:
                result.setdefault(entry.category, []).append(entry)
        return {cat: entries for cat, entries in result.items() if entries}

    def format_entry(self, entry: GlossaryEntry) -> str:
        """Formats a single glossary entry into a didactic Rich-styled card."""
        lines = [
            "[bold cyan]╔═══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            f"[bold cyan]║[/bold cyan] [bold yellow]GLOSSÁRIO DIDÁTICO LFS:[/bold yellow] [bold white]{entry.name}[/bold white]",
            "[bold cyan]╚═══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            f"[bold green]📌 Termo:[/bold green] [bold white]{entry.term}[/bold white] | [bold green]Categoria:[/bold green] [magenta]{entry.category}[/magenta]",
            f"[bold green]💻 Sintaxe de Exemplo:[/bold green] [yellow]{entry.syntax}[/yellow]",
            "",
            "[bold cyan]📖 O QUE FAZ:[/bold cyan]",
            f"{entry.what_it_does}",
            "",
            "[bold cyan]🎯 POR QUE NO LFS? (Contexto Didático):[/bold cyan]",
            f"{entry.why_in_lfs}",
            "",
            "[bold cyan]⚠️ PERIGO SE ESQUECER / EXECUTAR ERRADO:[/bold cyan]",
            f"[red]{entry.danger_if_missed}[/red]",
        ]
        if entry.related_terms:
            related_str = ", ".join(f"[white]{t}[/white]" for t in entry.related_terms)
            lines.extend([
                "",
                f"[bold cyan]🔗 Termos Relacionados:[/bold cyan] {related_str}",
            ])
        return "\n".join(lines)

    def format_index(self, category_filter: Optional[str] = None) -> str:
        """Formats an overview index of all terms grouped by category."""
        lines = [
            "[bold cyan]╔═══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]",
            "[bold cyan]║[/bold cyan]            [bold yellow]⚡ GLOSSÁRIO DIDÁTICO DO LINUX FROM SCRATCH (LFS 13.1) ⚡[/bold yellow]          [bold cyan]║[/bold cyan]",
            "[bold cyan]╚═══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]",
            "[dim]Aprenda o propósito real de cada comando, variável e flag da compilação.[/dim]",
            "[bold yellow]Dica de Consulta:[/bold yellow] Digite '[bold green]explain <termo>[/bold green]' (ou '[bold green]explicar <termo>[/bold green]') para ler o card completo.",
            "[bold yellow]Dica de Modo:[/bold yellow] Digite '[bold green]didactic on|off[/bold green]' para alternar dicas automáticas durante comandos.",
            "",
        ]
        categories = self.list_by_category()
        for cat_name, entries in categories.items():
            if category_filter:
                cf_clean = self._strip_accents(category_filter.lower())
                cat_clean = self._strip_accents(cat_name.lower())
                if cf_clean not in cat_clean:
                    continue
            lines.append(f"[bold yellow]📂 {cat_name}[/bold yellow]")
            terms_str = ", ".join(f"[white]{e.term}[/white]" for e in entries)
            lines.append(f"   {terms_str}")
            lines.append("")

        lines.append("[dim]Exemplos: 'explain export', 'explain LFS_TGT', 'explain sysroot', 'explain chroot'[/dim]")
        return "\n".join(lines)


# Singleton manager instance for shared use
glossary_manager = GlossaryManager()
