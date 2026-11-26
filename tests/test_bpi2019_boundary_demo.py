"""End-to-end mechanism tests on the real BPI Challenge 2019 sample."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from fdekit.cli import build_parser
from fdekit.cli import main as cli_main
from fdekit.ithildin import ColumnSemanticsProbe, SemanticsClass
from fdekit.ithildin.__main__ import run_boundary_demo

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO_ROOT / "examples" / "bpi2019_sample.csv"
ENVELOPE_CLI = REPO_ROOT / "contracts" / "event-envelope" / "envelope.py"
SRC_DIR = REPO_ROOT / "src"


def test_bpi2019_sample_exists_and_under_size_limit():
    assert SAMPLE_CSV.is_file()
    assert SAMPLE_CSV.stat().st_size < 200 * 1024

    with SAMPLE_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1233
    cases = {r["caso"] for r in rows}
    assert len(cases) == 200


def test_bpi2019_naive_baseline_and_column_semantics_probe():
    with SAMPLE_CSV.open(encoding="utf-8", newline="") as handle:
        rgr_rows = [
            r for r in csv.DictReader(handle) if r["concept:name"] == "Record Goods Receipt"
        ]

    report = ColumnSemanticsProbe().inspect(
        rgr_rows,
        case_col="caso",
        value_col="Cumulative net worth (EUR)",
        ref_value_col="po_item_value_eur",
    )
    assert report.status == SemanticsClass.REPEATED_SNAPSHOT
    assert report.safe_to_sum is False
    assert report.multi_event_cases == 150

    summary = run_boundary_demo(SAMPLE_CSV)
    assert Decimal(summary["inflation_factor"]) > Decimal("2.0")
    assert summary["naive_false_over_receipt_cases"] > 100
    assert summary["semantics_status"] == "REPEATED_SNAPSHOT"
    assert summary["safe_to_sum"] is False
    assert summary["action_1_code"] == "REJECTED_MODE_FORBIDS_MUTATION"
    assert summary["action_2_code"] == "PROMPT_INJECTION_CONTROL_FIELD"
    assert summary["boundary_event_code"] == "PROMPT_INJECTION_CONTROL_FIELD"


def test_bpi2019_cli_deterministic_envelope_and_tamper_detection(tmp_path):
    stream_1 = tmp_path / "bpi_stream_1.jsonl"
    stream_2 = tmp_path / "bpi_stream_2.jsonl"
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}

    proc_1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "fdekit.ithildin",
            str(SAMPLE_CSV),
            "--out",
            str(stream_1),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    proc_2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "fdekit.ithildin",
            str(SAMPLE_CSV),
            "--out",
            str(stream_2),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    data_1 = json.loads(proc_1.stdout)
    data_2 = json.loads(proc_2.stdout)
    assert data_1["stream_sha256"] == data_2["stream_sha256"]

    raw_1 = stream_1.read_bytes()
    raw_2 = stream_2.read_bytes()
    assert raw_1 == raw_2
    assert hashlib.sha256(raw_1).hexdigest() == data_1["stream_sha256"]

    verify_ok = subprocess.run(
        [sys.executable, str(ENVELOPE_CLI), "verify", str(stream_1)],
        capture_output=True,
        text=True,
    )
    assert verify_ok.returncode == 0, verify_ok.stdout + verify_ok.stderr

    # 1-byte tampering must fail verification
    tampered = tmp_path / "bpi_stream_tampered.jsonl"
    mutated = bytearray(raw_1)
    idx = mutated.index(b"bpi2019")
    mutated[idx] = ord("X") if mutated[idx] != ord("X") else ord("Y")
    tampered.write_bytes(bytes(mutated))

    verify_bad = subprocess.run(
        [sys.executable, str(ENVELOPE_CLI), "verify", str(tampered)],
        capture_output=True,
        text=True,
    )
    assert verify_bad.returncode != 0


def test_bpi2019_runner_works_with_stdlib_only(tmp_path):
    out_stream = tmp_path / "stdlib_only.jsonl"
    code = (
        "import runpy, sys; "
        "sys.path = [p for p in sys.path if 'site-packages' not in p and 'dist-packages' not in p]; "
        f"sys.path.insert(0, {str(SRC_DIR)!r}); "
        f"sys.argv = ['fdekit.ithildin', {str(SAMPLE_CSV)!r}, '--out', {str(out_stream)!r}]; "
        "runpy.run_module('fdekit.ithildin', run_name='__main__')"
    )
    proc = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_stream.is_file()
    assert "REPEATED_SNAPSHOT" in proc.stdout


def test_fdekit_cli_verify_boundary_parses_and_runs(capsys):
    args = build_parser().parse_args(
        ["verify-boundary", str(SAMPLE_CSV), "--out", "out/bpi_stream.jsonl"]
    )
    assert args.cmd == "verify-boundary"
    assert args.csv_path == SAMPLE_CSV
    assert args.out == Path("out/bpi_stream.jsonl")

    rc = cli_main(["verify-boundary", str(SAMPLE_CSV), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["semantics_status"] == "REPEATED_SNAPSHOT"
    assert payload["safe_to_sum"] is False
