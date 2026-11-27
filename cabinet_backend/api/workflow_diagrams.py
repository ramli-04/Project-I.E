"""Deterministic documentation of current routes; no database or command writes."""
from itertools import product
from pathlib import Path
from types import SimpleNamespace

from .workflow import METHODS, workflow_steps
from .workflow_spec import STEPS, rework_restart_options


WORKFLOW_DOCUMENT = Path(__file__).resolve().parents[2] / 'docs' / 'WORKFLOW.md'


def render_workflow():
    lines = [
        '# Parcours métier', '',
        'Document généré par `python cabinet_backend/manage.py export_workflow` ; ne pas modifier à la main.', '',
        'Les flèches pleines suivent `workflow_steps` ; les flèches pointillées représentent les commandes d’exception.',
        'Chaque famille réunit les variantes avec/sans validation du design et avec/sans frittage. '
        'Ces options ne modifient que les parcours qui les utilisent.',
        'Les libellés, les origines de reprise et les destinations autorisées proviennent de `workflow_spec`. '
        'Chaque transition reste soumise aux permissions, preuves et contrôles métier du serveur.', '',
        'Une reprise exige une origine, une cause, une action corrective et les pertes mesurées '
        '(ou une liste vide sans perte). Elle conserve le dossier et crée une nouvelle tentative. '
        'Les destinations hors du parcours principal ne créent pas de transition automatique supplémentaire.', '',
        'Ces diagrammes décrivent les dossiers actuels (`intake_version >= 2`). '
        'Les branches historiques, dont `FRITTAGE_9H`, restent prises en charge par le serveur.', '',
    ]
    for track, method in product(('PHYSIQUE', 'NUMERIQUE'), METHODS):
        title = 'Empreinte physique' if track == 'PHYSIQUE' else 'Empreinte numérique'
        lines += [f'## {title} · {METHODS[method]}', '', '```mermaid', 'flowchart TD']
        nodes, edges, exceptions = {}, set(), set()
        for review, treatment in product((False, True), ('AUCUN', 'FRITTAGE')):
            order = SimpleNamespace(impression_type=track, production_method=method,
                                    design_validation_requested=review, thermal_treatment=treatment,
                                    intake_version=2, status='DEMANDE_RECUE')
            route = workflow_steps(order)
            nodes.update((item['key'], item['label']) for item in route)
            edges.update((a['key'], b['key']) for a, b in zip(route, route[1:]))
            for item in route:
                key = item['key']
                if key in {'A_CONFIRMER', 'CONTROLE_DOSSIER'}:
                    exceptions.add((key, 'RETOUR_DEMANDE', 'Contrôle d’entrée non conforme'))
                    exceptions.add(('RETOUR_DEMANDE', 'A_CONFIRMER', 'Dossier corrigé et soumis à nouveau'))
                if key == 'VALIDATION_CAO':
                    exceptions.add((key, 'SALLE_CAO', 'Corrections demandées par le dentiste'))
                order.status = key
                for restart in sorted(rework_restart_options(order)):
                    rework = ('RECOULER' if restart == 'COULEE_PLATRE' else
                              'RESCANNER' if restart == 'SCAN_LABO' else 'A_REFAIRE')
                    exceptions.add((key, rework, 'Reprise documentée'))
                    exceptions.add((rework, restart, 'Reprendre à cette étape'))
        for source, target, _ in exceptions:
            nodes.setdefault(source, STEPS[source].label)
            nodes.setdefault(target, STEPS[target].label)
        for key, label in sorted(nodes.items()):
            lines.append(f'    {key}["{label}"]')
        lines.extend(f'    {source} --> {target}' for source, target in sorted(edges))
        lines.extend(f'    {source} -. "{label}" .-> {target}'
                     for source, target, label in sorted(exceptions))
        lines += ['```', '']
    return '\n'.join(lines)
