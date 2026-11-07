"""C8 - a draft paywall for a proposal: a copy of the live flow config with a new title.

Safe on purpose: we copy the config of the flow the proposal points at (a published, working flow), change only the
title text at one known place and upload the copy as a NEW draft flow. Nothing is published (a human does that in
Adapty, then approves the proposal again) and a feature the offered plan does not include is refused, so a paywall never
promises what the plan does not give. The title comes from the request; this service calls no model.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.integrations.adapty.cli import AdaptyCommands
from feature_signal.repositories.features import FeatureRepository
from feature_signal.schemas.proposals import PaywallDraftIn, PaywallDraftOut
from feature_signal.services.proposal_service import ProposalService

MAX_CONFIG_BYTES = 1_000_000


def _screen(config: dict[str, Any]) -> dict[str, Any]:
    screens = config.get("screens")
    if not screens or not isinstance(screens[0], dict):
        raise ApiError(422, "flow_has_no_screen", "The flow config has no screen to copy")
    return screens[0]


def screen_product_ids(config: dict[str, Any]) -> list[str]:
    return [p["id"] for p in _screen(config).get("products") or [] if isinstance(p, dict) and p.get("id")]


def find_title(config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """The first non-empty text element of the first screen (element ids ending in `T`), in the default locale."""
    locale = config.get("defaultLocale") or "en"
    for key, element in (_screen(config).get("elements") or {}).get("map", {}).items():
        if not key.endswith("T"):
            continue
        try:
            part = element["props"]["content"]["values"][locale][0]["content"][0]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
            path = f"screens[0].elements.map.{key}.props.content.values.{locale}[0].content[0].text"
            return part, path
    raise ApiError(422, "no_title_element", "Could not find a title text on the flow's first screen")


class PaywallService:
    def __init__(self, session: AsyncSession, commands: AdaptyCommands) -> None:
        self._session = session
        self._commands = commands
        self._proposals = ProposalService(session)

    async def draft(self, proposal_id: str, body: PaywallDraftIn) -> PaywallDraftOut:
        row = await self._proposals._get(proposal_id)
        if row.status != "draft":
            raise ApiError(
                409,
                "proposal_not_editable",
                "A paywall draft can only be made for a draft proposal",
                {"status": row.status},
            )
        base_flow_id = row.action["flow_id"]

        read = await self._commands.flows_config_get(base_flow_id)
        base = read.get("config")
        if not isinstance(base, dict):
            raise ApiError(422, "flow_has_no_config", "The flow has no config to copy", {"flow_id": base_flow_id})

        on_screen = screen_product_ids(base)
        offered = list(body.product_ids) or on_screen
        unknown = [p for p in offered if p not in on_screen]
        if unknown:
            raise ApiError(
                422, "product_not_in_flow", "These products are not on the flow's screen", {"product_ids": unknown}
            )

        feature_key = body.highlight_feature or row.action.get("highlight_feature")
        if feature_key:
            await self._check_plan(row.app_id, feature_key, offered)

        config = copy.deepcopy(base)
        part, path = find_title(config)
        part["text"] = body.title
        if set(config) != set(base) or len(json.dumps(config)) > MAX_CONFIG_BYTES:
            raise ApiError(422, "invalid_flow_config", "The edited config is not valid")

        draft = await self._commands.flows_create(f"[fs] {row.segment_key} {row.proposal_id}")
        draft_id = draft.get("id")
        if not draft_id:
            raise ApiError(502, "adapty_cli_bad_output", "Adapty did not return the new flow id")
        await self._commands.flows_config_update(draft_id, config)

        now = datetime.now(timezone.utc)
        row.edits = [
            *(row.edits or []),
            {"at": now.isoformat(), "field": "flow_id", "from": base_flow_id, "to": draft_id},
        ]
        row.action = {
            **row.action,
            "flow_id": draft_id,
            "flow_name": f"[fs] {row.segment_key}",
            "needs_publish": True,
            "highlight_feature": feature_key,
        }
        row.updated_at = now
        await self._session.commit()
        return PaywallDraftOut(base_flow_id=base_flow_id, draft_flow_id=draft_id, status="draft", changed_paths=[path])

    async def _check_plan(self, app_id: str, feature_key: str, offered: list[str]) -> None:
        feature = next((f for f in await FeatureRepository(self._session).rows(app_id) if f.key == feature_key), None)
        if feature is None:
            raise ApiError(422, "unknown_feature", f"No feature '{feature_key}'")
        by_id = {p["id"]: p for p in await self._commands.products_list()}
        identifiers = {i for pid in offered for i in (pid, (by_id.get(pid) or {}).get("access_level_id")) if i}
        if not identifiers & set(feature.plans or []):
            raise ApiError(
                422,
                "feature_not_in_plan",
                f"The offered plan does not include '{feature_key}', so the paywall must not promise it",
                {"feature": feature_key, "plans": list(feature.plans or [])},
            )
