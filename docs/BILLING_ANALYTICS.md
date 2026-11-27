# Billing analytics

Each laboratory has three materialized views:

- `monthly_billing_catalog`: one row per prescription. History is aggregated before joining, preventing duplicated amounts.
- `monthly_billing_summary`: one row per invoiced calendar month and partner clinic, including an explicit unassigned-clinic group.
- `monthly_stock_loss_catalog`: one row per loss month, inventory item and unit; see [inventory workflow](INVENTORY_WORKFLOW.md).

Billing views contain order-level invoiced totals in MAD, rather than invoice line items, tax accounting or payment reconciliation. Stock losses use a separate inventory ledger and catalog.

## Invoice data

`Prescription.partner_clinic` links directly to the tenant's `PartnerClinic`. Existing prescriptions remain unassigned; names and unrelated user/account IDs are not used to infer links.

Moving an order to `FACTURE` captures server-generated `invoiced_at`, `invoiced_amount`, and `invoiced_clinic_name`. Issued billing amount, date, stage, and clinic linkage are locked. Later operational changes do not move invoices between months. Month boundaries use `Africa/Casablanca`.

Pre-existing `FACTURE` records without dates are flagged as `legacy_invoice_without_date` in the detail catalog and excluded from monthly totals. Their number is reported in response metadata. No dates or historical audit events are invented. Reconciliation requires verified historical billing dates and amounts.

Use the standard prescription API to supply `partner_clinic` before invoicing. Do not join `PlatformAccount` IDs to Django Auth user IDs.

## Read endpoints

Laboratory authentication and tenant host routing are required:

```text
GET /api/analytics/billing-catalog/
GET /api/analytics/billing-catalog/<prescription UUID>/
GET /api/analytics/monthly-billing/
GET /api/analytics/monthly-billing/?month=2026-11&clinic=1&page_size=50
GET /api/analytics/monthly-billing/?clinic=unassigned
```

Responses are paginated (50 default, 200 maximum). Analytics queries read materialized views without request-time source-table joins or grouping. Tenant middleware and authentication still perform their normal checks.

List responses include last successful refresh, last attempt, failure/staleness flags, unknown-date invoice count, and currency. A snapshot becomes stale after 20 minutes; normal scheduling runs every 15 minutes. Queries remain available against the last successful snapshot if a refresh fails.

## Refresh pipeline

One Celery Beat scheduler dispatches `api.tasks.refresh_monthly_billing_catalog_task` every 15 minutes. It reads active tenants from `public` and dispatches one task per schema. Each task resolves the tenant, enters `tenant_context`, acquires a tenant-specific PostgreSQL advisory lock, and refreshes all three views concurrently in one transaction. Schema identifiers are quoted. SQL statement and lock timeouts bound refresh work. Database failures are logged, recorded per tenant, and retried up to three times.

`Client.is_active=False` excludes a lab from future refreshes and blocks its operational API access. Inactive labs also disappear from the login selector. Existing data is preserved.

After deploying migrations, rebuild and recreate worker and Beat:

```powershell
.\venv\Scripts\python.exe cabinet_backend/manage.py migrate_schemas --noinput
docker compose up -d --build celery_worker celery_beat
```

Run exactly one Beat instance. Its schedule file lives in a persistent, worker-owned Docker volume.

Immediate dispatch:

```powershell
docker compose exec -T celery_worker celery -A cabinet_backend.celery:app call api.tasks.refresh_monthly_billing_catalog_task
```

Materialized views initially populate during tenant migration; newly created labs get all three views automatically. Rollback drops the stock-loss catalog and billing summary before the detail billing catalog and removes their indexes with them.

Stock-loss analytics use the inventory movement ledger with explicit consumption, compensating rework entries and immutable cost snapshots. Unknown historical consumption and costs are not inferred.


## Encaissements et créances v1 (étape 8.2)

Les encaissements sont des enregistrements, sans passerelle de paiement. Le gestionnaire et la comptabilité peuvent enregistrer et consulter les chèques, LCN, virements et espèces ; les autres rôles n'accèdent pas aux listes financières. Un dentiste consulte seulement le solde de sa propre facture, depuis le chemin de dossier qui proposait déjà le PDF. Aucun envoi externe n'est activé.

### Preuves et contraintes

