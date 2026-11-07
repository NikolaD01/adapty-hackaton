# Onboarding (for people) — 10 minutes

1. **Get the code** (while setup lives on `chore/project-setup`):
   ```bash
   git clone https://github.com/NikolaD01/adapty-hackaton.git && cd adapty-hackaton
   git switch chore/project-setup        # after it is merged: stay on main
   ```
2. **Write your role** (this file is not committed):
   ```bash
   echo "My role: A" > CLAUDE.local.md     # A, B, C or D
   ```
   A = Ingest & Rules · B = Brain · C = Adapty & Proposals · D = Dashboard & Demo
3. **Create `.env`**: `cp .env.example .env`, then fill in the keys you need (C: `ADAPTY_SECRET_KEY`,
   B: `OPENAI_API_KEY`). Share keys one-to-one or through a password manager, never in the repo or a group chat.
4. **Environment**
   - Backend: `make install && make test` (needs `python3-venv`; without it: `make test-docker`).
   - Offline dataset (B must, others if needed): `make offline-data`.
   - Frontend (D): `cd web && npm install && npm run dev` (after the first chapter).
   - Adapty CLI (C): the team's dev container (`./dev adapty auth whoami` from the hackathon folder).
5. **Start Claude Code in the repo root** and send:
   > Read CLAUDE.md and your role brief in docs/team/. Create a branch for the first chapter and start. When the chapter is done, run chapter-done.
6. **Working rhythm**
   - One chapter = one branch `<area>/<short-name>` = one PR, ideally under 2 hours.
   - At the start of a session and whenever someone announces a merge: the `sync-main` skill.
   - Shared files (schemas, ports, contract) only through the `contract-change` skill, with one teammate's OK.
   - Commit messages: Conventional Commits, English, no mention of AI anywhere.
   - Everything written into the repo is in English. You may talk to your agent in Serbian.
7. **Sync points (10 min, everyone)**: S1 when ingest and D's mocks run · S2 first end-to-end loop
   (event → value → insight → proposal → approve → segment in Adapty) · S3 demo dry run.
