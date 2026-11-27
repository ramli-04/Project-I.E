# Gestion Labo - complete presentation and demo guide

Updated 25 November 2026. Commands use PowerShell from the repository root. The interface is in French; button names below match the application. Use a checkout containing the local Phase 8 changes for capacity, payments, the dashboard and laboratory identity; the handoff status is recorded in `docs/ROADMAP.md`. Phases 6 and 7 keep the demonstration's click paths unchanged. The generated [workflow diagrams](docs/WORKFLOW.md) explain the routes and exception commands; the [BPMN coverage matrix](docs/BPMN_COVERAGE.md) distinguishes verified behavior, partial mappings and missing product decisions.

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

## 5. How the case workspace and reason dropdowns work

Laboratory accounts now land on **À faire**. Accounting still lands on **Facturation** and can open **À faire** for unquoted J+1 requests. The manager can filter by workstation; other accounts see their own role and task assignments. Search by patient reference or dentist.

The four groups are **À faire**, **En attente**, **En pause** and **Travail de l’équipe**. Rows are ordered by delivery risk, deadline and service priority. Each row has one button opening the case workspace. Work assigned to another technician, unassigned work and future bookings show an explanation; opening the workspace does not start or complete anything. The original guards still apply. During an autonomous cycle, look in **En attente** for the explicit cycle-completion and unloading actions.

The dentist portal opens on **Mes commandes** (or **Nouvelle prescription** when there are no cases). Each case card shows a read-only stage strip and **Livraison prévue** (or **Date à confirmer par le laboratoire**). The dentist has an **À faire** block above it. Use its shortcuts for a pending design, delivery PIN, fitting or returned documents. These open the relevant control; the dentist still submits each decision explicitly.

Laboratory users land on **À faire** (accounting lands on **Facturation**). Laboratory alerts (stock, maintenance, contracts, qualifications) appear at the top of that landing page; the alert pop-up opens them there. Managers supervise with **Tableau de bord**. To find a closed case such as MY-TEST-001, use **Commandes**, search for the reference and click **Ouvrir le dossier [reference]**. Closing the workspace returns focus to that card; click it again to reopen. Closed cases are absent from the work queue. The stage strip is read-only, with no drag-and-drop or separate stage-selection tab.

In **Planning**, click a scheduled task to inspect its assignment drawer. **Ouvrir le dossier [reference]** opens the same workspace for the current clinical/task action. Assignment, resources and locking remain in the planning drawer.

| Section | What to do there |
| --- | --- |
| Votre action | The current confirmation, route choice, inspection, design decision or assigned task, with one primary button |
| Signaler un problème (collapsed) | Dossier suspension/resumption, task pause/block, documented rework, measured losses, workstation remark or dentist dispute |
| Dossier (collapsed) | Private documents, design review history, QR/PDF/PIN issuance, explicit information save, J+1 quote, evidence, full route and planning history |

The header lists every tooth, material and shade, the route, urgency, deadline and billing state. Risk uses the server's work queue; if no risk is available for this viewer or a closed case, the header says so rather than guessing. Dentist mode contains only cabinet actions and documents, with no laboratory or planning controls.

For **Notes et motif de l’action**, **Commentaire de progression / motif du blocage**, and planning **Motif de supervision**, choose a French **motif prédéfini**. Available choices depend on the clinical stage or current machine phase. For an ordinary reason, no typing is needed. Add an optional **Précision** when needed. Choose **Choisir un motif ou saisir une note libre** to use free text alone; existing detail is retained when changing the selected reason.

Selecting a reason only prepares a note. Click the intended action to save it. It never checks inspection criteria, approves a design, finishes a cycle or bypasses a mandatory reason. Failure retains the reason/detail for correction; a successful clinical or progress command clears the submitted note. Select the appropriate reason again for the next action. General **Problèmes actuels** and **Notes du dossier / consignes techniques** remain editable dossier information.

Success messages appear at the top for eight seconds. Errors stay until dismissed or replaced and remain visible above an open dialog. Read the message and confirm the new state before proceeding. Lists refresh periodically and when returning to a tab; the workspace refreshes approximately every 10 seconds without resetting drafts. Use **Actualiser le dossier** if needed. If an action succeeded but its refresh failed, the workspace says it was recorded and blocks another action until the data is refreshed.

