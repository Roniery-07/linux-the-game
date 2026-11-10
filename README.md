# O Último Kernel: Linux From Scratch RPG (LFS 13.1)

Um RPG cyberpunk imersivo no terminal onde você constrói o Linux From Scratch (LFS 13.1) passo a passo para restaurar os sistemas vitais da Estação Orbital Hera.

## Funcionalidades
- **Ato 1 (Capítulos 1 a 4 do LFS 13.1 pt_BR)**:
  - Preparação do hospedeiro, particionamento `/dev/sda` e montagem em `$LFS`.
  - Download e verificação das somas MD5 oficiais dos pacotes.
  - Criação do diretório de ferramentas temporárias e do usuário isolado `lfs`.
  - Configuração do ambiente estéril (`.bash_profile`, `.bashrc`).
- **Simulador de Shell Virtual**:
  - Sistema de arquivos virtual com suporte a permissões, variáveis de ambiente e dispositivos de bloco.
  - Parser interativo de comandos Unix reais com feedback da IA K.E.R.N.E.L.
- **Interface TUI Cyberpunk (Textual & Rich)**:
  - Telemetria da estação (Oxigênio, CPU, Temperatura, RAM).
  - Terminal interativo com auto-complete e histórico de comandos.
  - Visualizador de diálogos e missões com decisões interativas.
  - Inventário de partições montadas e pacotes de código-fonte.
