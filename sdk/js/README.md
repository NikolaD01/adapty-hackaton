# feature-signal-sdk

Send behavior events from the app to Feature Signal. Zero runtime dependencies (browser `fetch`,
`crypto.randomUUID`, timers). Contract: `docs/contracts/api.md`.

```ts
import { init, registerFeature, registerEventType, track, flush } from 'feature-signal-sdk'

init({ baseUrl: 'http://localhost:8000', appId: 'c6c7bdd1-1010-4343-8b29-837a77793cab', customerUserId: 'u_42' })
await registerFeature({ key: 'ai_generate', name: 'AI generation', description: 'Generate an image', plans: ['premium'] })
await registerEventType({ key: 'generate_click', name: 'Generate', description: 'User clicked generate', features: ['ai_generate'] })
track('generate_click', { tokens_used: 40, tokens_left: 0 })   // buffered; sent every 2 s or at 20 events
await flush()                                                   // optional: send now
```

- `track` stamps `event_id` (UUID) and `occurred_at` (phone time). A failed send keeps the events with the
  same ids; the next flush retries and the backend counts them once.
- Props: numbers, booleans, null, strings ≤100 chars, at most 20. Anything else (a prompt, an object) is
  dropped with a console warning — send `prompt_len`, not the prompt.
- `init({ apiKey })` sends `X-Api-Key` when the backend sets `INGEST_API_KEY` (off by default).
- Also: `setUser(id)`, `pending()`, `shutdown()`.

`npm test -- --run` · `npm run typecheck` · `npm run build` (Node 20).
