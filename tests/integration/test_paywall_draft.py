"""C8: a draft flow copied from the live config, with a new title, refused if the plan lacks the feature."""

import copy
import json

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import Feature
from feature_signal.integrations.adapty.cli import AdaptyCommands
from feature_signal.repositories.features import FeatureRepository
from feature_signal.schemas.proposals import PaywallDraftIn
from feature_signal.services.paywall_service import PaywallService
from feature_signal.services.proposal_service import ProposalService
from tests.integration.adapty_helpers import make_factory
from tests.integration.test_activation import ADAPTY, APP, proposal_input

BASE_FLOW = "f-lifetime"
P_ANNUAL, P_MONTHLY, P_LIFETIME = "prod-annual", "prod-monthly", "prod-lifetime"
LEVEL = "level-premium"


def base_config():
    def text(value):
        return {"props": {"content": {"values": {"en": [{"content": [{"text": value}]}]}}}}

    return {
        "defaultLocale": "en",
        "locales": ["en"],
        "screens": [
            {
                "products": [{"id": P_ANNUAL}, {"id": P_MONTHLY}, {"id": P_LIFETIME}],
                "elements": {
                    "map": {
                        "el_1T": text("Go Premium"),
                        "el_2T": text("Pay once and keep it forever."),
                        "el_3P": {"props": {"product": {"id": P_ANNUAL}}},
                        "el_4T": text("Annual"),
                    }
                },
            }
        ],
        "_meta": {"screens": {"scr": {"products": [{"id": P_ANNUAL, "flowProductId": "x"}]}}},
    }


class Cli:
    def __init__(self, config=None):
        self.calls: list[tuple[str, ...]] = []
        self.config = config if config is not None else base_config()
        self.written: dict | None = None

    async def run(self, *args):
        self.calls.append(args)
        command = " ".join(args[:2])
        if command == "products list":
            return {
                "data": [
                    {"id": P_ANNUAL, "access_level_id": LEVEL},
                    {"id": P_MONTHLY, "access_level_id": LEVEL},
                    {"id": P_LIFETIME, "access_level_id": LEVEL},
                ]
            }
        if command == "flows config" and args[2] == "get":
            return {"config": copy.deepcopy(self.config), "status": "published"}
        if command == "flows create":
            return {"id": "flow-draft"}
        if command == "flows config" and args[2] == "update":
            with open(args[args.index("--config-file") + 1], encoding="utf-8") as fh:
                self.written = json.load(fh)
            return {}
        return {}


@pytest.fixture
def factory(db_url):
    return make_factory(db_url)


