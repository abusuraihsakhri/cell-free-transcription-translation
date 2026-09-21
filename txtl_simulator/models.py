"""Data models for TXTL simulation and legacy parameter screening."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


class ExecutionStatus(str, Enum):
    NOMINAL = "NOMINAL"
    ELEVATED_RISK = "REVIEW"
    CRITICAL_INTERVENTION = "CRITICAL"


@dataclass
class FrontierPayload:
    """Legacy generic payload retained for backward-compatible audit commands."""

    task_id: str
    target_identifier: str
    primary_metric: float
    secondary_metric: float
    status_descriptor: str
    is_critical_flag: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentTelemetryAlert:
    alert_id: str
    origin_agent: str
    status: ExecutionStatus
    summary: str
    technical_details: str
    actionable_remediation: str
    standard_reference: str = "Configured screening rules"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "origin_agent": self.origin_agent,
            "status": self.status.value,
            "summary": self.summary,
            "technical_details": self.technical_details,
            "actionable_remediation": self.actionable_remediation,
            "standard_reference": self.standard_reference,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class KineticParameters:
    """Parameters for the reduced deterministic TXTL kinetic model.

    Concentration units are nM for DNA, ribosomes, mRNA and protein, and mM
    for nucleotide and amino-acid pools. Time is measured in minutes.
    """

    dna_nm: float = 5.0
    ntp_mm: float = 1.5
    aa_mm: float = 2.0
    ribosome_nm: float = 50.0
    duration_min: float = 120.0
    dt_min: float = 0.1

    vmax_tx_nm_min: float = 100.0
    promoter_kd_nm: float = 1.0
    ntp_km_mm: float = 0.1

    mrna_km_nm: float = 20.0
    aa_km_mm: float = 0.2
    elongation_aa_s: float = 10.0
    protein_length_aa: float = 240.0

    mrna_half_life_min: float = 8.0
    protein_half_life_min: float = 240.0
    nt_per_transcript: float = 720.0

    def validate(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.dt_min > self.duration_min:
            raise ValueError("dt_min cannot exceed duration_min")
        if self.duration_min / self.dt_min > 200_000:
            raise ValueError("simulation would require more than 200,000 integration steps")


@dataclass(frozen=True)
class SimulationPoint:
    time_min: float
    mrna_nm: float
    protein_nm: float
    ntp_mm: float
    aa_mm: float
    transcription_rate_nm_min: float
    translation_rate_nm_min: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class SimulationResult:
    parameters: KineticParameters
    points: List[SimulationPoint]
    summary: Dict[str, Any]

    def to_dict(self, include_points: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "parameters": asdict(self.parameters),
            "summary": self.summary,
        }
        if include_points:
            payload["points"] = [point.to_dict() for point in self.points]
        return payload
