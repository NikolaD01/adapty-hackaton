# System

Who talks to whom. Owners in brackets (A ingest & rules, B brain, C Adapty & proposals, D dashboard).
In the demo the mobile app is `web/demo`.

```mermaid
flowchart TB
    subgraph Client["Mobile app"]
        SDK["feature-signal-sdk<br/>track · flush"]
        ADSDK["Adapty SDK<br/>shows the paywall"]
    end
    DASH["Dashboard · web/ [D]"]

    subgraph FS["Feature Signal API (FastAPI) + SQLite"]
        ING["Catalog · ingest · rules · values [A]"]
        BRAIN["Ranking · tiers · uplift · insights [B]"]
        PROP["Proposals · membership sync · activation<br/>lookup · paywall draft [C]"]
        ING -- "after commit:<br/>users of the batch" --> PROP
        BRAIN -- "proposal drafts, tiers" --> PROP
        ING -- "values" --> BRAIN
    end

    subgraph EXT["Outside services"]
        LLM["OpenAI<br/>rule suggestions, texts"]
        OFF[("Offline dataset<br/>purchases, A/B arms")]
    end

    subgraph AD["Adapty"]
        ADAPI["Server-side API + CLI"]
        SEG["Segments · audiences · A/B tests · flows"]
        ADAPI --> SEG
    end

    SDK -- "POST /events" --> ING
    DASH -- "REST /v1" --> FS
    BRAIN -.-> LLM
    BRAIN --> OFF
    PROP -- "p_segment, f_*_tier,<br/>segment, A/B" --> ADAPI
    SEG -- "flow for the user's segment" --> ADSDK
```

## Code layers

Every area follows the same layers. `domain/` is pure, so statistics can never call the LLM.

```mermaid
flowchart TB
    R["api/v1 — thin routes<br/>parse · call service · return"] --> S["services — order of work<br/>ports passed in the constructor"]
    S --> P{{"domain/ports.py<br/>EventSink · ValueStore · TierStore · MembershipSync<br/>AttributeWriter · AdaptyCli · LLMProvider …"}}
    S --> D["domain — pure functions<br/>rules.apply · ranking · uplift"]
    P --> REP["repositories<br/>SQLAlchemy, tables"]
    P --> INT["integrations<br/>adapty · llm"]
    REP --> DB[("SQLite")]
    INT --> EXT["Adapty · OpenAI"]
    D -. "no I/O imports<br/>(tests/unit/test_architecture.py)" .- P
```
