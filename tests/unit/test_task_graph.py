"""The task graph in docs/tasks must stay valid: every edit by any role is checked here."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("tasks", Path(__file__).parents[2] / "tools" / "tasks.py")
tasks_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tasks_mod)


def test_graph_has_no_unknown_ids_cycles_or_orphan_inputs():
    _, tasks = tasks_mod.load()
    assert tasks_mod.validate(tasks) == []


def test_every_task_has_steps_and_done_when():
    _, tasks = tasks_mod.load()
    for tid, task in tasks.items():
        assert task["steps"], tid
        assert task["done_when"], tid


def test_impact_follows_produces_and_consumes():
    _, tasks = tasks_mod.load()
    direct = {tid for tid, depth, _ in tasks_mod.impact(tasks, ["A7"]) if depth == 1}
    assert {"B2", "C4", "B8"} <= direct  # B2 only consumes port:ValueStore.matrix, no explicit depends_on


def test_changed_path_maps_to_owning_task():
    _, tasks = tasks_mod.load()
    assert tasks_mod.tasks_for_paths(tasks, ["feature_signal/domain/rules.py"]) == ["A6"]
