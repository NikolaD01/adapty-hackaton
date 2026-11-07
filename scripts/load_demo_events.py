#!/usr/bin/env python3
"""Load synthetic demo events for Lumen seed users through the real API (owner A, task A8).

    python scripts/load_demo_events.py --base http://localhost:8000 --users 1000

Registers Lumen features and event types, then sends events for the first N seed users of
`lumen_dataset.json.gz` (Adapty ids `lumen_<run>_<i:05d>`), consistent with each user's
`ai_edits_first_day`, `photos_imported` and purchases. Every event has `props.synthetic = true`.
Event ids are deterministic (uuid5), so re-running sends duplicates the backend ignores.
Finally calls `values:recompute`.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

APP_ID = "c6c7bdd1-1010-4343-8b29-837a77793cab"
RUN_ID = "282506"
NAMESPACE = uuid.UUID("5f0c3b52-6d7e-4a51-9b7e-7a3c2b1d0e11")
FREE_DAILY_EDITS = 10

FEATURES = [
    {
        "key": "background",
        "name": "Background removal",
        "plans": [],
        "description": "User removes the background of a photo with the AI tool",
    },
    {
        "key": "ai_enhance",
        "name": "AI enhance",
        "plans": [],
        "description": "User improves a photo with AI; the free plan allows a limited number of edits per day",
    },
    {
        "key": "hd_export",
        "name": "Full-resolution export",
        "plans": ["premium"],
        "description": "User exports a photo in full resolution, which only the premium plan includes",
    },
    {
        "key": "photo_import",
        "name": "Photo import",
        "plans": [],
        "description": "User brings photos into the app before editing",
    },
]
EVENT_TYPES = [
    {
        "key": "photo_import",
        "name": "Photo imported",
        "features": ["photo_import"],
        "description": "User imported a photo from the gallery or camera",
    },
    {
        "key": "bg_remove",
        "name": "Background removed",
        "features": ["background"],
        "description": "User removed the background of a photo",
    },
    {
        "key": "ai_enhance",
        "name": "AI enhance applied",
        "features": ["ai_enhance"],
        "description": "User applied an AI enhancement; props.edits_left is the free edits left today",
    },
    {
        "key": "export",
        "name": "Photo exported",
        "features": [],
        "description": "User exported a photo in standard resolution",
    },
    {
        "key": "export_hd_attempt",
        "name": "Full-resolution export tried",
        "features": ["hd_export"],
        "description": "User tapped export in full resolution",
    },
    {
        "key": "pt_track_hd_export_blocked",
        "name": "Full-resolution export blocked",
        "features": ["hd_export"],
        "description": "The plan check blocked a full-resolution export because the user is on the free plan",
    },
    {
        "key": "edit_abandoned",
        "name": "Edit abandoned",
        "features": [],
        "description": "User left the editor without exporting",
    },
]

Post = Callable[[str, dict[str, Any] | None], Any]


def is_paying(user: dict) -> bool:
    return any(not t.get("refunded") for t in user.get("tx") or [])


def user_events(user: dict, run_id: str, now: datetime) -> list[dict]:
    """Synthetic last-7-days history for one seed user. Deterministic per user index."""
    i = int(user["i"])
    rnd = random.Random(f"{run_id}:{i}")
    cuid = f"lumen_{run_id}_{i:05d}"
    attrs = user.get("attrs") or {}
    edits = float(attrs.get("ai_edits_first_day") or 0)
    imports = min(int(float(attrs.get("photos_imported") or 0)), 30)
    paying = is_paying(user)
    out: list[dict] = []

    def add(key: str, at: datetime, **props: Any) -> None:
        n = len(out)
        out.append(
            {
                "event_id": str(uuid.uuid5(NAMESPACE, f"{run_id}:{i}:{n}:{key}")),
                "customer_user_id": cuid,
                "key": key,
                "occurred_at": at.isoformat().replace("+00:00", "Z"),
                "props": {**props, "synthetic": True},
            }
        )

    def moment() -> datetime:
        return now - timedelta(days=rnd.uniform(0, 6.9), minutes=rnd.randint(0, 59))

    photos = [f"p{i}_{k}" for k in range(max(imports, 1))]
    for k in range(imports):
        add("photo_import", moment(), photo_id=photos[k])
    weekly_edits = round(edits * rnd.uniform(1.0, 1.6))
    edits_today: dict[str, int] = {}
    for _ in range(weekly_edits):
        at, photo = moment(), rnd.choice(photos)
        if rnd.random() < 0.4:
            add("bg_remove", at, photo_id=photo)
        else:
            day = at.date().isoformat()
            edits_today[day] = edits_today.get(day, 0) + 1
            left = None if paying else max(FREE_DAILY_EDITS - edits_today[day], 0)
            add("ai_enhance", at, photo_id=photo, **({"edits_left": left} if left is not None else {}))
    for _ in range(round(weekly_edits * rnd.uniform(0.3, 0.7))):
        add("export", moment(), photo_id=rnd.choice(photos))
    if weekly_edits >= 4 and rnd.random() < 0.7:
        for _ in range(rnd.randint(1, 2)):
            at = moment()
            add("export_hd_attempt", at)
            if not paying:
                add("pt_track_hd_export_blocked", at + timedelta(seconds=1))
    for _ in range(rnd.randint(0, 2)):
        add("edit_abandoned", moment())
    return out


def load(
    post: Post, users: list[dict], app_id: str = APP_ID, run_id: str = RUN_ID, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    base = f"/v1/apps/{app_id}"
    for f in FEATURES:
        post(f"{base}/features", f)
    for e in EVENT_TYPES:
        post(f"{base}/event-types", e)
    events = [ev for u in users for ev in user_events(u, run_id, now)]
    accepted = duplicates = 0
    for start in range(0, len(events), 500):
        r = post(f"{base}/events", {"events": events[start : start + 500]})
        accepted, duplicates = accepted + r["accepted"], duplicates + r["duplicates"]
    recompute = post(f"{base}/values:recompute", None)
    return {
        "users": len(users),
        "events": len(events),
        "accepted": accepted,
        "duplicates": duplicates,
        "recompute": recompute,
    }


def read_users(path: Path, limit: int) -> list[dict]:
    with gzip.open(path, "rt") as fh:
        return json.load(fh)["users"][:limit]


def main() -> None:
    import httpx

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--users", type=int, default=1000)  # 200 is too few: the first 200 invert the edits signal
    p.add_argument("--dataset", type=Path, default=Path("data/lumen_dataset.json.gz"))
    p.add_argument("--app-id", default=APP_ID)
    p.add_argument("--run-id", default=RUN_ID)
    args = p.parse_args()
    if not args.dataset.exists():
        raise SystemExit(f"{args.dataset} not found: run `make offline-data` first")
    with httpx.Client(base_url=args.base, timeout=60) as client:

        def post(path: str, body: dict | None) -> Any:
            r = client.post(path, json=body)
            r.raise_for_status()
            return r.json()

        print(json.dumps(load(post, read_users(args.dataset, args.users), args.app_id, args.run_id), indent=2))


if __name__ == "__main__":
    main()
