---
name: sync-main
description: Use when the developer says "sync", "povuci main", "rebase", "update branch", at the start of a work session, before starting a new chapter, or when another area announces a merge. Rebases the current branch on origin/main, reinstalls dependencies if lockfiles changed, reruns the tests and pushes.
---

# sync-main

1. `git status` — uncommitted work? Commit it (conventional message, no AI attribution) or `git stash`.
2. `git fetch origin` then:
   - on `main`: `git pull --ff-only`;
   - on a branch: `git rebase origin/main`. Conflicts: own files → resolve; other areas' files → take
     theirs, re-apply your intent in your own files; shared files → resolve together with the owner.
3. If `pyproject.toml` changed: `pip install -e ".[dev]"`. If `web/package.json` / `sdk/js/package.json`
   changed: `npm install` there. If `feature_signal/db/migrations/` changed: `alembic upgrade head`.
4. Run the whole test suite (`make test`; `cd web && npm test -- --run` if web exists).
5. On a branch with pushed commits: `git push --force-with-lease`. Never force-push `main`.
6. Tell the developer (Serbian, 2 lines): what came in from main (`git log --oneline ORIG_HEAD..HEAD` or
   the merged PR titles) and whether tests are green.