Migration additive `0026_payments_and_receivables` : `Payment`, `PaymentAllocation`, `PaymentReversal`, et `PartnerClinic.payment_terms_days` (60 par défaut, 0 à 120). Les trois nouveaux journaux sont immuables au niveau modèle et PostgreSQL : UPDATE, DELETE et TRUNCATE refusés. Montants strictement positifs et finis ; une référence est requise pour chèque, LCN et virement ; une échéance est requise pour la LCN. Une affectation est unique par paiement/facture. Le champ interne `payload_digest` de Payment préserve l'identité exacte de la demande ; il n'est pas exposé par l'API.

Un paiement peut couvrir plusieurs factures du même cabinet. La somme des affectations doit correspondre exactement au montant ; aucun montant non affecté n'est accepté. Chaque affectation est plafonnée au solde positif courant. La transaction prend d'abord le verrou de facturation du cabinet, puis les factures dans l'ordre de leur identifiant. Les avoirs utilisent le même verrou de facture ; une course ne peut pas autoriser deux affectations dépassant le solde.

Un UUID `Idempotency-Key` est obligatoire pour enregistrer un paiement : même corps et même clé renvoient le même paiement ; corps différent, réponse 409. La clé reste fixe pendant l'ouverture du dialogue, y compris après une erreur de transport. Après une écriture confirmée suivie d'un échec d'actualisation, seul un nouvel essai de lecture est proposé.

L'annulation ajoute une preuve `PaymentReversal` ; elle ne modifie pas le paiement ou ses affectations. Elle rouvre le solde de chaque facture concernée. Une deuxième annulation est refusée. Le motif `IMPAYE` est réservé au chèque/LCN ; `ANNULE` peut corriger toute saisie. Une annulation n'est pas un remboursement. Les valeurs d'action persistées nouvelles sont **`RECORD_PAYMENT`** et **`REVERSE_PAYMENT`**, ajoutées à `workflow_spec.Action` et aux annotations immuables `WorkflowEvent` des dossiers facturés concernés. Aucune valeur existante n'est renommée et aucun état clinique n'est modifié.

### Source unique du solde et de l'ancienneté

`payments.invoice_balances` calcule en lot : montant facturé moins avoirs moins affectations de paiements non annulés. Il alimente les factures, les soldes dentistes et `receivables`, sans modifier le catalogue financier mensuel, les factures émises ou leurs PDF. Trois SELECT groupés, plus la mise en place du contexte de schéma, suffisent quel que soit le nombre de factures du lot.

Le solde nul est `PAYEE`, un paiement partiel avec solde positif `PARTIELLE`, le solde net sans encaissement actif `IMPAYEE`. Décision complémentaire du propriétaire le 25 novembre : un avoir après paiement peut produire un solde négatif **`TROP_PERCU`**, affiché « Trop-perçu à régulariser ». Les preuves sont conservées ; ce montant reste séparé des dettes et des tranches de retard, sans compensation ou remboursement automatique.

L'échéance de facture utilise la date d'émission en Africa/Casablanca et le délai actuellement configuré pour le cabinet. Aucun calcul de pénalité légale. Les jours de retard valent max(0, aujourd'hui moins l'échéance). Les sommes échéant aujourd'hui ou plus tard sont non échues ; les retards positifs sont regroupés dans 0–30, 31–60, 61–90 et plus de 90 jours, sans double compte. Le total dû additionne les soldes positifs ; `overpaid_amount` additionne séparément les trop-perçus. Le tableau regroupe les cabinets ayant des factures et trie le retard le plus ancien en premier.

### API et parcours

- `GET|POST /api/billing/payments/`, POST avec `allocations: [{invoice, amount}]` et `Idempotency-Key`.
- `GET /api/billing/payments/{id}/` et `POST .../{id}/reverse/` avec motif et notes facultatives.
- `GET /api/billing/receivables/` : cabinet, délai, total dû, non échu, quatre tranches, plus ancien retard, trop-perçu séparé. Montants transmis en chaînes décimales exactes.
- Factures : champs calculés `paid_amount`, `credited_amount`, `balance`, `payment_status`, `due_date`, `days_overdue`, `clinic`, `terms_days`.
- Dentiste : `GET /platform/dentist/orders/{lab}/{case}/invoice-balance/`, uniquement si le dossier et le cabinet de la facture lui appartiennent ; pas de détail des autres lignes, des paiements ou du personnel.

