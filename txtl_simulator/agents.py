"""Rule-based screening helpers retained for backward-compatible CLI commands."""

import uuid
from typing import Any, Dict, List

from .engine import FrontierDomainEngine
from .models import AgentTelemetryAlert, ExecutionStatus, FrontierPayload


class TranscriptionKineticsAgent:
    """Apply the configured primary-value screening rule."""

    def audit(self, payload: FrontierPayload) -> List[AgentTelemetryAlert]:
        result = FrontierDomainEngine.evaluate_primary_parameter(payload.primary_metric)
        if not result:
            return []
        return [
            AgentTelemetryAlert(
                alert_id=str(uuid.uuid4())[:8],
                origin_agent="TranscriptionKineticsAgent",
                status=ExecutionStatus.ELEVATED_RISK,
                summary=result["summary"],
                technical_details=result["details"],
                actionable_remediation=result["remediation"],
            )
        ]


class RibosomeElongationModelAgent:
    """Apply the configured secondary-value screening rule."""

    def audit(self, payload: FrontierPayload) -> List[AgentTelemetryAlert]:
        result = FrontierDomainEngine.evaluate_secondary_kinetics(
            payload.secondary_metric, payload.is_critical_flag
        )
        if not result:
            return []
        return [
            AgentTelemetryAlert(
                alert_id=str(uuid.uuid4())[:8],
                origin_agent="RibosomeElongationModelAgent",
                status=(
                    ExecutionStatus.CRITICAL_INTERVENTION
                    if payload.is_critical_flag
                    else ExecutionStatus.ELEVATED_RISK
                ),
                summary=result["summary"],
                technical_details=result["details"],
                actionable_remediation=result["remediation"],
            )
        ]


class ResourceDepletionTrackerAgent:
    """Flag configured descriptor keywords for manual review."""

    def audit(self, payload: FrontierPayload) -> List[AgentTelemetryAlert]:
        result = FrontierDomainEngine.audit_specification_conformance(
            payload.status_descriptor, payload.attributes
        )
        if not result:
            return []
        return [
            AgentTelemetryAlert(
                alert_id=str(uuid.uuid4())[:8],
                origin_agent="ResourceDepletionTrackerAgent",
                status=ExecutionStatus.ELEVATED_RISK,
                summary=result["summary"],
                technical_details=result["details"],
                actionable_remediation=result["remediation"],
            )
        ]


class TXTLSimulatorCoordinator:
    """Coordinate the legacy screening rules.

    This helper is intentionally separate from the mechanistic kinetic model.
    It is retained so existing audit/chat/batch invocations continue to work.
    """

    def __init__(self):
        self.sub_1 = TranscriptionKineticsAgent()
        self.sub_2 = RibosomeElongationModelAgent()
        self.sub_3 = ResourceDepletionTrackerAgent()
        self.execution_ledger: Dict[str, Dict[str, Any]] = {}

    def process(self, payload: FrontierPayload) -> Dict[str, Any]:
        all_alerts: List[AgentTelemetryAlert] = []
        all_alerts.extend(self.sub_1.audit(payload))
        all_alerts.extend(self.sub_2.audit(payload))
        all_alerts.extend(self.sub_3.audit(payload))

        critical_count = sum(
            1
            for alert in all_alerts
            if alert.status == ExecutionStatus.CRITICAL_INTERVENTION
        )
        warning_count = sum(
            1
            for alert in all_alerts
            if alert.status == ExecutionStatus.ELEVATED_RISK
        )

        if critical_count:
            status = ExecutionStatus.CRITICAL_INTERVENTION
        elif warning_count:
            status = ExecutionStatus.ELEVATED_RISK
        else:
            status = ExecutionStatus.NOMINAL

        dossier = {
            "system": "cell-free-transcription-translation",
            "task_id": payload.task_id,
            "target_identifier": payload.target_identifier,
            "overall_status": status.value,
            "total_alerts": len(all_alerts),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "alerts": [alert.to_dict() for alert in all_alerts],
            "screening_basis": "Configured repository rules; not validated biological thresholds",
            "summary": f"Screening completed with status [{status.value}].",
        }
        self.execution_ledger[payload.task_id] = dossier
        return dossier

    def query_supervisory_chat(self, query: str) -> str:
        q = query.strip().lower()
        if "status" in q or "ledger" in q:
            return f"{len(self.execution_ledger)} screening task(s) are stored in process memory."
        if "standard" in q or "spec" in q:
            return (
                "The legacy audit command uses configurable screening rules. "
                "Use the simulate command for the mechanistic TXTL kinetic model."
            )
        return (
            "Available workflows are kinetic simulation, CSV batch simulation, "
            "legacy parameter screening, and the optional local API."
        )
