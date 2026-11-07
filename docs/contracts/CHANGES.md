# Contract changes

Append newest first. Every change to a shared file (CLAUDE.md §6) gets a line here in the same PR.

| Date | Area | Change | Who acked |
|---|---|---|---|
| 2026-11-08 | contracts | Feature model: `features` resource with `plans` and default rules; event `features` list replaces `family`; typed `props` (no free text); measures `ratio`/`sum`/`last`/`max`/`min` + `where`; feature profile route; `tiers` + `hypotheses` in InsightRun; Adapty keys = `p_segment` + `f_<feature>_tier` (drops `p_tier`, `p_top_feature`, `p_top_feature_count`, `p_score`); proposal `adapty_filters`, `highlight_feature`, `needs_publish`, status `awaiting_publish`; `membership:sync` + `MembershipSync`/`TierStore`/`FeatureRepo` ports | pending |
| 2026-11-07 | contracts | v1 frozen: endpoints, schemas, ports, Adapty attribute keys | team |