def diff_paths(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff_paths(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [p for i, (x, y) in enumerate(zip(a, b, strict=True)) for p in diff_paths(x, y, f"{path}[{i}]")]
    return [] if a == b else [path]


async def setup(factory, *, plans=(LEVEL,), highlight="ai_generate", status_item=None):
    async with factory() as s:
        await FeatureRepository(s).upsert_row(APP, Feature("ai_generate", "AI", "d", plans=list(plans)))
        await s.commit()
        item = status_item or proposal_input(action={"flow_id": BASE_FLOW, "needs_publish": False})
        (created,) = await ProposalService(s).create(APP, [item])
    return created.proposal_id


async def draft(factory, pid, cli, **body):
    payload = {"title": "Unlimited AI generation", "highlight_feature": "ai_generate", **body}
    async with factory() as s:
        return await PaywallService(s, AdaptyCommands(cli, ADAPTY)).draft(pid, PaywallDraftIn(**payload))


async def test_the_draft_is_a_copy_of_the_live_config_with_only_the_title_changed(factory):
    pid = await setup(factory)
    cli = Cli()
    out = await draft(factory, pid, cli)
    assert (out.base_flow_id, out.draft_flow_id, out.status) == (BASE_FLOW, "flow-draft", "draft")
    changed = diff_paths(base_config(), cli.written)
    assert changed == ["screens[0].elements.map.el_1T.props.content.values.en[0].content[0].text"]
    assert out.changed_paths == changed
    assert (
        cli.written["screens"][0]["elements"]["map"]["el_1T"]["props"]["content"]["values"]["en"][0]["content"][0][
            "text"
        ]
        == "Unlimited AI generation"
    )


async def test_the_flow_is_created_then_written_and_never_published(factory):
    pid = await setup(factory)
    cli = Cli()
    await draft(factory, pid, cli)
    assert [c[:3] for c in cli.calls if c[0] == "flows"] == [
        ("flows", "config", "get"),
        ("flows", "create", "--app"),
        ("flows", "config", "update"),
    ]
    assert not any(c[:2] == ("flows", "publish") for c in cli.calls)
    assert any(c[:3] == ("flows", "config", "get") and c[3] == BASE_FLOW for c in cli.calls)


async def test_the_proposal_now_points_at_the_draft_flow_and_needs_a_publish(factory):
    pid = await setup(factory)
    await draft(factory, pid, Cli())
    async with factory() as s:
        (p,) = await ProposalService(s).list(APP, "draft")
    assert (p.action.flow_id, p.action.needs_publish, p.action.highlight_feature) == ("flow-draft", True, "ai_generate")
    assert [(e.field, e.from_, e.to) for e in p.edits] == [("flow_id", BASE_FLOW, "flow-draft")]


async def test_a_feature_the_offered_plan_does_not_include_is_refused_before_anything_is_created(factory):
    pid = await setup(factory, plans=("some-other-plan",))
    cli = Cli()
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, cli)
    assert (caught.value.status, caught.value.code) == (422, "feature_not_in_plan")
    assert not any(c[:2] in (("flows", "create"),) for c in cli.calls)
    assert cli.written is None


async def test_a_feature_listed_by_product_id_is_included(factory):
    pid = await setup(factory, plans=(P_LIFETIME,))
    out = await draft(factory, pid, Cli(), product_ids=[P_LIFETIME])
    assert out.draft_flow_id == "flow-draft"


async def test_only_the_offered_products_count_for_the_plan_check(factory):
    pid = await setup(factory, plans=(P_LIFETIME,))
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, Cli(), product_ids=[P_MONTHLY])
    assert caught.value.code == "feature_not_in_plan"


async def test_a_product_that_is_not_in_the_flow_is_refused(factory):
    pid = await setup(factory)
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, Cli(), product_ids=["prod-unknown"])
    assert (caught.value.status, caught.value.code) == (422, "product_not_in_flow")


async def test_an_unknown_feature_is_refused(factory):
    pid = await setup(factory)
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, Cli(), highlight_feature="nope")
    assert (caught.value.status, caught.value.code) == (422, "unknown_feature")


async def test_a_config_without_a_title_text_is_refused(factory):
    pid = await setup(factory)
    config = base_config()
    config["screens"][0]["elements"]["map"] = {"el_3P": {"props": {"product": {"id": P_ANNUAL}}}}
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, Cli(config))
    assert (caught.value.status, caught.value.code) == (422, "no_title_element")


async def test_only_a_draft_proposal_gets_a_paywall_draft(factory):
    pid = await setup(factory)
    async with factory() as s:
        await ProposalService(s).reject(pid, "no")
    with pytest.raises(ApiError) as caught:
        await draft(factory, pid, Cli())
    assert (caught.value.status, caught.value.code) == (409, "proposal_not_editable")


async def test_unknown_proposal_is_404(factory):
    with pytest.raises(ApiError) as caught:
        await draft(factory, "pr_missing", Cli())
    assert caught.value.status == 404


def test_paywall_draft_route(api, factory):
    import asyncio

    pid = asyncio.run(setup(factory))
    api.app.state.adapty_commands = AdaptyCommands(Cli(), ADAPTY)
    r = api.post(
        f"/v1/proposals/{pid}/paywall-draft",
        json={"title": "Unlimited AI generation", "highlight_feature": "ai_generate"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["draft_flow_id"] == "flow-draft"
    assert r.json()["status"] == "draft"
    bad = api.post(f"/v1/proposals/{pid}/paywall-draft", json={"title": ""})
    assert bad.status_code == 422
