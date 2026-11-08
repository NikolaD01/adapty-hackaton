# AI log

How we used AI on this project. Keep it to **½–1 page**: update the sections below, don't append a diary.
Owner: everyone (the `chapter-done` skill reminds you); final edit in Phase 6.

## Tools and what we used them for
- **Codex + Context7 MCP** — Brain implementation, current library documentation, offline tests, and independent subagent review.
- **Claude Code** (CLI, one session per developer) — research, dataset analysis, the plan, repo scaffold,
  and the code of each area under the rules in `CLAUDE.md`.
- **Adapty CLI 0.18 + Adapty skills plugin** (`adaptyteam/adapty-skills`: audiences, ab-tests,
  flow-generator) — reading the Lumen app, creating segments/placements/A-B tests, learning exact CLI
  syntax (e.g. `attributes__<key>@string`) from the skills instead of guessing.
- **Web-fetch subagents** — parallel reading of Adapty docs, Meta/TikTok/YouTube/Duolingo ranking
  papers and competitor docs (Helium), so research didn't block the main session.
- **REA (static reverse engineering, MCP + CLI)** — looked at how 16 popular apps structure monetization
  signals (event names, decision logs, holdouts). Static only; nothing from it is in our code.
- **Claude Docs** — the team decision document. **LLM inside the product** (OpenAI, behind a port):
  suggests rules and writes explanations only; statistics decides.

## Setup
- `CLAUDE.md` (shared rules: stack, layers, ownership, git, tests, verified Adapty facts) +
  `CLAUDE.local.md` per developer with their role, which points the agent to `docs/team/<role>.md`.
- Repo skills: `chapter-done` (tests → docs → small commits → rebase → PR), `sync-main`, `contract-change`.
- Frozen contract `docs/contracts/api.md` + fakes in `tests/fakes.py`, so four agents work in parallel
  without waiting. `tests/unit/test_architecture.py` enforces that `domain/` can't call the network or the LLM.
- Project settings: commit/PR attribution disabled; Adapty skills marketplace enabled. Dev container with
  the Adapty CLI logged in.

## Prompts that worked well
1. *"Check whether a placement can serve 'show nothing'. Test only on the `pulse_test` placement, try
   these four audience shapes, record what the API accepts, then restore the placement and delete the
   test profiles."* — a bounded, reversible experiment with explicit cleanup; it answered a design
   question in minutes and left the account clean.
2. *"Recompute the uplift with a fixed 90-day window for both arms, only users with a full window,
   bootstrap 90% interval."* — forcing the same window on both sides exposed a horizon bias in our
   earlier conclusion.
3. *"Before you say done: tests pass, ruff is clean, the chapter doc exists — then run chapter-done."*
   (in `CLAUDE.md`) — made every agent finish work the same way.
4. *"Run the exact commands the adapter will send, by hand, on one test profile or the test placement, and write the
   tests from the real answers."* — for the Adapty adapter (role C) this found, before any code existed, that the flow lookup
   returns `401` without an `Authorization` header and the real key names (`id` for a segment, `ab_test_id` for a test).

## One thing AI got wrong, and how we caught it
The agent wrote the Adapty attribute update as a `POST` with a JSON object. A real call on a single test
profile returned `400 "value is not a valid list"`; the correct form is `PATCH` with
`{"custom_attributes":[{"key":…,"value":…}]}`. We caught it because we test every Adapty call by hand on
one profile before writing code against it. (Also caught by review: the first plan let one measurement
choose both the group and the offer — split into ranking (who) and randomized arms (what to show).)
In role C the agent twice built on a gap it only found while writing the next piece: the membership sync counted only `live`
proposals, but activation writes the attributes *before* marking a proposal live, so `p_segment` would never have been
written; and a proposal stored the segment's value but not the rule that puts a user in it. Both surfaced when the step-order
test was written first and the sequence was read end to end; the second was reported to B as a task notice, not patched
around.

Brain review also caught schema-valid explanations claiming causal offer effects. Regression tests now
reject those statements; measured facts are rendered locally and generated hypotheses use a vetted set.

## What we would never delegate to AI
- Publishing a paywall or starting/stopping an A/B test on real users — always a human click.
- Deciding the success metric and the claims we make to the jury; every number is re-checked by a person.
- Handling secrets and production credentials.
- Prices and discounts.