Inspection criteria start unchecked. **Tout conforme** checks the current criteria locally, sends nothing and leaves the photo-gap flag unchanged. Review the criteria and untick any that fail before submitting. A passing checkpoint can save its evidence and advance in one transaction. A reason preset never checks criteria. Design approval, cycle completion, unloading and fitting keep their explicit decisions.

## 6. Short presentation using the completed local case

1. In Demo Manager, open **Commandes**, search **MY-TEST-001**, and click **Ouvrir le dossier MY-TEST-001**. Explain the read-only stages and the closed-case waiting notice. Expected final state: **Essayage validé**.
2. Expand **Dossier**. Show its private design attachment, approved design version, inspections and **Historique et preuves**. Its design wait suspended the deadline for 263 seconds. Do not create another inspection or rework for this completed example.
3. In **Dossier**, expand **Toutes les tâches du parcours** and **Historique du planning**. Explain loading, autonomous cycle and confirmed unloading. During the cycle the machine remains occupied while the technician is available for other work.
4. Show **Facturation**, select SIMULATION Clinic and November 2026 in **Cabinet et mois de livraison**, and locate **MY-TEST-001 : 1 500,00 MAD** exactly once. It was delivered21 November 2026; its standard-service surcharge is 0. Leave its line included and uncontested.
5. Explain that delivery enters the statement, whereas fitting closes the clinical case. Month-end invoicing is a separate operation after the month ends. Conclude with the preserved audit trail and tenant/role separation.

If MY-TEST-001 is not present, this is a fresh installation. Use the full walkthrough below, not an invented completed-case screenshot.

## 7. Dentist: create a fresh prescription

1. Sign into **Demo Dentist** and open **Nouvelle prescription**.
2. Select **SIMULATION Laboratory** and **SIMULATION Clinic** with its synthetic pickup address.
3. Enter your unique reference, e.g. DEMO-20261121-01.
4. On the tooth chart, click tooth **11** (keyboard: Tab then Enter). A **Dent 11** block appears; choose **Fonction Couronne**, **Forme Anatomique**, **Teinte A1** and **Matériau E-Max** in their dropdowns (**Autre…** opens a free-text field). Clicking a selected tooth again removes it; with several teeth, **Appliquer à toutes les dents** copies the first block on click. These are demonstration inputs, not a prescribed treatment.
5. Select **Empreinte Physique**, **Standard J+4**, and **Demander une validation du design avant fabrication**.
6. Check **Je confirme la désinfection selon le protocole** for this staged synthetic case. Click **Envoyer la prescription** once.
7. Expected: **Prescription enregistrée**, server-confirmed price **1 500,00 MAD** with the default demo catalogue. Save the one-time delivery PIN privately, or issue a new one later. If the catalogue was changed, explain the actual server price instead of forcing 1500.
8. Click **Voir mes commandes**. Filter for the exact reference. Keep this tab for design approval, QR and fitting.

## 8. Laboratory: accept and analyze

1. In **Demo Manager > Commandes**, search for the exact reference under received orders.
2. Click **Ouvrir le dossier [reference]**, then **Accepter et analyser** in **Votre action**. This accepts the request and opens the analysis stage in one action; it does not declare the analysis complete or mark physical reception.
3. Review the prescription and documents. If needed, expand **Dossier**, set **Livraison prévue (dossier)** and click **Enregistrer les informations** explicitly.
4. Click **Analyse validée → [next step]** in **Votre action**. Expected: **Ramassage à organiser / En attente de ramassage coursier**. This button is the explicit analysis confirmation; there is no separate checkbox.

## 9. Courier: collect the physical impression

1. In the dentist's workspace, expand **Dossier** and download **Étiquette QR** for this case. Show the label to the audience.
2. Run the QR helper from section 4 with the exact reference, or read the PNG with a QR scanner. Copy the entire signed token, including its leading dot if present.
3. In **Demo Courier > Collectes et livraisons**, locate the reference and click **Confirmer la collecte**.
4. Click **Importer l’image du QR (photo ou étiquette)** and choose the downloaded label PNG (or a photo of it): the signed content is filled automatically. Pasting into **Contenu du QR signé du dossier** still works, and `Read-DemoQr.ps1` remains a fallback. Confirm collection in the dialog.
5. Expected: courier is **en route vers le laboratoire**. The successful QR dialog closes and clears. Collection has not yet deposited the case.

