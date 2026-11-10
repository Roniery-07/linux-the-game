"""Compilation Anomaly and Mini-Game Encounter System (Act 2).

Simulates compilation hazards during LFS toolchain builds:
- CPU Overheat (temperature rising, requiring cooling or thread throttling)
- Linker Error (cross-linking issues requiring CFLAGS/rpath fixes)
- Host Contamination (polluted headers requiring sysroot verification)
"""

from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import GameEngine


@dataclass
class AnomalyChoice:
    key: str
    label: str
    is_correct: bool
    explanation: str
    xp_reward: int = 75
    patience_delta: int = 10
    temperature_delta: float = -15.0
    oxygen_delta: float = 0.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "is_correct": self.is_correct,
            "explanation": self.explanation,
            "xp_reward": self.xp_reward,
            "patience_delta": self.patience_delta,
            "temperature_delta": self.temperature_delta,
            "oxygen_delta": self.oxygen_delta,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnomalyChoice:
        return cls(**data)


@dataclass
class CompilationAnomaly:
    """Base compilation hazard encounter."""
    id: str
    name: str
    description: str
    severity: str  # "ALERTA", "CRÍTICO", "PERIGO"
    choices: List[AnomalyChoice] = field(default_factory=list)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "choices": [c.to_dict() for c in self.choices],
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CompilationAnomaly:
        choices = [AnomalyChoice.from_dict(c) for c in data.get("choices", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            severity=data["severity"],
            choices=choices,
            resolved=data.get("resolved", False),
        )


class CpuOverheatAnomaly(CompilationAnomaly):
    def __init__(self):
        super().__init__(
            id="CPU_OVERHEAT",
            name="Superaquecimento dos Núcleos de Processamento",
            description=(
                "ALERTA TÉRMICO: O compilador GCC levou todos os núcleos da Estação Hera a 100%! "
                "A temperatura do reator secundário subiu perigosamente para 84.5°C. "
                "Se os núcleos fundirem, o suporte vital será interrompido."
            ),
            severity="CRÍTICO",
            choices=[
                AnomalyChoice(
                    key="1",
                    label="Reduzir para MAKEFLAGS='-j1' e redirecionar fluido criogênico aos núcleos.",
                    is_correct=True,
                    explanation=(
                        "Decisão correta! A compilação desacelera para um único thread, mas a temperatura "
                        "cai imediatamente para níveis seguros (45°C). Estabilidade restaurada."
                    ),
                    xp_reward=100,
                    patience_delta=10,
                    temperature_delta=-25.0,
                    oxygen_delta=2.0,
                ),
                AnomalyChoice(
                    key="2",
                    label="Ignorar os alertas térmicos e continuar forçando 'make -j16' sem resfriamento.",
                    is_correct=False,
                    explanation=(
                        "ERRO GRAVE: Os circuitos superaqueceram e um pico de tensão queimou um regulador! "
                        "A estação sofreu uma queda de pressão de emergência."
                    ),
                    xp_reward=0,
                    patience_delta=-20,
                    temperature_delta=15.0,
                    oxygen_delta=-5.0,
                ),
            ]
        )


class LinkerErrorAnomaly(CompilationAnomaly):
    def __init__(self):
        super().__init__(
            id="LINKER_ERROR",
            name="Falha de Vinculação Cruzada (Linker Error)",
            description=(
                "ERRO DE LINKER: 'ld: undefined reference to __tls_get_addr'. "
                "O vinculador está misturando símbolos do hospedeiro com a toolchain do LFS!"
            ),
            severity="ALERTA",
            choices=[
                AnomalyChoice(
                    key="1",
                    label="Forçar flags de vinculação estrita com -Wl,-rpath-link=$LFS/tools/lib e verificar sysroot.",
                    is_correct=True,
                    explanation=(
                        "Excelente raciocínio! O caminho das bibliotecas cruzadas foi forçado no ld, "
                        "isolando completamente os símbolos da toolchain."
                    ),
                    xp_reward=120,
                    patience_delta=15,
                    temperature_delta=0.0,
                    oxygen_delta=0.0,
                ),
                AnomalyChoice(
                    key="2",
                    label="Copiar as bibliotecas compartilhadas de /usr/lib do hospedeiro para consertar o símbolo.",
                    is_correct=False,
                    explanation=(
                        "FALHA CRÍTICA: Você acabou de injetar binários do host na toolchain estéril! "
                        "A contaminação é severa e sua paciência cai drasticamente."
                    ),
                    xp_reward=0,
                    patience_delta=-25,
                    temperature_delta=5.0,
                    oxygen_delta=-2.0,
                ),
            ]
        )


class ContaminationWarningAnomaly(CompilationAnomaly):
    def __init__(self):
        super().__init__(
            id="HOST_CONTAMINATION",
            name="Aviso de Contaminação por Cabeçalhos Nativos",
            description=(
                "AVISO DE CONTAMINAÇÃO: O pré-processador tentou abrir '/usr/include/stdio.h' do host "
                "em vez dos cabeçalhos isolados em $LFS/usr/include!"
            ),
            severity="PERIGO",
            choices=[
                AnomalyChoice(
                    key="1",
                    label="Aplicar flag --with-sysroot=$LFS no configure e inspecionar os limites da árvore.",
                    is_correct=True,
                    explanation=(
                        "Perfeito! O sysroot foi reancorado à raiz da montagem do LFS. "
                        "O compilador agora busca exclusivamente os cabeçalhos limpos da estação."
                    ),
                    xp_reward=110,
                    patience_delta=12,
                    temperature_delta=-5.0,
                    oxygen_delta=1.0,
                ),
                AnomalyChoice(
                    key="2",
                    label="Ignorar o aviso: arquivos de cabeçalho padrão são todos iguais de qualquer forma.",
                    is_correct=False,
                    explanation=(
                        "ERRO FATAL: Cabeçalhos do hospedeiro diferem de versão e causam incompatibilidade de ABI! "
                        "Você perdeu tempo e paciência desfazendo a poluição."
                    ),
                    xp_reward=0,
                    patience_delta=-20,
                    temperature_delta=2.0,
                    oxygen_delta=-1.0,
                ),
            ]
        )


class AnomalyManager:
    """Manages active compilation encounters and resolution state."""

    def __init__(self):
        self.active_anomaly: Optional[CompilationAnomaly] = None
        self.resolved_history: List[str] = []

    def trigger_anomaly(self, anomaly_type: Optional[str] = None) -> CompilationAnomaly:
        """Creates and sets active anomaly."""
        if anomaly_type == "CPU_OVERHEAT" or anomaly_type == "overheat":
            anomaly = CpuOverheatAnomaly()
        elif anomaly_type == "LINKER_ERROR" or anomaly_type == "linker":
            anomaly = LinkerErrorAnomaly()
        elif anomaly_type == "HOST_CONTAMINATION" or anomaly_type == "contamination":
            anomaly = ContaminationWarningAnomaly()
        else:
            options = [CpuOverheatAnomaly, LinkerErrorAnomaly, ContaminationWarningAnomaly]
            anomaly = random.choice(options)()

        self.active_anomaly = anomaly
        return anomaly

    def format_active_prompt(self) -> str:
        """Renders rich formatted anomaly alert and choices."""
        if not self.active_anomaly:
            return ""
        a = self.active_anomaly
        color = "red" if a.severity in ("CRÍTICO", "PERIGO") else "yellow"
        lines = [
            f"[bold {color}]╔══════════════════════════════════════════════════════════════════╗[/bold {color}]",
            f"[bold {color}]║ [ANOMALIA DE COMPILAÇÃO] {a.name} ({a.severity})[/bold {color}]",
            f"[bold {color}]╚══════════════════════════════════════════════════════════════════╝[/bold {color}]",
            f"[yellow]{a.description}[/yellow]\n",
            "[bold white]Escolha sua ação corretiva (digite o número da opção):[/bold white]",
        ]
        for c in a.choices:
            lines.append(f"  [bold cyan][{c.key}][/bold cyan] {c.label}")
        return "\n".join(lines)

    def resolve(self, choice_key: str, engine: GameEngine) -> Tuple[bool, str]:
        """Resolves active anomaly with player choice."""
        if not self.active_anomaly:
            return False, "Nenhuma anomalia de compilação ativa no momento."

        choice = None
        for c in self.active_anomaly.choices:
            if c.key == choice_key.strip():
                choice = c
                break

        if not choice:
            return False, f"Opção '{choice_key}' inválida. Escolha uma das opções apresentadas."

        # Apply consequences
        engine.char.modify_patience(choice.patience_delta)
        if hasattr(engine, "telemetry"):
            engine.telemetry.temperature = max(30.0, min(100.0, engine.telemetry.temperature + choice.temperature_delta))
            engine.telemetry.oxygen = max(0.0, min(100.0, engine.telemetry.oxygen + choice.oxygen_delta))

        if choice.is_correct:
            leveled = engine.char.add_xp(choice.xp_reward)
            lvl_text = f" [bold yellow]★ NÍVEL AUMENTADO PARA {engine.char.level}! ★[/bold yellow]" if leveled else ""
            msg = (
                f"[bold green]✔ SUCESSO:[/bold green] {choice.explanation}\n"
                f"[green]+{choice.xp_reward} XP{lvl_text} | Paciência: {engine.char.patience}% | Temp: {engine.telemetry.temperature:.1f}°C[/green]"
            )
            self.active_anomaly.resolved = True
            self.resolved_history.append(self.active_anomaly.id)
            self.active_anomaly = None
            return True, msg
        else:
            msg = (
                f"[bold red]✖ FALHA:[/bold red] {choice.explanation}\n"
                f"[red]Paciência {choice.patience_delta} (Atual: {engine.char.patience}%) | Oxigênio: {engine.telemetry.oxygen:.1f}% | Temp: {engine.telemetry.temperature:.1f}°C[/red]"
            )
            # Anomaly remains active until resolved correctly
            return False, msg

    def to_dict(self) -> dict:
        return {
            "active_anomaly": self.active_anomaly.to_dict() if self.active_anomaly else None,
            "resolved_history": list(self.resolved_history),
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnomalyManager:
        mgr = cls()
        if data.get("active_anomaly"):
            mgr.active_anomaly = CompilationAnomaly.from_dict(data["active_anomaly"])
        mgr.resolved_history = list(data.get("resolved_history", []))
        return mgr
