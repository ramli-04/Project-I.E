import random
import uuid
from django.conf import settings
from django.db import models, router, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class EmployeeProfile(models.Model):
    class Role(models.TextChoices):
        RECEPTION = 'RECEPTION', 'Reception'
        CAO = 'CAO', 'CAO'
        FAO = 'FAO', 'FAO'
        QUALITE = 'QUALITE', 'Quality'
        COURSIER = 'COURSIER', 'Courier'

    class ContractType(models.TextChoices):
        CDI = 'CDI', 'CDI'
        CDD = 'CDD', 'CDD'
        STAGE = 'STAGE', 'Internship'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='employee_profile',
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    contract_type = models.CharField(max_length=5, choices=ContractType.choices)
    hire_date = models.DateField()
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['pk']


class Machine(models.Model):
    class MachineType(models.TextChoices):
        SCANNER = 'SCANNER', 'Scanner'
        USINEUSE_CNC = 'USINEUSE_CNC', 'CNC milling machine'
        FOUR_FRITTAGE = 'FOUR_FRITTAGE', 'Sintering furnace'

    class Status(models.TextChoices):
        ACTIF = 'ACTIF', 'Active'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        PANNE = 'PANNE', 'Out of order'

    name = models.CharField(max_length=120)
    machine_type = models.CharField(max_length=13, choices=MachineType.choices)
    capacity = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=11, choices=Status.choices, default=Status.ACTIF)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(capacity__gte=1), name='machine_positive_capacity'),
        ]


class InventoryQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Create inventory individually so opening balances are recorded.')


class Inventory(models.Model):
    class Unit(models.TextChoices):
        DISQUE = 'DISQUE', 'Disc'
        GRAMMES = 'GRAMMES', 'Grams'
        UNITES = 'UNITES', 'Units'

    material_name = models.CharField(max_length=120)
    quantity = models.DecimalField(max_digits=20, decimal_places=6, default=0, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=7, choices=Unit.choices)
    alert_threshold = models.DecimalField(max_digits=20, decimal_places=6, validators=[MinValueValidator(0)])
    unit_cost = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(0)])
    objects = InventoryQuerySet.as_manager()

    class Meta:
        ordering = ['material_name', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='inventory_nonnegative_quantity'),
            models.CheckConstraint(condition=models.Q(alert_threshold__gte=0), name='inventory_nonnegative_threshold'),
            models.CheckConstraint(condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0), name='inventory_unit_cost_nonnegative'),
        ]

    @property
    def is_low_stock(self):
        return self.quantity <= self.alert_threshold

    def save(self, *args, **kwargs):
        if not self._state.adding:
            return super().save(*args, **kwargs)
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        opening = Decimal(str(self.quantity))
        self.quantity = Decimal('0')
        with transaction.atomic(using=using):
            super().save(*args, **kwargs)
            from django.db import connections
            InventoryTransaction.objects.using(using).create(
                inventory_item=self, quantity_changed=opening,
                transaction_type='OPENING', notes='Opening balance observed when inventory was created.',
                changed_by=getattr(self, '_opening_actor', 'system'),
                idempotency_key=uuid.uuid5(uuid.NAMESPACE_URL, f'{connections[using].schema_name}:inventory:{self.pk}:opening'),
            )
            self.refresh_from_db(using=using, fields=['quantity'])


class PartnerClinic(models.Model):
    name = models.CharField(max_length=120)
    pickup_address = models.TextField()
    contact_phone = models.CharField(max_length=30)
    contact_email = models.EmailField(blank=True)
    platform_dentist = models.ForeignKey('customers.PlatformAccount', null=True, blank=True, on_delete=models.PROTECT, related_name='clinics')
    linked_dentist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='partner_clinics',
    )

    class Meta:
        ordering = ['name', 'pk']
        constraints = [
            models.CheckConstraint(condition=~models.Q(pickup_address=''), name='clinic_required_pickup_address'),
        ]


