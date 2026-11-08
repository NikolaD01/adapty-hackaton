# From a click to a paywall

Two speeds. The **slow loop** decides what matters and which offer a group gets (a few times in total).
The **fast loop** keeps each user in the right group after every event (seconds).

```mermaid
flowchart TD
    subgraph DEV["Developer, once"]
        F["Define features<br/>groups of events + plans that include them"]
        E["Register event types<br/>name, description, features"]
        F --> E
    end

    subgraph FAST["Fast loop — after every event batch"]
        T["App: track(key, props)"] --> H[("Event history<br/>one row per event")]
        H --> V["Feature profile<br/>default + composed values per user"]
        V --> M{"Tier or group<br/>changed?"}
        M -- yes --> W["PATCH only changed keys<br/>f_feature_tier, p_segment"]
        M -- no --> N["Nothing sent"]
    end

    subgraph SLOW["Slow loop — a few times"]
        AI["AI suggests composed values<br/>ratio · sum · last · where"] --> MEAS["Measurement on unseen users<br/>holdout + bootstrap CI"]
        MEAS -- passed --> TIER["Tiers low / mid / high<br/>measured cut points"]
        MEAS -- "no outcome data" --> HYP["Hypothesis<br/>only an A/B test can tell"]
        TIER --> SEGC["Segment candidates<br/>tiers + Adapty fields"]
        SEGC --> UP["Uplift from randomized arms<br/>which offer for which group"]
        UP --> PR["Proposal"]
        HYP --> PR
        PR --> MODE{"Human or<br/>Autopilot"}
    end

    E -.-> T
    V --> MEAS
    TIER -. "cut points" .-> M
    MODE -- "approve" --> ACT["Adapty: segment = p_segment AND no subscription<br/>A/B on the placement: control = current paywall"]
    W --> ACT
    ACT --> PW["User sees the paywall for their group"]
    PW --> RES["Net revenue in N days, both arms, same window<br/>90 by default, 60 in the live demo"]
    RES -. "learn" .-> MEAS
```

What goes to Adapty: at most 10 `f_<feature>_tier` keys plus `p_segment` (11 of 30 attributes).
Everything else — history, profiles, raw values — stays with us.
