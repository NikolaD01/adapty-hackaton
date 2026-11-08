# Ingest sequence

What happens when the app sends events. Implemented in `sdk/js/src/index.ts`,
`repositories/events.py`, `services/ingest_service.py`, `services/value_service.py`; the membership
sync is C's (`app.state.membership_sync`).

```mermaid
sequenceDiagram
    autonumber
    participant App
    participant SDK as feature-signal-sdk
    participant API as POST /events
    participant DB as SQLite
    participant Val as ValueService
    participant Sync as MembershipSync [C]
    participant Adapty as Adapty Server API

    App->>SDK: track("ai_enhance", {edits_left: 0})
    Note over SDK: event_id = uuid, occurred_at = phone time<br/>free text dropped, buffered
    SDK->>API: flush every 2 s or at 20 events (≤500)
    API->>DB: INSERT … ON CONFLICT(event_id) DO NOTHING RETURNING
    API->>DB: counters += only for inserted rows
    API->>DB: COMMIT
    alt network error or 5xx
        API--xSDK: failure
        Note over SDK: keep the same event_ids, retry on next flush
    end
    API->>Val: recompute values for the batch's users
    Val->>DB: rules.apply over each user's history, upsert values
    API-->>SDK: {accepted, duplicates, unknown_keys}
    API-)Sync: background: sync_users(app, users)
    Sync->>DB: tiers, live proposals, last written attributes
    opt a tier or the group changed
        Sync->>Adapty: PATCH profile custom_attributes (changed keys only)
        Note over Adapty: segment_hash changes in ~0.6 s
    end
```