class StaffMember(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=80)
    qualifications = models.TextField(blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    qualification_expiry_date = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    account_username = models.CharField(max_length=100, blank=True)
    account_status = models.CharField(max_length=20, choices=[('A_CREER', 'À créer'), ('ACTIF', 'Actif'), ('SUSPENDU', 'Suspendu')], default='A_CREER')
    availability = models.CharField(max_length=20, choices=[('DISPONIBLE', 'Disponible'), ('OCCUPE', 'Occupé'), ('ABSENT', 'Absent')], default='DISPONIBLE')
    schedule = models.CharField(max_length=255, blank=True)
    available_from = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']


class Equipment(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    availability = models.CharField(max_length=20, choices=[('DISPONIBLE', 'Disponible'), ('EN_SERVICE', 'En service'), ('MAINTENANCE', 'Maintenance'), ('HORS_SERVICE', 'Hors service')], default='DISPONIBLE')
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    capacity_unit = models.CharField(max_length=60, default='éléments / cycle')
    tasks = models.TextField()
    available_from = models.DateField(null=True, blank=True)
    maintenance_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']


class StockItem(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    unit = models.CharField(max_length=30, default='pièces')
    minimum_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    lot_number = models.CharField(max_length=80, blank=True)
    received_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']


class PrescriptionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Use Prescription.save() so audit signals and cache invalidation run.')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Create prescriptions individually so audit signals run.')


class Prescription(models.Model):
    """
    Represents a dental prescription order sent from a dentist to a lab.
    Patient identity is anonymised (patient_ref = PAT-XXXX) before reaching the lab,
    in compliance with Loi 09-08 / CNDP.

    Two-Way Courier + CFAO Technician Pipeline:
      PHYSIQUE:   Dentist → ATTENTE_RAMASSAGE → EN_ROUTE_LABO → A_CONFIRMER
      NUMERIQUE:  Dentist → A_CONFIRMER (bypass courier)
      Lab:        SALLE_CAO → USINAGE_CNC → FRITTAGE_9H → CONTROLE_QUALITE → PRET_EXPEDITION
      Courier:    EN_ROUTE_CABINET → LIVRE
    """

    objects = PrescriptionQuerySet.as_manager()

    class Status(models.TextChoices):
        RETOUR_DEMANDE = 'RETOUR_DEMANDE', 'Retour demandé'
        COULEE_PLATRE = 'COULEE_PLATRE', 'Coulée du plâtre'
        SCAN_LABO = 'SCAN_LABO', 'Scan laboratoire'
        CONTROLE_MODELE = 'CONTROLE_MODELE', 'Contrôle modèle et scan'
        RESCANNER = 'RESCANNER', 'Rescanner'
        VALIDATION_CAO = 'VALIDATION_CAO', 'Validation dentiste'
        ESSAYAGE = 'ESSAYAGE', 'Essayage clinique'
        CLOTURE = 'CLOTURE', 'Essayage validé'
        A_REFAIRE = 'A_REFAIRE', 'À refaire'
        RECOULER = 'RECOULER', 'Recouler'
        DEMANDE_RECUE = 'DEMANDE_RECUE', 'Demande reçue'
        ANALYSE_DEMANDE = 'ANALYSE_DEMANDE', 'Analyse de la demande'
        CONTROLE_DOSSIER = 'CONTROLE_DOSSIER', 'Contrôle du dossier'
        PLANIFICATION = 'PLANIFICATION', 'Planification'
        PREPARATION_CNC = 'PREPARATION_CNC', 'Préparation FAO'
        TRAITEMENT_THERMIQUE = 'TRAITEMENT_THERMIQUE', 'Traitement thermique'
        PREPARATION_3D = 'PREPARATION_3D', 'Préparation impression 3D'
        IMPRESSION_3D = 'IMPRESSION_3D', 'Impression 3D'
        LAVAGE_SECHAGE = 'LAVAGE_SECHAGE', 'Lavage et séchage'
        POST_POLYMERISATION = 'POST_POLYMERISATION', 'Post-polymérisation'
        MODELE_TRAVAIL = 'MODELE_TRAVAIL', 'Modèle de travail'
        MODELAGE = 'MODELAGE', 'Modelage'
        FABRICATION_MANUELLE = 'FABRICATION_MANUELLE', 'Fabrication conventionnelle'
        FINITION = 'FINITION', 'Finition'
        CONDITIONNEMENT = 'CONDITIONNEMENT', 'Conditionnement'
        # --- Pre-Lab Courier Phase (Physical Impressions Only) ---
        ATTENTE_RAMASSAGE = "ATTENTE_RAMASSAGE", "En attente de ramassage coursier"
        EN_ROUTE_LABO     = "EN_ROUTE_LABO",     "Coursier en route vers le labo"
        # --- Lab CFAO Pipeline ---
        A_CONFIRMER       = "A_CONFIRMER",       "Réception / Modèle"
        SALLE_CAO         = "SALLE_CAO",         "Conception Exocad / Fichier Construction"
        USINAGE_CNC       = "USINAGE_CNC",       "Calcul CNC & Usinage"
        FRITTAGE_9H       = "FRITTAGE_9H",       "Four de Frittage 9h & Refroidissement"
        CONTROLE_QUALITE  = "CONTROLE_QUALITE",  "Phase de Contrôle & Glaçage"
        PRET_EXPEDITION   = "PRET_EXPEDITION",   "Prêt pour Coursier"
        # --- Final Delivery Phase ---
        EN_ROUTE_CABINET  = "EN_ROUTE_CABINET",  "En livraison vers le cabinet"
        LIVRE             = "LIVRE",             "Livré au Cabinet"

    class ImpressionType(models.TextChoices):
        PHYSIQUE  = "PHYSIQUE",  "Empreinte Physique (Coursier)"
        NUMERIQUE = "NUMERIQUE", "Fichier Numérique (.STL)"

    class BillingStage(models.TextChoices):
        COMMANDE  = "COMMANDE",  "Bon de Commande"
        SITUATION = "SITUATION", "En Situation (Relevé)"
        FACTURE   = "FACTURE",   "Facturé & Payé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient_ref = models.CharField(max_length=50, help_text="Anonymised patient reference (e.g. PAT-4829)")
    dentist_name = models.CharField(max_length=100, help_text="Name of the dentist who created the order")
    dentist_account = models.ForeignKey('customers.PlatformAccount', null=True, blank=True, on_delete=models.PROTECT)
    partner_clinic = models.ForeignKey(
        PartnerClinic, null=True, blank=True, on_delete=models.PROTECT,
        related_name='prescriptions',
    )
    invoiced_at = models.DateTimeField(null=True, blank=True, editable=False)
    invoiced_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    invoiced_clinic_name = models.CharField(max_length=120, blank=True, editable=False)
    tooth_number = models.IntegerField()
    shade = models.CharField(max_length=10)
    material = models.CharField(max_length=50)
    disinfected = models.BooleanField(default=False)
    is_fast_track = models.BooleanField(default=False, help_text="Priority delivery option (+200 MAD)")
    delivery_service = models.CharField(max_length=8, default='STANDARD', choices=[('STANDARD', 'J+4'), ('EXPRESS', 'J+2'), ('NEXT_DAY', 'J+1')])
    design_validation_requested = models.BooleanField(default=False)
    state_version = models.PositiveBigIntegerField(default=1, editable=False)
    intake_version = models.PositiveSmallIntegerField(default=2, editable=False)
    intake_revision = models.PositiveIntegerField(default=1, editable=False)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    express_surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    manual_surcharge = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    workstation_notes = models.JSONField(default=dict, blank=True, editable=False)
    deadline_at = models.DateTimeField(null=True, blank=True, editable=False)
    pause_started_at = models.DateTimeField(null=True, blank=True, editable=False)
    deadline_suspended_seconds = models.PositiveBigIntegerField(default=0, editable=False)
    delivered_at = models.DateTimeField(null=True, blank=True, editable=False)
    fitting_validated_at = models.DateTimeField(null=True, blank=True, editable=False)
    qr_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    delivery_pin_hash = models.CharField(max_length=255, blank=True, editable=False)
    pin_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    pin_locked_until = models.DateTimeField(null=True, blank=True, editable=False)
    rework_restart_status = models.CharField(max_length=20, blank=True, editable=False)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Server-calculated quote in MAD")

    impression_type = models.CharField(
        max_length=20,
        choices=ImpressionType.choices,
        default=ImpressionType.PHYSIQUE,
        help_text="Type d'empreinte : physique (coursier) ou numérique (.STL)",
    )
    stl_file_name = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Nom du fichier .STL téléversé (mock) si empreinte numérique",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DEMANDE_RECUE,
    )
    delivery_date = models.DateField(null=True, blank=True, help_text="Delivery date set by the lab")
    production_method = models.CharField(max_length=20, blank=True, choices=[('CFAO', 'CFAO / usinage CNC'), ('IMPRESSION_3D', 'Impression 3D'), ('CONVENTIONNEL', 'Fabrication conventionnelle')])
    thermal_treatment = models.CharField(max_length=20, default='AUCUN', choices=[('AUCUN', 'Aucun'), ('FRITTAGE', 'Frittage'), ('CRISTALLISATION', 'Cristallisation'), ('CUISSON', 'Cuisson')])
    technical_notes = models.TextField(blank=True)
    analysis_validated = models.BooleanField(default=False)
    reception_validated = models.BooleanField(default=False)
    quality_validated = models.BooleanField(default=False)
    workflow_history = models.JSONField(default=list, blank=True)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    is_paused = models.BooleanField(default=False)
    pause_reason = models.TextField(blank=True)
    current_issues = models.TextField(blank=True)
    production_attempt = models.PositiveIntegerField(default=1, editable=False)
    automatic_deadline = models.DateField(null=True, blank=True, editable=False)
    deadline_calculated_at = models.DateTimeField(null=True, blank=True, editable=False)

    billing_stage = models.CharField(
        max_length=20,
        choices=BillingStage.choices,
        default=BillingStage.COMMANDE,
        help_text="Étape financière : Commande → Situation → Facture",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivery_pin = models.CharField(
        max_length=4, blank=True,
        help_text="Code PIN à 4 chiffres généré automatiquement",
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self._state.adding:
            import secrets
            from django.contrib.auth.hashers import make_password
            self._new_delivery_pin = f'{secrets.randbelow(10000):04d}'
            self.delivery_pin_hash = make_password(self._new_delivery_pin)
            self.delivery_pin = ''
            self.status = self.Status.DEMANDE_RECUE
            self.workflow_history = [{'status': self.status, 'at': timezone.now().isoformat()}]
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        # Keep the source write and synchronous audit INSERT in one transaction.
        with transaction.atomic(using=using):
            previous = None
            if not self._state.adding:
                previous = type(self).objects.using(using).select_for_update().filter(pk=self.pk).values(
                    'billing_stage', 'invoiced_at', 'invoiced_amount',
                    'invoiced_clinic_name', 'total_price', 'partner_clinic_id',
                    'status', 'state_version', 'intake_version', 'tooth_number', 'shade', 'material',
                    'delivery_service', 'design_validation_requested', 'disinfected', 'production_method',
                    'accepted', 'thermal_treatment', 'is_fast_track',
                ).first()
            fields = kwargs.get('update_fields')
            from .domain import validate_source_change
            validate_source_change(self, previous, fields)
            if previous and self.status != previous['status'] and (fields is None or 'status' in fields):
                self.state_version = previous['state_version'] + 1
                if fields is not None:
                    kwargs['update_fields'] = set(fields) | {'state_version'}
                    fields = kwargs['update_fields']
            billing_written = fields is None or 'billing_stage' in fields
            if previous and previous['invoiced_at']:
                for field in ('billing_stage', 'invoiced_at', 'invoiced_amount', 'invoiced_clinic_name', 'total_price', 'partner_clinic_id'):
                    value = previous[field]
                    model_field = 'partner_clinic' if field == 'partner_clinic_id' else field
                    if (fields is None or model_field in fields or field in fields) and getattr(self, field) != value:
                        raise ValidationError({model_field: 'Issued billing details are immutable.'})
            first_invoice = (
                billing_written and self.billing_stage == self.BillingStage.FACTURE
                and (previous is None or previous['billing_stage'] != self.BillingStage.FACTURE)
            )
            if first_invoice:
                amount = self.total_price if fields is None or 'total_price' in fields or previous is None else previous['total_price']
                clinic_id = self.partner_clinic_id if fields is None or 'partner_clinic' in fields or 'partner_clinic_id' in fields or previous is None else previous['partner_clinic_id']
                if amount is None or amount < 0:
                    raise ValidationError({'total_price': 'A non-negative amount is required before invoicing.'})
                self.invoiced_at = timezone.now()
                self.invoiced_amount = Decimal(amount)
                self.invoiced_clinic_name = PartnerClinic.objects.using(using).get(pk=clinic_id).name if clinic_id else self.dentist_name
                if fields is not None:
                    kwargs['update_fields'] = set(kwargs.get('update_fields', fields)) | {'invoiced_at', 'invoiced_amount', 'invoiced_clinic_name'}
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_ref} | Dent {self.tooth_number} | {self.material} | {self.status}"


class ImmutableHistoryQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Append entries individually so validation and synchronous signals run.')

    def update(self, **kwargs):
        raise ValidationError('Prescription history is append-only.')

    def delete(self):
        raise ValidationError('Prescription history cannot be deleted.')


class PrescriptionHistory(models.Model):
    prescription = models.ForeignKey(
        Prescription, on_delete=models.PROTECT, related_name='audit_history',
    )
    previous_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32)
    action_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    # Immutable identity snapshot: supports Django Auth and existing demo accounts.
    changed_by = models.CharField(max_length=255, default='system', editable=False)
    source_version = models.PositiveBigIntegerField(null=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True, editable=False)

    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ['created_at', 'pk']
        indexes = [models.Index(fields=['prescription', 'created_at'], name='prescription_history_time')]
        constraints = [models.UniqueConstraint(fields=['prescription', 'source_version'], name='one_history_per_source_version')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Prescription history is append-only.')
        kwargs['force_insert'] = True
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Prescription history cannot be deleted.')


class AnalyticsRefreshState(models.Model):
    pipeline = models.CharField(max_length=80, primary_key=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    undated_invoice_count = models.PositiveBigIntegerField(default=0)


class MonthlyBillingCatalog(models.Model):
    prescription_id = models.UUIDField(primary_key=True)
    partner_clinic_id = models.BigIntegerField(null=True)
    clinic_name = models.CharField(max_length=120)
    patient_ref = models.CharField(max_length=50)
    status = models.CharField(max_length=32)
    billing_stage = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    invoiced_at = models.DateTimeField(null=True)
    billing_month = models.DateField(null=True)
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.CharField(max_length=3)
    audit_event_count = models.BigIntegerField()
    status_transition_count = models.BigIntegerField()
    last_status_change_at = models.DateTimeField(null=True)
    legacy_invoice_without_date = models.BooleanField()
    refreshed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'monthly_billing_catalog'
        ordering = ['-created_at', 'prescription_id']


class MonthlyBillingSummary(models.Model):
    catalog_key = models.CharField(max_length=100, primary_key=True)
    billing_month = models.DateField()
    partner_clinic_id = models.BigIntegerField(null=True)
    clinic_name = models.CharField(max_length=120)
    invoice_count = models.BigIntegerField()
    invoiced_total = models.DecimalField(max_digits=20, decimal_places=2)
    delivered_count = models.BigIntegerField()
    in_progress_count = models.BigIntegerField()
    status_transition_count = models.BigIntegerField()
    missing_audit_count = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    refreshed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'monthly_billing_summary'
        ordering = ['-billing_month', 'catalog_key']


class InventoryTransaction(models.Model):
    class Type(models.TextChoices):
        OPENING = 'OPENING', 'Opening balance'
        RESTOCK = 'RESTOCK', 'Restock'
        USAGE = 'USAGE', 'Material consumed'
        REWORK_LOSS = 'REWORK_LOSS', 'Material loss'
        REVERSAL = 'REVERSAL', 'Compensating entry'
        LOSS_OFFSET = 'LOSS_OFFSET', 'Reclassification offset'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name='transactions')
    prescription = models.ForeignKey(Prescription, null=True, blank=True, on_delete=models.PROTECT, related_name='inventory_transactions')
    quantity_changed = models.DecimalField(max_digits=20, decimal_places=6)
    transaction_type = models.CharField(max_length=12, choices=Type.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.CharField(max_length=255, default='system')
    production_attempt = models.PositiveIntegerField(null=True, blank=True)
    source_history = models.ForeignKey(PrescriptionHistory, null=True, blank=True, on_delete=models.PROTECT, related_name='inventory_transactions')
    reversal_of = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal')
    reclassifies = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='loss_classification')
    source_usage = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='loss_offset')
    production_lot = models.ForeignKey('api.ProductionLot', null=True, blank=True, on_delete=models.PROTECT, related_name='movements')
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4)
    unit_snapshot = models.CharField(max_length=7)
    material_name_snapshot = models.CharField(max_length=120)
    unit_cost_snapshot = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ['created_at', 'pk']
        indexes = [
            models.Index(fields=['inventory_item', 'created_at'], name='inventory_ledger_time'),
            models.Index(fields=['prescription', 'production_attempt'], name='inventory_usage_attempt'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['inventory_item'], condition=models.Q(transaction_type='OPENING'), name='inventory_one_opening'),
            models.CheckConstraint(condition=(
                models.Q(transaction_type='OPENING', quantity_changed__gte=0)
                | models.Q(transaction_type='RESTOCK', quantity_changed__gt=0)
                | models.Q(transaction_type='LOSS_OFFSET', quantity_changed__gt=0)
                | models.Q(transaction_type__in=['USAGE', 'REWORK_LOSS'], quantity_changed__lt=0)
                | (models.Q(transaction_type='REVERSAL') & ~models.Q(quantity_changed=0))
            ), name='inventory_transaction_sign'),
            models.CheckConstraint(condition=models.Q(balance_after__gte=0), name='inventory_balance_nonnegative'),
            models.CheckConstraint(condition=models.Q(unit_cost_snapshot__isnull=True) | models.Q(unit_cost_snapshot__gte=0), name='inventory_cost_nonnegative'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Inventory transactions are append-only.')
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            source_id = self.reversal_of_id or self.reclassifies_id or self.source_usage_id
            source = type(self).objects.using(using).get(pk=source_id) if source_id else None
            order_id = source.prescription_id if source else self.prescription_id
            order = Prescription.objects.using(using).select_for_update().get(pk=order_id) if order_id else None
            item = Inventory.objects.using(using).select_for_update().get(pk=self.inventory_item_id)
            if self.production_lot_id:
                lot = self.production_lot
                if self.prescription_id and not lot.prescriptions.filter(pk=self.prescription_id).exists():
                    raise ValidationError('The production lot must be linked to this case.')
                if lot.inventory_item_id and lot.inventory_item_id != item.pk:
                    raise ValidationError('The lot material must match the consumed inventory item.')
            self.quantity_changed = Decimal(str(self.quantity_changed))
            if not self.quantity_changed.is_finite():
                raise ValidationError({'quantity_changed': 'A finite quantity is required.'})
            kind, quantity = self.transaction_type, self.quantity_changed
            if ((kind == 'OPENING' and quantity < 0)
                or (kind == 'RESTOCK' and quantity <= 0)
                or (kind in ['USAGE', 'REWORK_LOSS'] and quantity >= 0)
                or (kind == 'LOSS_OFFSET' and (quantity <= 0 or not self.source_usage_id))
                or (kind == 'REVERSAL' and (quantity == 0 or not self.reversal_of_id))):
                raise ValidationError({'quantity_changed': 'Invalid quantity or reversal reference for this movement type.'})
            if source is not None:
                if source.inventory_item_id != self.inventory_item_id:
                    raise ValidationError('A correction must reference the same inventory item.')
                if self.reversal_of_id and self.quantity_changed != -source.quantity_changed:
                    raise ValidationError('A correction must match its source quantity.')
                if self.reclassifies_id and not source.quantity_changed <= self.quantity_changed < 0:
                    raise ValidationError('Loss must not exceed the original consumption.')
                if self.source_usage_id and (self.transaction_type != 'LOSS_OFFSET' or source.transaction_type != 'USAGE' or self.quantity_changed > -source.quantity_changed):
                    raise ValidationError('Offset must reference measured consumption without exceeding it.')
                if self.reversal_of_id and (self.transaction_type != 'REVERSAL' or source.transaction_type in ['REVERSAL', 'OPENING']):
                    raise ValidationError('This transaction cannot be reversed.')
                if self.reversal_of_id and source.source_history_id:
                    raise ValidationError('Automatic rework classifications cannot be manually reversed.')
                if self.reclassifies_id and (self.transaction_type != 'REWORK_LOSS' or source.transaction_type != 'USAGE'):
                    raise ValidationError('Only consumed material can be reclassified as rework loss.')
                self.prescription_id = source.prescription_id
                self.production_attempt = source.production_attempt
                self.unit_snapshot = source.unit_snapshot
                self.material_name_snapshot = source.material_name_snapshot
                self.unit_cost_snapshot = source.unit_cost_snapshot
            else:
                self.unit_snapshot = item.unit
                self.material_name_snapshot = item.material_name
                self.unit_cost_snapshot = item.unit_cost
            if self.transaction_type == 'USAGE' and not self.prescription_id:
                raise ValidationError({'prescription': 'Material usage requires a prescription.'})
            if self.transaction_type in ['USAGE', 'REWORK_LOSS'] and order and source is None:
                if self.production_attempt is not None and self.production_attempt != order.production_attempt:
                    raise ValidationError('Material consumption must reference the current production attempt.')
                self.production_attempt = order.production_attempt
            self.balance_after = item.quantity + self.quantity_changed
            if self.balance_after < 0:
                raise ValidationError({'quantity_changed': 'Insufficient inventory.'})
            self.full_clean(validate_unique=False, validate_constraints=False)
            kwargs['force_insert'] = True
            # PostgreSQL insert trigger updates Inventory.quantity atomically.
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Inventory transactions cannot be deleted.')


class TaskOutbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=20, choices=[('CALENDAR', 'Calendar calculation'), ('INVOICE', 'Invoice PDF generation'), ('CACHE', 'Cache invalidation'), ('CREDIT', 'Credit note PDF'), ('CATALOG', 'Catalog refresh')])
    prescription = models.ForeignKey(Prescription, on_delete=models.PROTECT, related_name='task_events')
    created_at = models.DateTimeField(auto_now_add=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)


class InvoiceArtifact(models.Model):
    prescription = models.OneToOneField(Prescription, on_delete=models.PROTECT, related_name='invoice_artifact')
    status = models.CharField(max_length=20, default='MOCK_READY', editable=False)
    mock_reference = models.CharField(max_length=255, editable=False)
    snapshot = models.JSONField(editable=False)
    storage_name = models.CharField(max_length=255, blank=True, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Generated invoice snapshots are immutable.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Generated invoice snapshots cannot be deleted.')


class InvoiceDispatchLog(models.Model):
    artifact = models.ForeignKey(InvoiceArtifact, on_delete=models.PROTECT, related_name='dispatch_logs')
    channel = models.CharField(max_length=10, choices=[('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp')])
    status = models.CharField(max_length=24, default='SIMULATED_NOT_SENT', editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['artifact', 'channel'], name='invoice_one_mock_dispatch')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Dispatch logs are immutable.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Dispatch logs cannot be deleted.')


class MonthlyStockLossCatalog(models.Model):
    catalog_key = models.CharField(max_length=100, primary_key=True)
    loss_month = models.DateField()
    inventory_item_id = models.BigIntegerField()
    material_name = models.CharField(max_length=120)
    unit = models.CharField(max_length=7)
    lost_quantity = models.DecimalField(max_digits=28, decimal_places=6)
    valued_loss_amount = models.DecimalField(max_digits=44, decimal_places=12, null=True)
    unvalued_quantity = models.DecimalField(max_digits=28, decimal_places=6)
    complete_valuation = models.BooleanField()
    currency = models.CharField(max_length=3)
    refreshed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'monthly_stock_loss_catalog'
        ordering = ['-loss_month', 'catalog_key']


from .business_models import (  # noqa: E402,F401 -- register tenant models with Django
    WorkflowEvent, ClinicalItem, CaseAttachment, CaseInspection, DesignReview, ProductionLot,
    ReworkCase, BillingPeriod, StatementLine, FinanceInvoice, InvoiceDocument, CreditNote,
    CaseNotification, MessageDelivery, TenantReadVersion, MonthlyStatementCatalog,
    CaseCommandReceipt, BillingDispute,
    CreditDocument, MonthlyFinancialCatalog,
)