## 10. Courier arrival and laboratory reception

1. On the same courier case, click **Scanner à l’arrivée au laboratoire**. Paste a valid signed token and click **Valider le QR d’arrivée**.
2. Expected: laboratory reception is pending (**A_CONFIRMER**). This is a separate custody event from pickup.
3. Return to Demo Manager and the case. Use **Actualiser le dossier** if necessary. Confirm actual reception by clicking **Réception confirmée → Contrôle du dossier**. The passing intake inspection remains required at the next checkpoint.
4. If a problem is already evident at reception, expand **Contrôler les éléments reçus ou signaler une non-conformité** instead. Choose the actual failed criteria, a photo and a reason, then **Enregistrer la non-conformité** to return the intake. A passing inspection recorded here does not itself confirm reception or skip the next checkpoint.

## 11. Physical inspection, plaster and scan

1. At the inspection in **Votre action**, choose **Contrôle conforme** in the reason dropdown.
2. Review all five: **Absence de déformation**, **Absence de bulles**, **Limites lisibles**, **Occlusion**, **Hygiène**. Check each manually or click **Tout conforme** for this staged passing case, then review them. Leave **Écart nécessitant une photo** unchecked for the passing scenario.
3. Click **Valider le contrôle → Coulée du plâtre**. Expected: success at the top, a saved inspection and the plaster stage. Consult **Dossier > Historique et preuves** for the record. A reason alone cannot check or save an inspection. A previously saved passing control can still offer **Valider → [next step]**; **Recontrôler** opens a fresh unchecked checklist.
4. Plaster and scan are assigned work tasks: use **Démarrer**, then **Terminer l’étape** at each, reaching **Contrôle modèle et scan**. Follow any assignment/future-slot explanation instead of skipping stages. A manager may explicitly select supervision as described in section 15.
5. At the model inspection, select **Contrôle conforme**, review **Modèle** and **Scan**, check them manually or use **Tout conforme**, leave the gap unchecked, and click **Valider le contrôle → Planification**.
6. For a failed model/quality control, supply the photo and reason and click **Enregistrer la non-conformité**. The next primary button is **Documenter la reprise**; it opens the required origin, restart, cause and corrective-action form without submitting it. The stage strip cannot move the case.

## 12. Select the CNC route

1. In **Votre action**, select **Méthode de fabrication : CFAO / usinage CNC**.
2. Select **Traitement après usinage : Cristallisation**.
3. Review **Livraison prévue**, initially filled from the calculated deadline in Casablanca when no date was saved. Change it if needed. If **Échéance en cours de calcul** appears, enter the date manually. For optional instructions, edit **Dossier > Notes du dossier / consignes techniques**, then click **Enregistrer les informations** explicitly.
4. Click **Planifier → Conception numérique / CAO**. The server supplies that destination from the selected method; a conventional route shows **Préparation du modèle de travail** instead. For J+1, a missing quote shows **Devis J+1 requis par la comptabilité**; accounting must quote before planning can proceed.
5. Show **Planning** briefly: employee, equipment, chronological reservations and workload. Synthetic shifts initially cover almost the whole day, every day, for rehearsals. They are not proposed real working conditions.

## 13. Upload and request design approval

1. Return to the case at CAO. In **Votre action**, choose the file with **Fichier de design** and click **Téléverser le design**; the new version is selected automatically. (The **Dossier > Documents privés** upload still works.)
2. Choose `demo/demo-design.stl` and click **Téléverser**. Expected: the private DESIGN attachment appears in the list.
3. Choose **Design prêt à soumettre** from the reason dropdown.
4. In **Votre action**, select **Version de design téléversée** and click **Soumettre au dentiste et suspendre le délai**.
5. Expected: a pending design version and a suspended deadline. Do not use a production completion button to bypass the dentist decision.
6. Switch to Demo Dentist and use **Examiner le design** in **À faire**, or open the same reference from **Mes commandes**. Click **Consulter le design**, keep **Décision du design : Approuver**, choose **Design approuvé** as the optional note, then explicitly click **Approuver**.
7. Expected: design status **Approuvé**, visible under **Dossier > Validations du design**. Return to Demo Manager; the deadline resumes and the case reaches **Préparation FAO / placement et parcours outil**. No manual resume can replace a pending dentist decision.

