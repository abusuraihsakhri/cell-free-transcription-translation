"""Command-line interface for the TXTL simulator."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .agents import TXTLSimulatorCoordinator
from .engine import TXTLKineticModel, downsample_points
from .models import ScreeningPayload, KineticParameters


coordinator = TXTLSimulatorCoordinator()


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def _add_simulation_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = KineticParameters()
    parser.add_argument("--dna-nm", type=float, default=defaults.dna_nm)
    parser.add_argument("--ntp-mm", type=float, default=defaults.ntp_mm)
    parser.add_argument("--aa-mm", type=float, default=defaults.aa_mm)
    parser.add_argument("--ribosome-nm", type=float, default=defaults.ribosome_nm)
    parser.add_argument("--duration-min", type=float, default=defaults.duration_min)
    parser.add_argument("--dt-min", type=float, default=defaults.dt_min)
    parser.add_argument("--vmax-tx-nm-min", type=float, default=defaults.vmax_tx_nm_min)
    parser.add_argument("--promoter-kd-nm", type=float, default=defaults.promoter_kd_nm)
    parser.add_argument("--ntp-km-mm", type=float, default=defaults.ntp_km_mm)
    parser.add_argument("--mrna-km-nm", type=float, default=defaults.mrna_km_nm)
    parser.add_argument("--aa-km-mm", type=float, default=defaults.aa_km_mm)
    parser.add_argument("--elongation-aa-s", type=float, default=defaults.elongation_aa_s)
    parser.add_argument("--protein-length-aa", type=float, default=defaults.protein_length_aa)
    parser.add_argument(
        "--mrna-half-life-min", type=float, default=defaults.mrna_half_life_min
    )
    parser.add_argument(
        "--protein-half-life-min", type=float, default=defaults.protein_half_life_min
    )
    parser.add_argument(
        "--nt-per-transcript", type=float, default=defaults.nt_per_transcript
    )


def _params_from_namespace(args: argparse.Namespace) -> KineticParameters:
    return KineticParameters(
        dna_nm=args.dna_nm,
        ntp_mm=args.ntp_mm,
        aa_mm=args.aa_mm,
        ribosome_nm=args.ribosome_nm,
        duration_min=args.duration_min,
        dt_min=args.dt_min,
        vmax_tx_nm_min=args.vmax_tx_nm_min,
        promoter_kd_nm=args.promoter_kd_nm,
        ntp_km_mm=args.ntp_km_mm,
        mrna_km_nm=args.mrna_km_nm,
        aa_km_mm=args.aa_km_mm,
        elongation_aa_s=args.elongation_aa_s,
        protein_length_aa=args.protein_length_aa,
        mrna_half_life_min=args.mrna_half_life_min,
        protein_half_life_min=args.protein_half_life_min,
        nt_per_transcript=args.nt_per_transcript,
    )


def _write_time_series(path: str, points: Iterable) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "time_min",
        "mrna_nm",
        "protein_nm",
        "ntp_mm",
        "aa_mm",
        "transcription_rate_nm_min",
        "translation_rate_nm_min",
    ]
    with path_obj.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for point in points:
            writer.writerow(point.to_dict())


def _print_simulation_summary(result) -> None:
    summary = result.summary
    print("TXTL kinetic simulation")
    print(f"  Final protein:       {summary['final_protein_nm']:.3f} nM")
    print(f"  Peak mRNA:           {summary['peak_mrna_nm']:.3f} nM")
    print(f"  Residual NTP:        {summary['residual_ntp_mm']:.4f} mM")
    print(f"  Residual amino acid: {summary['residual_aa_mm']:.4f} mM")
    print(
        f"  Peak translation:    {summary['peak_translation_rate_nm_min']:.3f} nM/min"
    )
    print(f"  Substrate limited:   {summary['substrate_limited']}")


def _kinetic_params_from_row(row: dict[str, str]) -> KineticParameters:
    defaults = asdict(KineticParameters())
    values = {}
    for name, default in defaults.items():
        raw = row.get(name, "")
        values[name] = float(raw) if str(raw).strip() else default
    return KineticParameters(**values)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cell-free-transcription-translation",
        description="Deterministic cell-free transcription-translation simulator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate_parser = subparsers.add_parser(
        "simulate", help="Run the mechanistic TXTL kinetic model"
    )
    _add_simulation_arguments(simulate_parser)
    simulate_parser.add_argument("--json", action="store_true", help="Print JSON")
    simulate_parser.add_argument(
        "--csv-out", help="Write the simulated time series to a CSV file"
    )

    audit_parser = subparsers.add_parser(
        "audit", help="Run the legacy configurable parameter screen"
    )
    audit_parser.add_argument("--task-id", default="TASK-001")
    audit_parser.add_argument("--target", default="TARGET-01")
    audit_parser.add_argument("--primary", type=float, default=20.0)
    audit_parser.add_argument("--secondary", type=float, default=5.0)
    audit_parser.add_argument("--critical", action="store_true")
    audit_parser.add_argument("--status", default="NOMINAL")

    chat_parser = subparsers.add_parser(
        "chat", help="Show local workflow/configuration guidance"
    )
    chat_parser.add_argument("query", nargs="+")

    batch_parser = subparsers.add_parser(
        "batch", help="Batch process kinetic or legacy-screening CSV records"
    )
    batch_parser.add_argument("-i", "--input", required=True)
    batch_parser.add_argument("-o", "--output", default="results.csv")

    serve_parser = subparsers.add_parser(
        "serve", help="Launch the optional local FastAPI server"
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.command == "simulate":
        try:
            result = TXTLKineticModel.simulate(_params_from_namespace(args))
        except (TypeError, ValueError) as exc:
            parser.error(str(exc))

        if args.json:
            print(json.dumps(result.to_dict(include_points=False), indent=2))
        else:
            _print_simulation_summary(result)

        if args.csv_out:
            _write_time_series(args.csv_out, downsample_points(result.points, 2000))
            print(f"Time series written to {args.csv_out}")
        return 0

    if args.command == "audit":
        payload = ScreeningPayload(
            task_id=args.task_id,
            target_identifier=args.target,
            primary_metric=args.primary,
            secondary_metric=args.secondary,
            status_descriptor=args.status,
            is_critical_flag=args.critical,
        )
        dossier = coordinator.process(payload)
        print(json.dumps(dossier, indent=2))
        return 0

    if args.command == "chat":
        print(coordinator.query_supervisory_chat(" ".join(args.query)))
        return 0

    if args.command == "batch":
        with open(args.input, mode="r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        kinetic_mode = "dna_nm" in fieldnames
        out_rows = []

        if kinetic_mode:
            summary_fields = [
                "final_protein_nm",
                "peak_mrna_nm",
                "residual_ntp_mm",
                "residual_aa_mm",
                "peak_translation_rate_nm_min",
                "substrate_limited",
            ]
            out_fields = fieldnames + [
                name for name in summary_fields if name not in fieldnames
            ]
            for row in rows:
                result = TXTLKineticModel.simulate(_kinetic_params_from_row(row))
                output = dict(row)
                for name in summary_fields:
                    output[name] = result.summary[name]
                out_rows.append(output)
        else:
            legacy_fields = [
                "overall_status",
                "total_alerts",
                "critical_count",
                "summary",
            ]
            out_fields = fieldnames + [
                name for name in legacy_fields if name not in fieldnames
            ]
            for row in rows:
                payload = ScreeningPayload(
                    task_id=row.get("task_id", "TASK-01"),
                    target_identifier=row.get("target_identifier", "TARGET-01"),
                    primary_metric=float(row.get("primary_metric") or 15.0),
                    secondary_metric=float(row.get("secondary_metric") or 5.0),
                    status_descriptor=row.get("status_descriptor", "NOMINAL"),
                    is_critical_flag=parse_bool(row.get("is_critical_flag", False)),
                )
                dossier = coordinator.process(payload)
                output = dict(row)
                for name in legacy_fields:
                    output[name] = dossier[name]
                out_rows.append(output)

        with open(args.output, mode="w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=out_fields)
            writer.writeheader()
            writer.writerows(out_rows)

        print(f"Processed {len(out_rows)} records -> {args.output}")
        return 0

    if args.command == "serve":
        try:
            import uvicorn
            from .server import create_app
        except ImportError:
            print("Server dependencies are not installed. Use: pip install '.[server]'")
            return 1

        app = create_app()
        if app is None:
            print("Server dependencies are not installed. Use: pip install '.[server]'")
            return 1
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
