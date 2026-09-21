"""Deterministic TXTL kinetics plus legacy rule-based screening helpers."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional, Tuple

from .models import KineticParameters, SimulationPoint, SimulationResult


class FrontierDomainEngine:
    """Legacy screening helper retained for CLI compatibility.

    The bounds are configurable repository defaults, not biological reference
    intervals or validated experimental decision limits.
    """

    PRIMARY_BOUND = 25.0
    SECONDARY_BOUND = 10.0

    @classmethod
    def evaluate_primary_parameter(cls, value: float) -> Optional[Dict[str, Any]]:
        if value > cls.PRIMARY_BOUND:
            return {
                "summary": "Primary screening bound exceeded",
                "details": (
                    f"Primary value ({value:.3f}) exceeds the configured screening "
                    f"bound ({cls.PRIMARY_BOUND:.1f})."
                ),
                "remediation": "Review the input and adjust the configured screening bound if appropriate.",
            }
        return None

    @classmethod
    def evaluate_secondary_kinetics(
        cls, value: float, is_critical: bool
    ) -> Optional[Dict[str, Any]]:
        if value > cls.SECONDARY_BOUND or is_critical:
            return {
                "summary": "Secondary screening condition triggered",
                "details": (
                    f"Secondary value ({value:.3f}); critical flag={is_critical}. "
                    "This is a configurable rule, not a validated biological threshold."
                ),
                "remediation": "Review the input values and model assumptions before interpretation.",
            }
        return None

    @classmethod
    def audit_specification_conformance(
        cls, descriptor: str, attributes: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        del attributes
        desc_upper = str(descriptor).upper()
        if any(flag in desc_upper for flag in ("VIOLATION", "DISCORDANT", "ANOMALY", "FAIL", "REJECT")):
            return {
                "summary": "Descriptor flagged for review",
                "details": f"Descriptor '{descriptor}' matched a configured review keyword.",
                "remediation": "Confirm the descriptor and inspect the underlying experiment or assay record.",
            }
        return None


class TXTLKineticModel:
    """Reduced coupled transcription-translation model.

    This model is intentionally compact. It uses saturable transcription and
    translation terms, first-order mRNA/protein loss, and explicit depletion
    of nucleotide and amino-acid pools. It is suitable for educational and
    exploratory parameter studies, not quantitative prediction without
    calibration against a specific cell-free system.
    """

    @staticmethod
    def transcription_rate_nm_min(
        dna_nm: float,
        ntp_mm: float,
        params: KineticParameters,
    ) -> float:
        dna_sat = dna_nm / (params.promoter_kd_nm + dna_nm)
        ntp_sat = ntp_mm / (params.ntp_km_mm + ntp_mm)
        return params.vmax_tx_nm_min * dna_sat * (ntp_sat ** 4)

    @staticmethod
    def translation_rate_nm_min(
        mrna_nm: float,
        aa_mm: float,
        params: KineticParameters,
    ) -> float:
        mrna_sat = mrna_nm / (params.mrna_km_nm + mrna_nm) if mrna_nm > 0 else 0.0
        aa_sat = aa_mm / (params.aa_km_mm + aa_mm)
        proteins_per_ribosome_min = (
            params.elongation_aa_s * 60.0 / params.protein_length_aa
        )
        return (
            proteins_per_ribosome_min
            * params.ribosome_nm
            * mrna_sat
            * aa_sat
        )

    @classmethod
    def _derivatives(
        cls,
        state: Tuple[float, float, float, float],
        params: KineticParameters,
    ) -> Tuple[float, float, float, float]:
        mrna_nm, protein_nm, ntp_mm, aa_mm = state
        mrna_nm = max(0.0, mrna_nm)
        protein_nm = max(0.0, protein_nm)
        ntp_mm = max(0.0, ntp_mm)
        aa_mm = max(0.0, aa_mm)

        tx_rate = cls.transcription_rate_nm_min(params.dna_nm, ntp_mm, params)
        tl_rate = cls.translation_rate_nm_min(mrna_nm, aa_mm, params)

        mrna_decay = math.log(2.0) / params.mrna_half_life_min
        protein_decay = math.log(2.0) / params.protein_half_life_min

        d_mrna = tx_rate - mrna_decay * mrna_nm
        d_protein = tl_rate - protein_decay * protein_nm
        d_ntp = -(params.nt_per_transcript * tx_rate) / 1_000_000.0
        d_aa = -(params.protein_length_aa * tl_rate) / 1_000_000.0
        return d_mrna, d_protein, d_ntp, d_aa

    @staticmethod
    def _combine(
        state: Tuple[float, float, float, float],
        derivative: Tuple[float, float, float, float],
        scale: float,
    ) -> Tuple[float, float, float, float]:
        return tuple(s + scale * d for s, d in zip(state, derivative))  # type: ignore[return-value]

    @classmethod
    def _rk4_step(
        cls,
        state: Tuple[float, float, float, float],
        h: float,
        params: KineticParameters,
    ) -> Tuple[float, float, float, float]:
        k1 = cls._derivatives(state, params)
        k2 = cls._derivatives(cls._combine(state, k1, h / 2.0), params)
        k3 = cls._derivatives(cls._combine(state, k2, h / 2.0), params)
        k4 = cls._derivatives(cls._combine(state, k3, h), params)

        next_state = tuple(
            s + h * (a + 2.0 * b + 2.0 * c + d) / 6.0
            for s, a, b, c, d in zip(state, k1, k2, k3, k4)
        )
        return tuple(max(0.0, value) for value in next_state)  # type: ignore[return-value]

    @classmethod
    def simulate(cls, params: KineticParameters) -> SimulationResult:
        params.validate()

        state = (0.0, 0.0, params.ntp_mm, params.aa_mm)
        time_min = 0.0
        points = []

        while True:
            mrna_nm, protein_nm, ntp_mm, aa_mm = state
            tx_rate = cls.transcription_rate_nm_min(params.dna_nm, ntp_mm, params)
            tl_rate = cls.translation_rate_nm_min(mrna_nm, aa_mm, params)
            points.append(
                SimulationPoint(
                    time_min=round(time_min, 10),
                    mrna_nm=mrna_nm,
                    protein_nm=protein_nm,
                    ntp_mm=ntp_mm,
                    aa_mm=aa_mm,
                    transcription_rate_nm_min=tx_rate,
                    translation_rate_nm_min=tl_rate,
                )
            )

            if time_min >= params.duration_min - 1e-12:
                break

            h = min(params.dt_min, params.duration_min - time_min)
            state = cls._rk4_step(state, h, params)
            time_min += h

        final = points[-1]
        peak_mrna = max(point.mrna_nm for point in points)
        peak_tl_rate = max(point.translation_rate_nm_min for point in points)
        ntp_fraction = final.ntp_mm / params.ntp_mm
        aa_fraction = final.aa_mm / params.aa_mm

        summary = {
            "final_protein_nm": final.protein_nm,
            "peak_mrna_nm": peak_mrna,
            "residual_ntp_mm": final.ntp_mm,
            "residual_aa_mm": final.aa_mm,
            "peak_translation_rate_nm_min": peak_tl_rate,
            "ntp_fraction_remaining": ntp_fraction,
            "aa_fraction_remaining": aa_fraction,
            "substrate_limited": ntp_fraction < 0.1 or aa_fraction < 0.1,
            "integration_method": "RK4",
        }
        return SimulationResult(parameters=params, points=points, summary=summary)


def downsample_points(
    points: Iterable[SimulationPoint], max_points: int = 500
) -> list[SimulationPoint]:
    """Return evenly spaced points for display/export without altering simulation."""

    point_list = list(points)
    if max_points <= 0:
        raise ValueError("max_points must be greater than zero")
    if len(point_list) <= max_points:
        return point_list

    stride = max(1, math.ceil((len(point_list) - 1) / (max_points - 1)))
    sampled = point_list[::stride]
    if sampled[-1] is not point_list[-1]:
        sampled.append(point_list[-1])
    return sampled