## 14. Create the production lot

1. Fastest path: at **Préparation FAO**, the case's **Votre action** shows **Lot de production** with this case preselected (code `LOT-<référence>`, machine, consumable) — click **Créer et lier le lot**. Alternative: in Demo Manager, open **Stocks et lots > Stock** and find **Créer et lier un lot** (only eligible cases are listed).
2. Enter a unique **Code unique**, e.g. **LOT-DEMO-20261121-01**.
3. Choose **Virtual mill** as the machine. Select only your current case in **Dossiers du lot**; this is a multiple-selection list, so verify the highlighted reference.
4. For the main successful demonstration, leave **Consommable du lot : Sans consommable**. Click **Créer le lot**.
5. Expected: the lot appears under **Lots enregistrés** linked to your case. This demonstrates lot linkage, not measured stock consumption. Stock/loss testing is separate.
6. Return to the case. In **Votre action**, start and complete the assigned **Préparation FAO** task to reach **Usinage CNC**, after explaining the staged preparation. Resolve assignment/lot/prerequisite errors through their normal controls.

## 15. CNC: demonstrate all technician/machine phases

In **Votre action**, use the current Usinage CNC task. Keep its current state visible to the audience. The workspace offers one primary action at a time.

| Action | Reason dropdown | Expected occupancy/state |
| --- | --- | --- |
| Démarrer | Optional note | Attended loading/setup; technician and machine occupied |
| Select Démarrage supervisé par le responsable, then Démarrer maintenant et replanifier | Démarrage anticipé; manager only | Starts now only if protected reservations and availability allow |
| Chargement terminé : lancer le cycle | Chargement terminé, optional | Autonomous cycle; technician released, machine occupied |
| Confirmer la fin réelle du cycle | Cycle terminé, required note | Cycle acknowledged; machine still occupied pending unloading |
| Commencer le déchargement | Déchargement en cours, optional | Technician checked/reserved again; machine remains occupied |
| Confirmer le déchargement et terminer | Déchargement terminé, optional | Task finished; machine released; next eligible workflow step |

Use standard **Démarrer** when the schedule allows it. Selecting the manager's supervision checkbox changes that same primary button to **Démarrer maintenant et replanifier** and requires a reason; it cannot displace protected work. A chosen reason enables an action requiring notes, but still does not execute it automatically. For task pause or blocking, expand **Signaler un problème**; dossier suspension and task pause remain distinct.

The normal work path uses the assigned task's start/finish or equipment controls. Only a manager can use **Signaler un problème > Forcer le passage à l’étape suivante**, with a required reason. This exceptional action still cannot bypass missing clinical evidence, a required lot or equipment unloading.

During this staged demo, the presenter represents the operator acknowledging simulated work completion. Do not claim actual equipment telemetry, elapsed manufacturing time or automatic quality approval. The estimated duration is planning information; an elapsed estimate never unloads an occupied machine.

## 16. Crystallisation

1. After CNC unloading, expected case stage is **Traitement thermique**, with a **Cristallisation** task.
2. If it briefly retains a predecessor-unloading block, click **Actualiser le dossier** and allow the worker/replan to complete. Do not report a successful start while the task remains blocked.
3. Use the same sequence from section 15: start, launch cycle, choose **Cycle terminé** and confirm, begin unloading, choose **Déchargement terminé** and finish.
4. Point out the intermediate message **Cycle terminé · machine occupée jusqu’au déchargement**. It illustrates why cycle end and machine availability are different events.
5. Expected: **Finition et caractérisation**. A real equipment or operator conflict requires resolution through normal planning, not bypassing the guard.

## 17. Finish the piece

1. In **Votre action**, use **Actualiser le dossier** if Finition is still awaiting replanning after furnace unloading.
2. Start the task normally, or explicitly check **Démarrage supervisé par le responsable**, select **Démarrage anticipé** and use the changed primary button if the only issue is a future movable reservation.
3. When the staged finishing work is complete, choose **Finition terminée** and click **Terminer l’étape**.
4. Expected: **Contrôle qualité final**. Manual work uses start/complete; it has no autonomous-cycle buttons.

