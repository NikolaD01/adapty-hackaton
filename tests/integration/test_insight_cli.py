import json
import subprocess
import sys

from tests.service.test_insight_service import Dataset


def test_cli_analysis_reports_fixed_window_evidence_and_refunds(tmp_path):
    dataset = Dataset()
    dataset.users().rename(columns={"edits": "ai_edits_first_day"}).to_csv(tmp_path / "users.csv.gz", index=False)
    dataset.transactions().to_csv(tmp_path / "transactions.csv.gz", index=False)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_from_offline.py",
            "--data-dir",
            str(tmp_path),
            "--as-of",
            "2026-05-01T00:00:00Z",
            "--analysis",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(result.stdout)
    assert body["users"] == 3000
    assert body["outcome_window_days"] == 90
    assert body["rankings"][0]["passed"]
    assert body["tiers"][0]["passed"]
    assert 0 < len(body["segments"]) <= 5
    assert body["uplift"]
    assert all(item["refunds"] for item in body["uplift"])
    assert all(item["refunds"] for item in body["fixed_window_reference_checks"])


def test_cli_seed_json_uses_relative_clock_and_mature_seed_users(tmp_path):
    import gzip

    path = tmp_path / "lumen_dataset.json.gz"
    users = [
        {
            "i": 0,
            "install": -100 * 86400,
            "attrs": {},
            "tx": [
                {"t": -99 * 86400, "usd": 10.0, "refunded": None},
            ],
        },
        {"i": 1, "install": -10 * 86400, "attrs": {}, "tx": []},
    ]
    with gzip.open(path, "wt") as stream:
        json.dump({"version": 1, "app": "lumen", "days": 120, "users": users}, stream)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_from_offline.py",
            "--seed-json",
            str(path),
            "--as-of",
            "2026-11-08T00:00:00Z",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(result.stdout)
    assert body["source"] == "synthetic_seed"
    assert body["users"] == 1 and body["mean_net_revenue_90d"] == 10
    assert body["provenance"]["time_basis"] == "relative_to_dataset_now"
