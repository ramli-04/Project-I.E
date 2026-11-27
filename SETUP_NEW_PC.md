# Setup on a new PC — instructions for the coding agent

You are setting up **Gestion Labo v1.0** on a fresh Windows PC so the owner can run and test the demo. Do the steps in order and report the result of each one. Explain each step to the owner in **Darija** in short sentences. Keep code and commands in English.

## 0. Rules

- **Never run `docker compose … down -v`** and never delete Docker volumes: that erases the demo data.
- **Never commit or push** unless the owner explicitly asks.
- **Never create or print secrets.** `.env`, `.runtime/` and `private_media/` are local only and are not in git; the demo does not need a `.env`.
- **Never connect real devices and never enable real email or WhatsApp.** The demo runs in SIMULATION mode.
- **Graphify:** read `AGENTS.md`. If `graphify-out/graph.json` exists, query it before exploring code. It is usually absent on a fresh clone; that is fine for setup work.
- **Know what is missing on purpose:** on this PC the database starts **empty except for the seeded demo**. The owner's hand-tested cases from the main PC (**MY-TEST-001**, **TEST-2611-01**) live only in that PC's Docker volumes. They are not in git, and their absence is expected. Never "recreate" them by editing rows.

## 1. Prerequisites (check, don't guess)

```powershell
docker version
docker compose version
git --version
```

- **Docker Desktop** must be running Linux containers, with WSL 2 and "Engine running". If it isn't, tell the owner how to start it and wait.
- **Ports 18080 and 18000 must be free:**
  ```powershell
  netstat -ano | findstr ":18080 :18000"
  ```
  This should print nothing. If something is listed, report which process owns the port; don't kill it without the owner's OK.
- **Internet** is required for the first build (images, pip and npm packages).

## 2. Get the code

```powershell
git clone https://github.com/ramli-04/Project-I.E.git GestionLabo
cd GestionLabo
git log -1 --oneline
```

`main` contains v1.0. If `main` does not contain this file, `SETUP_NEW_PC.md`, use the branch instead:

```powershell
git checkout feat/virtual-lab-demo
```

## 3. Build and start the demo

```powershell
docker compose -f compose.demo.yml up -d --build
docker compose -f compose.demo.yml ps -a
```

The first build takes about 5–15 minutes. Expected `ps -a` state:
- `bootstrap`: **Exited (0)**. It ran migrations and seeded the synthetic demo.
- `postgres`, `redis`, `backend`: **healthy**.
- `frontend`, `celery_worker`, `celery_beat`: **running**.

Then run the built-in health check:

```powershell
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
```

Open http://localhost:18080 and confirm the yellow **SIMULATION** banner. http://localhost:18000/platform/environment/ must report `SIMULATION` and a reachable database.

## 4. Demo accounts (created by the seed)

| Portal | Laboratory | Accounts |
|---|---|---|
| Laboratoire | SIMULATION Laboratory | Demo Manager, Demo Reception, Demo CAD A, Demo CAD B, Demo Fabrication, Demo Quality |
| Dentiste | (choose the lab per order) | Demo Dentist |
| Coursier | SIMULATION Laboratory | Demo Courier |

Initial password: **`Demo-Lab-2026!`**. It is a public synthetic password defined in `compose.demo.yml`.

## 5. Presentation data (recommended)

These scripts add realistic data **through the real API**. Both are idempotent, so running them twice changes nothing. Keep the `cmd /c "… < file"` form: it preserves French accents. A PowerShell pipe would corrupt them.

```powershell
cmd /c "docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python - < demo\prepare_v1_operations.py"
cmd /c "docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python - < demo\prepare_v1_cases.py"
```

**What `prepare_v1_operations.py` does:**
- adds 5 staff, for a team of 10: 2 reception, 3 CAO, 3 FAO, 2 quality, with skill levels and Mon–Fri 08:00–17:00 shifts;
- sets lab hours to Mon–Sat 08:00–17:00 with a 12:00–13:00 break;
- adds 12 consumables, 2 of them below the alert threshold;
- pauses and archives old or test cases, which are then hidden behind a toggle in the UI.

**What `prepare_v1_cases.py` does:** adds one `V1-…` case at each of the 9 stages, plus a late case, a rework and a design pause.

**Never run `prepare_v1_operations.py` on the verification project** (`cabinet-ui-verification`). Its live tests start tasks immediately and expect the 24/7 seed hours.

Because the hours are real, outside 08:00–17:00 each production step needs the manager's **"Démarrage supervisé"**. Tell the owner to test during the day.

## 6. Quick functional check (read-only, nothing submitted)

Log in and confirm each screen shows what is expected:

1. **Demo Manager:**
   - lands on **À faire**, with alerts at the top;
   - **Tableau de bord**;
   - **Commandes**, showing a "Afficher les dossiers de test et archivés" toggle;
   - **Stocks et lots**: 12 consumables after step 5;
   - **Planning**;
   - **Facturation**: the "Commandes livrées" table;
   - **Configuration**, which contains "Diagnostic technique".
2. **Demo Dentist:** lands on **Mes commandes**. In **Nouvelle prescription**, the teeth are clicked on a chart, and Fonction, Forme and Teinte are dropdowns.
3. **Demo Courier:** **Collectes et livraisons**. Each handover offers "Importer l'image du QR".

Report anything broken with a screenshot plus:

```powershell
docker compose -f compose.demo.yml ps -a
docker compose -f compose.demo.yml logs bootstrap --tail 50
docker compose -f compose.demo.yml logs backend --tail 50
```

## 7. Stop and resume without losing data

```powershell
docker compose -f compose.demo.yml stop      # stop
docker compose -f compose.demo.yml up -d     # resume (no rebuild needed)
```

## 8. Optional: tests (only if the owner asks)

- **Frontend unit tests:**
  ```powershell
  cd cabinet_frontend
  npm ci
  npm test
  ```
- **Mocked browser tests:**
  ```powershell
  npx playwright install chromium
  npx playwright test
  ```
- **Live and backend suites:** follow `DEMO_GUIDE.md` §25, which uses the separate `cabinet-ui-verification` project. Stop that project afterwards **without** `-v`.

## 9. Where to learn more

- `README.md`: features, architecture, v1.0 scope and v2 roadmap.
- `DEMO_GUIDE.md`: full click-by-click walkthrough. See the sections on QR, lots, billing and the v1.0 presentation data.
- `docs/GUIDE_UTILISATEUR.md`: a French guide per role.
- `docs/TEST_RESULTS.md`: latest verified results, newest first.
- The development brief (`AGENT_PROMPT_UX_STREAMLINING.md`) is kept only on the owner's main PC, outside git. Do not start new development work on this PC unless the owner asks.

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| Build fails downloading packages | Internet, proxy or VPN; rerun `up -d --build` |
| `bootstrap` exited non-zero | `docker compose -f compose.demo.yml logs bootstrap --tail 80` |
| Port already in use | `netstat -ano \| findstr :18080`; ask the owner before stopping anything |
| Page loads but API errors | http://localhost:18000/platform/environment/; Docker health |
| `simlab.localhost` not resolving | Use http://localhost:18080 exactly; the app handles the lab host internally |
| Login refused | Exact account name (e.g. `Demo Manager`), portal and lab selected, password `Demo-Lab-2026!` |