## 18. Final quality inspection

1. In **Votre action > Inspection · Qualité**, choose **Contrôle conforme**.
2. Review all seven: **Marges**, **Contacts**, **Teinte**, **Occlusion**, **Esthétique**, **Glaçage**, **Polissage**. Check them individually or explicitly use **Tout conforme**, then review them.
3. Leave the gap unchecked for this passing synthetic scenario. Click **Valider le contrôle → Conditionnement et documents** once.
4. Confirm the top success notification and the new **Conditionnement et documents** stage. The evidence and transition commit together; inspect **Dossier > Historique et preuves > Inspections** to show the record. With no success message, do not infer that the control saved.
5. Missing/failed evidence must be resolved before advancement. A failure or gap requires a private PHOTO attachment and selecting it as evidence; non-compliance also requires a reason. After **Enregistrer la non-conformité**, use **Documenter la reprise** to open the required corrective-action form.

## 19. Packaging and dispatch documents

1. Expand **Dossier** and download **Bon de livraison PDF**. Verify the case reference and synthetic clinic/address. Download **Étiquette QR** for the same case.
2. In **Votre action**, start **Conditionnement et documents** (or use the explicit supervision/reason path).
3. For the staged packed piece, choose **Conditionnement terminé**, then **Terminer l’étape**.
4. Expected: **Prêt pour expédition**. Downloaded documents alone do not complete packaging.

## 20. Courier dispatch, PIN delivery and clinical fitting

1. Obtain fresh signed QR content for this reference using the label/scanner or helper. In Demo Courier click **Sortir du laboratoire**, paste the token in its dialog, and confirm.
2. Expected: **En route vers le cabinet**; the QR dialog closes/clears. Show the separate **Confirmer la livraison** action.
3. In Demo Dentist, use the privately saved PIN. If unavailable, open the case's **Dossier > Émettre un nouveau PIN de livraison**. It appears once; the old PIN is superseded.
4. Back in Demo Courier, click **Confirmer la livraison**, enter the current four-digit PIN, then confirm. Expected: **Livré**, and the PIN dialog closes/clears.
5. In Demo Dentist, use the fitting shortcut in **À faire** or reopen the same case. In **Votre action**, choose **Essayage conforme**, then explicitly click **Valider l’essayage clinique** for the successful staged fitting. Alternatively, the dentist can enter the delivery PIN in its own workspace; PIN confirmation and fitting are still separate actions.
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

Requires Compose support for `!override`. Verification creates persistent BROWSER cases in its own volumes. Repeated starts preserve them. To include the full backend regression, run `docker compose -p cabinet-ui-verification -f compose.demo.yml -f compose.verify.yml exec -T backend python manage.py test api customers --noinput` before `Push-Location` in that script, while the verification stack is running. It uses the disposable `test_cabinet_demo` database; historical-schema tests and clock changes stay inside the test process. The verification override mounts repository documentation read-only, which lets the Phase 6 freshness test compare `docs/WORKFLOW.md` with the generated diagrams.

Current results: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md). Technical documentation: [docs/README.md](docs/README.md). Native development setup: [README.md](README.md). Graphify: [docs/GRAPHIFY.md](docs/GRAPHIFY.md). Device connections remain future work.


## v1.0 - Advisory capacity at prescription entry (Step 8.1)

As **Demo Dentist**, open **Nouvelle prescription**, select a laboratory and clinic, then complete the usual clinical fields. The advisory refreshes after changing service, impression or teeth. When the lab can estimate a date, it is labelled **provisoire**; the laboratory still selects the real fabrication route during planning. A busy/closed requested date may show **Le laboratoire est chargé à cette date** and the earliest estimated date. **Envoyer quand même** performs the same normal validated submission; it never bypasses missing disinfection or clinical fields. **Choisir un délai plus long** changes J+1 to J+2, then J+4 and previews again. At J+4 no slower service exists. No estimate, or an unavailable preview, leaves the normal submit path usable.

