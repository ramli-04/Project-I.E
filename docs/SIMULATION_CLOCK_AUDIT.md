# Audit des horloges du simulateur

Audit du25novembre2026, avant les exécutions mensuelles. Recherche Graphify, puis inventaire des appels/déclarations dans api/, customers/ et les migrations, sans accès aux paramètres locaux ou fichiers privés. Le tableau liste les128occurrences du code applicatif examiné avant ajout du simulateur ; les anciennes migrations sont incluses pour vérifier les définitions PostgreSQL.

- `timezone.now`, `timezone.localdate/localtime` et `auto_now(_add)` : horloge virtuelle limitée au processus de commande, restaurée à la sortie. Le calendrier reste Africa/Casablanca selon les données zoneinfo de l’image. Aucun décalage UTC n’est codé en dur.
- `default=timezone.now` : Django conserve le callable importé et son cache `_get_default`. Le contexte du simulateur remplace ces seuls défauts des modèles api/customers et restaure callable et cache. Le probe sur des instances non enregistrées confirme la différence avec `auto_now_add`. Aucun fichier de production ou champ de base existant n’est modifié.
- UUID des modèles : défauts d’identifiants issus d’un RNG semé dans ce même contexte, puis restaurés. Les UUID interviennent dans les départages du vrai planificateur ; les stabiliser rend les rapports reproductibles. Les mots de passe, sessions, PIN et signatures gardent leurs générateurs de sécurité normaux et ne figurent jamais dans les rapports.
- PostgreSQL `CURRENT_TIMESTAMP` : seulement les dates de rafraîchissement des catalogues et leur initialisation (migrations0017/0020/0023). Aucune horloge SQL ne pilote une transition, réservation ou garde temporelle. Ces horodatages restent réels ; les montants et mois du catalogue viennent des preuves datées par l’application. AnalyticsRefreshState est actualisé par le service normal sous l’horloge de simulation. Aucun contournement d’horloge SQL n’est nécessaire.
- Aucun `datetime.now`/`date.today`/`CURRENT_DATE` ou autre horloge SQL de garde n’a été trouvé dans le code applicatif inventorié sur ce chemin. Les fonctions de durée mesurent l’exécution réelle, sans alimenter les indicateurs virtuels.
- Le `TimestampSigner` de Django utilise `time.time()` : les QR sont signés et vérifiés normalement pendant l’exécution. La simulation ne prouve pas leur expiration après une année virtuelle. Aucun patch du générateur cryptographique.
- ReportLab `TimeStamp` utilise `time.time()` pour les métadonnées de création du PDF. Ces métadonnées restent réelles ; les dates métier imprimées viennent des preuves applicatives virtuelles. Elles ne pilotent aucune garde ni mesure. La reproduction vise les métriques JSON, pas des octets PDF identiques.
- Le TTL Redis reste réel. Les invalidations et générations TenantReadVersion sont contrôlées après des écritures entrelacées dans la même minute virtuelle ; l’expiration temporelle du cache est hors preuve.
- Aucun worker/Beat n’exécute des actions hors horloge. L’outbox est conservée mais sa publication est désactivée. Le planning est appelé normalement et les PDF de contrôle utilisent la tâche existante en mode direct. Les tests généraux couvrent séparément la reprise Celery.

Les appels du nouveau module simulation/ utilisent cette horloge, les primitives du planning, le vrai middleware DRF et l’authentification Bearer. Les requêtes sont internes au processus pour partager le temps simulé ; ce n’est pas un test de latence HTTP réseau. Les sessions sont créées par le service normal `issue_session`, sans mock d’authentification. Le chemin de mot de passe est couvert par les suites générales, pas par ce simulateur.

