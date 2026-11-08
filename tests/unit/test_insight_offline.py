"""Outcome accounting: no cohort loss, duplicate revenue, or future information."""

import json
import subprocess
import sys

import pandas as pd
import pytest

from feature_signal.integrations.offline import CsvOfflineDataset, build_outcomes


def fixture_frames():
    users = pd.DataFrame(
        {
            "user_id": ["paid", "zero", "refund", "late", "young"],
            "install_at": ["2026-01-01T00:00:00Z"] * 4 + ["2026-04-01T00:00:00Z"],
            "ai_edits_first_day": ["5.0", "0.0", "1.0", "2.0", "3.0"],
        }
    )
    transactions = pd.DataFrame(
        {
            "user_id": ["paid", "refund", "late", "young"],
            "seq": [1, 2, 3, 4],
            "purchased_at": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-04-01T00:00:00Z",
                "2026-04-02T00:00:00Z",
            ],
            "price_usd": [10, 8, 20, 50],
            "refunded_at": [None, "2026-01-03T00:00:00Z", None, None],
        }
    )
    return users, transactions


def test_outcome_keeps_nonpayers_and_excludes_refunds_late_and_immature():
    users, transactions = fixture_frames()
    result = build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z").set_index("user_id")
    assert result.net_revenue_90d.to_dict() == {"paid": 10, "zero": 0, "refund": 0, "late": 0}
    assert result.loc["refund", "refunded_transactions_90d"] == 1
    assert result.loc["refund", "paid_transactions_90d"] == 1
    assert result.loc["zero", "paid_transactions_90d"] == 0
    assert result.loc["paid", "ai_edits_first_day"] == 5.0
    assert users.loc[0, "ai_edits_first_day"] == "5.0"


def test_exact_maturity_boundary_and_preinstall_purchase():
    users, transactions = fixture_frames()
    transactions.loc[0, "purchased_at"] = "2025-12-31T23:59:59Z"
    result = build_outcomes(users, transactions, as_of="2026-04-01T00:00:00Z")
    assert len(result) == 4
    assert result.net_revenue_90d.sum() == 0
    assert build_outcomes(users, transactions, as_of="2026-03-31T23:59:59Z").empty


def test_refund_after_observation_cutoff_is_not_known_yet():
    users, transactions = fixture_frames()
    transactions.loc[1, "refunded_at"] = "2026-06-01T00:00:00Z"
    result = build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z").set_index("user_id")
    assert result.loc["refund", "net_revenue_90d"] == 8
    assert result.loc["refund", "refunded_transactions_90d"] == 0


def test_empty_transactions_keep_mature_users():
    users, transactions = fixture_frames()
    result = build_outcomes(users, transactions.iloc[:0], as_of="2026-05-01T00:00:00Z")
    assert len(result) == 4
    assert result.net_revenue_90d.sum() == 0


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf"), "invalid"])
def test_invalid_price_rejected(price):
    users, transactions = fixture_frames()
    transactions["price_usd"] = transactions.price_usd.astype(object)
    transactions.loc[0, "price_usd"] = price
    with pytest.raises(ValueError, match="price_usd"):
        build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z")


def test_duplicate_user_rejected_before_join():
    users, transactions = fixture_frames()
    with pytest.raises(ValueError, match="duplicate.*user"):
        build_outcomes(pd.concat([users, users.iloc[:1]]), transactions, as_of="2026-05-01T00:00:00Z")


def test_duplicate_transaction_rejected_before_aggregation():
    users, transactions = fixture_frames()
    with pytest.raises(ValueError, match="duplicate.*transaction"):
        build_outcomes(users, pd.concat([transactions, transactions.iloc[:1]]), as_of="2026-05-01T00:00:00Z")


def test_unknown_transaction_user_rejected():
    users, transactions = fixture_frames()
    transactions.loc[0, "user_id"] = "unknown"
    with pytest.raises(ValueError, match="unknown.*user"):
        build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z")


def test_invalid_timestamp_rejected():
    users, transactions = fixture_frames()
    users.loc[0, "install_at"] = "not-a-date"
    with pytest.raises(ValueError, match="install_at"):
        build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z")


def test_compressed_adapter_and_cli_print_reproducible_summary(tmp_path):
    users, transactions = fixture_frames()
    users.to_csv(tmp_path / "users.csv.gz", index=False)
    transactions.to_csv(tmp_path / "transactions.csv.gz", index=False)
    dataset = CsvOfflineDataset(tmp_path)
    assert dataset.users().user_id.tolist() == users.user_id.tolist()
    assert len(dataset.transactions()) == 4
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_from_offline.py",
            "--data-dir",
            str(tmp_path),
            "--as-of",
            "2026-05-01T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["users"] == 4
    assert summary["mean_net_revenue_90d"] == 2.5
    assert summary["as_of"] == "2026-05-01T00:00:00+00:00"
    assert len(summary["sha256"]["users.csv.gz"]) == 64


def test_missing_dataset_has_actionable_error(tmp_path):
    with pytest.raises(ValueError, match="users.csv.gz"):
        CsvOfflineDataset(tmp_path).users()
