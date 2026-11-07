"""C2 - Adapty CLI adapter.

`SubprocessAdaptyCli` implements the `AdaptyCli` port: it runs `adapty ... --json` as a subprocess (never
through a shell) and returns the parsed JSON. `AdaptyCommands` is a thin typed layer on top with the
commands activation needs. It checks what the CLI itself does not: an empty filter list, a placement update
without `--developer-id`, audiences without a default last, A/B weights that do not sum to 100, and a flow
publish nobody confirmed.

Facts (CLAUDE.md section 5): segments cannot be deleted from the CLI; `placements update` replaces every
audience, so the full list is always sent; `ab-tests start` cannot be undone; a flow must be published
before it goes on an audience.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import Condition

Runner = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]

PAGE_SIZE = 100
ALLOWED_OPERATORS = frozenset({"IN", "NOT IN", ">", ">=", "<", "<=", "BETWEEN", "IS NULL", "IS NOT NULL"})
NO_VALUE_OPERATORS = frozenset({"IS NULL", "IS NOT NULL"})


async def _run_process(argv: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ApiError(502, "adapty_cli_missing", f"Cannot run '{argv[0]}': not found", {"binary": argv[0]}) from exc
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError as exc:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()
        raise ApiError(504, "adapty_cli_timeout", f"Adapty CLI did not answer in {timeout:g}s") from exc
    return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


class SubprocessAdaptyCli:
    """Runs the Adapty CLI. `prefix` is `Settings.adapty_cli` (e.g. `adapty` or a docker compose command)."""

    def __init__(self, prefix: str = "adapty", *, timeout: float = 60.0, runner: Runner = _run_process) -> None:
        self._prefix = shlex.split(prefix)
        if not self._prefix:
            raise ValueError("The Adapty CLI command must not be empty")
        self._timeout = timeout
        self._runner = runner

    async def run(self, *args: str) -> dict[str, Any]:
        argv = [*self._prefix, *args]
        if "--json" not in argv:
            argv.append("--json")
        command = " ".join(args[:2])
        rc, stdout, stderr = await self._runner(argv, self._timeout)
        if rc != 0:
            raise ApiError(
                502,
                "adapty_cli_failed",
                f"Adapty CLI '{command}' failed (exit {rc})",
                {"command": command, "exit_code": rc, "stderr": stderr.strip()[:500]},
            )
        text = stdout.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiError(
                502,
                "adapty_cli_bad_output",
                f"Adapty CLI '{command}' did not return JSON",
                {"command": command, "stdout": text[:300]},
            ) from exc
        return parsed if isinstance(parsed, dict) else {"data": parsed}


def custom_attribute_filter(key: str, values: Sequence[str]) -> str:
    """`attributes__<key>@string:IN:a,b` - the only way Adapty filters on a custom attribute."""
    return f"attributes__{key}@string:IN:{','.join(values)}"


def condition_to_filter(condition: Condition) -> str:
    """Turn a proposal's `adapty_filters` entry into a `--filter` argument."""
    op = condition.op.upper()
    if op not in ALLOWED_OPERATORS:
        raise ApiError(
            422,
            "invalid_filter",
            f"Operator '{condition.op}' is not an Adapty segment operator",
            {"field": condition.field},
        )
    if op in NO_VALUE_OPERATORS:
        return f"{condition.field}:{op}"
    values = condition.value if isinstance(condition.value, list | tuple) else [condition.value]
    if any("," in str(v) for v in values):
        return json.dumps({"field_name": condition.field, "operator": op, "value_list": list(values)})
    return f"{condition.field}:{op}:{','.join(str(v) for v in values)}"


def _validate_audiences(audiences: Sequence[dict[str, Any]]) -> None:
    def bad(message: str) -> ApiError:
        return ApiError(422, "invalid_audiences", message)

    if not audiences:
        raise bad("A placement needs at least one audience")
    for entry in audiences:
        if not entry.get("content_type"):
            raise bad("Every audience entry needs an explicit content_type")
    if audiences[-1].get("segment_ids"):
        raise bad("The default audience (no segments) must be last")
    if any(not entry.get("segment_ids") for entry in audiences[:-1]):
        raise bad("Only the last audience may be the default one")


