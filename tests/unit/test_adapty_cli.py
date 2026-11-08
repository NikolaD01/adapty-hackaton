"""C2: the Adapty CLI adapter - argv, JSON parsing, errors and the typed commands. No real process runs."""

import json

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import Condition
from feature_signal.integrations.adapty.cli import (
    AdaptyCommands,
    SubprocessAdaptyCli,
    condition_to_filter,
    custom_attribute_filter,
)

APP = "9ccde368-e282-4385-a260-18b428560ba5"


class FakeRunner:
    """Records argv and answers with (rc, stdout, stderr) in order; the last answer repeats."""

    def __init__(self, *answers: tuple[int, str, str]) -> None:
        self.calls: list[list[str]] = []
        self.answers = list(answers) or [(0, "{}", "")]

    async def __call__(self, argv: list[str], timeout: float) -> tuple[int, str, str]:
        self.calls.append(argv)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


class RecordingCli:
    """An `AdaptyCli` that records args and returns canned JSON per command (first two words)."""

    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.responses = responses or {}
        self.config_files: dict[str, object] = {}

    async def run(self, *args: str) -> dict:
        self.calls.append(args)
        if "--config-file" in args:
            path = args[args.index("--config-file") + 1]
            with open(path, encoding="utf-8") as fh:
                self.config_files[path] = json.load(fh)
        answer = self.responses.get(" ".join(args[:2]), {})
        return answer(args) if callable(answer) else answer


def arg(call: tuple[str, ...], flag: str) -> str:
    return call[call.index(flag) + 1]


# --- SubprocessAdaptyCli -------------------------------------------------------------------------


async def test_command_prefix_comes_from_settings_string():
    runner = FakeRunner()
    cli = SubprocessAdaptyCli("docker compose run --rm -T dev adapty", runner=runner)
    await cli.run("segments", "list", "--app", APP)
    assert runner.calls[0][:6] == ["docker", "compose", "run", "--rm", "-T", "dev"]
    assert runner.calls[0][6:] == ["adapty", "segments", "list", "--app", APP, "--json"]


async def test_every_call_adds_json_flag_once_and_parses_stdout():
    runner = FakeRunner((0, '{"data": [{"id": "s1"}]}', ""))
    cli = SubprocessAdaptyCli("adapty", runner=runner)
    result = await cli.run("segments", "list", "--json")
    assert runner.calls[0].count("--json") == 1
    assert result == {"data": [{"id": "s1"}]}


async def test_empty_stdout_returns_empty_dict():
    cli = SubprocessAdaptyCli("adapty", runner=FakeRunner((0, "  \n", "")))
    assert await cli.run("ab-tests", "start", "t1") == {}


async def test_a_json_list_is_wrapped_in_data():
    cli = SubprocessAdaptyCli("adapty", runner=FakeRunner((0, '[{"id": 1}]', "")))
    assert await cli.run("x", "y") == {"data": [{"id": 1}]}


async def test_nonzero_exit_raises_api_error_with_stderr():
    runner = FakeRunner((1, "", "Error: 400 filter field unknown"))
    cli = SubprocessAdaptyCli("adapty", runner=runner)
    with pytest.raises(ApiError) as caught:
        await cli.run("segments", "create", "--app", APP)
    assert (caught.value.status, caught.value.code) == (502, "adapty_cli_failed")
    assert caught.value.details["command"] == "segments create"
    assert "filter field unknown" in caught.value.details["stderr"]


async def test_non_json_stdout_raises_bad_output():
    cli = SubprocessAdaptyCli("adapty", runner=FakeRunner((0, "Segment created!", "")))
    with pytest.raises(ApiError) as caught:
        await cli.run("segments", "create")
    assert caught.value.code == "adapty_cli_bad_output"


async def test_real_runner_reports_a_missing_binary_as_api_error():
    cli = SubprocessAdaptyCli("definitely-not-a-binary-fs")
    with pytest.raises(ApiError) as caught:
        await cli.run("apps", "list")
    assert caught.value.code == "adapty_cli_missing"


async def test_real_runner_times_out():
    cli = SubprocessAdaptyCli("python3 -c 'import time; time.sleep(5)'", timeout=0.2)
    with pytest.raises(ApiError) as caught:
        await cli.run()
    assert (caught.value.status, caught.value.code) == (504, "adapty_cli_timeout")


# --- filters --------------------------------------------------------------------------------------


def test_custom_attribute_filter_uses_string_type_and_in():
    assert custom_attribute_filter("p_segment", ["power_editor"]) == "attributes__p_segment@string:IN:power_editor"


