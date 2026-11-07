# Task graph

One file per role (`A.json`, `B.json`, `C.json`, `D.json`, `shared.json`). Each task has `steps` (the small
todo list), `depends_on` (`hard` = cannot start before it is done; `contract` = can start now against the
contract and fakes, but must be re-checked when that task changes), `produces` / `consumes` (named artifacts:
`api:*`, `port:*`, `table:*`, `domain:*`, `data:*`, `path:<glob>`) and `done_when`.

Dependencies are found two ways: explicit `depends_on`, and implicit — any task that **consumes** something
another task **produces**. So if A changes `port:ValueStore.matrix`, B2 is flagged even though B2 never named A7.

## Commands (`python3 tools/tasks.py …`, stdlib only)
| Command | When |
|---|---|
| `board [--role A]` | start of a session: what is ready, what is blocked and by whom |
| `impact A3 [--depth 1]` | before changing something: who depends on it |
| `impact --diff origin/main` (`make impact`) | before a PR: which tasks your changed files touch, and their dependents |
| `flag A3 --by A --reason "…"` | you changed or found a problem in a task's output → writes `changes/<time>-A3.json` |
| `inbox --role B` | start of a session / after `sync-main`: notices that hit your tasks (REVIEW NOW = direct) |
| `ack --role B` | after you reviewed them |
| `set A3 doing\|done\|needs-review\|blocked` | status of your own task |
| `check` | graph validation (also a unit test) |

## Rules
- Edit only your role's file. Shared milestones (`shared.json`) change through `contract-change`.
- A change notice is one new file in `changes/` — never edit someone else's notice or task file.
- `flag` whenever a task's output changes after others may have used it: contract shape, column, meaning of a
  value, a verified fact that turned out wrong. Found a problem in **someone else's** task? `flag <their id>
  --by <you>` and tell them; they fix it.
- On a direct (REVIEW NOW) hit: re-read the notice, re-run your tests, set `needs-review` if something must
  change, fix it in your next chapter, then `ack`.
- New task or new dependency discovered → add it to your file in the same PR (`check` must stay green).
