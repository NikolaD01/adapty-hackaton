# Demo script (3 minutes)

The story: Adapty can show a different paywall to a different group, but it doesn't know what users do in
the app. We add that — and the decision still runs on Adapty's own segments and A/B tests.

Status markers: ✅ works on `main` today · ⏳ waits for an open task (owner in brackets). Before the
rehearsal (S3) every line must be ✅ or cut.

## Before you start (10 minutes earlier)
```bash
make demo-reset                 # clean DB, api on :8000, 5000 demo users (≈1 min)
cd web && npm run dev           # http://localhost:5173
```
Tabs, in this order: `localhost:5173/demo` · `localhost:5173/dashboard/insights` ·
`localhost:5173/dashboard/proposals` · Adapty dashboard (Lumen app → Segments, A/B tests) ·
`localhost:5173/dashboard/lookup`. Demo user: **`lumen_282506_00032`** (Android, free, Serbia, **0 AI enhances in 7
days**): one AI enhance moves them into the Android group `0 < ai_enhance_uses_7d ≤ 3`, which gets the lifetime anchor on
`main`. Contrast user for the lookup: **`lumen_282506_00005`** (iOS, 4+ AI enhances, another group).
Approve the proposal **before** going on stage: the first sync writes `f_ai_enhance_tier` to ~5000 real profiles
(measured 37–150 s per approval, `docs/adapty/14-real-run.md`). On stage only the one demo user changes (≈1 s).
Backup: the recorded video (task X3) on the laptop, offline.

## Script
| Time | Screen | Do | Say | State |
|---|---|---|---|---|
| 0:00–0:20 | slide / README | — | "Adapty's own skill says: *a segment over an attribute nobody sets matches nobody.* Apps don't send behavior, so every user sees the same offer." | ✅ |
| 0:20–1:00 | `/demo` | As `lumen_282506_00032`: one **AI enhance** (profile: `ai_enhance_uses_7d` 0 → 1, tier low → mid), then **Export in full resolution** → "Pro only" | "Every click is an event through our 50-line SDK. Watch the profile: uses in 7 days go up, the full-resolution export was blocked." | ✅ (A, D) |
| 1:00–1:40 | `/dashboard/insights` + `/dashboard/metrics` | Show ranking, then **Suggest with AI** | "AI suggests what to measure; statistics decides. AI edits: $3.73 → $16.57 per user. Photos imported sound just as good and predict nothing: flat $8.73–$9.55. Only measured values become tiers in Adapty." | ⏳ ranking (B) · AI suggestions (B6) |
| 1:40–2:40 | `/dashboard/proposals` → Adapty dashboard | **Approve** the proposal; switch to Adapty: the `[fs] …` segment and the running A/B test | "One click. In Adapty: a segment over two attributes we wrote — 11 of 30 slots, whatever the number of features — and an A/B test with a control arm. Users with 5+ edits gain $14.40 from the lifetime offer, users with none only $5.36: the group changes which offer wins." | ⏳ proposals + activation (C3, C4) |
| 2:40–3:00 | `/dashboard/lookup` | Same placement, two users | "Same placement, different paywall, decided by what they did. Purchases come back through Adapty's webhook, so we measure net revenue, refunds included." | ⏳ lookup (C6), membership sync (C9) |

## Numbers we say (and where they come from)
| Claim | Source |
|---|---|
| `ai_edits_first_day` $3.73 → $16.57 ARPU; `photos_imported` flat $8.73–$9.55 | offline dataset, `docs/plan.md` |
| Lifetime anchor +$14.40 (5+ edits) vs +$5.36 (0 edits), randomized, 90 days | offline A/B arms, B4 test reproduces it |
| Live: Android, 1–3 AI enhances in 7 days → lifetime anchor on `main`, **+$22.60 per user in 60 days** | local live run 2026-11-08 (synthetic events); re-read the number from the proposal card after the rehearsal run |
| 60-day window, not 90 | the seed data covers ~4 months; 90 days leaves too few users per group (`docs/brain/10-outcome-window.md`) |
| Weekly plan refunds 6.9% → we never show conversion alone | offline dataset |
| 11 of 30 attributes | `docs/contracts/api.md` (Adapty attributes) |
| 0.6 s from attribute write to segment change | measured on the seed account (`CLAUDE.md` §5) |

## What we don't claim (say it if asked)
Demo events are synthetic (`props.synthetic = true`); the Lumen dataset is synthetic. Adapty serves per
segment, not per user. The limit-reached paywall's higher revenue is a hint, not causal.

## If something breaks on stage
| Problem | Do |
|---|---|
| API not responding | `make demo` (≈16 s); keep talking over the flow diagram (docs/diagrams/flow.md) |
| Adapty dashboard slow | Show `/dashboard/decisions` (our log of every Adapty step) |
| Lookup returns the same flow | The SDK cache: lookup uses `disable_cache`; re-run after 2 s |
| Anything else | Play the backup video from the current minute |
