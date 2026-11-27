"""Shared workflow specification and read-only case descriptors.

Workstation ownership does not replace specialized clinic/custody commands or
execution permissions. Compatibility tests freeze the original guard values.
"""
from dataclasses import dataclass
from enum import StrEnum


WORKFLOW_PAYLOAD_SHAPE = 'workflow-step-v3'


class Action(StrEnum):
    """Existing audit spellings, including command defaults and explicit overrides."""
    ACCEPT = 'ACCEPT'
    ADVANCE = 'ADVANCE'
    ASSESS_LOSS = 'ASSESS-LOSS'
    CHECKOUT = 'CHECKOUT'
    CONFIRM_DELIVERY_COMMAND = 'CONFIRM-DELIVERY'
    CONFIRM_DELIVERY = 'CONFIRM_DELIVERY'
    DESIGN_DECISION_COMMAND = 'DESIGN-DECISION'
    DESIGN_REQUEST_COMMAND = 'DESIGN-REQUEST'
    DESIGN_DECISION = 'DESIGN_DECISION'
    DESIGN_REQUEST = 'DESIGN_REQUEST'
    DISPUTE = 'DISPUTE'
    FITTING = 'FITTING'
    INSPECTION = 'INSPECTION'
    INSPECTION_ADVANCE = 'INSPECTION_ADVANCE'
    INSPECTION_FAILED = 'INSPECTION_FAILED'
    ISSUE_PIN = 'ISSUE-PIN'
    ISSUE_INVOICE = 'ISSUE_INVOICE'
    LAB_DEPOSIT = 'LAB-DEPOSIT'
    NOTE = 'NOTE'
    PAUSE = 'PAUSE'
    PICKUP = 'PICKUP'
    PLANNING_ASSIGN = 'PLANNING-ASSIGN'
    PLANNING_BEGIN_UNLOAD = 'PLANNING-BEGIN-UNLOAD'
    PLANNING_BLOCK = 'PLANNING-BLOCK'
    PLANNING_COMPLETE = 'PLANNING-COMPLETE'
    PLANNING_CYCLE_FINISHED = 'PLANNING-CYCLE-FINISHED'
    PLANNING_ESTIMATE = 'PLANNING-ESTIMATE'
    PLANNING_LAUNCH_CYCLE = 'PLANNING-LAUNCH-CYCLE'
    PLANNING_LOCK = 'PLANNING-LOCK'
    PLANNING_PAUSE = 'PLANNING-PAUSE'
    PLANNING_RESCHEDULE = 'PLANNING-RESCHEDULE'
    PLANNING_RESUME = 'PLANNING-RESUME'
    PLANNING_START = 'PLANNING-START'
    RECORD_PAYMENT = 'RECORD_PAYMENT'
    REVERSE_PAYMENT = 'REVERSE_PAYMENT'
    QUOTE = 'QUOTE'
    RESUBMIT = 'RESUBMIT'
    REWORK = 'REWORK'
    SAVE = 'SAVE'
    TRANSITION = 'TRANSITION'


class StepKind(StrEnum):
    ACCEPT = 'ACCEPT'
    CONFIRM = 'CONFIRM'
    PLAN = 'PLAN'
    INSPECT = 'INSPECT'
    DESIGN = 'DESIGN'
    WORK = 'WORK'
    REWORK = 'REWORK'
    CUSTODY = 'CUSTODY'
    CLINIC = 'CLINIC'
    DONE = 'DONE'


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    stage: str
    kind: StepKind
    owner_roles: frozenset[str]
    external: bool
    rework_origin: bool
    manufacturing: bool
    inspection_stages: tuple[str, ...] = ()
    confirm_field: str = ''
    instruction: str = ''


STAGES = [
    ('COMMANDE', 'Commande'),
    ('RECEPTION', 'Collecte et réception'),
    ('CONTROLE_ENTREE', "Contrôle d'entrée"),
    ('MODELE', 'Plâtre et scan'),
    ('CONCEPTION', 'Planification et conception'),
    ('FABRICATION', 'Fabrication'),
    ('FINITION_QC', 'Finition et contrôle qualité'),
    ('LIVRAISON', 'Livraison et essayage'),
    ('CLOTURE', 'Clôturé'),
]
_STAGE_LABELS = dict(STAGES)


