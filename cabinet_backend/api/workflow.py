METHODS = {'CFAO': 'CFAO / usinage CNC', 'IMPRESSION_3D': 'Impression 3D', 'CONVENTIONNEL': 'Fabrication conventionnelle'}
LABELS = {
    'RETOUR_DEMANDE': 'Retour demandé', 'COULEE_PLATRE': 'Coulée du plâtre', 'SCAN_LABO': 'Scan laboratoire',
    'CONTROLE_MODELE': 'Contrôle modèle et scan', 'RESCANNER': 'Rescanner',
    'VALIDATION_CAO': 'Validation du design par le dentiste', 'ESSAYAGE': 'Essayage clinique', 'CLOTURE': 'Essayage validé',
    'A_REFAIRE': 'Reprise de fabrication', 'RECOULER': 'Reprise de coulée',
    'DEMANDE_RECUE': 'Demande reçue / acceptation',
    'ANALYSE_DEMANDE': 'Analyse de la demande', 'ATTENTE_RAMASSAGE': 'Ramassage à organiser',
    'EN_ROUTE_LABO': 'Acheminement vers le labo', 'A_CONFIRMER': 'Réception au laboratoire',
    'CONTROLE_DOSSIER': 'Contrôle du dossier et des empreintes', 'PLANIFICATION': 'Planification et choix technique',
    'SALLE_CAO': 'Conception numérique / CAO', 'PREPARATION_CNC': 'Préparation FAO / placement et parcours outil',
    'USINAGE_CNC': 'Usinage CNC', 'TRAITEMENT_THERMIQUE': 'Traitement thermique', 'FRITTAGE_9H': 'Frittage (ancien parcours)',
    'PREPARATION_3D': 'Orientation, supports et préparation du plateau', 'IMPRESSION_3D': 'Impression 3D',
    'LAVAGE_SECHAGE': 'Lavage et séchage', 'POST_POLYMERISATION': 'Post-polymérisation',
    'MODELE_TRAVAIL': 'Préparation du modèle de travail', 'MODELAGE': 'Modelage / maquette',
    'FABRICATION_MANUELLE': 'Fabrication conventionnelle', 'FINITION': 'Finition et caractérisation',
    'CONTROLE_QUALITE': 'Contrôle qualité final', 'CONDITIONNEMENT': 'Conditionnement et documents',
    'PRET_EXPEDITION': 'Prêt pour expédition', 'EN_ROUTE_CABINET': 'Livraison au cabinet', 'LIVRE': 'Livré',
}
TREATMENTS = {'AUCUN': 'Sans traitement thermique', 'FRITTAGE': 'Frittage', 'CRISTALLISATION': 'Cristallisation', 'CUISSON': 'Cuisson'}


def workflow_steps(order):
    keys = ['DEMANDE_RECUE', 'ANALYSE_DEMANDE']
    if order.impression_type == 'PHYSIQUE':
        keys += ['ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO']
    keys += ['A_CONFIRMER', 'CONTROLE_DOSSIER']
    if order.impression_type == 'PHYSIQUE' and order.intake_version >= 2:
        keys += ['COULEE_PLATRE', 'SCAN_LABO', 'CONTROLE_MODELE']
    keys += ['PLANIFICATION']
    if order.production_method == 'CFAO':
        keys += ['SALLE_CAO']
        if order.design_validation_requested:
            keys += ['VALIDATION_CAO']
        keys += ['PREPARATION_CNC', 'USINAGE_CNC']
        if order.status == 'FRITTAGE_9H':
            keys += ['FRITTAGE_9H']
        elif order.thermal_treatment != 'AUCUN':
            keys += ['TRAITEMENT_THERMIQUE']
    elif order.production_method == 'IMPRESSION_3D':
        keys += ['SALLE_CAO']
        if order.design_validation_requested:
            keys += ['VALIDATION_CAO']
        keys += ['PREPARATION_3D', 'IMPRESSION_3D', 'LAVAGE_SECHAGE', 'POST_POLYMERISATION']
    elif order.production_method == 'CONVENTIONNEL':
        keys += ['MODELE_TRAVAIL', 'MODELAGE', 'FABRICATION_MANUELLE']
    keys += ['FINITION', 'CONTROLE_QUALITE', 'CONDITIONNEMENT', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET', 'LIVRE']
    if order.intake_version >= 2:
        keys += ['ESSAYAGE', 'CLOTURE']
    if order.status == 'RETOUR_DEMANDE':
        keys.insert(keys.index('A_CONFIRMER'), 'RETOUR_DEMANDE')
    if order.status in {'A_REFAIRE', 'RECOULER', 'RESCANNER'}:
        restart = order.rework_restart_status or ('MODELAGE' if order.status == 'RECOULER' else (
            'MODELE_TRAVAIL' if order.production_method == 'CONVENTIONNEL' else 'SALLE_CAO'
        ))
        if restart not in keys:
            keys.insert(keys.index('PLANIFICATION'), restart)
        keys.insert(keys.index(restart), order.status)
    return [{'key': key, 'label': TREATMENTS.get(order.thermal_treatment, LABELS[key]) if key == 'TRAITEMENT_THERMIQUE' else LABELS[key]} for key in keys]


def next_status(order):
    keys = [step['key'] for step in workflow_steps(order)]
    if order.status not in keys or keys.index(order.status) == len(keys) - 1:
        return None
    return keys[keys.index(order.status) + 1]