The estimate uses configured routes, staff calendars and known workload. It excludes unknown transport/approval waits and does not reserve capacity. Never change MY-TEST-001 to demonstrate a warning. Use a new `V1-` case for the form; demonstrate a deliberately loaded calendar in the isolated verification project. Payments, dashboard and document identity remain pending until their own steps are verified.


## v1.0 - Encaissements, impayés et annulations (étape 8.2)

1. Se connecter comme **Demo Manager** ou au poste **Comptabilité**, puis ouvrir **Facturation**. Les factures affichent état, reste à payer, échéance et retard ; le tableau **Impayés** distingue non échu, quatre tranches de retard et trop-perçus.
2. Sur un cabinet ayant une facture de test, cliquer **Enregistrer un encaissement**, choisir cabinet/moyen, saisir montant, date, référence et banque. Une LCN exige son échéance. Pour les espèces, conserver un reçu signé.
3. Vérifier la répartition préremplie par ancienneté, la modifier si besoin : son total doit correspondre exactement au montant. **Enregistrer le paiement**. Une saisie partielle affiche **Partiellement payée** ; aucune somme non affectée n'est autorisée.
4. Dans l'historique, ouvrir **Marquer comme impayé / Annuler la saisie**, choisir le motif et confirmer dans le dialogue. La saisie reste visible avec sa preuve d'annulation ; les soldes sont rouverts. Une deuxième annulation est refusée. Ce geste ne rembourse pas le cabinet.
5. Un avoir après paiement peut afficher **Trop-perçu à régulariser**. Le montant reste séparé des créances ; aucune compensation automatique. Le délai de paiement (60 jours par défaut, 0–120) se règle dans **Configuration → Cabinets**.

Répéter la démonstration du paiement sur une **nouvelle facture du projet de vérification**, jamais sur MY-TEST-001 ou sa ligne de novembre. La suite réelle de la section 25 prépare un nouveau cabinet/dossier et une facture d'octobre par les commandes normales, avec un utilitaire explicitement refusé hors vérification. Ne pas clôturer le relevé de novembre du projet principal sans l'instruction du propriétaire. Migrations additives autorisées :0026 uniquement dans les projets Docker ; les anciennes factures/PDF restent immuables. Aucun paiement en ligne ni envoi externe.

## Tableau de bord v1 (responsable et comptabilité)

1. Se connecter au laboratoire. Le responsable arrive dans **À faire** ; la comptabilité garde son arrivée dans **Facturation**.
2. Ouvrir **Tableau de bord** dans la navigation. Le responsable voit dossiers actifs, risques, livraisons dues et reprises sur30jours. La comptabilité voit uniquement les finances.
3. Lire le nombre et le libellé de chaque barre d’étape. Les dossiers livrés restent actifs pour l’essayage mais ne sont plus comptés comme risques de livraison.
4. Dans **En retard** ou **À risque**, ouvrir un dossier : le même espace clinique et ses gardes s’affichent. Fermer rend le focus au bouton d’origine.
5. Lire **Finances** : facturé ce mois = mois d’émission ; dernier mois clôturé = mois du relevé, montant avant avoirs. La date du catalogue et son avertissement d’ancienneté sont visibles. Les créances, trop-perçus et contestations sont lus en direct.
6. **Actualiser le tableau de bord** recharge les données et affiche un message. Cette consultation ne réserve rien, ne valide rien et ne clôture aucun relevé.

Le taux de reprises divise les preuves de reprise des30derniers jours par les dossiers livrés dans cette fenêtre ; il peut dépasser100% si plusieurs tentatives existent. Sans livraison, le taux est indéfini et affiché « — », avec les deux nombres.

## Identité du laboratoire sur les nouveaux documents