def _step(key, label, stage, kind, *owner_roles, external=False,
          rework_origin=False, manufacturing=False, inspection_stages=(),
          confirm_field='', instruction=''):
    return Step(key, label, stage, kind, frozenset(owner_roles), external,
                rework_origin, manufacturing, inspection_stages, confirm_field,
                instruction)


STEPS: dict[str, Step] = {step.key: step for step in (
    _step('DEMANDE_RECUE', 'Demande reçue / acceptation', 'COMMANDE', StepKind.ACCEPT, 'RECEPTION'),
    _step('ANALYSE_DEMANDE', 'Analyse de la demande', 'COMMANDE', StepKind.CONFIRM, 'RECEPTION',
          confirm_field='analysis_validated',
          instruction='Vérifier la prescription, la dent, la teinte, le matériau demandé et les informations nécessaires avant d’accepter la demande.'),
    _step('ATTENTE_RAMASSAGE', 'Ramassage à organiser', 'RECEPTION', StepKind.CUSTODY, 'COURIER',
          external=True,
          instruction='Analyse validée. Le coursier doit récupérer l’empreinte physique au cabinet.'),
    _step('EN_ROUTE_LABO', 'Acheminement vers le labo', 'RECEPTION', StepKind.CUSTODY, 'COURIER',
          external=True,
          instruction='L’empreinte est en cours d’acheminement. Le coursier confirmera son dépôt au laboratoire.'),
    _step('A_CONFIRMER', 'Réception au laboratoire', 'RECEPTION', StepKind.CONFIRM, 'RECEPTION',
          inspection_stages=('PHYSICAL', 'DIGITAL'), confirm_field='reception_validated',
          instruction='Enregistrer la réception des empreintes ou fichiers et vérifier leur conformité et la désinfection déclarée.'),
    _step('CONTROLE_DOSSIER', 'Contrôle du dossier et des empreintes', 'CONTROLE_ENTREE', StepKind.INSPECT, 'RECEPTION',
          inspection_stages=('PHYSICAL', 'DIGITAL'),
          instruction='Contrôler la complétude des fichiers, modèles et informations du dossier. Consigner les précisions demandées au cabinet dans les notes.'),
    _step('RETOUR_DEMANDE', 'Retour demandé', 'CONTROLE_ENTREE', StepKind.CLINIC, 'RECEPTION', external=True),
    _step('COULEE_PLATRE', 'Coulée du plâtre', 'MODELE', StepKind.WORK, 'RECEPTION', rework_origin=True),
    _step('SCAN_LABO', 'Scan laboratoire', 'MODELE', StepKind.WORK, 'RECEPTION', rework_origin=True),
    _step('CONTROLE_MODELE', 'Contrôle modèle et scan', 'MODELE', StepKind.INSPECT, 'RECEPTION',
          rework_origin=True, inspection_stages=('MODEL',)),
    _step('RECOULER', 'Reprise de coulée', 'MODELE', StepKind.REWORK, 'FAO'),
    _step('RESCANNER', 'Rescanner', 'MODELE', StepKind.REWORK, 'FAO'),
    _step('PLANIFICATION', 'Planification et choix technique', 'CONCEPTION', StepKind.PLAN, 'RECEPTION',
          instruction='Choisir la méthode de fabrication et fixer la livraison prévue. Le parcours technique s’adaptera à ce choix.'),
    _step('SALLE_CAO', 'Conception numérique / CAO', 'CONCEPTION', StepKind.DESIGN, 'CAO', rework_origin=True,
          instruction='Réaliser la conception numérique et valider le fichier de fabrication.'),
    _step('VALIDATION_CAO', 'Validation du design par le dentiste', 'CONCEPTION', StepKind.CLINIC, 'CAO', external=True),
    _step('MODELE_TRAVAIL', 'Préparation du modèle de travail', 'CONCEPTION', StepKind.WORK, 'FAO', rework_origin=True,
          instruction='Préparer et contrôler le modèle de travail.'),
    _step('MODELAGE', 'Modelage / maquette', 'CONCEPTION', StepKind.WORK, 'FAO', rework_origin=True,
          instruction='Préparer la maquette et les formes selon la prescription.'),
    _step('PREPARATION_CNC', 'Préparation FAO / placement et parcours outil', 'FABRICATION', StepKind.WORK, 'FAO',
          rework_origin=True,
          instruction='Préparer la FAO, le placement dans le brut et le parcours d’usinage.'),
    _step('USINAGE_CNC', 'Usinage CNC', 'FABRICATION', StepKind.WORK, 'FAO', rework_origin=True, manufacturing=True,
          instruction='Suivre l’usinage selon le dossier technique de la commande.'),
    _step('TRAITEMENT_THERMIQUE', 'Traitement thermique', 'FABRICATION', StepKind.WORK, 'FAO',
          rework_origin=True, manufacturing=True,
          instruction='Effectuer le traitement prévu selon le protocole du matériau et de l’appareil.'),
    _step('FRITTAGE_9H', 'Frittage (ancien parcours)', 'FABRICATION', StepKind.WORK, 'FAO',
          rework_origin=True, manufacturing=True,
          instruction='Terminer le traitement du dossier déjà engagé dans l’ancien parcours.'),
    _step('PREPARATION_3D', 'Orientation, supports et préparation du plateau', 'FABRICATION', StepKind.WORK, 'FAO',
          rework_origin=True,
          instruction='Préparer l’orientation, les supports et le plateau de fabrication.'),
    _step('IMPRESSION_3D', 'Impression 3D', 'FABRICATION', StepKind.WORK, 'FAO', rework_origin=True, manufacturing=True,
          instruction='Réaliser l’impression avec le matériau et le profil validés pour ce travail.'),
    _step('LAVAGE_SECHAGE', 'Lavage et séchage', 'FABRICATION', StepKind.WORK, 'FAO', rework_origin=True,
          instruction='Réaliser le lavage et le séchage selon le protocole du matériau.'),
    _step('POST_POLYMERISATION', 'Post-polymérisation', 'FABRICATION', StepKind.WORK, 'FAO', rework_origin=True,
          instruction='Réaliser la post-polymérisation selon le protocole du matériau.'),
    _step('FABRICATION_MANUELLE', 'Fabrication conventionnelle', 'FABRICATION', StepKind.WORK, 'FAO',
          rework_origin=True, manufacturing=True,
          instruction='Réaliser la fabrication conventionnelle conformément au dossier technique.'),
    _step('A_REFAIRE', 'Reprise de fabrication', 'FABRICATION', StepKind.REWORK, 'FAO'),
    _step('FINITION', 'Finition et caractérisation', 'FINITION_QC', StepKind.WORK, 'FAO', rework_origin=True,
          instruction='Effectuer les finitions et la caractérisation prévues pour la restauration.'),
    _step('CONTROLE_QUALITE', 'Contrôle qualité final', 'FINITION_QC', StepKind.INSPECT, 'QUALITE',
          rework_origin=True, inspection_stages=('QUALITY',),
          instruction='Contrôler la conformité à la prescription, l’ajustage, les contacts, l’occlusion, la teinte et la traçabilité.'),
    _step('CONDITIONNEMENT', 'Conditionnement et documents', 'FINITION_QC', StepKind.WORK, 'QUALITE',
          instruction='Préparer le conditionnement, les documents et l’identification de la commande.'),
    _step('PRET_EXPEDITION', 'Prêt pour expédition', 'LIVRAISON', StepKind.CUSTODY, 'COURIER', external=True,
          instruction='Commande terminée, disponible pour le ramassage du coursier.'),
    _step('EN_ROUTE_CABINET', 'Livraison au cabinet', 'LIVRAISON', StepKind.CUSTODY, 'COURIER', external=True,
          instruction='Le coursier livre la commande au cabinet.'),
    _step('LIVRE', 'Livré', 'LIVRAISON', StepKind.CLINIC, external=True, rework_origin=True,
          instruction='Commande livrée au cabinet.'),
    _step('ESSAYAGE', 'Essayage clinique', 'LIVRAISON', StepKind.CLINIC, external=True, rework_origin=True),
    _step('CLOTURE', 'Essayage validé', 'CLOTURE', StepKind.DONE, external=True, rework_origin=True),
)}


