# Gestion Labo - complete presentation and demo guide

Updated 21 November 2026. Commands use PowerShell from the repository root. The interface is in French; button names below match the application.

Quick navigation: [prepare the PC](#2-prepare-the-presentation-pc), [accounts](#3-accounts-and-three-browser-tabs), [short presentation](#6-short-presentation-using-the-completed-local-case), [full walkthrough](#7-dentist-create-a-fresh-prescription), [machine phases](#15-cnc-demonstrate-all-technicianmachine-phases), [billing](#21-verify-the-delivery-month-statement), [troubleshooting](#23-troubleshooting-during-rehearsal), [stop/resume](#24-stop-cleanly-and-resume).

## 1. What this demonstration proves

Gestion Labo connects a dentist, a dental laboratory and a courier around one traceable prosthesis order. Demonstrate prescription creation, acceptance, physical custody, inspections, design approval, planning, separate technician/machine occupancy, delivery, fitting and the delivery-month statement.

The demo runs the real Django API, PostgreSQL tenant schema, Redis and Celery. Its accounts, equipment and files are synthetic. Machine phases are acknowledged by a person; no CNC, furnace, scanner, printer or CAD application is connected. The sample STL is a tetrahedron for upload testing, not a dental restoration. Inspection selections represent a staged presentation, not clinical certification.

Two presentation options:

- **8-10 minutes:** show completed **MY-TEST-001**, its evidence and statement, then explain the phase sequence using its history. This requires the existing local volumes.
- **25-40 minutes:** create a fresh case and perform sections 7-21. Rehearse once beforehand. A pause or resource conflict can extend the session; clocks and reservation checks remain active.

Do not restart or remake MY-TEST-001: it is already closed. A new installation has seed cases, not the local MY-TEST-001 history. Create a fresh case for a portable live presentation.

## 2. Prepare the presentation PC

Use Docker Desktop running Linux containers and a current Docker Compose plugin. Chrome or Edge must resolve `simlab.localhost` to loopback. Git is useful for transferring source; Node and host Python are unnecessary for the normal Docker walkthrough. They are needed only for development tests.

Clone the demo handoff branch from the contributor repository:

```powershell
git clone --branch feat/virtual-lab-demo --single-branch https://github.com/ramli-04/Project-I.E.git GestionLaboDemo
cd GestionLaboDemo
```

This branch includes the application source, migrations, lockfiles, Dockerfiles, Compose files, `demo/` and maintained documentation. Local credentials, agent checkpoint notes, databases, private files, installed dependencies and generated builds are excluded. A fresh installation creates synthetic fixtures; it does not contain the original PC's completed MY-TEST-001 case.

Build on the destination PC while internet is available:

```powershell
docker compose -f compose.demo.yml up -d --build
docker compose -f compose.demo.yml ps -a
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
```

Expected: `bootstrap` exited with code 0; PostgreSQL, Redis and backend are healthy; frontend, worker and Beat are running. First startup builds images, migrates dedicated demo schemas and seeds synthetic data. Existing progress is preserved on later starts.

Open **http://localhost:18080/**. Confirm the simulation indication. The environment diagnostic at **http://localhost:18000/platform/environment/** must report SIMULATION and a reachable database.

The dedicated project is `cabinet-virtual-lab`. Frontend 18080 and API 18000 bind to localhost. Database, Redis, signing key and private demo files live in its named volumes. The native Windows database and `.env` are not mounted. External email/WhatsApp dispatch is disabled in simulation mode.

## 3. Accounts and three browser tabs

All accounts initially use the synthetic password **`Demo-Lab-2026!`**. An existing environment preserves changed passwords; use those if someone deliberately changed them.

| Tab / portal | Account | Laboratory | Purpose |
| --- | --- | --- | --- |
| Laboratory | Demo Manager | SIMULATION Laboratory | Full guided demo, supervision and billing |
| Dentist | Demo Dentist | Choose SIMULATION Laboratory when creating an order | Prescription, design decision, PIN and fitting |
| Courier | Demo Courier | SIMULATION Laboratory | Signed custody scans and delivery |

Other laboratory accounts: **Demo Reception**, **Demo CAD A**, **Demo CAD B**, **Demo Fabrication**, **Demo Quality**. Use them to demonstrate role restrictions after the main walkthrough. The manager is used for the main presentation so early-start supervision is available. Planning still checks the assigned technician's resources and qualifications.

Open three tabs at localhost18080 and sign into the appropriate portal in each. A newly opened or duplicated tab may initially copy the first tab's session; use **Mon compte > Déconnexion** in that tab before signing in as another role. Verify the visible account before each action.

## 4. Prepare the test file, reference and signed QR input

Use **`demo/demo-design.stl`** for the DESIGN upload. It is small, closed, synthetic geometry and carries an explicit non-manufacturing name inside the file. No clinical STL is needed for this physical-impression scenario. A digital variant can use the same file as its synthetic scan.

Choose a unique anonymous reference, for example **DEMO-20261121-01**. Use a new suffix on each rehearsal. Write it down and use exactly the same reference in all portals, the production lot and the QR helper. Never use a person's name.

The courier requires **signed QR content**, not the patient reference, UUID or PNG filename. A physical scanner can provide the label's decoded text. For a laptop-only presentation, the included helper produces a fresh signed token using the same signing function as the label endpoint:

```powershell
.\demo\Read-DemoQr.ps1 -Reference DEMO-20261121-01 -Copy
```

Replace the example reference with your actual fresh case. `-Copy` puts the token on the Windows clipboard; omit it to print only. If local execution policy prevents running the file, invoke it in a process without changing machine policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\Read-DemoQr.ps1 -Reference DEMO-20261121-01 -Copy
```

The helper is restricted to the simulation container, schema `simlab`, and demo-style references. It only reads the case and generates signed label content; it does not record a collection, deposit, checkout or delivery. The normal authenticated courier button still performs each action and its validations. It fails if the reference is absent or ambiguous. Never commit tokens or PINs to documentation. Generate fresh content when a label expires; old labels can fail after a signing-key or case nonce change.

## 5. How the clinical dialog and reason dropdowns work

In **Commandes**, search for the reference, click **Ouvrir le diagramme**, then use the clinical dialog. If closed, reopen with **Ouvrir les documents et actions**.

| Section | What to do there |
| --- | --- |
| Étape et choix techniques | Analysis/reception confirmations, route, delivery date, saving and advancing |
| Contrôles et documents | Inspections, uploads, design decisions, QR/PDF downloads, PIN, fitting, pause and rework |
| Progression et machines | Current task, start/complete, equipment phases, operational pause and blocking |

For **Notes et motif de l’action**, **Commentaire de progression / motif du blocage**, and planning **Motif de supervision**, choose a French **motif prédéfini**. Available choices depend on the clinical stage or current machine phase. For an ordinary reason, no typing is needed. Add an optional **Précision** when needed. Choose **Choisir un motif ou saisir une note libre** to use free text alone; existing detail is retained when changing the selected reason.

Selecting a reason only prepares a note. Click the intended action to save it. It never checks inspection criteria, approves a design, finishes a cycle or bypasses a mandatory reason. Failure retains the reason/detail for correction; a successful clinical or progress command clears the submitted note. Select the appropriate reason again for the next action. General **Problèmes actuels** and **Notes du dossier / consignes techniques** remain editable dossier information.

Success messages appear at the top for eight seconds. Errors stay until dismissed or replaced and remain visible above an open dialog. Read the message and confirm the new state before proceeding. Case lists refresh periodically and when returning to a tab; planning refreshes approximately every 10 seconds. Use **Actualiser** or **Actualiser le dossier** if a preceding action just completed.

## 6. Short presentation using the completed local case

1. In Demo Manager, open **Commandes**, search **MY-TEST-001**, and open its diagram. Explain the ordered checkpoints from prescription to validated fitting. Expected final state: **Essayage validé**.
2. Open **Contrôles et documents**. Show its private design attachment, approved design version, inspections and **Historique et preuves**. Its design wait suspended the deadline for 263 seconds. Do not create another inspection or rework for this completed example.
3. Open **Progression et machines**, expand **Afficher tout le parcours** and the history. Explain loading, autonomous cycle and confirmed unloading. During the cycle the machine remains occupied while the technician is available for other work.
4. Show **Facturation**, select SIMULATION Clinic and November 2026 in **Cabinet et mois de livraison**, and locate **MY-TEST-001 : 1 500,00 MAD** exactly once. It was delivered21 November 2026; its standard-service surcharge is 0. Leave its line included and uncontested.
5. Explain that delivery enters the statement, whereas fitting closes the clinical case. Month-end invoicing is a separate operation after the month ends. Conclude with the preserved audit trail and tenant/role separation.

If MY-TEST-001 is not present, this is a fresh installation. Use the full walkthrough below, not an invented completed-case screenshot.

## 7. Dentist: create a fresh prescription

1. Sign into **Demo Dentist** and open **Nouvelle prescription**.
2. Select **SIMULATION Laboratory** and **SIMULATION Clinic** with its synthetic pickup address.
3. Enter your unique reference, e.g. DEMO-20261121-01.
4. Keep one tooth: **Dent FDI 11**, **Fonction Couronne**, **Forme Anatomique**, **Teinte A1**, **Matériau E-Max**. These are demonstration inputs, not a prescribed treatment.
5. Select **Empreinte Physique**, **Standard J+4**, and **Demander une validation du design avant fabrication**.
6. Check **Je confirme la désinfection selon le protocole** for this staged synthetic case. Click **Envoyer la prescription** once.
7. Expected: **Prescription enregistrée**, server-confirmed price **1 500,00 MAD** with the default demo catalogue. Save the one-time delivery PIN privately, or issue a new one later. If the catalogue was changed, explain the actual server price instead of forcing 1500.
8. Click **Voir mes commandes**. Filter for the exact reference. Keep this tab for design approval, QR and fitting.

## 8. Laboratory: accept and analyze

1. In **Demo Manager > Commandes**, search for the exact reference under received orders.
2. Click **Accepter [reference]**. Open its diagram. Acceptance creates the planning work; it does not mark the case physically received.
3. In **Étape et choix techniques**, advance from **Demande reçue** to **Analyse de la demande** if that preliminary step is shown.
4. Check **Analyse de la demande validée**. Set a reasonable future **Livraison prévue** date and save the information if needed.
5. Click **Valider → [next step]**. Expected: **Ramassage à organiser / En attente de ramassage coursier**. The analysis checkbox belongs to the stage section, not the inspection checklist.

## 9. Courier: collect the physical impression

1. In the dentist's **Contrôles et documents**, download **Étiquette QR** for this case. Show the label to the audience.
2. Run the QR helper from section 4 with the exact reference, or read the PNG with a QR scanner. Copy the entire signed token, including its leading dot if present.
3. In **Demo Courier > Collectes et livraisons**, locate the reference and click **Confirmer la collecte**.
4. Paste into **Contenu du QR signé du dossier** and confirm collection in the dialog.
5. Expected: courier is **en route vers le laboratoire**. The successful QR dialog closes and clears. Collection has not yet deposited the case.

## 10. Courier arrival and laboratory reception

1. On the same courier case, click **Scanner à l’arrivée au laboratoire**. Paste a valid signed token and click **Valider le QR d’arrivée**.
2. Expected: laboratory reception is pending (**A_CONFIRMER**). This is a separate custody event from pickup.
3. Return to Demo Manager and the case. Refresh if necessary. In **Étape et choix techniques**, check **Réception et conformité des éléments confirmées** and save.
4. Advance to the dossier/physical inspection checkpoint. If the same reception step still offers inspection, complete it there before advancing.

## 11. Physical inspection, plaster and scan

1. In **Contrôles et documents**, choose **Contrôle conforme** in the reason dropdown.
2. Manually check all five: **Absence de déformation**, **Absence de bulles**, **Limites lisibles**, **Occlusion**, **Hygiène**. Leave **Écart nécessitant une photo** unchecked for the passing scenario.
3. Click **Enregistrer le contrôle**. Expected: success at the top. The checklist resets after successful saving; consult **Historique et preuves** for the saved inspection. A reason selection alone cannot save a passing inspection.
4. In **Étape et choix techniques**, advance to **Coulée du plâtre**. Explain that the physical work is staged, then advance through **Scan laboratoire** to **Contrôle modèle et scan**. Use the current **Valider → ...** button at each checkpoint; do not attempt to drag across several stages.
5. At the model inspection, select **Contrôle conforme**, manually check **Modèle** and **Scan**, leave the gap unchecked, and click **Enregistrer le contrôle**.
6. Advance to **Planification**. If a control is disabled, review the saved inspection and current stage instead of selecting later workflow cards.

## 12. Select the CNC route

1. In **Étape et choix techniques**, select **Méthode de fabrication : CFAO / usinage CNC**.
2. Select **Traitement après usinage : Cristallisation**.
3. Choose a future **Livraison prévue** date suitable for the presentation; enter any optional dossier instructions.
4. Save/advance with the visible stage button to **Conception numérique / CAO**. The server now supplies the CNC and thermal route in the diagram.
5. Show **Planning** briefly: employee, equipment, chronological reservations and workload. Synthetic shifts initially cover almost the whole day, every day, for rehearsals. They are not proposed real working conditions.

## 13. Upload and request design approval

1. Return to the case at CAO. In **Contrôles et documents > Documents privés**, select **Type Design**.
2. Choose `demo/demo-design.stl` and click **Téléverser**. Expected: the private DESIGN attachment appears in the list.
3. Choose **Design prêt à soumettre** from the reason dropdown.
4. Under **Demander la validation du design**, select the uploaded file and click **Soumettre au dentiste et suspendre le délai**.
5. Expected: a pending design version and a suspended deadline. Do not use a production completion button to bypass the dentist decision.
6. Switch to Demo Dentist, filter the same reference, and open **Contrôles et documents**. Refresh if needed. Click **Consulter le design** to show the private download, choose **Design approuvé**, then click **Approuver** for the staged successful case.
7. Expected: design status **Approuvé**. Return to Demo Manager; the deadline resumes and the case can reach **Préparation FAO / placement et parcours outil**. If CAO still needs its displayed advance control, use it after approval. The accumulated suspension is shown in seconds.

## 14. Create the production lot

1. In Demo Manager, open **Stocks et lots > Stock** and find **Créer et lier un lot**.
2. Enter a unique **Code unique**, e.g. **LOT-DEMO-20261121-01**.
3. Choose **Virtual mill** as the machine. Select only your current case in **Dossiers du lot**; this is a multiple-selection list, so verify the highlighted reference.
4. For the main successful demonstration, leave **Consommable du lot : Sans consommable**. Click **Créer le lot**.
5. Expected: the lot appears under **Lots enregistrés** linked to your case. This demonstrates lot linkage, not measured stock consumption. Stock/loss testing is separate.
6. Return to the case. Complete the displayed **Préparation FAO** checkpoint and advance to **Usinage CNC** using the stage controls after explaining the staged setup preparation.

## 15. CNC: demonstrate all technician/machine phases

In **Progression et machines**, use the current Usinage CNC task. Keep its current state visible to the audience.

| Action | Reason dropdown | Expected occupancy/state |
| --- | --- | --- |
| Démarrer | Optional note | Attended loading/setup; technician and machine occupied |
| Démarrer maintenant et replanifier, if reservation is in the future | Démarrage anticipé; manager only | Starts now only if protected reservations and availability allow |
| Chargement terminé : lancer le cycle | Chargement terminé, optional | Autonomous cycle; technician released, machine occupied |
| Confirmer la fin réelle du cycle | Cycle terminé, required note | Cycle acknowledged; machine still occupied pending unloading |
| Commencer le déchargement | Déchargement en cours, optional | Technician checked/reserved again; machine remains occupied |
| Confirmer le déchargement et terminer | Déchargement terminé, optional | Task finished; machine released; next eligible workflow step |

Choose one of the two start actions, not both. Early start requires an explicit reason and cannot displace other started/locked work. Use standard **Démarrer** when the schedule allows it. A chosen reason enables an action requiring notes, but still does not execute it automatically.

During this staged demo, the presenter represents the operator acknowledging simulated work completion. Do not claim actual equipment telemetry, elapsed manufacturing time or automatic quality approval. The estimated duration is planning information; an elapsed estimate never unloads an occupied machine.

## 16. Crystallisation

1. After CNC unloading, expected case stage is **Traitement thermique**, with a **Cristallisation** task.
2. If it briefly retains a predecessor-unloading block, click **Actualiser** and allow the worker/replan to complete. Do not report a successful start while the task remains blocked.
3. Use the same sequence from section 15: start, launch cycle, choose **Cycle terminé** and confirm, begin unloading, choose **Déchargement terminé** and finish.
4. Point out the intermediate message **Cycle terminé · machine occupée jusqu’au déchargement**. It illustrates why cycle end and machine availability are different events.
5. Expected: **Finition et caractérisation**. A real equipment or operator conflict requires resolution through normal planning, not bypassing the guard.

## 17. Finish the piece

1. In **Progression et machines**, use **Actualiser** if Finition is still awaiting replanning after furnace unloading.
2. Start the task normally, or select **Démarrage anticipé** and use the manager's early-start button if the only issue is a future movable reservation.
3. When the staged finishing work is complete, choose **Finition terminée** and click **Terminer l’étape**.
4. Expected: **Contrôle qualité final**. Manual work uses start/complete; it has no autonomous-cycle buttons.

## 18. Final quality inspection

1. Open **Contrôles et documents > Inspection · Qualité**. Choose **Contrôle conforme**.
2. Manually check all seven: **Marges**, **Contacts**, **Teinte**, **Occlusion**, **Esthétique**, **Glaçage**, **Polissage**.
3. Leave the gap unchecked for this passing synthetic scenario. Click **Enregistrer le contrôle**.
4. Confirm the top success notification. Inputs reset after saving; inspect **Historique et preuves > Inspections** to show the saved record if needed. With no success message, do not infer that the control saved.
5. Open **Étape et choix techniques**, then **Valider → Conditionnement et documents**. Missing/failed evidence must be resolved before advancement. A failure or gap requires a private PHOTO attachment and selecting it as evidence.

## 19. Packaging and dispatch documents

1. In **Contrôles et documents**, download **Bon de livraison PDF**. Verify the case reference and synthetic clinic/address. Download **Étiquette QR** for the same case.
2. In **Progression et machines**, start **Conditionnement et documents** (or use the authorized reason/early-start path).
3. For the staged packed piece, choose **Conditionnement terminé**, then **Terminer l’étape**.
4. Expected: **Prêt pour expédition**. Downloaded documents alone do not complete packaging.

## 20. Courier dispatch, PIN delivery and clinical fitting

1. Obtain fresh signed QR content for this reference using the label/scanner or helper. In Demo Courier click **Sortir du laboratoire**, paste the token in its dialog, and confirm.
2. Expected: **En route vers le cabinet**; the QR dialog closes/clears. Show the separate **Confirmer la livraison** action.
3. In Demo Dentist, use the privately saved PIN. If unavailable, open the case's **Contrôles et documents > Émettre un nouveau PIN de livraison**. It appears once; the old PIN is superseded.
4. Back in Demo Courier, click **Confirmer la livraison**, enter the current four-digit PIN, then confirm. Expected: **Livré**, and the PIN dialog closes/clears.
5. In Demo Dentist, reopen/refresh the same case. Choose **Essayage conforme**, then click **Valider l’essayage clinique** for the successful staged fitting.
6. Expected: **Essayage validé / case closed**. Delivery and fitting are distinct recorded actions. A failed fitting belongs to the documented rework path, not this successful scenario.

## 21. Verify the delivery-month statement

1. In Demo Manager open **Facturation**.
2. In **Cabinet et mois de livraison**, select **SIMULATION Clinic** and the month in which you just confirmed delivery. This is the actual delivery month in **Africa/Casablanca**, not the prescription's planned delivery date.
3. Locate your exact reference once. Default one-tooth E-Max, STANDARD service: **1 500,00 MAD**, no 30% express surcharge. An edited catalogue or multi-tooth case has a different expected amount.
4. Keep the successful case included/uncontested. **Contestée**, **Exclue** and **Motif de l’ajustement** are for a deliberate accounting exception, not steps required to save normal billing.
5. Explain that the delivery statement is created on delivery; clinical fitting closes the case separately. A monthly statement is not yet a closed invoice.
6. Close a period only after its delivery month ends. For November 2026, the earliest eligible date is 1 December in the application's local calendar. If a past, open test period exists and its lines are appropriate, click **Vérifier la clôture**, review the included count/amount, then **Confirmer la clôture et émettre la facture**. Wait for background generation and use **Télécharger le PDF** under **Factures et avoirs**. Do not claim invoice issuance from the current open statement or change the runtime clock to force it.

For a presentation before month-end, stop successfully at the open statement and explain this guard. Historical monthly-closing/PDF regression evidence is recorded in docs/TEST_RESULTS.md; it uses an isolated test database and does not alter the demo server clock.

## 22. Optional controlled error and alternate-route demonstrations

Use a separate fresh case for each exception. Preserve the completed example.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Bad QR | Alter one character and submit once | French error at top; dialog/input retained; custody stage unchanged |
| Incomplete inspection | Leave one criterion unchecked without required photo | Rejected; French photographic-evidence guidance; no advancement |
| Design corrections | Dentist enters a reason and requests corrections | Approval withheld; corrected design/version must be resubmitted |
| Incorrect PIN | Submit one wrong PIN, then the actual PIN | French rejection, then normal delivery; repeated guesses trigger protection |
| Digital intake | New NUMERIQUE case with the synthetic STL | Upload and digital inspection instead of physical collection/plaster steps |
| Express pricing | Separate new E-Max case, Express J+2 | Default1500 base + 450 surcharge = 1950 MAD |
| Rework/stock | Separate case with real measured synthetic consumption | Linked cause/corrective action; losses reference existing usage without a second deduction |

Measured-stock testing needs a compatible inventory item, lot and usage movement. The main no-consumable lot does not prove stock valuation or losses. Do not invent measurements. Rework, concurrency, historical billing and tenant isolation also have automated coverage; physical device compatibility remains unverified.

## 23. Troubleshooting during rehearsal

| Symptom | What to check |
| --- | --- |
| Cannot log in | Correct portal, account, laboratory and preserved password. For HTTP429 wait for the throttle window; do not disable it. |
| API/network error | Docker health, SIMULATION environment endpoint, browser resolution of simlab.localhost. If required, configure a machine-local hosts entry to 127.0.0.1. |
| Case missing in another tab | Exact reference, owning dentist/laboratory, account identity; refresh after the prior action. |
| Disabled cycle confirmation/pause/block | Select the appropriate reason or enter a free note. Verify operator permission and current phase. |
| Future start | Wait for the reservation, or manager selects Démarrage anticipé and uses the dedicated button. |
| Equipment or technician blocked | Check predecessor unload, active tasks, qualifications, shifts and protected reservations in Planning. An unresolved real hold must be completed normally. |
| Old predecessor block after unloading | Actualiser; wait for the asynchronous replan. Inspect planning/history if it persists. |
| Inspection checkboxes empty after save | Check success notice and saved evidence. This is a new blank input form after success, not proof the saved inspection vanished. |
| Invalid QR | Exact signed content for this case; no surrounding quotes/spaces, no filename. Generate fresh content if expired. |
| Invalid PIN | Use the current four digits; reissuing replaces the old PIN. Preserve leading zeroes. |
| No current-month closing | Expected until the month ends. Show the open statement. |

Diagnostic commands from the repository root:

```powershell
docker compose -f compose.demo.yml ps -a
docker compose -f compose.demo.yml logs --tail=80 bootstrap backend celery_worker
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
```

## 24. Stop cleanly and resume

```powershell
docker compose -f compose.demo.yml stop
docker compose -f compose.demo.yml ps -a
```

This preserves database, audit history, private uploads and signing keys. Start again with:

```powershell
docker compose -f compose.demo.yml up -d
```

Do not remove volumes to restart a presentation. A volume reset destroys the local completed case and its files. No reset command is required for this guide. Seed reruns preserve existing progress and account changes.

## 25. Developer verification, separate from the audience walkthrough

From `cabinet_frontend`, with Node dependencies and Playwright Chromium installed:

```powershell
npm.cmd ci
npx.cmd playwright install chromium
npm.cmd test
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

The default browser suite uses mocked API responses. For real-API/browser tests, use the separate verification project so a presentation's loaded resources are not occupied by test cases. From the repository root:

```powershell
docker compose -p cabinet-ui-verification -f compose.demo.yml -f compose.verify.yml up -d --build
Push-Location cabinet_frontend
$env:VIRTUAL_LAB_FRONTEND = 'http://localhost:18081'
$env:VIRTUAL_LAB_BACKEND = 'http://127.0.0.1:18001'
$env:VIRTUAL_LAB_PROJECT = 'cabinet-ui-verification'
try {
    npx.cmd playwright test --config=playwright.live.config.js
} finally {
    Remove-Item Env:VIRTUAL_LAB_FRONTEND, Env:VIRTUAL_LAB_BACKEND, Env:VIRTUAL_LAB_PROJECT
    Pop-Location
    docker compose -p cabinet-ui-verification -f compose.demo.yml -f compose.verify.yml stop
}
```

Requires Compose support for `!override`. Verification creates persistent BROWSER cases in its own volumes. Repeated starts preserve them. A full backend regression can be run against a disposable PostgreSQL test database using `docker compose -f compose.demo.yml exec -T backend python manage.py test api customers --noinput`. Historical-schema tests and clock changes stay inside that test process.

Current results: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md). Technical documentation: [docs/README.md](docs/README.md). Native development setup: [README.md](README.md). Graphify: [docs/GRAPHIFY.md](docs/GRAPHIFY.md). Device connections remain future work.
