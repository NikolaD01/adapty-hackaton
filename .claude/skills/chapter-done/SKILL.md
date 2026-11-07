---
name: chapter-done
description: Use when a chapter (a feature from your role brief) is finished or the developer says "done", "gotovo", "završi poglavlje", "commit this", "push", "merge". Checks scope, adds missing tests, runs all tests, writes the chapter doc, updates STATUS and AI_LOG, commits in small conventional commits without any AI attribution, rebases on origin/main, pushes and squash-merges when green.
---

# chapter-done

Run every step in order. Stop and tell the developer (in Serbian) if a step fails; never skip one.

## 1. Know the context
- Read `CLAUDE.local.md` → role (A/B/C/D). Read the chapter in `docs/team/<role>.md` you just did.
- `git status` and `git diff --stat origin/main...HEAD` + uncommitted changes.
- Branch must be `<area>/<kebab>`. On `main`? Create the branch now: `git switch -c <area>/<slug>`.

## 2. Scope check
- Every changed path must be owned by your role (CLAUDE.md §6). A shared file changed → stop and
  run the `contract-change` skill for that part instead. Another area's file changed → revert it
  (`git restore --source=origin/main -- <path>`) and redo the change in your own files.
- No secrets: grep the diff for `secret_live_`, `sk-`, `Api-Key ` followed by a value, `.env`. Any hit → stop.

## 3. Tests for what you built
- For each new or changed function/endpoint/component, there must be a test at the right level
  (CLAUDE.md §8). Write the missing ones now. The chapter's "Done when" line in the brief must be
  covered by at least one test.
- Run: backend `make test` (or `pytest -q`) and `ruff check .`; frontend `cd web && npm test -- --run`
  and `npm run build`; SDK `cd sdk/js && npm test -- --run`. Run the whole suite, not just yours.
- Red → fix, rerun. Do not continue with failing tests or lint errors.

## 4. Documentation
- Create or update `docs/<area>/<NN>-<slug>.md` from `docs/templates/chapter.md`. Fill every section;
  "How to test" must contain the exact command and the expected output. Numbers with units.
- `docs/STATUS.md`: update only your area's row (chapter, state, next).
- `AI_LOG.md`: if during this chapter the AI claimed something that a check proved wrong (or a test
  caught an AI bug), append an entry: date · claim · how it was checked · correction. If nothing, skip.
- If behavior differs from `docs/contracts/api.md` → that is a contract change: stop, use `contract-change`.

## 5. Commit in pieces
- Group changes into logical commits, each with its tests: e.g. `feat(ingest): add events table`,
  `feat(ingest): ingest batch with idempotent counters`, `test(ingest): cover duplicate event ids`,
  `docs(ingest): chapter 3 ingest`.
- Format: Conventional Commits, English, imperative, subject ≤72 chars, scope = area.
- **Never** add `Co-Authored-By`, "Generated with", model names or any AI mention to a commit or PR.
  Use `git commit -m "<subject>" [-m "<why>"]` only.

## 6. Sync and push
- `git fetch origin && git rebase origin/main`. Conflicts in your files → resolve; in other areas'
  files → take theirs (`git checkout --theirs`) and re-apply your intent in your own files.
- Rerun the full test suite after the rebase.
- `git push -u origin HEAD` (on your branch only; `--force-with-lease` if you rebased an already pushed branch).

## 7. Merge
- If `gh` is available: `gh pr create --base main --title "<conventional title>" --body "<what, why, how to test>"`
  (no AI mention), then `gh pr merge --squash --delete-branch` once checks are green. Shared files in
  the diff → ask for one teammate's ack first and do not merge yourself.
- No `gh`: tell the developer the branch is pushed and give the PR link
  `https://github.com/NikolaD01/adapty-hackaton/compare/main...<branch>`.
- After merge: `git switch main && git pull --ff-only`, start the next chapter on a new branch.

## 8. Report (to the developer, Serbian, 3–5 lines)
What was done, tests run (count passed), doc path, PR/merge state, what the next chapter is.
