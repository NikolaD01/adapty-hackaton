# AI log

We used Codex and Claude Code throughout development—for research, planning, writing code and tests, debugging, and reviewing changes. Each of the four developers worked with an agent. We spent time setting up shared instructions and repeatable workflows so that each session could pick up the work without needing the whole project explained again.

## Tools we used

Alongside the coding agents, we used:

- **Context7 MCP** to look up library documentation while implementing, especially where SDK behavior or response formats mattered.
- **Adapty’s skills plugin and MCP server, together with its CLI**, for platform documentation, account inspection, and checking how integration calls actually behaved.
- **Playwright** to exercise the interface in a browser, check interactions against the local backend, and rehearse the demo.
- **Research subagents** to read documentation and papers in parallel. We also used **REA MCP/CLI** for static research into monetization patterns in other apps; none of their code was incorporated.

## How we set up the agents

Our shared instructions lived in `CLAUDE.md`: the agreed stack, code boundaries, file ownership, testing requirements, git workflow, and integration facts we had already verified. Each developer also had a `CLAUDE.local.md` pointing to their role brief. This kept agents from independently redesigning shared parts or editing another developer’s files.

We agreed on API contracts and shared interfaces early. Agents could work against fakes while another developer was still implementing the real dependency. We also kept a task graph with dependencies and change notices, so a change in one area could flag the people and agents relying on it.

We wrote three project skills for work we otherwise would have had to explain repeatedly:

- **`chapter-done`** covered finishing a piece of work: check scope, run tests, update its documentation, and follow the commit and PR workflow.
- **`contract-change`** covered shared interface changes, including updating the documentation, schemas, fakes, and affected mocks together and getting teammate review.
- **`sync-main`** covered bringing in other developers’ work, checking dependency changes, and rerunning tests.

We also used Superpowers skills for implementation planning, test-first development, and review. For larger tasks, implementation and review were separate agent assignments. The reviewer checked the requirements and actual code, and findings went back to the implementer for correction.

Automated tests used fake external services. Real API checks were separate, deliberately scoped actions. We used isolated worktrees and disposable containers where needed, including database copies for checks alongside the running demo. Agents were expected to report what they had actually tested and what still needed verification.

## Three prompts that worked well

**Checking an integration before coding against it**

> “Run the exact commands the adapter will send, by hand, on one test profile or the test placement, and write the tests from the real answers.”

This caught missing authorization and differences between expected and actual response fields. Giving the agent a specific target and asking for observable results made the answer useful for implementation.

**Checking an analysis instead of accepting its headline number**

> “Recompute the uplift with a fixed 90-day window for both arms, only users with a full window, bootstrap 90% interval.”

This exposed that an earlier comparison used a different observation window. We kept the corrected result, including its uncertainty, even though it made the original conclusion less convincing.

**Evaluating whether better context actually helped**

> “Compare the AI’s rule suggestions before and after, and check each one against the real data.”

Adding typed event properties let the model suggest more relevant rules. But one plausible suggestion—detecting an exhausted quota—matched no users in the seed data. Checking the computed values stopped us from treating a better-sounding suggestion as a useful finding.

## One thing AI got wrong

An agent produced an Adapty attribute update with the wrong payload shape. It looked reasonable, but a call on one test profile returned `400`: Adapty expected a list of key/value entries.

We corrected the request, added tests for the actual payload and headers, and recorded the verified format in the shared instructions. That last step mattered: the next agent session had the answer available instead of having to rediscover it.

The check worked because we tested against the service itself. Tests written around the agent’s original assumption could have passed while the integration remained broken.

## What we would never delegate to AI

Our product automates the routine part of experimentation, so we draw the line at what cannot be undone. Autopilot
may compute values, write attributes, create segments and start an A/B test, but only on placements we allow-list,
at most three at a time and always with a control group of at least 10%. Inside the product the AI does two things
only: it suggests new rules and explains measured results in plain language. It never picks a threshold, segment or
offer, and it does not write paywalls: a person types the title of a paywall draft. Publishing a paywall to real
users is always a human click.

Three things stay with people: publishing paywalls and changing prices, setting the limits Autopilot works inside,
and choosing the success metric and what our evidence lets us claim. We learned this during a live run: drafts
approved by hand pointed at the app's real onboarding placement. We stopped them before anything was created, and
the placement allow-list exists because of that.