def derived_labels():
    return {key: step.label for key, step in STEPS.items()}


def derived_role_stages():
    roles = {}
    for step in STEPS.values():
        for role in step.owner_roles:
            roles.setdefault(role, set()).add(step.key)
    return roles


def derived_rework_origins():
    return {step.key for step in STEPS.values() if step.rework_origin}


def derived_manufacturing():
    return {step.key for step in STEPS.values() if step.manufacturing}


def derived_external():
    return {step.key for step in STEPS.values() if step.external}


def inspection_permitted():
    permitted = {}
    for step in STEPS.values():
        for stage in step.inspection_stages:
            permitted.setdefault(stage, set()).add(step.key)
    return permitted


def rework_restart_options(order):
    """Allowed restart set shared by command validation and case descriptors."""
    step = STEPS.get(order.status)
    if step is None or not step.rework_origin:
        return set()
    valid = {'SALLE_CAO', 'FINITION'}
    valid.add({'CFAO': 'PREPARATION_CNC', 'IMPRESSION_3D': 'PREPARATION_3D',
               'CONVENTIONNEL': 'MODELAGE'}.get(order.production_method, 'COULEE_PLATRE'))
    if order.impression_type == 'PHYSIQUE':
        valid |= {'COULEE_PLATRE', 'SCAN_LABO'}
    return valid