1. Se connecter comme **Demo Manager**, ouvrir **Configuration**, puis déplier **Identité du laboratoire**. Le clavier permet d'atteindre ce titre et de l'ouvrir avec Entrée.
2. Pour la présentation, saisir des valeurs explicitement fictives : **Laboratoire Démo Atlas**, **Adresse fictive de démonstration**, **Ville fictive**, téléphone **0000000000**, e-mail **demo@example.invalid**, ICE **000000000000000**. Laisser IF, RC et patente vides si aucun identifiant fictif n'est nécessaire.
3. Cliquer **Enregistrer l’identité**. Le message de réussite apparaît en haut de l'écran. Fermer puis rouvrir la section pour vérifier les valeurs enregistrées et la date de mise à jour.
4. L'ICE reste un texte : les zéros initiaux sont conservés. Le champ accepte une valeur vide ou exactement 15 chiffres de 0 à 9. Le contrôle porte sur le format. Une erreur affiche son explication en français et conserve la saisie.
5. Générer un nouveau bon de livraison, une nouvelle facture ou un nouvel avoir dans le parcours de démonstration. L'en-tête affiche **Gestion Labo · nom légal**, adresse et coordonnées. Le pied de page contient uniquement les identifiants fiscaux renseignés. Avec un profil vide, le nom habituel du laboratoire est utilisé.
6. La comptabilité peut consulter cette section en **lecture seule**. Les autres postes ne chargent pas le profil. Le serveur vérifie aussi ces droits.

Les factures et avoirs déjà stockés conservent leurs octets d'origine et leur présentation historique. Un bon de livraison est généré à la demande. La démonstration des nouvelles factures et des avoirs se fait sur les dossiers du projet de vérification décrit en section 25 ; la clôture de novembre du projet principal reste soumise à l'accord du propriétaire.

## Jeu de démonstration V1 : neuf étapes et trois exceptions

Ce jeu s’ajoute aux données existantes ; il ne remplace ni ne réinitialise aucun dossier.
Avant la présentation, démarrer le projet principal puis exécuter une fois, depuis PowerShell à la racine :

```powershell
cmd /c "docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python - < demo\prepare_v1_cases.py"
if ($LASTEXITCODE -ne 0) { throw 'Preparation V1 interrompue ; conserver les donnees et le journal' }
```

La redirection transmet les octets UTF-8 du fichier sans conversion de PowerShell. Le script exige un conteneur de simulation, la base Docker `cabinet_demo` et un envoi externe désactivé. Il utilise les comptes synthétiques habituels ; si leurs mots de passe ont été changés, lui fournir `V1_DEMO_PASSWORD` uniquement dans l’environnement du conteneur, sans le publier. Chaque lancement ajoute un **nouveau** cabinet et un suffixe aléatoire : conserver la sortie non sensible pour retrouver les références. Une interruption conserve les dossiers déjà créés ; ne pas les supprimer pour relancer.

| Préfixe de référence | Écran à montrer |
| --- | --- |
| V1-COMMANDE | Demande reçue, acceptation et analyse |
| V1-RECEPTION | Empreinte physique déposée, réception à confirmer |
| V1-CONTROLE_ENTREE | Contrôle du fichier numérique |
| V1-MODELE | Contrôle du modèle et du scan |
| V1-CONCEPTION | Conception CAO |
| V1-FABRICATION | Préparation FAO avant le cycle CNC |
| V1-FINITION_QC | Contrôle qualité final |
| V1-LIVRAISON | Prêt à expédier |
| V1-CLOTURE | Livraison et essayage conformes, dossier clôturé |
| V1-RETARD | Date de livraison confirmée dépassée |
| V1-REPRISE | Contrôle qualité fictif échoué, photo de preuve et reprise documentée au modelage |
| V1-DESIGN | Version de design déposée et attente d’approbation du dentiste, délai suspendu |

Utiliser **Commandes** et rechercher le préfixe, ou **À faire** pour les actions du poste. Les trois dossiers avancés et la reprise utilisent le parcours conventionnel ; la préparation FAO et le design montrent le parcours CFAO. Le STL est une géométrie synthétique et la photo une preuve fictive clairement nommée. Ce sont des positions de démonstration obtenues par les commandes métier, sans prétendre mesurer un temps réel de fabrication. Le parcours CNC complet de la section 15 conserve toutes les confirmations de chargement/cycle/déchargement.

**Présentation courte :** montrer la file d’un technicien, ouvrir un dossier et son action principale, choisir un motif sans soumettre, montrer **Dossier** et les preuves. Passer au tableau de bord, puis au compte dentiste pour le design. Utiliser V1-LIVRAISON pour une nouvelle remise et V1-CLOTURE pour l’historique, sans modifier MY-TEST-001.

