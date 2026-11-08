"""Composition of B (the brain) for the running app, supplied by C as B's docs ask.

B needs three app-specific facts it must not guess: an explicit cutoff, the proposal sink and the verified
published flows.
- Flows come from Adapty itself (`flows list`, matched by name), with their real published state, never from a
  hard-coded id.
- The cutoff, the 30-day outcome window and the identity/rule assertions below are DEMO settings for the synthetic
  seed data (`lumen_282506_NNNNN`, 5000 users): the live rules named here are asserted to be comparable with the
  seed outcomes. They must not be reused for another dataset.
Nothing here runs inside `create_app()`; `main.py` calls `wire_brain` for the running app only.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any

from feature_signal.core.config import Settings
from feature_signal.services.insight_service import PublishedFlow

log = logging.getLogger(__name__)

DEMO_APP_ID = "c6c7bdd1-1010-4343-8b29-837a77793cab"  # the id the demo data, scripts and web use
AS_OF = "2026-11-08T00:00:00Z"  # arithmetic anchor of the seed dataset's relative clock (B, chapter 09)
OUTCOME_WINDOW_DAYS = 60  # decided by the team on 2026-11-08, see docs/brain/10-outcome-window.md
SEED_RUN = "282506"
SEED_USERS = 5000
LIVE_OUTCOME_RULES = frozenset(
    {"ai_enhance_uses_7d", "background_uses_7d", "hd_export_uses_7d", "photo_import_uses_7d"}
)
# B's arm names (the dataset's `flow` values) -> the flow names in the Adapty app
FLOW_NAMES = {
    "main_lifetime": "Main - Lifetime anchor",
    "main": "Main - 3 plans",
    "onb_trial": "Onboarding - Annual trial",
    "onb_weekly": "Onboarding - Weekly first",
    "settings": "Settings - Upgrade",
}


def published_flows_from_listing(listing: list[dict[str, Any]]) -> dict[str, PublishedFlow]:
    by_name = {item.get("name"): item for item in listing if isinstance(item, dict)}
    flows: dict[str, PublishedFlow] = {}
    for arm, name in FLOW_NAMES.items():
        item = by_name.get(name)
        if item and item.get("id"):
            flows[arm] = PublishedFlow(item["id"], name, item.get("status") == "published")
        else:
            log.warning("Adapty has no flow named %r; arm %s cannot be offered", name, arm)
    return flows


def list_flows(settings: Settings, timeout: float = 30.0) -> list[dict[str, Any]] | None:
    """`adapty flows list` of the configured app, or None when the CLI is missing or not logged in."""
    argv = [
        *shlex.split(settings.adapty_cli),
        "flows",
        "list",
        "--app",
        settings.adapty_app_id,
        "--page-size",
        "100",
        "--json",
    ]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        log.warning("Could not run the Adapty CLI; the brain stays unconfigured")
        return None
    if done.returncode != 0:
        log.warning("`adapty flows list` failed (exit %s); the brain stays unconfigured", done.returncode)
        return None
    try:
        return list(json.loads(done.stdout).get("data") or [])
    except (ValueError, AttributeError):
        return None


def configure_demo_brain(app: Any, settings: Settings, *, listing: list[dict[str, Any]] | None) -> bool:
    """Register B's runtime for the demo app id (and the Adapty app id if it differs). False = not configured."""
    from feature_signal.api.v1.insights import BrainRuntime, configure_brain
    from feature_signal.integrations.offline import SeedJsonDataset
    from feature_signal.services.proposal_service import ProposalService

    flows = published_flows_from_listing(listing) if listing else {}
    if not flows:
        return False
    dataset_path = Path(settings.offline_data_dir).parent / "lumen_dataset.json.gz"
    live_dataset = (
        SeedJsonDataset(dataset_path, as_of=AS_OF, run_id=SEED_RUN, limit=SEED_USERS) if dataset_path.exists() else None
    )
    ids = {f"lumen_{SEED_RUN}_{i:05d}": f"lumen_{SEED_RUN}_{i:05d}" for i in range(SEED_USERS)}
    runtime = BrainRuntime(
        as_of=AS_OF,
        proposal_sink_factory=lambda session: ProposalService(session),
        published_flows=flows,
        live_dataset=live_dataset,
        user_id_map=ids,
        live_outcome_rules=LIVE_OUTCOME_RULES if live_dataset else frozenset(),
        explain=bool(settings.openai_api_key.get_secret_value()),
        outcome_window_days=OUTCOME_WINDOW_DAYS,
    )
    for app_id in dict.fromkeys([DEMO_APP_ID, settings.adapty_app_id]):
        configure_brain(app, app_id, runtime)
    return True