| Source | Expression |
| --- | --- |
| `cabinet_backend/api/alerts.py:7` | `today = today or timezone.localdate()` |
| `cabinet_backend/api/analytics.py:23` | `attempt = timezone.now()` |
| `cabinet_backend/api/analytics.py:44` | `'last_success_at': timezone.now(),` |
| `cabinet_backend/api/analytics_views.py:75` | `'stale': last_success is None or timezone.now() - last_success > timedelta(minutes=20),` |
| `cabinet_backend/api/billing.py:25` | `month = timezone.localdate(order.delivered_at).replace(day=1)` |
| `cabinet_backend/api/billing.py:48` | `if period.month >= timezone.localdate().replace(day=1):` |
| `cabinet_backend/api/billing.py:75` | `period.closed_at, period.closed_by = timezone.now(), actor` |
| `cabinet_backend/api/business_models.py:44` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:56` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:66` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:91` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:104` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:114` | `requested_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:129` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:143` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:181` | `issued_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:189` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:200` | `issued_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:207` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:216` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:227` | `next_attempt_at = models.DateTimeField(default=timezone.now)` |
| `cabinet_backend/api/business_models.py:293` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_models.py:321` | `reversed_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/business_views.py:204` | `dispute.status, dispute.resolved_at, dispute.resolution_notes = decision, timezone.now(), notes` |
| `cabinet_backend/api/business_views.py:229` | `event.failed_at, event.attempts, event.last_error, event.next_attempt_at = None, 0, '', timezone.now()` |
| `cabinet_backend/api/business_views.py:257` | `delivery.sent_at = timezone.now() if sent else None` |
| `cabinet_backend/api/capacity.py:36` | `now = timezone.now().astimezone(TZ)` |
| `cabinet_backend/api/case_commands.py:64` | `now = timezone.now()` |
| `cabinet_backend/api/case_commands.py:75` | `order.workflow_history = [*order.workflow_history, {'status': status, 'at': timezone.now().isoformat()}]` |
| `cabinet_backend/api/case_commands.py:293` | `review.status, review.response_notes, review.responded_at, review.responded_by = decision, notes, timezone.now(), actor` |
| `cabinet_backend/api/case_commands.py:362` | `now = timezone.now()` |
| `cabinet_backend/api/case_commands.py:401` | `order.fitting_validated_at = timezone.now()` |
| `cabinet_backend/api/case_serializers.py:166` | `validated_data['accepted_at'] = timezone.now()` |
| `cabinet_backend/api/case_serializers.py:168` | `validated_data['received_at'] = timezone.now()` |
| `cabinet_backend/api/case_serializers.py:170` | `validated_data['workflow_history'] = [*instance.workflow_history, {'status': validated_data['status'], 'at': timezone.now().isoformat()}]` |
| `cabinet_backend/api/dashboard.py:30` | `today = timezone.localdate(now, TZ)` |
| `cabinet_backend/api/dashboard.py:53` | `today = timezone.localdate(now, TZ)` |
| `cabinet_backend/api/dashboard.py:77` | `due = timezone.localdate(risk['deadline'], TZ)` |
| `cabinet_backend/api/dashboard.py:115` | `now = timezone.now()` |
| `cabinet_backend/api/messaging.py:63` | `ids = list(MessageDelivery.objects.filter(status__in=['PENDING', 'WAIT_CONFIGURATION'], next_attempt_at__lte=timezone.now())` |
| `cabinet_backend/api/messaging.py:99` | `delivery.status, delivery.sent_at, delivery.provider_reference = 'SENT', timezone.now(), reference` |
| `cabinet_backend/api/models.py:173` | `updated_at = models.DateTimeField(auto_now=True)` |
| `cabinet_backend/api/models.py:329` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/models.py:330` | `updated_at = models.DateTimeField(auto_now=True)` |
| `cabinet_backend/api/models.py:347` | `self.workflow_history = [{'status': self.status, 'at': timezone.now().isoformat()}]` |
| `cabinet_backend/api/models.py:384` | `self.invoiced_at = timezone.now()` |
| `cabinet_backend/api/models.py:415` | `created_at = models.DateTimeField(auto_now_add=True, editable=False)` |
| `cabinet_backend/api/models.py:507` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/models.py:614` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/models.py:615` | `next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)` |
| `cabinet_backend/api/models.py:631` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/models.py:648` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/outbox.py:38` | `now = timezone.now()` |
| `cabinet_backend/api/payments.py:32` | `today = today or timezone.localdate(timezone.now(), TZ)` |
| `cabinet_backend/api/payments.py:56` | `today = today or timezone.localdate(timezone.now(), TZ)` |
| `cabinet_backend/api/planning.py:95` | `now = timezone.now()` |
| `cabinet_backend/api/planning.py:280` | `horizon = timezone.localdate(timezone.now(), TZ) + timedelta(days=settings.horizon_days)` |
| `cabinet_backend/api/planning.py:369` | `now = now or timezone.now()` |
| `cabinet_backend/api/planning.py:480` | `now = now or timezone.now()` |
| `cabinet_backend/api/planning.py:510` | `settings, now = configuration(), timezone.now()` |
| `cabinet_backend/api/planning.py:645` | `# auto_now timestamps and correctly trips the immutable-task SQL trigger.` |
| `cabinet_backend/api/planning_models.py:34` | `updated_at = models.DateTimeField(auto_now=True)` |
| `cabinet_backend/api/planning_models.py:135` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/planning_models.py:136` | `updated_at = models.DateTimeField(auto_now=True)` |
| `cabinet_backend/api/planning_models.py:178` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/api/planning_phases.py:61` | `horizon = timezone.localdate(timezone.now(),TZ) + timedelta(days=settings.horizon_days)` |
| `cabinet_backend/api/planning_views.py:127` | `return timezone_transitions(timezone.now().year)` |
| `cabinet_backend/api/planning_views.py:218` | `now = timezone.localtime(timezone.now(),TZ)` |
| `cabinet_backend/api/tasks.py:27` | `event.failed_at = timezone.now()` |
| `cabinet_backend/api/tasks.py:80` | `event.processed_at = timezone.now()` |
| `cabinet_backend/api/tasks.py:122` | `deadline_at = timezone.localtime(order.created_at, ZoneInfo('Africa/Casablanca')) + timedelta(days=days)` |
| `cabinet_backend/api/tasks.py:124` | `deadline = timezone.localdate(deadline_at)` |
| `cabinet_backend/api/tasks.py:127` | `order.deadline_calculated_at = timezone.now()` |
| `cabinet_backend/api/tasks.py:177` | `ids = list(TaskOutbox.objects.filter(processed_at__isnull=True, failed_at__isnull=True, next_attempt_at__lte=timezone.now())` |
| `cabinet_backend/api/work_queue.py:145` | `now = timezone.now()` |
| `cabinet_backend/api/migrations/0001_initial.py:25` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0004_prescription_delivery_pin_and_more.py:26` | `field=models.DateTimeField(auto_now=True),` |
| `cabinet_backend/api/migrations/0007_equipment_staffmember_stockitem.py:64` | `('updated_at', models.DateTimeField(auto_now=True)),` |
| `cabinet_backend/api/migrations/0015_prescription_history.py:54` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0017_monthly_billing_materialized_views.py:30` | `CURRENT_TIMESTAMP AS refreshed_at` |
| `cabinet_backend/api/migrations/0017_monthly_billing_materialized_views.py:63` | `CURRENT_TIMESTAMP AS refreshed_at` |
| `cabinet_backend/api/migrations/0017_monthly_billing_materialized_views.py:75` | `SELECT 'monthly_billing_catalog', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '',` |
| `cabinet_backend/api/migrations/0018_inventory_ledger_and_background_events.py:101` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0018_inventory_ledger_and_background_events.py:111` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0018_inventory_ledger_and_background_events.py:112` | `('next_attempt_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),` |
| `cabinet_backend/api/migrations/0018_inventory_ledger_and_background_events.py:127` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0018_inventory_ledger_and_background_events.py:153` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0020_monthly_stock_loss_catalog.py:28` | `'MAD'::varchar(3) AS currency, CURRENT_TIMESTAMP AS refreshed_at` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:61` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:78` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:91` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:118` | `('issued_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:131` | `('requested_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:147` | `('issued_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:160` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:174` | `('next_attempt_at', models.DateTimeField(default=django.utils.timezone.now)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:185` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:199` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:228` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:565` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:579` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0021_bpmn_workflow_and_accounting.py:592` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0023_delivery_statements_and_financial_catalogs.py:21` | `CURRENT_TIMESTAMP AS refreshed_at` |
| `cabinet_backend/api/migrations/0023_delivery_statements_and_financial_catalogs.py:37` | `CURRENT_TIMESTAMP AS refreshed_at` |
| `cabinet_backend/api/migrations/0024_production_planning.py:52` | `('updated_at', models.DateTimeField(auto_now=True)),` |
| `cabinet_backend/api/migrations/0024_production_planning.py:90` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0024_production_planning.py:91` | `('updated_at', models.DateTimeField(auto_now=True)),` |
| `cabinet_backend/api/migrations/0024_production_planning.py:109` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0026_payments_and_receivables.py:48` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/api/migrations/0026_payments_and_receivables.py:65` | `('reversed_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/customers/authentication.py:19` | `expires_at=timezone.now() + timedelta(hours=12))` |
| `cabinet_backend/customers/authentication.py:36` | `token_digest=digest, revoked_at__isnull=True, expires_at__gt=timezone.now(), account__is_active=True,` |
| `cabinet_backend/customers/authentication.py:57` | `now = timezone.now()` |
| `cabinet_backend/customers/models.py:32` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/customers/models.py:60` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/customers/models.py:77` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/customers/models.py:88` | `created_at = models.DateTimeField(auto_now_add=True)` |
| `cabinet_backend/customers/views.py:126` | `request.auth.revoked_at = timezone.now()` |
| `cabinet_backend/customers/views.py:175` | `account.password_reset_at = timezone.now()` |
| `cabinet_backend/customers/views.py:183` | `account.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())` |
| `cabinet_backend/customers/views.py:200` | `account.password_reset_at = timezone.now()` |
| `cabinet_backend/customers/views.py:202` | `account.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())` |
| `cabinet_backend/customers/migrations/0002_platformaccount_accesslog_supportticket.py:25` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/customers/migrations/0002_platformaccount_accesslog_supportticket.py:40` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/customers/migrations/0002_platformaccount_accesslog_supportticket.py:54` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/customers/migrations/0004_authenticated_platform_sessions.py:37` | `('created_at', models.DateTimeField(auto_now_add=True)),` |
| `cabinet_backend/customers/management/commands/secure_platform.py:24` | `account.password_hash, account.password_reset_at = make_password(password), timezone.now()` |
| `cabinet_backend/customers/management/commands/seed_virtual_lab.py:157` | `order.production_method, order.delivery_date = method, timezone.localdate() + timedelta(days=4 if service == 'STANDARD' else 2)` |