Dans **Facturation**, ouvrir **Enregistrer un encaissement**. La répartition est préremplie par échéance la plus ancienne, reste modifiable et utilise des centimes entiers exacts côté navigateur. Les montants réels restent calculés et contrôlés côté serveur. L'historique propose une annulation avec motif et confirmation dans le dialogue ; aucun `window.confirm`. Pour les espèces : « Conservez un reçu signé. » Le délai du cabinet se modifie dans la fiche existante **Configuration → Cabinets**.

### Vérification isolée

La suite réelle crée une nouvelle facture via `api/testdata/payment_live_fixture.py`, utilitaire non enregistré comme commande du produit. Il exige `GESTION_LABO_VERIFICATION=1`, défini uniquement sur le backend de `compose.verify.yml`, et les paramètres Docker de simulation. Il crée un nouveau cabinet et un dossier BROWSER-PAY, puis utilise les vraies API, inspections et commandes pour la livraison d'octobre, avant de clôturer uniquement sa propre période. Le temps de test est limité au processus. Il ne modifie aucun dossier existant, ne cible jamais le projet principal et n'active aucun appareil ou envoi. Les résultats complets datés sont dans TEST_RESULTS.md.

## Dashboard composition (Step8.3)

`GET /api/dashboard/summary/` is an uncached, tenant-local function view with `Cache-Control: no-store`. It does not use `active_orders` or write settings, catalogs, audit rows or read versions. MANAGER receives operations and finance; COMPTABILITE only finance; all other roles are denied.

Finance reuses `MonthlyBillingSummary.invoiced_total` for the current Casablanca issue month and `MonthlyFinancialCatalog.gross_amount` for the latest closed BillingPeriod month. These are the existing definitions, not a second ledger; freshness/failure metadata comes from AnalyticsRefreshState and is shown beside the tiles. Receivables/over60days/overpayment reuse `payments.receivables` live, with exact decimal strings; disputes count OPEN rows.

Operations group active cases using workflow_spec.STAGES/STEPS. Current-attempt/current-revision tasks feed the existing case_risk with read-only unsaved PlanningSettings defaults. LATE includes projected lateness, not just a past deadline. Delivery risks and due counts stop at actual delivery, while fitting cases remain active until closure. Due-this-week means today through Sunday in Casablanca. Pause/blocked totals count the union, with blocked meaning a BLOCKED task at the current source step. The30-day rework ratio uses ReworkCase rows divided by cases actually delivered in that timestamp window, returning both counts and null if no deliveries.


## Laboratory identity on newly generated documents

Additive migration 0027 creates a tenant-owned LaboratoryProfile singleton. A primary key fixed by a database CHECK to 1 permits an empty table or one row. The ICE is optional; a model/API validator and database CHECK require 15 ASCII digits when populated. No registration lookup is performed. Legal name, address, city, phone, email and optional IF/RC/patente are stored with server-attributed updated_by/updated_at.

GET /api/laboratory-profile/ returns an unsaved empty representation when no profile exists, with Cache-Control:no-store and no creation side effect. MANAGER may GET/PUT; COMPTABILITE may GET; every other role is denied by the existing tenant-membership rule and the endpoint role check. PUT locks the owning public Client row to serialize initial singleton creation. Request-supplied id/updated_at/updated_by are read-only. Profile edits do not write a case action or introduce a persisted metadata action value.

The existing PDF renderer reads the profile for a newly generated document. It escapes text, falls back to Client.name when legal_name is blank, prints the Gestion Labo identity/contact header and repeats only populated ICE/IF/RC/Patente entries in the footer. Delivery slips keep the patient reference, clinic and signed QR. They contain no full patient-name field. PDF author metadata is Gestion Labo.

Existing InvoiceDocument/CreditDocument rows and stored bytes remain append-only. Their task branches return the stored document; neither a profile edit nor a download regenerates it. The regression fixture stores valid legacy Cabinet 2.0 PDFs, changes identity, invokes both generation tasks and downloads both artifacts, then compares every byte and financial/document row. Footer repetition, missing/empty profiles, escaping, role permissions and singleton/ICE database constraints have separate tests. A mutable identity profile is not a revision history of previously issued financial evidence.
