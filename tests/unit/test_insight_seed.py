"""Relative-clock Lumen seed inputs reuse the fixed 90-day outcome accounting."""

import gzip
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd
import pytest

from feature_signal.integrations import offline
from feature_signal.integrations.offline import build_outcomes

DAY = 86400
AS_OF = "2026-05-01T00:00:00Z"


def seed_user(index, *, install=-100 * DAY, tx=None):
    return {
        "i": index,
        "install": install,
        "attrs": {"ai_edits_first_day": 5, "photos_imported": 12, "onboarding_goal": "edit"},
        "platform": "ios",
        "country": "US",
        "placement": "onboarding",
        "flow": "weekly",
        "ab_test": "randomized-test",
        "tx": tx or [],
    }


def seed_tx(offset, usd=10, refunded=None):
    return {"t": offset, "usd": usd, "refunded": refunded}


def write_seed(tmp_path, users=None, **overrides):
    payload = {"version": 1, "app": "lumen", "days": 120, "users": users or []}
    payload.update(overrides)
    path = tmp_path / "lumen_dataset.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)
    return path


def dataset(path, **kwargs):
    # A missing adapter produces an assertion failure during the initial RED run.
    assert hasattr(offline, "SeedJsonDataset"), "SeedJsonDataset adapter is not implemented"
    return offline.SeedJsonDataset(path, as_of=kwargs.pop("as_of", AS_OF), **kwargs)


def test_seed_outcomes_keep_zero_payers_maturity_and_exclusive_purchase_bounds(tmp_path):
    path = write_seed(
        tmp_path,
        [
            seed_user(
                0,
                tx=[
                    seed_tx(-100 * DAY - 1, 99),  # Before install.
                    seed_tx(-100 * DAY, 10),
                    seed_tx(-10 * DAY - 1, 20),
                    seed_tx(-10 * DAY, 99),  # Exactly 90 days after install.
                ],
            ),
            seed_user(1),
            seed_user(2, install=-90 * DAY),
            seed_user(3, install=-90 * DAY + 1, tx=[seed_tx(-DAY, 99)]),
        ],
    )
    source = dataset(path)
    result = build_outcomes(source.users(), source.transactions(), as_of=AS_OF).set_index("user_id")
    assert result.net_revenue_90d.to_dict() == {
        "lumen_282506_00000": 30,
        "lumen_282506_00001": 0,
        "lumen_282506_00002": 0,
    }
    assert result.loc["lumen_282506_00000", "paid_transactions_90d"] == 2


def test_seed_refund_zero_is_observed_and_future_refund_is_not(tmp_path):
    path = write_seed(
        tmp_path,
        [seed_user(7, install=-90 * DAY, tx=[seed_tx(-DAY, 8, 0), seed_tx(-DAY, 9, 1)])],
    )
    source = dataset(path)
    result = build_outcomes(source.users(), source.transactions(), as_of=AS_OF).iloc[0]
    assert result.net_revenue_90d == 9
    assert result.paid_transactions_90d == 2
    assert result.refunded_transactions_90d == 1
    assert source.transactions().seq.tolist() == [0, 1]
    assert source.transactions().refunded_at.iloc[0] == pd.Timestamp(AS_OF)


def test_seed_preserves_attributes_metadata_and_returns_independent_frames(tmp_path):
    payload = seed_user(42, tx=[seed_tx(-DAY)])
    original = deepcopy(payload)
    source = dataset(write_seed(tmp_path, [payload]), run_id="123456")
    users = source.users()
    assert users.user_id.tolist() == ["lumen_123456_00042"]
    assert users.loc[0, "ai_edits_first_day"] == 5
    assert users.loc[0, "photos_imported"] == 12
    assert users.loc[0, "onboarding_goal"] == "edit"
    for key in ("platform", "country", "placement", "flow", "ab_test"):
        assert users.loc[0, key] == payload[key]
    assert users.install_at.iloc[0] == pd.Timestamp(AS_OF) - pd.Timedelta(days=100)
    users.loc[0, "ai_edits_first_day"] = 999
    transactions = source.transactions()
    transactions.loc[0, "price_usd"] = 999
    assert source.users().loc[0, "ai_edits_first_day"] == 5
    assert source.transactions().loc[0, "price_usd"] == 10
    assert payload == original


@pytest.mark.parametrize("field", ["ab_test", "flow", "placement", "platform", "country"])
@pytest.mark.parametrize("native_field_present", [True, False])
def test_seed_rejects_attrs_that_override_or_manufacture_assignment(tmp_path, field, native_field_present):
    user = seed_user(0)
    if not native_field_present:
        user.pop(field)
    user["attrs"][field] = "forged-assignment"
    with pytest.raises(ValueError, match=f"attrs.*reserved.*{field}"):
        dataset(write_seed(tmp_path, [user])).users()


@pytest.mark.parametrize(
    "field",
    [
        "i",
        "index",
        "install",
        "attrs",
        "tx",
        "user_id",
        "install_at",
        "seq",
        "purchased_at",
        "price_usd",
        "refunded_at",
        "net_revenue_90d",
        "paid_transactions_90d",
        "refunded_transactions_90d",
        "currency",
        "country_tier",
        "subscription_state",
        "device",
        "locale",
        "os",
        "timezone",
    ],
)
def test_seed_rejects_reserved_identity_outcome_and_native_metadata_attrs(tmp_path, field):
    user = seed_user(0)
    user["attrs"][field] = "forged-value"
    with pytest.raises(ValueError, match=f"attrs.*reserved.*{field}"):
        dataset(write_seed(tmp_path, [user])).users()