def describe_current_step(order):
    """Case metadata only: never request-user permissions or planning records."""
    from .workflow import next_status, workflow_steps

    step = STEPS.get(order.status)
    if step is None:
        return None
    labels = {item['key']: item['label'] for item in workflow_steps(order)}
    next_key = next_status(order)
    inspection_stages = [stage for stage in step.inspection_stages
                         if stage not in {'PHYSICAL', 'DIGITAL'}
                         or stage == ('PHYSICAL' if order.impression_type == 'PHYSIQUE' else 'DIGITAL')]
    descriptor = {
        'key': step.key, 'label': labels.get(step.key, step.label),
        'stage': step.stage, 'stage_label': _STAGE_LABELS[step.stage],
        'kind': step.kind.value, 'owner_roles': sorted(step.owner_roles),
        'external': step.external, 'rework_origin': step.rework_origin,
        'inspection_stages': inspection_stages, 'confirm_field': step.confirm_field,
        'instruction': step.instruction, 'next_key': next_key,
        'next_label': labels.get(next_key),
        # Static route metadata: entering this next step requires a linked production lot.
        'next_requires_lot': next_key in derived_manufacturing(),
    }
    if step.kind == StepKind.PLAN:
        from copy import copy
        from .workflow import METHODS
        options = {}
        for method in METHODS:
            proposed = copy(order)
            proposed.production_method = method
            target = next_status(proposed)
            route_labels = {item['key']: item['label'] for item in workflow_steps(proposed)}
            options[method] = {'next_key': target, 'next_label': route_labels.get(target)}
        descriptor['planning_options'] = options
    return descriptor


def describe_stages(order):
    """Group the applicable route without inventing completion across a rework."""
    from .workflow import workflow_steps

    route = workflow_steps(order)
    current = next((i for i, item in enumerate(route) if item['key'] == order.status), None)
    groups = {}
    for i, item in enumerate(route):
        groups.setdefault(STEPS[item['key']].stage, []).append((i, item))
    stages = []
    for key, label in STAGES:
        rows = groups.get(key)
        if not rows:
            continue
        if current is not None and any(i == current for i, _ in rows):
            state = 'current'
        elif current is not None and all(i < current for i, _ in rows):
            state = 'done'
        else:
            state = 'todo'
        stages.append({'key': key, 'label': label, 'state': state,
                       'steps': [item for _, item in rows]})
    return stages


def describe_rework_options(order):
    return [{'key': key, 'label': STEPS[key].label}
            for key in sorted(rework_restart_options(order))]
