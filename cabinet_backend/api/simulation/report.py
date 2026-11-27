"""Render only completed, verified monthly runs into the French defense report."""
import argparse
import json
from pathlib import Path

NAMES={'normal':'Mois normal','ramadan':'Horaires réduits (variante Ramadan)',
       'mixed':'Pic de demandes et panne machine'}
ROLES={'RECEPTION':'Réception','CAO':'CAO','FAO':'Fabrication','QUALITE':'Qualité'}


def number(value):
    return '—' if value is None else f'{value:,.2f}'.replace(',',' ').replace('.',',')


def render(reports):
    by_key={row['scenario']:row for row in reports}
    if set(by_key)!={'normal','ramadan','mixed'} or len(reports)!=3:
        raise ValueError('Three distinct monthly scenarios are required.')
    for row in reports:
        if (row['days']!=28 or row['tiny'] or row['scope']!='real-api-workflow-and-planning'
                or not row.get('isolation') or row['isolation']['leaks'] or row['isolation']['unauthorized_writes']):
            raise ValueError('Only complete 28-day runs with successful isolation may enter the report.')
    lines=['# Rapport de simulation - Gestion Labo v1.0','',
        '**Données synthétiques — simulation.** Aucun patient réel, aucun appareil connecté, aucun envoi externe.',
        '', '## Périmètre et hypothèses','',
        'Trois laboratoires par exécution, dans le projet Compose cabinet-sim, avec base/Redis/volumes distincts de la démonstration et de la vérification. Les schémas techniques simpetit/simmoyen/simgrand correspondent aux noms SIM-PETIT/MOYEN/GRAND. Le schéma de présentation simlab est refusé. Les trois laboratoires travaillent de façon entrelacée sur la même horloge virtuelle.',
        '', 'Le personnel planifié comporte 2/5/10 techniciens de conception/fabrication plus un réceptionniste et un opérateur qualité distincts : 4/7/12 personnes. Les comptes de supervision, comptabilité et coursier sont des acteurs de contrôle sans profil de capacité supplémentaire.',
        '', 'Demandes synthétiques en lot à 8 h 05 (9 h 05 en horaires réduits), avec alternance des laboratoires ; volume de samedi divisé par deux. Calendrier lundi–vendredi 8 h–18 h, pause 12 h–13 h ; vendredi 12 h–14 h ; samedi 8 h–12 h ; dimanche fermé. Absence collective synthétique le 18 novembre. Variante Ramadan 9 h–15 h, vendredi 12 h–13 h et samedi 9 h–12 h. Ce sont des variantes appliquées aux mêmes dates de novembre, pas une affirmation des dates religieuses ou de congés réels.',
        '', 'Le petit laboratoire utilise le parcours conventionnel ; le modèle ne propose pas de sous-traitance de fraisage. Les autres combinent CFAO, impression 3D et conventionnel selon les routes existantes. Les durées, qualifications, réservations, dépendances, règles d’urgence et gardes viennent du vrai planning. Les cycles machine comprennent explicitement chargement, cycle, fin réelle et déchargement. Aucune physique ni validation clinique réelle n’est simulée.',
        '', 'Mix des services : 80 % J+4, 17 % J+2, 3 % J+1 ; devis J+1 explicite. Contrôles et décisions synthétiques soumis par les vraies commandes : échec d’entrée 4 %, modèle 2 %, modification du design 10 %, qualité 4 %, essayage 2 %. Une occurrence maximale par type/dossier borne les corrections. Pertes laissées vides pour ces corrections sans perte mesurée. Deux tournées de coursier 10 h/16 h, trajet 1 h, réponse/essayage dentiste 4 h et resoumission 1 jour : hypothèses de scénario sans modèle routier.',
        '', 'Les actions empruntent le middleware, les permissions, les sessions Bearer et les routes DRF réels, dans le processus de commande pour partager l’horloge. Les sessions proviennent du service issue_session ; les inspections et approbations sont des actions explicites des acteurs SIM. Aucune mise à jour ORM/SQL n’avance un dossier. L’outbox reste conservée mais la publication/les workers sont exclus ; le PDF de contrôle utilise la tâche existante directement. Voir [l’audit des horloges](SIMULATION_CLOCK_AUDIT.md).',
        '', 'Les trois exécutions utilisent les images figées après l’implémentation 8.2b, avant l’identité PDF et la finition d’interface. Cette isolation conserve exactement la même version du workflow et du planning pour les trois scénarios. Les évolutions 8.4/8.5 disposent de leurs vérifications distinctes dans TEST_RESULTS.md.',
        '', 'Les dates confirmées du scénario sont la date de création + 1/2/4 jours calendaires selon le service, y compris si cette date tombe sur une fermeture ; le planning applique ses vrais calendriers. Ce choix de promesse est une hypothèse de charge, pas un calcul du devis de capacité à la prescription.',
        '', '## Volumes effectivement testés','']
    for key in ['normal','ramadan','mixed']:
        row=by_key[key]
        lines.append(f"- {NAMES[key]} : PETIT 8/jour, MOYEN {'30' if key=='mixed' else '20'}/jour, GRAND {row['grand_daily_cases']}/jour (nominal 60). Samedi : moitié de ces volumes. Graine {row['seed']}, du {row['simulated_start']} au {row['simulated_end']}.")
    lines+=['', 'Le volume GRAND a été réduit pour borner le temps d’exécution et le nombre de tâches en attente. Le probe initial à 60/jour a effectivement créé 88 dossiers sur les trois laboratoires en 261,17 s pour une journée. Ces résultats ne valident donc pas une charge soutenue de 60 dossiers/jour. Les effectifs GRAND restent 10 techniciens + 2 opérateurs distincts.', '', '## Résultats des quatre semaines','']
    for key in ['normal','ramadan','mixed']:
        report=by_key[key]
        lines += [f'### {NAMES[key]}','',
            '| Labo | Effectif total | Créés | Livrés | Clôturés | Non livrés en fin de fenêtre | J+4 à temps | J+2 à temps | J+1 à temps | Médiane h | P90 h |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for profile in ['PETIT','MOYEN','GRAND']:
            data=report['labs'][profile]
            cells=[profile,str(data['staffing']['total_scheduled_staff']),str(data['cases_created']),str(data['cases_delivered']),str(data['cases_closed']),str(data['unfinished_at_horizon'])]
            cells += [number(data['services'][service]['on_time_percent'])+' %' for service in ['STANDARD','EXPRESS','NEXT_DAY']]
            cells += [number(data['lead_time_hours'][field]) for field in ['median','p90']]
            lines.append('| '+' | '.join(cells)+' |')
        lines += ['', '| Labo | Occupation réception / CAO / fabrication / qualité | Reprises | Écart médian h, reprise vs sans reprise |', '| --- | --- | --- | --- |']
        for profile,data in report['labs'].items():
            use=' / '.join(number(row['utilization_percent'])+' %' for row in data['staff_utilization'])
            lines.append(f"| {profile} | {use} | {data['rework_count']} | {number(data['rework_delay_hours']['median_difference'])} |")
        lines += ['', '| Labo | Trois attentes les plus longues (moyenne min) |', '| --- | --- |']
        for profile,data in report['labs'].items():
            text=' ; '.join(f"{item['label']} : {number(item['mean_wait_minutes'])} ({item['still_waiting']} encore en attente)" for item in data['bottlenecks'])
            lines.append(f'| {profile} | {text} |')
        lines+=['','| Labo | Machine | Occupation du temps calendaire |','| --- | --- | --- |']
        for profile,data in report['labs'].items():
            for machine in data['machines']:
                lines.append(f"| {profile} | {machine['name']} | {number(machine['occupancy_percent'])} % |")
        lines+=['']
    lines += ['## Démarrages différés par les gardes','',
        'Un créneau lu peut avoir été déplacé par une commande de planning. Le simulateur conserve le refus, vérifie que l’état source est inchangé, recalcule par le service existant et attend. Il ne force aucun démarrage supervisé. Les premiers diagnostics (horloges et créneaux, sans secrets) figurent dans les JSON.', '',
        '| Exécution | PETIT | MOYEN | GRAND |', '| --- | --- | --- | --- |']
    for key in ['normal','ramadan','mixed']:
        counts=[str(by_key[key]['labs'][profile]['deferred_starts']) for profile in ['PETIT','MOYEN','GRAND']]
        lines.append('| '+NAMES[key]+' | '+' | '.join(counts)+' |')
    lines+=['']
    base=by_key['normal']['labs']['GRAND'];mixed=by_key['mixed']['labs']['GRAND']
    lines += ['## Panne du grand laboratoire','',
        f"Dans la variante mixte, une usineuse est indisponible pendant un jour (deux changements d’état via l’API). Écart observé par rapport au scénario normal : {mixed['cases_delivered']-base['cases_delivered']} dossier(s) livré(s). Les métriques détaillées, occupations et horodatages de panne restent dans les JSON. Cet écart n’est pas une estimation causale contrôlée ; les autres files et le mix synthétique influencent l’attente.",
        '', '## Isolation multi-tenant','',
        '| Exécution | Assertions | Tentatives interdites | Fuites | Écritures non autorisées |', '| --- | --- | --- | --- | --- |']
    for key in ['normal','ramadan','mixed']:
        proof=by_key[key]['isolation']
        lines.append(f"| {NAMES[key]} | {proof['assertions']} | {proof['attack_attempts']} | {proof['leaks']} | {proof['unauthorized_writes']} |")
    lines += ['', 'Les contrôles couvrent les sept rôles labo/coursier : dossiers, file de travail, tâches, charge, facturation/paiements/créances, tableau de bord, fichiers et PDF. Les identifiants étrangers et hôtes d’autres laboratoires renvoient 403/404 ; les comptes de lignes et empreintes des états sources/tâches restent inchangés. Les deux dentistes globaux voient exactement leurs dossiers dans plusieurs laboratoires.',
        '', 'Après la fenêtre de mesure, deux dossiers de contrôle SIM-CACHE sont ajoutés, un dans chacun des deux premiers laboratoires, dans la même minute virtuelle. Les lectures Redis/générations sont vérifiées après leurs écritures entrelacées. L’horloge est ensuite avancée au mois suivant pour clôturer un relevé propre au simulateur, enregistrer un paiement et tester les PDF. Ces dossiers et opérations de contrôle sont explicitement exclus des métriques de charge. Aucun relevé de la démonstration n’est clôturé.',
        '', 'La numérotation réelle est UUID/référence fournie pour les dossiers ; les factures suivent INV-AAAAMM-schéma-préfixeUUIDpériode. Il n’existe pas de compteur séquentiel de facture. Le test vérifie l’unicité, l’appartenance au schéma et l’absence de compteur partagé ; il ne prétend pas à une séquence légale continue.',
        '', '## Lecture des indicateurs et limites','',
        'Les livraisons retenues sont celles de la dernière tentative d’un dossier encore livré/fermé en fin de fenêtre. Les cas jamais terminés ou de nouveau en fabrication restent visibles parmi les non-livrés. Le pourcentage à temps porte sur les livrés du service, comparés à la date confirmée du vrai planning ; il faut le lire avec le nombre de créés/non-livrés. Médiane et P90 (rang supérieur) portent sur création→dernière livraison. Une absence d’observation est affichée —, jamais remplacée par zéro.',
        '', 'Les attentes ouvertes en fin de simulation sont des bornes inférieures censurées, ajoutées aux attentes observées avant démarrage/handoff. Les heures de technicien proviennent du travail enregistré et des vraies fenêtres de disponibilité. L’occupation machine couvre le temps calendaire, y compris les attentes de déchargement : ce n’est pas un taux de coupe/cuisson productive. L’écart de délai entre cohortes avec/sans reprise est descriptif, sans causalité revendiquée.',
        '', '## Ce que la simulation montre / ne montre pas','',
        'Elle apporte une preuve reproductible de cohérence du workflow, des contraintes de capacité, des gardes et des frontières de laboratoire pour ces hypothèses synthétiques. Elle ne valide ni comportement de vrais techniciens, ni qualité clinique, ni physique machine, ni latence réseau, ni expiration virtuelle des QR/TTL Redis, ni une charge soutenue de 60 dossiers/jour. Elle n’est pas un certificat de fonctionnement en laboratoire réel. La prochaine étape est un pilote avec un laboratoire, pour mesurer les durées, calendriers, lots et distributions de demandes avant calibration.',
        '', 'Données brutes : [normal](simulation/normal.json), [horaires réduits](simulation/ramadan.json), [mixte](simulation/mixed.json). Commandes reproductibles : [guide de démonstration](../DEMO_GUIDE.md).', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('reports',nargs=3)
    parser.add_argument('--output',default='docs/SIMULATION_REPORT.md')
    args=parser.parse_args()
    reports=[json.loads(Path(name).read_text(encoding='utf-8')) for name in args.reports]
    Path(args.output).write_text(render(reports),encoding='utf-8')


if __name__=='__main__':
    main()
