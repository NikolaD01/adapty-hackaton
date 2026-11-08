# 05 — Membership sync (the fast loop)

**Area:** C · **Branch/PR:** `adapty/membership-sync` · **Date:** 2026-11-08

## What
After every ingest batch (or on `POST /membership:sync`) each user's Adapty attributes are re-computed and only the
changed ones are written: `f_<feature>_tier` and `p_segment`.

## Why
A click must move the user into the Adapty segment in seconds (0.6 s on Adapty's side), without ever rewriting
unchanged profiles or leaking history into the 30 attribute slots.

## How it works
1. `services/membership_service.py:MembershipService.sync_users(app_id, ids | None)` — `None` = every user with values.
2. Per user: `f_<feature>_tier` for each **passed** tier (`TierStore`, max 10 features, sorted by feature) from the user's
   value (`ValueStore.matrix`); `p_segment` = `segment_key` of the **first live proposal** (oldest first) whose segment
   conditions the user meets.
3. Diff against `adapty_attribute_state` (`repositories/proposals.py:AttributeStateRepository`): changed keys are
   written, keys the user no longer has are written as `null`. Unchanged user → 0 writes.
4. Writes go through the `AttributeWriter` (C1), at most 8 at once. State is saved only for users whose write succeeded;
   if some failed the call raises `502 membership_sync_partial` after saving the rest, so the next sync retries only those.
5. `SqlMembershipSync(session_factory, writer)` is the `MembershipSync` port A calls after ingest (own session, commits state).
   `POST /membership:sync` uses the same service on the request session; the writer is `app.state.attribute_writer` or the real client.

6. **One `p_segment` per user, shared by identical behaviour.** B splits one behaviour group by native filters (platform,
   country), which Adapty applies itself. Proposals whose `segment_conditions` are identical therefore share the key of the
   earliest of them (`canonical_segment_keys`; drafts count so activating a later one never re-keys users, rejected and failed
   ones do not). Activation (C4) uses the same function for the segment filter (`p_segment IN [<shared key>] AND platform IN
   [Android]`), unless a human edited `condition_value`. Found on 2026-11-08 with B's real drafts: without it the Android
   segments had no members.
7. **The key is frozen on activation** (fix, 2026-11-08). Activation stores the key it used in `condition.value`; for
   `live`/`awaiting_publish` proposals (or any value that differs from the proposal's own key, e.g. a human edit)
   `canonical_segment_keys` uses that value first. Before, rejecting the earlier draft re-keyed the users and left the
   live Adapty segment empty; a human-edited value also differed from what sync wrote.

## Contract touched
`POST /apps/{app_id}/membership:sync`, port `MembershipSync`, table `adapty_attribute_state`.
**Gap found:** a proposal stores only `condition = {attribute: "p_segment", ...}`, not the rule that puts a user in the
segment (the contract text says "our part goes into `condition`"). C reads it from
`evidence["segment_conditions"] = [{field, op, value}]` (field = a rule key, number, or `f_<feature>_tier`, text; ops
`> >= < <= IN NOT IN`; all must hold; none = nobody). B must write it into every draft (task notice `B3`).
Wiring `app.state.membership_sync = SqlMembershipSync(SessionFactory, writer)` in `main.py` is a shared file: separate
contract-change PR.

## How to test
```bash
docker compose run --rm test
```
Expected: `184 passed`, `39 tasks, 0 problems`. Manual (2026-11-08, real Adapty, one test profile): first sync wrote
`f_ai_generate_tier=high` and `p_segment=fs_demo`; the second wrote nothing; lowering the value removed `p_segment`
(`null`); removing the tier cleaned the profile.

## Limits / not claimed
- Segment conditions on Adapty-known fields (`adapty_filters`) are not evaluated here; Adapty's segment does that.
- Condition values are matched on our values as stored; no time windows beyond what the rule already computed.
- Not wired into ingest until `main.py` is changed.

## Status
Done · Next: C4 — activation on approve
