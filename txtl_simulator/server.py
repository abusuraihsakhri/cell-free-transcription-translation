"""Optional FastAPI server for local TXTL simulation."""

from typing import Any, Dict, Optional

from .agents import TXTLSimulatorCoordinator
from .engine import TXTLKineticModel, downsample_points
from .models import ScreeningPayload, KineticParameters


coordinator = TXTLSimulatorCoordinator()


def create_app() -> Optional[Any]:
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
    except ImportError:
        return None

    app = FastAPI(
        title="Cell-Free Transcription-Translation Simulator",
        description=(
            "Reduced deterministic TXTL kinetic model for exploratory and "
            "educational parameter studies."
        ),
        version="3.0.0",
    )

    class SimulationRequest(BaseModel):
        dna_nm: float = Field(default=5.0, gt=0)
        ntp_mm: float = Field(default=1.5, gt=0)
        aa_mm: float = Field(default=2.0, gt=0)
        ribosome_nm: float = Field(default=50.0, gt=0)
        duration_min: float = Field(default=120.0, gt=0)
        dt_min: float = Field(default=0.1, gt=0)
        vmax_tx_nm_min: float = Field(default=100.0, gt=0)
        promoter_kd_nm: float = Field(default=1.0, gt=0)
        ntp_km_mm: float = Field(default=0.1, gt=0)
        mrna_km_nm: float = Field(default=20.0, gt=0)
        aa_km_mm: float = Field(default=0.2, gt=0)
        elongation_aa_s: float = Field(default=10.0, gt=0)
        protein_length_aa: float = Field(default=240.0, gt=0)
        mrna_half_life_min: float = Field(default=8.0, gt=0)
        protein_half_life_min: float = Field(default=240.0, gt=0)
        nt_per_transcript: float = Field(default=720.0, gt=0)

    class LegacyAuditRequest(BaseModel):
        task_id: str = "TASK-001"
        target_identifier: str = "TARGET-01"
        primary_metric: float = 20.0
        secondary_metric: float = 5.0
        status_descriptor: str = "NOMINAL"
        is_critical_flag: bool = False
        attributes: Dict[str, Any] = Field(default_factory=dict)

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "service": "cell-free-transcription-translation",
            "version": "3.0.0",
        }

    @app.post("/api/simulate")
    def simulate(req: SimulationRequest):
        try:
            params = KineticParameters(**req.model_dump())
            result = TXTLKineticModel.simulate(params)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        payload = result.to_dict(include_points=False)
        payload["points"] = [
            point.to_dict() for point in downsample_points(result.points, max_points=500)
        ]
        return payload

    @app.post("/api/audit")
    def audit(req: LegacyAuditRequest):
        payload = ScreeningPayload(**req.model_dump())
        return coordinator.process(payload)

    return app