@pytest.mark.parametrize("value", [["edit"], {"goal": "edit"}])
def test_seed_rejects_nested_attrs_that_would_share_mutable_frame_values(tmp_path, value):
    user = seed_user(0)
    user["attrs"]["labels"] = value
    with pytest.raises(ValueError, match="attrs.*scalar"):
        dataset(write_seed(tmp_path, [user])).users()


def test_seed_default_limit_selects_first_1000_and_keeps_source_indices(tmp_path):
    source = dataset(write_seed(tmp_path, [seed_user(i + 20) for i in range(1001)]))
    assert len(source.users()) == 1000
    assert source.users().user_id.iloc[[0, -1]].tolist() == ["lumen_282506_00020", "lumen_282506_01019"]
    assert len(dataset(source.path, limit=1001).users()) == 1001


def test_seed_empty_transactions_and_empty_users_keep_required_columns(tmp_path):
    path = write_seed(tmp_path, [seed_user(0)])
    source = dataset(path)
    assert {"user_id", "seq", "purchased_at", "price_usd", "refunded_at"} <= set(source.transactions())
    assert build_outcomes(source.users(), source.transactions(), as_of=AS_OF).net_revenue_90d.tolist() == [0]
    empty = dataset(write_seed(tmp_path))
    assert build_outcomes(empty.users(), empty.transactions(), as_of=AS_OF).empty


def test_seed_anchor_changes_dates_without_changing_maturity_or_revenue(tmp_path):
    path = write_seed(tmp_path, [seed_user(0, tx=[seed_tx(-DAY, refunded=0)]), seed_user(1)])
    first = dataset(path)
    second_anchor = datetime(2030, 1, 1, tzinfo=timezone.utc)
    second = dataset(path, as_of=second_anchor)
    columns = ["user_id", "net_revenue_90d", "paid_transactions_90d", "refunded_transactions_90d"]
    pd.testing.assert_frame_equal(
        build_outcomes(first.users(), first.transactions(), as_of=AS_OF)[columns],
        build_outcomes(second.users(), second.transactions(), as_of=second_anchor)[columns],
    )
    assert first.users().install_at.iloc[0] != second.users().install_at.iloc[0]


def test_seed_provenance_and_sha256_describe_relative_synthetic_source(tmp_path):
    path = write_seed(tmp_path, [seed_user(0)])
    source = dataset(path)
    assert source.provenance == {
        "dataset_format": "seed_json",
        "time_basis": "relative_to_dataset_now",
        "run_id": "282506",
        "user_limit": 1000,
        "synthetic": True,
    }
    source.provenance["run_id"] = "changed"
    assert source.provenance["run_id"] == "282506"
    assert source.fingerprints() == {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"limit": 1.5},
        {"run_id": ""},
        {"run_id": "run_1"},
        {"run_id": 123},
        {"as_of": None},
        {"as_of": "bad-date"},
        {"as_of": 0},
    ],
)
def test_seed_rejects_invalid_options(tmp_path, kwargs):
    with pytest.raises(ValueError):
        dataset(write_seed(tmp_path), **kwargs).users()


@pytest.mark.parametrize("field", ["install", "t", "refunded", "usd"])
@pytest.mark.parametrize("value", [True, "1.0", float("nan"), float("inf"), {}, 10**1000])
def test_seed_rejects_invalid_numeric_fields(tmp_path, field, value):
    user = seed_user(0, tx=[seed_tx(-DAY)])
    (user if field == "install" else user["tx"][0])[field] = value
    with pytest.raises(ValueError, match=field):
        dataset(write_seed(tmp_path, [user])).users()


@pytest.mark.parametrize("index", [True, -1, 1.5, "0", None])
def test_seed_rejects_invalid_user_indices(tmp_path, index):
    with pytest.raises(ValueError, match="index"):
        dataset(write_seed(tmp_path, [seed_user(index)])).users()


def test_seed_rejects_duplicate_user_indices(tmp_path):
    with pytest.raises(ValueError, match="duplicate.*index"):
        dataset(write_seed(tmp_path, [seed_user(0), seed_user(0)])).users()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"version": 2},
        {"version": 1, "app": "other", "days": 120, "users": []},
        {"version": True, "app": "lumen", "days": 120, "users": []},
        {"version": 1, "app": "lumen", "days": 120, "users": {}},
        {"version": 1, "app": "lumen", "days": 120, "users": [None]},
    ],
)
def test_seed_rejects_invalid_structure(tmp_path, payload):
    path = tmp_path / "lumen_dataset.json.gz"
    with gzip.open(path, "wt") as stream:
        json.dump(payload, stream)
    with pytest.raises(ValueError):
        dataset(path).users()


@pytest.mark.parametrize("field,value", [("attrs", []), ("tx", {}), ("tx", [None])])
def test_seed_rejects_invalid_user_structure(tmp_path, field, value):
    user = seed_user(0)
    user[field] = value
    with pytest.raises(ValueError):
        dataset(write_seed(tmp_path, [user])).users()


def test_seed_rejects_missing_transaction_fields_and_negative_price(tmp_path):
    for tx in ({"t": -DAY, "usd": 1}, seed_tx(-DAY, -1)):
        with pytest.raises(ValueError):
            dataset(write_seed(tmp_path, [seed_user(0, tx=[tx])])).transactions()


def test_seed_missing_file_and_malformed_json_have_actionable_errors(tmp_path):
    missing = tmp_path / "missing.json.gz"
    with pytest.raises(ValueError, match="missing.json.gz"):
        dataset(missing).users()
    with pytest.raises(ValueError, match="missing.json.gz"):
        dataset(missing).fingerprints()
    path = tmp_path / "broken.json.gz"
    with gzip.open(path, "wt") as stream:
        stream.write("{invalid")
    with pytest.raises(ValueError, match="broken.json.gz"):
        dataset(path).users()