Les textes **Choisir un fichier** et **Aucun fichier sélectionné** sont désormais en français, même avec un navigateur configuré en anglais. Le bouton ouvre le sélecteur natif avec Entrée ou Espace. Le libellé de version **Gestion Labo v1.0** figure sur la connexion et en bas de la navigation.

## Deux exemples d’ancienneté — vérification uniquement

Les factures historiques sont préparées dans **cabinet-ui-verification**, jamais dans le projet principal.
Après le démarrage et la migration de la section 25 :

```powershell
cmd /c "docker compose -p cabinet-ui-verification -f compose.demo.yml -f compose.verify.yml exec -T backend python - < demo\prepare_v1_aging.py"
if ($LASTEXITCODE -ne 0) { throw 'Preparation des exemples comptables interrompue' }
```

Ce script exige aussi `GESTION_LABO_VERIFICATION=1`, fourni par `compose.verify.yml`. Il crée deux nouveaux cabinets V1-AGING, livre deux nouveaux dossiers par les commandes normales, puis clôture uniquement leurs relevés historiques. L’horloge de test reste locale au processus ; celle du serveur et des workers ne change pas. Les dates d’émission sont calculées à 85 et 45 jours avant la date courante, avec un délai de paiement de 30 jours, pour afficher respectivement les tranches **31–60 jours** et **0–30 jours**.

Ouvrir **http://localhost:18081**, se connecter au laboratoire, puis **Facturation → Impayés**. Rechercher les cabinets indiqués dans la sortie du script. Les deux soldes de 500 MAD restent impayés pour les captures ; utiliser une autre nouvelle facture pour les essais de paiement et d’annulation. Le projet principal ne dispose pas d’horloge de test publique et ses relevés de novembre restent ouverts sans autorisation du propriétaire.

Le [guide utilisateur](docs/GUIDE_UTILISATEUR.md) résume les actions de chaque rôle. Les tests automatisés, leur portée et les validations encore en cours sont datés dans [TEST_RESULTS](docs/TEST_RESULTS.md).


## Préparation de présentation v1.0 (étape 8.8)

**Données (projet principal uniquement).** `demo/prepare_v1_operations.py` s’exécute dans le conteneur backend de démonstration et passe par l’API réelle :

```powershell
cmd /c "docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python - < demo\prepare_v1_operations.py"
```

Il est idempotent (une seconde exécution ne change rien) et ajoute :
- une équipe réaliste (2 réception, 3 CAO, 3 FAO, 2 qualité) avec niveaux de qualification différents et horaires lun–ven 08:00–17:00 (+ samedi matin pour une personne par rôle) ;
- des horaires du laboratoire lun–sam 08:00–17:00, pause 12:00–13:00 ;
- un catalogue de 12 consommables (dont 2 sous le seuil d’alerte) ;
- la mise en pause des dossiers de test automatisés `BROWSER-…` ouverts (motif « Données de test automatisées — hors démonstration », réversible par la reprise normale).

Ne pas l’exécuter sur le projet de vérification : les tests réels y démarrent des tâches immédiatement.

**Horaires réels.** En dehors de 08:00–17:00, une étape affiche « Prévu le … » ; le responsable peut cocher le **démarrage supervisé**. Répéter la démonstration en journée.

**Dossiers de test masqués.** Dans le mode SIMULATION, les dossiers `BROWSER-…` en pause de test ou clôturés depuis plus d’un jour sont masqués des listes ; la case **Afficher les dossiers de test automatisés (N)** les réaffiche.

**Nouveaux parcours.**
- Dentiste : **Télécharger l’étiquette QR** sur l’écran « Prescription enregistrée ».
- Coursier : **Importer l’image du QR** dans chaque remise.
- Facturation : **Commandes livrées** (mois en cours présélectionné, cabinet, travail, service, montant, statut, total) ; un clic sur la référence ouvre le dossier ; les lignes du relevé s’ajustent via **Ajuster**.
- Planning : **Par technicien (journée)** ; chaque tâche affiche **Pourquoi cette affectation ?**.
- Configuration : **Diagnostic technique** (ancien menu Opérations), éléments en échec ou en attente par défaut.
- Bon de livraison : identification, contenu, dates, lot de traçabilité et cadres de signature.