def test_condition_with_list_value_joins_with_commas():
    cond = Condition(field="subscription_state", op="IN", value=["never_subscribed", "subscription_cancelled"])
    assert condition_to_filter(cond) == "subscription_state:IN:never_subscribed,subscription_cancelled"


def test_condition_is_null_has_no_value():
    assert condition_to_filter(Condition(field="customer_user_id", op="IS NOT NULL", value=None)) == (
        "customer_user_id:IS NOT NULL"
    )


def test_condition_with_a_comma_in_a_value_uses_the_json_form():
    cond = Condition(field="device", op="IN", value=["a,b"])
    assert json.loads(condition_to_filter(cond)) == {"field_name": "device", "operator": "IN", "value_list": ["a,b"]}


def test_unknown_operator_is_refused():
    with pytest.raises(ApiError) as caught:
        condition_to_filter(Condition(field="age", op="=", value=[18]))
    assert caught.value.code == "invalid_filter"


# --- AdaptyCommands -------------------------------------------------------------------------------


async def test_segments_create_passes_every_filter_and_returns_the_segment():
    cli = RecordingCli({"segments create": {"id": "seg1", "title": "[fs] power_editor"}})
    commands = AdaptyCommands(cli, APP)
    filters = [custom_attribute_filter("p_segment", ["power_editor"]), "subscription_state:IN:never_subscribed"]
    segment = await commands.segments_create("[fs] power_editor", filters)
    (call,) = cli.calls
    assert call[:2] == ("segments", "create")
    assert arg(call, "--app") == APP
    assert arg(call, "--title") == "[fs] power_editor"
    assert [call[i + 1] for i, a in enumerate(call) if a == "--filter"] == filters
    assert segment["id"] == "seg1"


async def test_segments_create_refuses_no_filters():
    with pytest.raises(ApiError):
        await AdaptyCommands(RecordingCli(), APP).segments_create("[fs] x", [])


async def test_products_list_pages_with_size_100():
    cli = RecordingCli({"products list": {"data": [{"id": "p1", "access_level_id": "a1"}]}})
    assert await AdaptyCommands(cli, APP).products_list() == [{"id": "p1", "access_level_id": "a1"}]
    assert arg(cli.calls[0], "--page-size") == "100"


async def test_segments_update_sends_the_segment_id_and_every_filter():
    cli = RecordingCli({"segments update": {"id": "seg1"}})
    await AdaptyCommands(cli, APP).segments_update("seg1", "[fs] x", ["a:IN:1", "b:IN:2"])
    (call,) = cli.calls
    assert call[:3] == ("segments", "update", "seg1")
    assert [call[i + 1] for i, a in enumerate(call) if a == "--filter"] == ["a:IN:1", "b:IN:2"]


async def test_find_segment_by_title_pages_through_the_list():
    pages = {
        "1": {"data": [{"id": f"s{i}", "title": f"other {i}"} for i in range(100)]},
        "2": {"data": [{"id": "target", "title": "[fs] power_editor"}]},
    }
    cli = RecordingCli({"segments list": lambda args: pages[arg(args, "--page")]})
    found = await AdaptyCommands(cli, APP).find_segment_by_title("[fs] power_editor")
    assert found == {"id": "target", "title": "[fs] power_editor"}
    assert [arg(c, "--page-size") for c in cli.calls] == ["100", "100"]


async def test_find_segment_by_title_returns_none_when_missing():
    cli = RecordingCli({"segments list": {"data": [{"id": "a", "title": "Payers"}]}})
    assert await AdaptyCommands(cli, APP).find_segment_by_title("[fs] nope") is None


async def test_placement_by_developer_id_reads_the_full_placement():
    cli = RecordingCli(
        {
            "placements list": {"data": [{"id": "p1", "developer_id": "main"}, {"id": "p2", "developer_id": "x"}]},
            "placements get": {"id": "p1", "developer_id": "main", "title": "Main", "audiences": []},
        }
    )
    placement = await AdaptyCommands(cli, APP).placement_by_developer_id("main")
    assert placement["title"] == "Main"
    assert cli.calls[-1][:3] == ("placements", "get", "p1")


async def test_placement_by_developer_id_unknown_is_404():
    cli = RecordingCli({"placements list": {"data": []}})
    with pytest.raises(ApiError) as caught:
        await AdaptyCommands(cli, APP).placement_by_developer_id("main")
    assert caught.value.status == 404


