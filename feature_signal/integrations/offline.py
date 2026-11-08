"""Offline CSV input and fixed-window accounting (Brain ownership)."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd


class CsvOfflineDataset:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def _read(self, name: str) -> pd.DataFrame:
        path = self.data_dir / name
        try:
            return pd.read_csv(path, dtype={"user_id": str})
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read offline dataset {path}: {exc}") from exc

    def users(self) -> pd.DataFrame:
        return self._read("users.csv.gz")

    def transactions(self) -> pd.DataFrame:
        return self._read("transactions.csv.gz")

    def fingerprints(self) -> dict[str, str]:
        result = {}
        for name in ("users.csv.gz", "transactions.csv.gz"):
            digest = hashlib.sha256()
            with (self.data_dir / name).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[name] = digest.hexdigest()
        return result


class SeedJsonDataset:
    """Adapt the relative-clock Lumen seed export without inventing an export date.

    ``as_of`` anchors dataset offset zero for arithmetic only. Pass the same anchor
    to ``build_outcomes``; its choice does not change maturity or revenue.
    """

    _RESERVED_ATTRS = {
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
        "ab_test",
        "flow",
        "placement",
        "platform",
        "country",
        "country_tier",
        "subscription_state",
        "currency",
        "device",
        "locale",
        "os",
        "timezone",
    }

    def __init__(
        self,
        path: str | Path,
        *,
        as_of: str | datetime,
        run_id: str = "282506",
        limit: int = 1000,
    ) -> None:
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be a positive integer")
        if not isinstance(run_id, str) or not run_id.isascii() or not run_id.isdecimal():
            raise ValueError("run_id must be a nonempty string of decimal digits")
        if not isinstance(as_of, (str, datetime)):
            raise ValueError("as_of must be an explicit datetime anchor")
        try:
            anchor = pd.to_datetime(as_of, utc=True, errors="raise")
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("as_of must be an explicit datetime anchor") from exc
        if pd.isna(anchor):
            raise ValueError("as_of must be an explicit datetime anchor")
        self.path = Path(path)
        self.as_of = anchor
        self.run_id = run_id
        self.limit = limit
        self._frames: tuple[pd.DataFrame, pd.DataFrame] | None = None

    @property
    def provenance(self) -> dict[str, str | int | bool]:
        return {
            "dataset_format": "seed_json",
            "time_basis": "relative_to_dataset_now",
            "run_id": self.run_id,
            "user_limit": self.limit,
            "synthetic": True,
        }

    @staticmethod
    def _number(value: object, name: str) -> int | float:
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"{name} must be a finite JSON number, not a boolean or string")
        return value

    def _timestamp(self, offset: object, name: str) -> pd.Timestamp:
        number = self._number(offset, name)
        try:
            return self.as_of + pd.to_timedelta(number, unit="s")
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"{name} offset is outside the supported timestamp range") from exc

    def _load(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self._frames is not None:
            return self._frames
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, EOFError) as exc:
            raise ValueError(f"Cannot read seed dataset {self.path}: {exc}") from exc
        if (
            not isinstance(payload, dict)
            or type(payload.get("version")) is not int
            or payload["version"] != 1
            or payload.get("app") != "lumen"
            or type(payload.get("days")) is not int
            or payload["days"] <= 0
            or not isinstance(payload.get("users"), list)
        ):
            raise ValueError("seed dataset requires version 1, app lumen, positive days, and a users list")

        users, transactions, indices = [], [], set()
        for position, user in enumerate(payload["users"]):
            if not isinstance(user, dict):
                raise ValueError("seed user must be an object")
            index = user.get("i")
            if type(index) is not int or index < 0:
                raise ValueError("seed user index must be a nonnegative integer")
            if index in indices:
                raise ValueError("duplicate seed user index")
            indices.add(index)
            if not isinstance(user.get("attrs"), dict) or not isinstance(user.get("tx"), list):
                raise ValueError("seed user requires attrs object and tx list")
            collisions = user["attrs"].keys() & (self._RESERVED_ATTRS | user.keys())
            if collisions:
                raise ValueError(f"seed attrs contain reserved keys: {', '.join(sorted(collisions))}")
            if any(isinstance(value, (dict, list)) for value in user["attrs"].values()):
                raise ValueError("seed attrs must contain only JSON scalar values")
            install = self._timestamp(user.get("install"), "install")
            user_id = f"lumen_{self.run_id}_{index:05d}"
            row = {key: value for key, value in user.items() if key not in {"i", "install", "attrs", "tx"}}
            row.update(user["attrs"])
            row.update(user_id=user_id, install_at=install)
            if position < self.limit:
                users.append(row)
            for seq, transaction in enumerate(user["tx"]):
                if not isinstance(transaction, dict) or "refunded" not in transaction:
                    raise ValueError("seed transaction requires an object with t, usd, and refunded")
                purchased = self._timestamp(transaction.get("t"), "t")
                price = self._number(transaction.get("usd"), "usd")
                if price < 0:
                    raise ValueError("usd must be nonnegative")
                refund = transaction["refunded"]
                refunded = None if refund is None else self._timestamp(refund, "refunded")
                if position < self.limit:
                    transactions.append(
                        {
                            "user_id": user_id,
                            "seq": seq,
                            "purchased_at": purchased,
                            "price_usd": price,
                            "refunded_at": refunded,
                        }
                    )
        user_frame = pd.DataFrame(users) if users else pd.DataFrame(columns=["user_id", "install_at"])
        transaction_frame = pd.DataFrame(
            transactions, columns=["user_id", "seq", "purchased_at", "price_usd", "refunded_at"]
        )
        self._frames = user_frame, transaction_frame
        return self._frames

    def users(self) -> pd.DataFrame:
        return self._load()[0].copy()

    def transactions(self) -> pd.DataFrame:
        return self._load()[1].copy()

    def fingerprints(self) -> dict[str, str]:
        digest = hashlib.sha256()
        try:
            with self.path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ValueError(f"Cannot read seed dataset {self.path}: {exc}") from exc
        return {self.path.name: digest.hexdigest()}


def _required(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {', '.join(sorted(missing))}")
    if frame.user_id.isna().any() or frame.user_id.astype(str).str.strip().eq("").any():
        raise ValueError(f"{name} contains an empty user_id")


def _dates(values: pd.Series, name: str, *, nullable: bool = False) -> pd.Series:
    try:
        parsed = pd.to_datetime(values.replace("", None), format="mixed", utc=True, errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {name} timestamp") from exc
    if not nullable and parsed.isna().any():
        raise ValueError(f"Missing {name} timestamp")
    return parsed


def build_outcomes(
    users: pd.DataFrame,
    transactions: pd.DataFrame,
    *,
    as_of: str | datetime,
    window_days: int = 90,
) -> pd.DataFrame:
    """One mature user per row, including nonpayers; refunds known by as_of contribute zero.

    Purchases use [install, install + window_days), 90 by default. A user is mature once the whole window has passed.
    Refunds marked in the export are excluded once observed, including refunds after the purchase window. This
    follows the role brief's non-refunded-purchase definition, not cash-flow LTV. The `*_90d` column names are
    historical; the real window is `window_days` and is recorded in `attrs["outcome_window_days"]`.
    """
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 365:
        raise ValueError("window_days must be a whole number of days between 1 and 365")
    window_length = pd.Timedelta(days=window_days)
    _required(users, {"user_id", "install_at"}, "users")
    _required(transactions, {"user_id", "purchased_at", "price_usd", "refunded_at"}, "transactions")
    users, transactions = users.copy(), transactions.copy()
    if users.user_id.duplicated().any():
        raise ValueError("duplicate user_id in users")
    if "seq" in transactions and transactions.duplicated(["user_id", "seq"]).any():
        raise ValueError("duplicate transaction (user_id, seq)")
    if not transactions.user_id.isin(users.user_id).all():
        raise ValueError("transactions contain unknown user_id")
    cutoff = pd.to_datetime(as_of, utc=True, errors="raise")
    if pd.isna(cutoff):
        raise ValueError("as_of must be an explicit observation cutoff")
    users["install_at"] = _dates(users.install_at, "install_at")
    for column in ("ai_edits_first_day", "photos_imported"):
        if column in users:
            users[column] = pd.to_numeric(users[column], errors="raise")
    transactions["purchased_at"] = _dates(transactions.purchased_at, "purchased_at")
    transactions["refunded_at"] = _dates(transactions.refunded_at, "refunded_at", nullable=True)
    try:
        transactions["price_usd"] = pd.to_numeric(transactions.price_usd, errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError("price_usd must be finite and nonnegative") from exc
    if not transactions.price_usd.map(math.isfinite).all() or (transactions.price_usd < 0).any():
        raise ValueError("price_usd must be finite and nonnegative")

    mature = users.loc[users.install_at + window_length <= cutoff].copy()
    joined = transactions.merge(mature[["user_id", "install_at"]], on="user_id", validate="many_to_one")
    window = joined.loc[
        (joined.purchased_at >= joined.install_at) & (joined.purchased_at < joined.install_at + window_length)
    ].copy()
    refunded = window.refunded_at.notna() & (window.refunded_at <= cutoff)
    paid = window.price_usd > 0
    aggregates = {
        "net_revenue_90d": window.loc[~refunded].groupby("user_id").price_usd.sum(),
        "paid_transactions_90d": window.loc[paid].groupby("user_id").size(),
        "refunded_transactions_90d": window.loc[paid & refunded].groupby("user_id").size(),
    }
    for name, values in aggregates.items():
        mature[name] = mature.user_id.map(values).fillna(0).astype(float if name == "net_revenue_90d" else int)
    mature = mature.sort_values("user_id").reset_index(drop=True)
    mature.attrs.update(as_of=cutoff.isoformat(), outcome_window_days=window_days, synthetic=True)
    return mature