class AdaptyCommands:
    """The CLI commands activation and paywall drafts need, for one Adapty app."""

    def __init__(self, cli: Any, app_id: str) -> None:
        self._cli = cli
        self._app = app_id

    async def _pages(self, *command: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            result = await self._cli.run(
                *command, "--app", self._app, "--page", str(page), "--page-size", str(PAGE_SIZE)
            )
            batch = result.get("data") or []
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                return items
            page += 1

    # segments
    async def segments_create(self, title: str, filters: Sequence[str]) -> dict[str, Any]:
        if not filters:
            raise ApiError(422, "invalid_filter", "A segment needs at least one filter")
        args = ["segments", "create", "--app", self._app, "--title", title]
        for item in filters:
            args += ["--filter", item]
        return await self._cli.run(*args)

    async def find_segment_by_title(self, title: str) -> dict[str, Any] | None:
        for segment in await self._pages("segments", "list"):
            if segment.get("title") == title:
                return segment
        return None

    # placements
    async def placement_by_developer_id(self, developer_id: str) -> dict[str, Any]:
        for item in await self._pages("placements", "list"):
            if item.get("developer_id") == developer_id:
                return await self._cli.run("placements", "get", item["id"], "--app", self._app)
        raise ApiError(404, "placement_not_found", f"No placement with developer id '{developer_id}'")

    async def placements_update(
        self, placement_id: str, *, developer_id: str, title: str, audiences: Sequence[dict[str, Any]]
    ) -> dict[str, Any]:
        if not developer_id:
            raise ApiError(422, "invalid_placement", "placements update needs the placement's developer id")
        _validate_audiences(audiences)
        return await self._cli.run(
            "placements",
            "update",
            placement_id,
            "--app",
            self._app,
            "--developer-id",
            developer_id,
            "--title",
            title,
            "--audiences",
            json.dumps(list(audiences)),
        )

    # A/B tests
    async def ab_tests_create(
        self, title: str, *, placement_id: str, segment_id: str, arms: Sequence[tuple[str, int, str]]
    ) -> dict[str, Any]:
        """Draft test for one segment. `arms` = (flow_id, weight, title); weights must sum to 100."""
        if sum(weight for _, weight, _ in arms) != 100:
            raise ApiError(422, "invalid_arms", "A/B test weights must sum to 100")
        flows = [{"flow_id": flow_id, "weight": weight, "title": arm_title} for flow_id, weight, arm_title in arms]
        return await self._cli.run(
            "ab-tests",
            "create",
            "--app",
            self._app,
            "--title",
            title,
            "--placement",
            placement_id,
            "--flows",
            json.dumps(flows),
            "--segment",
            segment_id,
        )

    async def ab_tests_start(self, test_id: str, *, placement_id: str, segment_id: str) -> dict[str, Any]:
        """Cannot be undone. Callers decide when this is allowed (approve / autopilot)."""
        return await self._cli.run(
            "ab-tests",
            "start",
            test_id,
            "--app",
            self._app,
            "--placement",
            placement_id,
            "--segment",
            segment_id,
            "--yes",
        )

    # flows
    async def flows_get(self, flow_id: str) -> dict[str, Any]:
        return await self._cli.run("flows", "get", flow_id, "--app", self._app)

    async def flows_config_get(self, flow_id: str) -> dict[str, Any]:
        return await self._cli.run("flows", "config", "get", flow_id, "--app", self._app)

    async def flows_create(self, name: str) -> dict[str, Any]:
        return await self._cli.run("flows", "create", "--app", self._app, "--name", name)

    async def flows_config_update(self, flow_id: str, config: dict[str, Any]) -> dict[str, Any]:
        fd, path = tempfile.mkstemp(prefix="fs-flow-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(config, fh)
            return await self._cli.run("flows", "config", "update", flow_id, "--app", self._app, "--config-file", path)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(path)

    async def flows_publish(self, flow_id: str, *, confirmed_by_human: bool = False) -> dict[str, Any]:
        """Users see a published flow immediately, so only an explicit human decision may call this."""
        if not confirmed_by_human:
            raise ApiError(403, "publish_not_confirmed", "Publishing a flow needs a human confirmation")
        return await self._cli.run("flows", "publish", flow_id, "--app", self._app, "--yes")
