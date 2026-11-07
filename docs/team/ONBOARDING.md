# Onboarding (za ljude) — 10 minuta

1. **Kloniraj repo** i uđi u njega:
   ```bash
   git clone https://github.com/NikolaD01/adapty-hackaton.git && cd adapty-hackaton
   ```
2. **Upiši svoju ulogu** (fajl se ne commit-uje):
   ```bash
   echo "My role: A" > CLAUDE.local.md     # A, B, C ili D
   ```
   A = Ingest & Rules · B = Brain · C = Adapty & Proposals · D = Dashboard & Demo
3. **Napravi `.env`**: `cp .env.example .env`, pa upiši ključeve koje ti treba (C: `ADAPTY_SECRET_KEY`,
   B: `OPENAI_API_KEY`). Ključeve deli preko password managera ili poruke 1-na-1, nikad u repo ili grupni chat.
4. **Okruženje**
   - Backend: `make install && make test` (traži `python3-venv`; ako ga nemaš: `make test-docker`).
   - Offline dataset (B obavezno, ostali po potrebi): `make offline-data`.
   - Frontend (D): `cd web && npm install && npm run dev` (posle prvog poglavlja).
   - Adapty CLI (C): kontejner iz root-a hakaton foldera (`./dev adapty auth whoami`).
5. **Pokreni Claude Code u root-u repoa** i pošalji mu prvu poruku:
   > Pročitaj CLAUDE.md i svoj brief iz docs/team/. Napravi granu za prvo poglavlje i kreni. Kad završiš poglavlje, pokreni chapter-done.
6. **Ritam rada**
   - Jedno poglavlje = jedna grana `<oblast>/<kratko-ime>` = jedan PR, idealno ispod 2 sata.
   - Na početku sesije i kad neko javi merge: `sync-main` skill.
   - Zajednički fajlovi (šeme, portovi, ugovor) samo preko `contract-change` skill-a, uz OK jednog kolege.
   - Commit poruke: Conventional Commits, engleski, bez ikakvog pominjanja AI-ja.
7. **Sync tačke (10 min, svi)**: S1 kad ingest i D-ovi mockovi rade · S2 prvi krug od kraja do kraja
   (događaj → vrednost → uvid → predlog → odobri → segment u Adapty-ju) · S3 proba demoa.