AUDIENCES = [
    {"content_type": "flow", "segment_ids": ["seg1"], "flow_id": "f2", "priority": 0},
    {"content_type": "flow_ab_test", "segment_ids": ["seg9"], "ab_test_id": "t9", "priority": 1},
    {"content_type": "flow", "segment_ids": [], "flow_id": "f1", "priority": 2},
]


async def test_placements_update_sends_developer_id_title_and_full_audience_list():
    cli = RecordingCli()
    await AdaptyCommands(cli, APP).placements_update("p1", developer_id="main", title="Main", audiences=AUDIENCES)
    (call,) = cli.calls
    assert call[:3] == ("placements", "update", "p1")
    assert arg(call, "--developer-id") == "main"
    assert arg(call, "--title") == "Main"
    assert json.loads(arg(call, "--audiences")) == AUDIENCES


async def test_placements_update_without_developer_id_is_refused_before_running():
    cli = RecordingCli()
    with pytest.raises(ApiError):
        await AdaptyCommands(cli, APP).placements_update("p1", developer_id="", title="Main", audiences=AUDIENCES)
    assert cli.calls == []


@pytest.mark.parametrize(
    "audiences",
    [
        [{"content_type": "flow", "segment_ids": ["seg1"], "flow_id": "f2", "priority": 0}],  # no default
        list(reversed(AUDIENCES)),  # default not last
        [{"segment_ids": [], "flow_id": "f1", "priority": 0}],  # missing content_type
    ],
    ids=["no-default", "default-not-last", "no-content-type"],
)
async def test_placements_update_validates_the_audience_list(audiences):
    cli = RecordingCli()
    with pytest.raises(ApiError) as caught:
        await AdaptyCommands(cli, APP).placements_update("p1", developer_id="main", title="Main", audiences=audiences)
    assert caught.value.code == "invalid_audiences"
    assert cli.calls == []


async def test_ab_tests_create_is_a_draft_for_one_segment_with_weighted_arms():
    cli = RecordingCli({"ab-tests create": {"ab_test_id": "t1", "state": "draft"}})
    test = await AdaptyCommands(cli, APP).ab_tests_create(
        "[fs] power_editor",
        placement_id="p1",
        segment_id="seg1",
        arms=[("f1", 20, "control"), ("f2", 80, "offer")],
    )
    (call,) = cli.calls
    assert arg(call, "--placement") == "p1"
    assert arg(call, "--segment") == "seg1"
    assert json.loads(arg(call, "--flows")) == [
        {"flow_id": "f1", "weight": 20, "title": "control"},
        {"flow_id": "f2", "weight": 80, "title": "offer"},
    ]
    assert "--all-users" not in call
    assert test["ab_test_id"] == "t1"


async def test_ab_tests_create_weights_must_sum_to_100():
    with pytest.raises(ApiError):
        await AdaptyCommands(RecordingCli(), APP).ab_tests_create(
            "t", placement_id="p1", segment_id="s1", arms=[("f1", 20, "a"), ("f2", 70, "b")]
        )


async def test_ab_tests_start_runs_for_the_segment_without_prompting():
    cli = RecordingCli()
    await AdaptyCommands(cli, APP).ab_tests_start("t1", placement_id="p1", segment_id="seg1")
    (call,) = cli.calls
    assert call[:3] == ("ab-tests", "start", "t1")
    assert arg(call, "--placement") == "p1"
    assert arg(call, "--segment") == "seg1"
    assert "--yes" in call


async def test_flows_create_and_config_update_write_the_config_through_a_file():
    cli = RecordingCli({"flows create": {"id": "f9"}})
    commands = AdaptyCommands(cli, APP)
    flow = await commands.flows_create("[fs] draft")
    await commands.flows_config_update(flow["id"], {"screens": [{"title": "Hi"}]})
    create, update = cli.calls
    assert arg(create, "--name") == "[fs] draft"
    assert update[:4] == ("flows", "config", "update", "f9")
    assert cli.config_files[arg(update, "--config-file")] == {"screens": [{"title": "Hi"}]}


async def test_flows_publish_requires_explicit_confirmation():
    cli = RecordingCli()
    commands = AdaptyCommands(cli, APP)
    with pytest.raises(ApiError) as caught:
        await commands.flows_publish("f9")
    assert caught.value.code == "publish_not_confirmed"
    assert cli.calls == []
    await commands.flows_publish("f9", confirmed_by_human=True)
    assert cli.calls == [("flows", "publish", "f9", "--app", APP, "--yes")]
