#!/usr/bin/env python3
"""Task graph for the team: who depends on what, and what to re-check when something changes.

Data: docs/tasks/<ROLE>.json (each role edits only its own file) and docs/tasks/changes/*.json
(one file per change notice, so parallel branches never conflict). Standard library only.

  python tools/tasks.py board [--role A]          todo list with ready/blocked state
  python tools/tasks.py impact A3 [--depth 1]     everything that depends on A3 (transitively, or direct only)
  python tools/tasks.py impact --diff origin/main tasks affected by the files changed on this branch
  python tools/tasks.py flag A3 --by A --reason "events now require session_id"
                                                  write a change notice + print who must review
  python tools/tasks.py inbox --role B            notices since B's last ack that hit B's tasks
  python tools/tasks.py ack --role B              mark B's inbox as read
  python tools/tasks.py set A3 done               set status (todo|doing|done|needs-review|blocked)
  python tools/tasks.py check                     validate the graph (ids, cycles, unknown inputs)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc  # noqa: UP017 — must also run on the host python3.10

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "docs" / "tasks"
CHANGES_DIR = TASKS_DIR / "changes"
STATUSES = {"todo", "doing", "done", "needs-review", "blocked"}
# Inputs that come from outside the team (no task produces them).
EXTERNAL = {"data:offline-dataset", "adapty:server-api", "adapty:cli", "contract:api"}


def load() -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (role files by file stem, tasks by id with a back-reference to their role file)."""
    files, tasks = {}, {}
    for path in sorted(TASKS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        data["_path"] = path
        files[path.stem] = data
        for task in data["tasks"]:
            if task["id"] in tasks:
                raise SystemExit(f"duplicate task id {task['id']}")
            task["_file"] = path.stem
            task["_role"] = data["role"]
            tasks[task["id"]] = task
    return files, tasks


def save(file_data: dict) -> None:
    path = file_data.pop("_path")
    for task in file_data["tasks"]:
        task.pop("_file", None)
        task.pop("_role", None)
    path.write_text(json.dumps(file_data, indent=2, ensure_ascii=False) + "\n")


def direct_dependents(tasks: dict[str, dict], task_id: str) -> dict[str, str]:
    """Tasks that list task_id in depends_on, or consume something task_id produces -> reason."""
    src = tasks[task_id]
    produced = {p for p in src["produces"] if not p.startswith("path:")}
    out = {}
    for tid, task in tasks.items():
        if tid == task_id:
            continue
        for dep in task["depends_on"]:
            if dep["id"] == task_id:
                out[tid] = f"{dep['kind']} dependency on {task_id}"
        shared = produced.intersection(task["consumes"])
        if shared and tid not in out:
            out[tid] = f"consumes {', '.join(sorted(shared))}"
    return out


def impact(tasks: dict[str, dict], roots: list[str], max_depth: int = 99) -> list[tuple[str, int, str]]:
    """Breadth-first walk over dependents. Returns (task id, depth, reason) without the roots."""
    seen, queue, result = set(roots), [(r, 0) for r in roots], []
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for tid, reason in sorted(direct_dependents(tasks, current).items()):
            if tid in seen:
                continue
            seen.add(tid)
            result.append((tid, depth + 1, f"{reason} (via {current})" if depth else reason))
            queue.append((tid, depth + 1))
    return result


def tasks_for_paths(tasks: dict[str, dict], paths: list[str]) -> list[str]:
    hits = []
    for tid, task in tasks.items():
        globs = [p[5:] for p in task["produces"] if p.startswith("path:")]
        if any(fnmatch.fnmatch(path, g) for path in paths for g in globs):
            hits.append(tid)
    return sorted(hits)


def changed_paths(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    out += subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return sorted(set(out))


def readiness(tasks: dict[str, dict], task: dict) -> str:
    if task["status"] != "todo":
        return task["status"]
    hard = [d["id"] for d in task["depends_on"] if d["kind"] == "hard" and tasks[d["id"]]["status"] != "done"]
    return f"blocked by {', '.join(hard)}" if hard else "ready"


def print_impact(tasks: dict[str, dict], roots: list[str], max_depth: int = 99) -> list[tuple[str, int, str]]:
    rows = impact(tasks, roots, max_depth)
    if not rows:
        print("No other task depends on this.")
    for tid, depth, reason in rows:
        task = tasks[tid]
        print(f"  {'  ' * (depth - 1)}{tid} [{task['_role']}] {task['title']} — {reason} — status {task['status']}")
    return rows


def cmd_board(args, files, tasks):
    for data in files.values():
        if args.role and data["role"] not in (args.role, "ALL"):
            continue
        print(f"\n## {data['role']} — {data['name']}")
        for task in data["tasks"]:
            mark = "x" if task["status"] == "done" else " "
            deps = ", ".join(f"{d['id']}({d['kind'][0]})" for d in task["depends_on"]) or "-"
            print(f"- [{mark}] {task['id']} {task['title']}  · {readiness(tasks, task)} · deps: {deps}")


def cmd_impact(args, files, tasks):
    roots = args.ids or []
    if args.diff:
        paths = changed_paths(args.diff)
        roots += tasks_for_paths(tasks, paths)
        print(f"Changed files: {len(paths)} → owning tasks: {', '.join(roots) or 'none'}")
    unknown = [r for r in roots if r not in tasks]
    if unknown:
        raise SystemExit(f"unknown task id(s): {', '.join(unknown)}")
    if roots:
        print("Must be re-checked (depth 1 = direct, deeper = knock-on):")
        print_impact(tasks, roots, args.depth)


def cmd_flag(args, files, tasks):
    if args.id not in tasks:
        raise SystemExit(f"unknown task id {args.id}")
    rows = impact(tasks, [args.id])
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    notice = {
        "at": now,
        "by": args.by,
        "task": args.id,
        "reason": args.reason,
        "affects": [{"id": tid, "role": tasks[tid]["_role"], "depth": d, "why": why} for tid, d, why in rows],
    }
    CHANGES_DIR.mkdir(exist_ok=True)
    name = f"{now.replace(':', '').replace('-', '')}-{args.id}.json"
    (CHANGES_DIR / name).write_text(json.dumps(notice, indent=2, ensure_ascii=False) + "\n")
    print(f"Notice written: docs/tasks/changes/{name}")
    print_impact(tasks, [args.id])
    roles = sorted({tasks[tid]["_role"] for tid, _, _ in rows} - {tasks[args.id]["_role"], "ALL"})
    if roles:
        print(f"Tell roles: {', '.join(roles)} — they will also see it in `tasks.py inbox`.")


def notices_for(role: str, files, tasks, since: str) -> list[dict]:
    own = {tid for tid, t in tasks.items() if t["_role"] == role}
    out = []
    for path in sorted(CHANGES_DIR.glob("*.json")) if CHANGES_DIR.exists() else []:
        notice = json.loads(path.read_text())
        hit = [a for a in notice["affects"] if a["id"] in own]
        if notice["at"] > since and hit and notice["by"] != role:
            out.append({**notice, "affects": hit})
    return out


def role_file(files, role: str) -> dict:
    for data in files.values():
        if data["role"] == role:
            return data
    raise SystemExit(f"no task file for role {role}")


def cmd_inbox(args, files, tasks):
    data = role_file(files, args.role)
    notices = notices_for(args.role, files, tasks, data.get("inbox_ack", ""))
    if not notices:
        print(f"Inbox {args.role}: nothing new.")
    for n in notices:
        print(f"- {n['at']} {n['by']} changed {n['task']}: {n['reason']}")
        for a in sorted(n["affects"], key=lambda a: a.get("depth", 1)):
            label = "REVIEW NOW" if a.get("depth", 1) == 1 else "knock-on, check if the one above changes"
            print(f"    {a['id']} {tasks[a['id']]['title']} — {label} — {a['why']}")


def cmd_ack(args, files, tasks):
    data = role_file(files, args.role)
    data["inbox_ack"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    save(data)
    print(f"Inbox {args.role} acknowledged at {data['inbox_ack']}.")


def cmd_set(args, files, tasks):
    if args.status not in STATUSES:
        raise SystemExit(f"status must be one of {sorted(STATUSES)}")
    task = tasks.get(args.id) or sys.exit(f"unknown task id {args.id}")
    data = files[task["_file"]]
    for t in data["tasks"]:
        if t["id"] == args.id:
            t["status"] = args.status
    save(data)
    print(f"{args.id} → {args.status}")


def validate(tasks: dict[str, dict]) -> list[str]:
    errors = []
    produced = {p for t in tasks.values() for p in t["produces"]}
    for tid, task in tasks.items():
        if task["status"] not in STATUSES:
            errors.append(f"{tid}: bad status {task['status']}")
        for dep in task["depends_on"]:
            if dep["id"] not in tasks:
                errors.append(f"{tid}: depends on unknown {dep['id']}")
            if dep["kind"] not in {"hard", "contract"}:
                errors.append(f"{tid}: dependency kind must be hard|contract")
        for c in task["consumes"]:
            if c not in produced and c not in EXTERNAL:
                errors.append(f"{tid}: consumes {c} which no task produces")
    state: dict[str, int] = {}

    def visit(tid: str, stack: list[str]) -> None:
        if state.get(tid) == 2:
            return
        if state.get(tid) == 1:
            errors.append("cycle: " + " -> ".join(stack + [tid]))
            return
        state[tid] = 1
        for dep in tasks[tid]["depends_on"]:
            if dep["id"] in tasks:
                visit(dep["id"], stack + [tid])
        state[tid] = 2

    for tid in tasks:
        visit(tid, [])
    return errors


def cmd_check(args, files, tasks):
    errors = validate(tasks)
    for e in errors:
        print(e)
    print(f"{len(tasks)} tasks, {len(errors)} problems")
    sys.exit(1 if errors else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("board")
    p.add_argument("--role")
    p = sub.add_parser("impact")
    p.add_argument("ids", nargs="*")
    p.add_argument("--diff", metavar="BASE")
    p.add_argument("--depth", type=int, default=99, help="1 = direct dependents only")
    p = sub.add_parser("flag")
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p.add_argument("--reason", required=True)
    for name in ("inbox", "ack"):
        sub.add_parser(name).add_argument("--role", required=True)
    p = sub.add_parser("set")
    p.add_argument("id")
    p.add_argument("status")
    sub.add_parser("check")
    args = parser.parse_args()
    files, tasks = load()
    globals()[f"cmd_{args.cmd}"](args, files, tasks)


if __name__ == "__main__":
    main()
