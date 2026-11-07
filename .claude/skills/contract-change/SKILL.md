---
name: contract-change
description: Use whenever a change touches a shared file - schemas/, domain/models.py, domain/ports.py, docs/contracts/, core/, main.py, api/v1/router.py, pyproject.toml, Makefile, .claude/, CLAUDE.md - or when an endpoint, payload, port signature or Adapty attribute key needs to change. Keeps the four parallel areas from breaking each other.
---

# contract-change

Shared files are the contract between four people working at once. Change them small, explicit and fast.

1. **Is it really needed?** Prefer an additive change (new optional field, new endpoint) over changing
   or removing anything. Removing/renaming a field, an endpoint or an attribute key (`p_segment`, `f_<feature>_tier`) needs the
   whole team's yes — ask the developer to get it.
2. Create a separate branch `contracts/<slug>` from fresh `origin/main` (do not mix with feature work).
3. Make the change in all twins at once:
   - `docs/contracts/api.md` (and `ports.md` if a port changes),
   - `feature_signal/schemas/*.py` / `domain/models.py` / `domain/ports.py`,
   - fakes in `tests/fakes.py` if a port changed,
   - MSW mock examples in `web/src/mocks/` if a response shape changed (tell D if web isn't yours).
4. Append a line to `docs/contracts/CHANGES.md`: date · area · change · who acked.
5. Run the whole test suite; it must stay green (additive changes should not break anyone).
6. Commit `docs(contracts): <what>` / `feat(contracts): <what>`, push, open a PR titled the same.
   Ask the developer to get one teammate (preferably the owner of the affected area) to ack. Then
   squash-merge and tell the developer to announce it to the team ("contract changed: …, run sync-main").
7. Return to your feature branch and run `sync-main`.
