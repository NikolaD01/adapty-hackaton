"""Reproduce Brain outcomes from the synthetic offline snapshot without network calls."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from feature_signal.core.config import get_settings
from feature_signal.domain.models import Condition, FeatureMatrix, SegmentCandidate
from feature_signal.domain.ranking import build_segments, derive_tiers, rank
from feature_signal.domain.uplift import by_segment, refund_diagnostics
from feature_signal.integrations.offline import CsvOfflineDataset, SeedJsonDataset, build_outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--data-dir", help="Folder containing users.csv.gz and transactions.csv.gz")
    source.add_argument("--seed-json", help="Path to lumen_dataset.json.gz (relative dataset clock)")
    parser.add_argument("--users", type=int, default=1000, help="Seed JSON user limit; default 1000")
    parser.add_argument(
        "--as-of", required=True, help="Observation cutoff; arithmetic dataset-now anchor for seed JSON"
    )
    parser.add_argument(
        "--analysis", action="store_true", help="Include ranking, tiers, segments and randomized uplift"
    )
    args = parser.parse_args()
    if not args.seed_json and args.users != 1000:
        parser.error("--users requires --seed-json")
    try:
        dataset = (
            SeedJsonDataset(args.seed_json, as_of=args.as_of, limit=args.users)
            if args.seed_json
            else CsvOfflineDataset(args.data_dir or get_settings().offline_data_dir)
        )
        frame = build_outcomes(dataset.users(), dataset.transactions(), as_of=args.as_of)
        summary = {
            "source": "synthetic_seed" if args.seed_json else "synthetic_offline",
            "as_of": frame.attrs["as_of"],
            "outcome_window_days": 90,
            "users": len(frame),
            "mean_net_revenue_90d": float(frame.net_revenue_90d.mean()) if len(frame) else 0.0,
            "sha256": dataset.fingerprints(),
            "provenance": dict(getattr(dataset, "provenance", {})),
        }
        if args.analysis:
            columns = [key for key in ("ai_edits_first_day", "photos_imported") if key in frame]
            matrix = FeatureMatrix(frame.user_id.tolist(), columns, frame[columns].values.tolist())
            outcomes = frame.set_index("user_id").net_revenue_90d.to_dict()
            rankings = rank(matrix, outcomes)
            # CLI diagnostics use explicit historical column identities, never live-rule aliases.
            tiers = derive_tiers(matrix, outcomes, rankings, {key: key for key in columns})
            segments = build_segments(frame, tiers)
            effects = by_segment(frame, segments) if segments else []
            summary.update(
                rankings=[asdict(item) for item in rankings],
                tiers=[asdict(item) for item in tiers],
                segments=[asdict(item) for item in segments],
                uplift=[
                    {
                        **asdict(item),
                        "refunds": refund_diagnostics(
                            frame,
                            next(segment for segment in segments if segment.segment_key == item.segment_key),
                            item.test,
                        ),
                    }
                    for item in effects
                ],
            )
            if "ai_edits_first_day" in frame:
                checks = [
                    SegmentCandidate(key, key, [Condition("ai_edits_first_day", op, value)], 0, 0, 0, 0)
                    for key, op, value in (("edits_5_plus", ">=", 5), ("edits_zero", "==", 0))
                ]
                summary["fixed_window_reference_checks"] = [
                    {
                        **asdict(item),
                        "refunds": refund_diagnostics(
                            frame,
                            next(check for check in checks if check.segment_key == item.segment_key),
                            item.test,
                        ),
                    }
                    for item in by_segment(frame, checks)
                ]
    except (ValueError, OSError) as exc:
        print(f"Offline analysis failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
