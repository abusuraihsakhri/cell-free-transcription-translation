import csv
from pathlib import Path

import pytest

from txtl_simulator.agents import TXTLSimulatorCoordinator
from txtl_simulator.cli import main, parse_bool
from txtl_simulator.engine import TXTLKineticModel, downsample_points
from txtl_simulator.models import FrontierPayload, KineticParameters


def test_default_simulation_is_finite_and_nonnegative():
    result = TXTLKineticModel.simulate(KineticParameters())
    assert len(result.points) > 10
    assert result.summary["final_protein_nm"] > 0
    assert result.summary["peak_mrna_nm"] > 0
    assert 0 <= result.summary["residual_ntp_mm"] <= 1.5
    assert 0 <= result.summary["residual_aa_mm"] <= 2.0

    for point in result.points:
        assert point.mrna_nm >= 0
        assert point.protein_nm >= 0
        assert point.ntp_mm >= 0
        assert point.aa_mm >= 0


def test_more_dna_increases_initial_transcription_rate():
    low = KineticParameters(dna_nm=1.0)
    high = KineticParameters(dna_nm=10.0)
    low_rate = TXTLKineticModel.transcription_rate_nm_min(
        low.dna_nm, low.ntp_mm, low
    )
    high_rate = TXTLKineticModel.transcription_rate_nm_min(
        high.dna_nm, high.ntp_mm, high
    )
    assert high_rate > low_rate


def test_validation_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        TXTLKineticModel.simulate(KineticParameters(dna_nm=0))
    with pytest.raises(ValueError):
        TXTLKineticModel.simulate(
            KineticParameters(duration_min=1.0, dt_min=2.0)
        )


def test_downsampling_keeps_first_and_last_points():
    result = TXTLKineticModel.simulate(KineticParameters(duration_min=20, dt_min=0.05))
    sampled = downsample_points(result.points, max_points=25)
    assert len(sampled) <= 26
    assert sampled[0] == result.points[0]
    assert sampled[-1] == result.points[-1]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("True", True),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("False", False),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
    ],
)
def test_parse_bool(raw, expected):
    assert parse_bool(raw) is expected


def test_legacy_screening_still_runs():
    coordinator = TXTLSimulatorCoordinator()
    payload = FrontierPayload(
        task_id="T1",
        target_identifier="TARGET-1",
        primary_metric=35.0,
        secondary_metric=4.0,
        status_descriptor="NOMINAL",
    )
    dossier = coordinator.process(payload)
    assert dossier["total_alerts"] == 1
    assert dossier["overall_status"] == "REVIEW"


def test_cli_simulate_smoke(capsys):
    assert main(["simulate", "--duration-min", "2", "--dt-min", "0.1"]) == 0
    output = capsys.readouterr().out
    assert "Final protein" in output


def test_cli_legacy_batch_false_is_not_true(tmp_path: Path):
    input_path = tmp_path / "legacy.csv"
    output_path = tmp_path / "results.csv"
    input_path.write_text(
        "task_id,target_identifier,primary_metric,secondary_metric,is_critical_flag,status_descriptor\n"
        "T1,TARGET-1,5,5,False,NOMINAL\n",
        encoding="utf-8",
    )

    assert main(["batch", "-i", str(input_path), "-o", str(output_path)]) == 0

    with output_path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["critical_count"] == "0"


def test_cli_kinetic_batch(tmp_path: Path):
    input_path = tmp_path / "kinetic.csv"
    output_path = tmp_path / "results.csv"
    input_path.write_text(
        "dna_nm,ntp_mm,aa_mm,ribosome_nm,duration_min,dt_min\n"
        "5,1.5,2.0,50,5,0.1\n",
        encoding="utf-8",
    )

    assert main(["batch", "-i", str(input_path), "-o", str(output_path)]) == 0

    with output_path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert float(row["final_protein_nm"]) > 0
