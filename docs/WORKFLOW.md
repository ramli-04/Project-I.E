# Parcours métier

Document généré par `python cabinet_backend/manage.py export_workflow` ; ne pas modifier à la main.

Les flèches pleines suivent `workflow_steps` ; les flèches pointillées représentent les commandes d’exception.
Chaque famille réunit les variantes avec/sans validation du design et avec/sans frittage. Ces options ne modifient que les parcours qui les utilisent.
Les libellés, les origines de reprise et les destinations autorisées proviennent de `workflow_spec`. Chaque transition reste soumise aux permissions, preuves et contrôles métier du serveur.

Une reprise exige une origine, une cause, une action corrective et les pertes mesurées (ou une liste vide sans perte). Elle conserve le dossier et crée une nouvelle tentative. Les destinations hors du parcours principal ne créent pas de transition automatique supplémentaire.

Ces diagrammes décrivent les dossiers actuels (`intake_version >= 2`). Les branches historiques, dont `FRITTAGE_9H`, restent prises en charge par le serveur.

## Empreinte physique · CFAO / usinage CNC

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    ATTENTE_RAMASSAGE["Ramassage à organiser"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_MODELE["Contrôle modèle et scan"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    COULEE_PLATRE["Coulée du plâtre"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    EN_ROUTE_LABO["Acheminement vers le labo"]
    ESSAYAGE["Essayage clinique"]
    FINITION["Finition et caractérisation"]
    LIVRE["Livré"]
    PLANIFICATION["Planification et choix technique"]
    PREPARATION_CNC["Préparation FAO / placement et parcours outil"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RECOULER["Reprise de coulée"]
    RESCANNER["Rescanner"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    SCAN_LABO["Scan laboratoire"]
    TRAITEMENT_THERMIQUE["Frittage"]
    USINAGE_CNC["Usinage CNC"]
    VALIDATION_CAO["Validation du design par le dentiste"]
    ANALYSE_DEMANDE --> ATTENTE_RAMASSAGE
    ATTENTE_RAMASSAGE --> EN_ROUTE_LABO
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> COULEE_PLATRE
    CONTROLE_MODELE --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    COULEE_PLATRE --> SCAN_LABO
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    EN_ROUTE_LABO --> A_CONFIRMER
    ESSAYAGE --> CLOTURE
    FINITION --> CONTROLE_QUALITE
    LIVRE --> ESSAYAGE
    PLANIFICATION --> SALLE_CAO
    PREPARATION_CNC --> USINAGE_CNC
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    SALLE_CAO --> PREPARATION_CNC
    SALLE_CAO --> VALIDATION_CAO
    SCAN_LABO --> CONTROLE_MODELE
    TRAITEMENT_THERMIQUE --> FINITION
    USINAGE_CNC --> FINITION
    USINAGE_CNC --> TRAITEMENT_THERMIQUE
    VALIDATION_CAO --> PREPARATION_CNC
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> PREPARATION_CNC
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CLOTURE -. "Reprise documentée" .-> RECOULER
    CLOTURE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_MODELE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_MODELE -. "Reprise documentée" .-> RECOULER
    CONTROLE_MODELE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_QUALITE -. "Reprise documentée" .-> RECOULER
    CONTROLE_QUALITE -. "Reprise documentée" .-> RESCANNER
    COULEE_PLATRE -. "Reprise documentée" .-> A_REFAIRE
    COULEE_PLATRE -. "Reprise documentée" .-> RECOULER
    COULEE_PLATRE -. "Reprise documentée" .-> RESCANNER
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> RECOULER
    ESSAYAGE -. "Reprise documentée" .-> RESCANNER
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> RECOULER
    FINITION -. "Reprise documentée" .-> RESCANNER
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> RECOULER
    LIVRE -. "Reprise documentée" .-> RESCANNER
    PREPARATION_CNC -. "Reprise documentée" .-> A_REFAIRE
    PREPARATION_CNC -. "Reprise documentée" .-> RECOULER
    PREPARATION_CNC -. "Reprise documentée" .-> RESCANNER
    RECOULER -. "Reprendre à cette étape" .-> COULEE_PLATRE
    RESCANNER -. "Reprendre à cette étape" .-> SCAN_LABO
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
    SALLE_CAO -. "Reprise documentée" .-> A_REFAIRE
    SALLE_CAO -. "Reprise documentée" .-> RECOULER
    SALLE_CAO -. "Reprise documentée" .-> RESCANNER
    SCAN_LABO -. "Reprise documentée" .-> A_REFAIRE
    SCAN_LABO -. "Reprise documentée" .-> RECOULER
    SCAN_LABO -. "Reprise documentée" .-> RESCANNER
    TRAITEMENT_THERMIQUE -. "Reprise documentée" .-> A_REFAIRE
    TRAITEMENT_THERMIQUE -. "Reprise documentée" .-> RECOULER
    TRAITEMENT_THERMIQUE -. "Reprise documentée" .-> RESCANNER
    USINAGE_CNC -. "Reprise documentée" .-> A_REFAIRE
    USINAGE_CNC -. "Reprise documentée" .-> RECOULER
    USINAGE_CNC -. "Reprise documentée" .-> RESCANNER
    VALIDATION_CAO -. "Corrections demandées par le dentiste" .-> SALLE_CAO
```

## Empreinte physique · Impression 3D

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    ATTENTE_RAMASSAGE["Ramassage à organiser"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_MODELE["Contrôle modèle et scan"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    COULEE_PLATRE["Coulée du plâtre"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    EN_ROUTE_LABO["Acheminement vers le labo"]
    ESSAYAGE["Essayage clinique"]
    FINITION["Finition et caractérisation"]
    IMPRESSION_3D["Impression 3D"]
    LAVAGE_SECHAGE["Lavage et séchage"]
    LIVRE["Livré"]
    PLANIFICATION["Planification et choix technique"]
    POST_POLYMERISATION["Post-polymérisation"]
    PREPARATION_3D["Orientation, supports et préparation du plateau"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RECOULER["Reprise de coulée"]
    RESCANNER["Rescanner"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    SCAN_LABO["Scan laboratoire"]
    VALIDATION_CAO["Validation du design par le dentiste"]
    ANALYSE_DEMANDE --> ATTENTE_RAMASSAGE
    ATTENTE_RAMASSAGE --> EN_ROUTE_LABO
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> COULEE_PLATRE
    CONTROLE_MODELE --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    COULEE_PLATRE --> SCAN_LABO
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    EN_ROUTE_LABO --> A_CONFIRMER
    ESSAYAGE --> CLOTURE
    FINITION --> CONTROLE_QUALITE
    IMPRESSION_3D --> LAVAGE_SECHAGE
    LAVAGE_SECHAGE --> POST_POLYMERISATION
    LIVRE --> ESSAYAGE
    PLANIFICATION --> SALLE_CAO
    POST_POLYMERISATION --> FINITION
    PREPARATION_3D --> IMPRESSION_3D
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    SALLE_CAO --> PREPARATION_3D
    SALLE_CAO --> VALIDATION_CAO
    SCAN_LABO --> CONTROLE_MODELE
    VALIDATION_CAO --> PREPARATION_3D
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> PREPARATION_3D
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CLOTURE -. "Reprise documentée" .-> RECOULER
    CLOTURE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_MODELE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_MODELE -. "Reprise documentée" .-> RECOULER
    CONTROLE_MODELE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_QUALITE -. "Reprise documentée" .-> RECOULER
    CONTROLE_QUALITE -. "Reprise documentée" .-> RESCANNER
    COULEE_PLATRE -. "Reprise documentée" .-> A_REFAIRE
    COULEE_PLATRE -. "Reprise documentée" .-> RECOULER
    COULEE_PLATRE -. "Reprise documentée" .-> RESCANNER
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> RECOULER
    ESSAYAGE -. "Reprise documentée" .-> RESCANNER
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> RECOULER
    FINITION -. "Reprise documentée" .-> RESCANNER
    IMPRESSION_3D -. "Reprise documentée" .-> A_REFAIRE
    IMPRESSION_3D -. "Reprise documentée" .-> RECOULER
    IMPRESSION_3D -. "Reprise documentée" .-> RESCANNER
    LAVAGE_SECHAGE -. "Reprise documentée" .-> A_REFAIRE
    LAVAGE_SECHAGE -. "Reprise documentée" .-> RECOULER
    LAVAGE_SECHAGE -. "Reprise documentée" .-> RESCANNER
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> RECOULER
    LIVRE -. "Reprise documentée" .-> RESCANNER
    POST_POLYMERISATION -. "Reprise documentée" .-> A_REFAIRE
    POST_POLYMERISATION -. "Reprise documentée" .-> RECOULER
    POST_POLYMERISATION -. "Reprise documentée" .-> RESCANNER
    PREPARATION_3D -. "Reprise documentée" .-> A_REFAIRE
    PREPARATION_3D -. "Reprise documentée" .-> RECOULER
    PREPARATION_3D -. "Reprise documentée" .-> RESCANNER
    RECOULER -. "Reprendre à cette étape" .-> COULEE_PLATRE
    RESCANNER -. "Reprendre à cette étape" .-> SCAN_LABO
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
    SALLE_CAO -. "Reprise documentée" .-> A_REFAIRE
    SALLE_CAO -. "Reprise documentée" .-> RECOULER
    SALLE_CAO -. "Reprise documentée" .-> RESCANNER
    SCAN_LABO -. "Reprise documentée" .-> A_REFAIRE
    SCAN_LABO -. "Reprise documentée" .-> RECOULER
    SCAN_LABO -. "Reprise documentée" .-> RESCANNER
    VALIDATION_CAO -. "Corrections demandées par le dentiste" .-> SALLE_CAO
```

## Empreinte physique · Fabrication conventionnelle

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    ATTENTE_RAMASSAGE["Ramassage à organiser"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_MODELE["Contrôle modèle et scan"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    COULEE_PLATRE["Coulée du plâtre"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    EN_ROUTE_LABO["Acheminement vers le labo"]
    ESSAYAGE["Essayage clinique"]
    FABRICATION_MANUELLE["Fabrication conventionnelle"]
    FINITION["Finition et caractérisation"]
    LIVRE["Livré"]
    MODELAGE["Modelage / maquette"]
    MODELE_TRAVAIL["Préparation du modèle de travail"]
    PLANIFICATION["Planification et choix technique"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RECOULER["Reprise de coulée"]
    RESCANNER["Rescanner"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    SCAN_LABO["Scan laboratoire"]
    ANALYSE_DEMANDE --> ATTENTE_RAMASSAGE
    ATTENTE_RAMASSAGE --> EN_ROUTE_LABO
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> COULEE_PLATRE
    CONTROLE_MODELE --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    COULEE_PLATRE --> SCAN_LABO
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    EN_ROUTE_LABO --> A_CONFIRMER
    ESSAYAGE --> CLOTURE
    FABRICATION_MANUELLE --> FINITION
    FINITION --> CONTROLE_QUALITE
    LIVRE --> ESSAYAGE
    MODELAGE --> FABRICATION_MANUELLE
    MODELE_TRAVAIL --> MODELAGE
    PLANIFICATION --> MODELE_TRAVAIL
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    SCAN_LABO --> CONTROLE_MODELE
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> MODELAGE
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CLOTURE -. "Reprise documentée" .-> RECOULER
    CLOTURE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_MODELE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_MODELE -. "Reprise documentée" .-> RECOULER
    CONTROLE_MODELE -. "Reprise documentée" .-> RESCANNER
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_QUALITE -. "Reprise documentée" .-> RECOULER
    CONTROLE_QUALITE -. "Reprise documentée" .-> RESCANNER
    COULEE_PLATRE -. "Reprise documentée" .-> A_REFAIRE
    COULEE_PLATRE -. "Reprise documentée" .-> RECOULER
    COULEE_PLATRE -. "Reprise documentée" .-> RESCANNER
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> RECOULER
    ESSAYAGE -. "Reprise documentée" .-> RESCANNER
    FABRICATION_MANUELLE -. "Reprise documentée" .-> A_REFAIRE
    FABRICATION_MANUELLE -. "Reprise documentée" .-> RECOULER
    FABRICATION_MANUELLE -. "Reprise documentée" .-> RESCANNER
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> RECOULER
    FINITION -. "Reprise documentée" .-> RESCANNER
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> RECOULER
    LIVRE -. "Reprise documentée" .-> RESCANNER
    MODELAGE -. "Reprise documentée" .-> A_REFAIRE
    MODELAGE -. "Reprise documentée" .-> RECOULER
    MODELAGE -. "Reprise documentée" .-> RESCANNER
    MODELE_TRAVAIL -. "Reprise documentée" .-> A_REFAIRE
    MODELE_TRAVAIL -. "Reprise documentée" .-> RECOULER
    MODELE_TRAVAIL -. "Reprise documentée" .-> RESCANNER
    RECOULER -. "Reprendre à cette étape" .-> COULEE_PLATRE
    RESCANNER -. "Reprendre à cette étape" .-> SCAN_LABO
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
    SCAN_LABO -. "Reprise documentée" .-> A_REFAIRE
    SCAN_LABO -. "Reprise documentée" .-> RECOULER
    SCAN_LABO -. "Reprise documentée" .-> RESCANNER
```

## Empreinte numérique · CFAO / usinage CNC

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    ESSAYAGE["Essayage clinique"]
    FINITION["Finition et caractérisation"]
    LIVRE["Livré"]
    PLANIFICATION["Planification et choix technique"]
    PREPARATION_CNC["Préparation FAO / placement et parcours outil"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    TRAITEMENT_THERMIQUE["Frittage"]
    USINAGE_CNC["Usinage CNC"]
    VALIDATION_CAO["Validation du design par le dentiste"]
    ANALYSE_DEMANDE --> A_CONFIRMER
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    ESSAYAGE --> CLOTURE
    FINITION --> CONTROLE_QUALITE
    LIVRE --> ESSAYAGE
    PLANIFICATION --> SALLE_CAO
    PREPARATION_CNC --> USINAGE_CNC
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    SALLE_CAO --> PREPARATION_CNC
    SALLE_CAO --> VALIDATION_CAO
    TRAITEMENT_THERMIQUE --> FINITION
    USINAGE_CNC --> FINITION
    USINAGE_CNC --> TRAITEMENT_THERMIQUE
    VALIDATION_CAO --> PREPARATION_CNC
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> PREPARATION_CNC
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    PREPARATION_CNC -. "Reprise documentée" .-> A_REFAIRE
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
    SALLE_CAO -. "Reprise documentée" .-> A_REFAIRE
    TRAITEMENT_THERMIQUE -. "Reprise documentée" .-> A_REFAIRE
    USINAGE_CNC -. "Reprise documentée" .-> A_REFAIRE
    VALIDATION_CAO -. "Corrections demandées par le dentiste" .-> SALLE_CAO
```

## Empreinte numérique · Impression 3D

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    ESSAYAGE["Essayage clinique"]
    FINITION["Finition et caractérisation"]
    IMPRESSION_3D["Impression 3D"]
    LAVAGE_SECHAGE["Lavage et séchage"]
    LIVRE["Livré"]
    PLANIFICATION["Planification et choix technique"]
    POST_POLYMERISATION["Post-polymérisation"]
    PREPARATION_3D["Orientation, supports et préparation du plateau"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    VALIDATION_CAO["Validation du design par le dentiste"]
    ANALYSE_DEMANDE --> A_CONFIRMER
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    ESSAYAGE --> CLOTURE
    FINITION --> CONTROLE_QUALITE
    IMPRESSION_3D --> LAVAGE_SECHAGE
    LAVAGE_SECHAGE --> POST_POLYMERISATION
    LIVRE --> ESSAYAGE
    PLANIFICATION --> SALLE_CAO
    POST_POLYMERISATION --> FINITION
    PREPARATION_3D --> IMPRESSION_3D
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    SALLE_CAO --> PREPARATION_3D
    SALLE_CAO --> VALIDATION_CAO
    VALIDATION_CAO --> PREPARATION_3D
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> PREPARATION_3D
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    IMPRESSION_3D -. "Reprise documentée" .-> A_REFAIRE
    LAVAGE_SECHAGE -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    POST_POLYMERISATION -. "Reprise documentée" .-> A_REFAIRE
    PREPARATION_3D -. "Reprise documentée" .-> A_REFAIRE
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
    SALLE_CAO -. "Reprise documentée" .-> A_REFAIRE
    VALIDATION_CAO -. "Corrections demandées par le dentiste" .-> SALLE_CAO
```

## Empreinte numérique · Fabrication conventionnelle

```mermaid
flowchart TD
    ANALYSE_DEMANDE["Analyse de la demande"]
    A_CONFIRMER["Réception au laboratoire"]
    A_REFAIRE["Reprise de fabrication"]
    CLOTURE["Essayage validé"]
    CONDITIONNEMENT["Conditionnement et documents"]
    CONTROLE_DOSSIER["Contrôle du dossier et des empreintes"]
    CONTROLE_QUALITE["Contrôle qualité final"]
    DEMANDE_RECUE["Demande reçue / acceptation"]
    EN_ROUTE_CABINET["Livraison au cabinet"]
    ESSAYAGE["Essayage clinique"]
    FABRICATION_MANUELLE["Fabrication conventionnelle"]
    FINITION["Finition et caractérisation"]
    LIVRE["Livré"]
    MODELAGE["Modelage / maquette"]
    MODELE_TRAVAIL["Préparation du modèle de travail"]
    PLANIFICATION["Planification et choix technique"]
    PRET_EXPEDITION["Prêt pour expédition"]
    RETOUR_DEMANDE["Retour demandé"]
    SALLE_CAO["Conception numérique / CAO"]
    ANALYSE_DEMANDE --> A_CONFIRMER
    A_CONFIRMER --> CONTROLE_DOSSIER
    CONDITIONNEMENT --> PRET_EXPEDITION
    CONTROLE_DOSSIER --> PLANIFICATION
    CONTROLE_QUALITE --> CONDITIONNEMENT
    DEMANDE_RECUE --> ANALYSE_DEMANDE
    EN_ROUTE_CABINET --> LIVRE
    ESSAYAGE --> CLOTURE
    FABRICATION_MANUELLE --> FINITION
    FINITION --> CONTROLE_QUALITE
    LIVRE --> ESSAYAGE
    MODELAGE --> FABRICATION_MANUELLE
    MODELE_TRAVAIL --> MODELAGE
    PLANIFICATION --> MODELE_TRAVAIL
    PRET_EXPEDITION --> EN_ROUTE_CABINET
    A_CONFIRMER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    A_REFAIRE -. "Reprendre à cette étape" .-> FINITION
    A_REFAIRE -. "Reprendre à cette étape" .-> MODELAGE
    A_REFAIRE -. "Reprendre à cette étape" .-> SALLE_CAO
    CLOTURE -. "Reprise documentée" .-> A_REFAIRE
    CONTROLE_DOSSIER -. "Contrôle d’entrée non conforme" .-> RETOUR_DEMANDE
    CONTROLE_QUALITE -. "Reprise documentée" .-> A_REFAIRE
    ESSAYAGE -. "Reprise documentée" .-> A_REFAIRE
    FABRICATION_MANUELLE -. "Reprise documentée" .-> A_REFAIRE
    FINITION -. "Reprise documentée" .-> A_REFAIRE
    LIVRE -. "Reprise documentée" .-> A_REFAIRE
    MODELAGE -. "Reprise documentée" .-> A_REFAIRE
    MODELE_TRAVAIL -. "Reprise documentée" .-> A_REFAIRE
    RETOUR_DEMANDE -. "Dossier corrigé et soumis à nouveau" .-> A_CONFIRMER
```
