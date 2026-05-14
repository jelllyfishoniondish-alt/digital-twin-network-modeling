# Jumeaux Numeriques pour la Modelisation de Reseaux : Approches et Experimentations

**Rapport TER — Semestre de Printemps 2026**

**Encadrant** : Guillaume Beduneau (guillaume.beduneau@univ-evry.fr)

---

## Table des matieres

1. [Resume](#1-resume)
2. [Introduction](#2-introduction)
3. [Conception et architecture du systeme](#3-conception-et-architecture-du-systeme)
4. [Proposition d'implementation](#4-proposition-dimplementation)
5. [Protocole de tests et conception experimentale](#5-protocole-de-tests-et-conception-experimentale)
6. [Resultats experimentaux et analyse](#6-resultats-experimentaux-et-analyse)
7. [Discussion et limitations](#7-discussion-et-limitations)
8. [Conclusion et perspectives](#8-conclusion-et-perspectives)
9. [Annexes](#9-annexes)

---

## 1. Resume

Ce projet realise et valide un prototype de jumeau numerique (digital twin) dedie aux reseaux informatiques. Le systeme repose sur l'emulateur reseau Mininet et le controleur SDN Ryu, et maintient une replique structuree de l'etat du reseau au moyen de deux mecanismes de synchronisation : le polling periodique et la notification evenementielle.

Le systeme prend en charge trois modes de synchronisation (polling, evenementiel, hybride) et detecte en temps reel les changements d'etat : pannes et retablissements de liens, apparitions et disparitions de commutateurs, et migrations d'hotes. Il offre egalement une evaluation quantitative de la fidelite ainsi qu'un module de detection d'anomalies de trafic.

Les experiences ont ete menees sur des topologies allant de 3 noeuds (topologie minimale) a environ 40 noeuds (topologie GEANT reelle), couvrant des scenarios de panne simple, de retablissement, de pannes multiples, de battement de lien et de degradation de l'observabilite.

**Resultats cles** : avec un intervalle de polling de 2 secondes, le delai de detection des pannes se situe entre 0.2 et 1.6 seconde ; le mode evenementiel reduit la duree du cycle de synchronisation d'environ 60 ms a environ 2 ms ; le systeme reste stable sous differentes charges de trafic, tailles de topologie et strategies de controle.

---

## 2. Introduction

### 2.1 Contexte

Dans le domaine de l'exploitation et de la gestion des reseaux, les operateurs s'appuient traditionnellement sur des outils de supervision classiques (SNMP, Nagios, Zabbix) pour observer l'etat du reseau. Ces outils fonctionnent generalement par collecte independante de metriques et ne disposent pas d'une capacite de modelisation structuree de l'etat global du reseau.

Le concept de **jumeau numerique** (digital twin), initialement propose par Michael Grieves en 2002 dans le cadre de la gestion du cycle de vie des produits, puis popularise par la NASA dans le domaine aerospatial, est de plus en plus applique aux reseaux grace a l'essor du SDN (Software-Defined Networking) et du NFV (Network Functions Virtualization). Il permet une perception plus fine de l'etat du reseau, la prediction de pannes et l'automatisation de l'exploitation.

### 2.2 Problematique

Ce projet s'articule autour de trois questions de recherche fondamentales :

1. **Comment modeliser fidelement un reseau physique sous forme de jumeau numerique ?** — Comment definir un modele de donnees d'etat reseau a la fois complet et calculable ?
2. **Quelles sont les approches existantes pour relier le jumeau numerique avec son homologue physique ?** — Quels mecanismes de synchronisation permettent de maintenir la coherence entre le jumeau et le reseau reel ?
3. **Quels sont les defis specifiques a la gemellisation des reseaux ?** — Par rapport a d'autres domaines, quelles difficultes specifiques la gemellisation des reseaux pose-t-elle ?

### 2.3 Objectifs du projet

- Identifier les caracteristiques d'interet des jumeaux numeriques pour les reseaux
- Proposer et implementer une preuve de concept (PoC) sur un reseau simple
- Evaluer les performances et les limitations de l'approche selectionnee au moyen d'experiences systematiques

---

## 3. Conception et architecture du systeme

### 3.1 Architecture globale

Le systeme adopte une architecture en quatre couches, chacune ayant des responsabilites clairement delimitees :

![Diagramme d'architecture](../data/plots/report/architecture.png)

*Figure 1 : Architecture en quatre couches du systeme. De l'emulation reseau en bas a la visualisation et l'experimentation en haut, les couches sont decouplees par des interfaces bien definies.*

| Couche | Nom | Composants principaux | Responsabilite |
|--------|-----|----------------------|----------------|
| Couche 1 | Emulation reseau | Mininet, Open vSwitch | Simuler la topologie physique, injecter des pannes |
| Couche 2 | Observation SDN | Controleur Ryu, RyuAPIClient | Collecter les donnees d'etat du reseau |
| Couche 3 | Noyau du jumeau | SyncEngine, DiffEngine, EventEngine | Synchronisation d'etat, detection de differences, generation d'evenements |
| Couche 4 | Presentation et experimentation | API Flask, Visualisation, ExperimentRunner | Services API, visualisation, orchestration d'experiences |

### 3.2 Flux de donnees

![Diagramme de flux de donnees](../data/plots/report/data_flow.png)

*Figure 2 : Flux de donnees. Le chemin de gauche correspond au mode polling (appels REST periodiques), le chemin de droite au mode evenementiel (file d'evenements du controleur). Les deux chemins convergent vers la construction du NetworkState.*

Le parcours des donnees a travers le systeme est le suivant :

```
Mininet / OVS (evenements reseau)
    |
    v
Controleur Ryu (API REST / File d'evenements)
    |
    +--- [Polling] ---> SyncEngine ---> NetworkState
    |
    +--- [Evenements] ---> EventSyncEngine ---> NetworkState
                                |
                                v
                           DiffEngine (comparaison ancien/nouveau snapshot)
                                |
                                v
                           EventEngine (generation d'evenements structures)
                                |
                           +----+----+
                           |         |
                           v         v
                        Stockage   Fidelite / Anomalies
                       (JSONL)    (metriques de qualite)
```

### 3.3 Modele d'etat

Le modele de donnees central de l'etat reseau est compose des structures suivantes :

```
NetworkState
  +-- timestamp: str                 # Horodatage ISO 8601
  +-- switches: list[SwitchState]    # Liste des commutateurs
  |     +-- dpid: str                # Identifiant du datapath
  |     +-- name: str                # Nom lisible
  |     +-- city / country / lat / lon   # Metadonnees geographiques
  |     +-- ports: list[PortState]   # Liste des ports
  |     |     +-- port_no: int
  |     |     +-- rx/tx_packets/bytes
  |     |     +-- is_up: bool
  |     +-- flow_count: int          # Nombre d'entrees de flux
  +-- links: list[LinkState]         # Liste des liens
  |     +-- src_dpid, dst_dpid       # Commutateurs source/destination
  |     +-- src_port, dst_port       # Ports source/destination
  |     +-- is_up: bool              # Etat du lien
  |     +-- latency_ms: float        # Latence
  |     +-- bandwidth_mbps: int      # Bande passante
  +-- hosts: list[HostState]         # Liste des hotes
        +-- name, ip, mac
        +-- attached_switch, attached_port
```

**Choix de conception** : tous les modeles sont implementes avec le `dataclass(slots=True)` de Python, garantissant a la fois la surete des types et l'optimisation memoire via `slots`. Chaque modele dispose d'une methode `to_dict()` pour la serialisation JSON.

### 3.4 Mecanismes de synchronisation

#### 3.4.1 Mode polling

```
tant que non arrete:
    payload = ryu_client.collect_state_payload()  # Appels API REST
    nouvel_etat = build_network_state(payload)
    changements = diff_engine.diff(ancien_etat, nouvel_etat)
    evenements = event_engine.build_events(changements)
    stocker(nouvel_etat, evenements)
    attendre(intervalle_polling)
```

- **Avantages** : implementation simple, comportement previsible, consommation de ressources constante
- **Inconvenients** : delai de detection borne par l'intervalle de polling, gaspillage d'appels API en periode d'inactivite

#### 3.4.2 Mode evenementiel (Event-Driven)

```
tant que non arrete:
    evenement = file_evenements.get(timeout=delai_attente)
    si evenement:
        attendre_stabilisation_et_synchroniser()
    sinon:
        # Timeout sans evenement, possibilite de polling de secours
```

- **Avantages** : delai de detection tres faible (de l'ordre de la milliseconde), zero appels API en periode d'inactivite
- **Inconvenients** : depend de la fiabilite de la livraison des evenements, risque de perte d'evenements

#### 3.4.3 Mode hybride

Combine les avantages des deux modes : les evenements comme mecanisme principal, avec un polling periodique a faible frequence (par exemple toutes les 10 secondes) comme filet de securite, garantissant que meme en cas de perte d'evenement, l'etat sera corrige dans un delai borne.

### 3.5 Detection des differences et generation d'evenements

Le DiffEngine compare deux snapshots `NetworkState` et identifie les types de changements suivants :

| Type de changement | Condition de detection | Evenement genere |
|--------------------|----------------------|------------------|
| Lien tombe | `is_up: True -> False` | `LINK_DOWN` |
| Lien retabli | `is_up: False -> True` | `LINK_UP` |
| Commutateur disparu | Present dans l'ancien etat, absent du nouveau | `SWITCH_DOWN` |
| Commutateur apparu | Absent de l'ancien etat, present dans le nouveau | `SWITCH_UP` |
| Hote rejoint | Nouvelle adresse MAC detectee | `HOST_JOIN` |
| Hote parti | Adresse MAC disparue | `HOST_LEAVE` |
| Hote migre | Changement de `attached_switch` pour une meme MAC | `HOST_MIGRATE` |
| Variation importante du nombre de flux | Variation du `flow_count` > 50 % | Enregistre sans generation d'evenement |
| Echec d'appel API | Exception lors de la requete REST | `SYNC_ERROR` |

### 3.6 Metriques de fidelite

Afin de quantifier le degre de coherence entre le jumeau et le reseau reel, le systeme implemente les metriques suivantes :

| Metrique | Methode de calcul | Poids |
|----------|-------------------|-------|
| **topology_accuracy** | Similarite de Jaccard des ensembles de commutateurs et de liens | 30 % |
| **link_state_accuracy** | Proportion de liens dont l'etat `is_up` est coherent | 50 % |
| **port_counter_drift** | Ecart en pourcentage moyen des compteurs de ports | 20 % |
| **state_staleness_ms** | Temps actuel - dernier horodatage de synchronisation | Metrique auxiliaire |

**Fidelite globale** = 0.3 x topology_accuracy + 0.5 x link_state_accuracy + 0.2 x counter_score

### 3.7 Detection d'anomalies de trafic

Un mecanisme de detection d'anomalies base sur des statistiques a fenetre glissante :

- Maintient une fenetre de longueur N (10 par defaut) enregistrant l'increment d'octets de chaque port a chaque cycle
- Calcule la moyenne (mu) et l'ecart-type (sigma) dans la fenetre
- Regles de determination des anomalies :

| Type d'alerte | Condition de declenchement | Severite |
|---------------|---------------------------|----------|
| `TRAFFIC_SPIKE` | Increment actuel > mu + 2 sigma | warning |
| `TRAFFIC_SPIKE` | Increment actuel > mu + 3 sigma | critical |
| `TRAFFIC_DROP` | Increment actuel < mu - 2 sigma | warning |
| `COUNTER_STALL` | Increment = 0 et mu > 100 octets | warning |

---

## 4. Proposition d'implementation

### 4.1 Choix technologiques

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Emulation reseau | Mininet + Open vSwitch | Outils d'emulation de reference pour le SDN, support OpenFlow |
| Controleur SDN | Ryu | Controleur leger en Python, API REST completes |
| Langage | Python 3.10+ | Coherent avec l'ecosysteme Ryu/Mininet, haute productivite |
| Framework web | Flask | Leger, adapte au PoC |
| Visualisation | vis-network (CDN) + matplotlib | Zero dependance de build cote client, graphiques automatises cote serveur |
| Stockage | Fichiers JSON / JSONL | Pas de base de donnees requise, facilite le debogage et la citation dans le rapport |
| Tests | pytest | Framework de test standard en Python |

**Pourquoi ces choix plutot que d'autres ?**

- **Pourquoi pas une base de donnees (SQLite) ?** — Le projet est un PoC de recherche. Les fichiers JSON/JSONL sont directement inspectables avec un editeur de texte, ce qui facilite le debogage et la citation dans le rapport. Un systeme en production devrait envisager une base de donnees temporelle.
- **Pourquoi pas ONOS a la place de Ryu ?** — Ryu est ecrit en Python, coherent avec le reste du projet, et suffisant pour l'echelle du PoC. ONOS serait plus adapte a un deploiement a grande echelle.
- **Pourquoi pas une file de messages (Kafka) ?** — Le `queue.Queue` de Python suffit pour la communication intra-processus du PoC, sans introduire de dependances externes.

### 4.2 Structure du projet

```
twin/
+-- src/
|   +-- controller/             # Modules lies au controleur SDN
|   |   +-- ryu_api_client.py          # Client REST Ryu
|   |   +-- event_queue.py             # File d'evenements (mode evenementiel)
|   |   +-- topology_aware_switch.py   # Application de commutation avec conscience de topologie
|   |   +-- tree_routing_switch.py     # Application de routage arborescent (comparaison)
|   +-- topology/               # Gestion de la topologie
|   |   +-- minimal_topology.py        # Topologie minimale a 3 noeuds
|   |   +-- data_driven_topology.py    # Topologie pilotee par les donnees
|   |   +-- topology_loader.py         # Chargeur de topologie
|   |   +-- importers/                 # Importeurs GraphML/GML
|   +-- twin/                   # Noyau du jumeau
|   |   +-- models.py                  # Modeles de donnees d'etat
|   |   +-- sync_engine.py             # Moteur de synchronisation par polling
|   |   +-- event_sync_engine.py       # Moteur de synchronisation evenementiel
|   |   +-- diff_engine.py             # Moteur de detection des differences
|   |   +-- event_engine.py            # Moteur de generation d'evenements
|   |   +-- fidelity.py                # Metriques de fidelite
|   |   +-- anomaly_detector.py        # Detection d'anomalies
|   |   +-- storage.py                 # Stockage (JSON/JSONL)
|   |   +-- service.py                 # Couche d'orchestration de services
|   |   +-- config.py                  # Configuration centralisee
|   |   +-- experiment_runner.py       # Executeur d'experiences
|   |   +-- plotting.py                # Generation de graphiques
|   |   +-- scalability_experiment.py  # Experience de scalabilite
|   |   +-- sync_mode_comparison.py    # Experience de comparaison des modes de synchronisation
|   +-- web/                    # Presentation web
|       +-- app.py                     # API Flask
|       +-- templates/
|           +-- index.html             # Page d'accueil
|           +-- topology.html          # Page de visualisation de la topologie
+-- tests/                      # Tests unitaires (22 fichiers de test)
+-- scripts/                    # Scripts d'automatisation des experiences
+-- data/
|   +-- topologies/             # Fichiers de definition de topologie
|   +-- events/                 # Journaux d'evenements
|   +-- snapshots/              # Snapshots d'etat
|   +-- exports/                # Resultats d'experience (CSV/JSON)
|   +-- plots/                  # Graphiques de sortie
+-- scenarios/                  # Definitions de scenarios d'experience
```

### 4.3 Modelisation de la topologie

Le systeme prend en charge des topologies de complexite croissante :

![Topologie GEANT 8 villes](../data/plots/report/topology_geant8.png)

*Figure 3 : Topologie du reseau dorsal europeen GEANT a 8 villes (Stage 3). Elle comprend 8 noeuds urbains et 10 liens dorsaux, construite a partir des donnees reelles du reseau de recherche GEANT.*

| Topologie | Noeuds | Liens | Source | Utilisation |
|-----------|--------|-------|--------|-------------|
| minimal | 3 | 2 | Definie manuellement | Validation rapide |
| geant_subset | 6 | 5 | Sous-ensemble GEANT | Tests de base |
| geant_backbone_8cities | 8 | 10 | Dorsale GEANT | **Ligne de base experimentale principale** |
| geant2012_core12 | 12 | 15 | Topology Zoo | Comparaison inter-topologies |
| geant2012_full | ~40 | ~60 | Topology Zoo | Tests de scalabilite |

### 4.4 Parametres de configuration

Toute la configuration est injectee par variables d'environnement et centralisee dans `AppConfig` :

| Parametre | Valeur par defaut | Description |
|-----------|-------------------|-------------|
| `SYNC_MODE` | `polling` | Mode de synchronisation : polling / event_driven / hybrid |
| `POLL_INTERVAL_SECONDS` | `2` | Intervalle de polling (secondes) |
| `HYBRID_POLL_INTERVAL_SECONDS` | `10` | Intervalle de polling de secours en mode hybride |
| `EVENT_QUEUE_WAIT_SECONDS` | `0.5` | Timeout d'attente de la file d'evenements |
| `EVENT_SETTLE_TIMEOUT_SECONDS` | `1.0` | Temps d'attente de stabilisation apres evenement |
| `SCENARIO_TIMEOUT_SECONDS` | `20` | Timeout du scenario d'experience |
| `RYU_BASE_URL` | `http://127.0.0.1:8080` | Adresse de l'API REST Ryu |

### 4.5 API Web et visualisation

Flask expose les points de terminaison suivants :

| Point de terminaison | Methode | Contenu retourne |
|---------------------|---------|------------------|
| `/api/health` | GET | Etat de sante du service |
| `/api/state` | GET | Etat complet du jumeau |
| `/api/topology` | GET | Vue topologique (commutateurs, liens, hotes) |
| `/api/events?limit=N` | GET | N derniers evenements |
| `/api/fidelity` | GET | Rapport de fidelite |
| `/api/anomalies?limit=N` | GET | N dernieres alertes d'anomalie |
| `/topology` | GET | Page de visualisation interactive de la topologie |

La page de visualisation de la topologie utilise la bibliotheque vis-network pour dessiner un graphe reseau interactif :
- Les noeuds representent les commutateurs, etiquetes par le nom de la ville
- La couleur des liens reflete l'etat en temps reel : **vert = operationnel**, **rouge = en panne**
- Rafraichissement automatique toutes les 3 secondes
- Support du positionnement par coordonnees geographiques
- Panneau lateral affichant les evenements recents

---

## 5. Protocole de tests et conception experimentale

### 5.1 Definition de la ligne de base experimentale

Afin de garantir la comparabilite des resultats, la ligne de base immutable suivante est definie :

| Dimension | Valeur de reference |
|-----------|---------------------|
| **Topologie** | `geant_backbone_8cities_stage3` (8 villes, 10 liens) |
| **Controleur** | `topology_aware_switch` (commutation par plus court chemin) |
| **Intervalle de polling** | 2.0 secondes |
| **Nombre de repetitions** | 3 par scenario |

### 5.2 Scenarios d'experience

#### Scenario 1 : Detection de retablissement (Recovery Scenario)

```
[0s]  Demarrage du reseau, etablissement de l'etat de reference
[2s]  Injection de panne : link s1 s2 down
[?s]  Le jumeau detecte LINK_DOWN (mesure du delai de detection)
[+2s] Retablissement du lien : link s1 s2 up
[?s]  Le jumeau detecte LINK_UP (mesure du delai de retablissement)
```

**Objectif de validation** : le delai de detection doit etre inferieur a l'intervalle de polling ; la detection du retablissement doit fonctionner correctement.

#### Scenario 2 : Battement de lien (Link Flap Scenario)

```
[0s]  Demarrage du reseau
[2s]  link down -> [+2s] link up -> [+2s] link down -> [+2s] link up
```

**Objectif de validation** : le jumeau doit suivre correctement les changements d'etat rapides, sans omission ni faux positif.

#### Scenario 3 : Pannes multiples (Multi-Fault Scenario)

```
[0s]  Demarrage du reseau
[2s]  link s1-s2 down
[+1s] link s2-s3 down
```

**Objectif de validation** : les deux pannes doivent etre detectees ; l'ordre des evenements doit etre correct.

#### Scenario 4 : Degradation de l'observabilite (Observation Degradation)

Simulation de l'indisponibilite de l'API REST Ryu pour verifier la tolerance aux pannes du systeme.

**Objectif de validation** : generation d'evenements `SYNC_ERROR` plutot que de faux `LINK_DOWN` ; reprise automatique de la synchronisation apres retablissement de l'API.

### 5.3 Variables experimentales

A partir de la ligne de base, les variables suivantes sont modifiees une a une pour des experiences comparatives :

| Dimension experimentale | Valeurs | Objectif |
|------------------------|---------|----------|
| **Charge de trafic** | none / icmp / iperf_tcp | Evaluer l'impact de la charge sur le delai de detection |
| **Intervalle de polling** | 1s / 2s / 4s | Evaluer la relation entre frequence de polling et delai |
| **Taille de la topologie** | 3 / 6 / 8 / 12 / 40 noeuds | Evaluer la scalabilite |
| **Strategie de controle** | topology_aware / tree_routing | Evaluer l'impact de la strategie du plan de controle |
| **Mode de synchronisation** | polling / event_driven / hybrid | Comparer les mecanismes de synchronisation |

### 5.4 Indicateurs de mesure

| Indicateur | Definition | Unite |
|------------|-----------|-------|
| **detection_delay** | Intervalle entre l'injection de la panne et la detection de LINK_DOWN par le jumeau | secondes |
| **recovery_delay** | Intervalle entre le retablissement du lien et la detection de LINK_UP par le jumeau | secondes |
| **sync_duration_ms** | Duree d'execution d'un cycle sync_once() | millisecondes |
| **api_call_count** | Nombre d'appels API REST effectues par cycle de synchronisation | nombre |
| **fidelity** | Score de fidelite globale | 0.0 - 1.0 |
| **false_positive_rate** | Nombre d'evenements faux positifs / nombre total d'evenements | ratio |

### 5.5 Execution des experiences

```bash
# Matrice d'experience principale (3 scenarios x 3 profils de trafic x 3 repetitions = 27 experiences)
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
     REPEAT=3 bash scripts/run_experiment_matrix.sh

# Experience de sensibilite au polling
sudo bash scripts/run_polling_comparison.sh

# Experience de comparaison des modes de synchronisation
bash scripts/run_sync_mode_comparison.sh

# Experience de scalabilite
bash scripts/run_scalability_experiment.sh
```

---

## 6. Resultats experimentaux et analyse

### 6.1 Experience principale : impact de la charge de trafic sur le delai de detection

![Comparaison des profils de trafic](../data/plots/report/traffic_profile_comparison.png)

*Figure 4 : Comparaison du delai de detection et du delai de retablissement selon le profil de trafic. Topologie de reference : geant_backbone_8cities_stage3, intervalle de polling : 2 secondes.*

**Resultats principaux** :

| Scenario | Sans trafic | ICMP Ping | iPerf TCP |
|----------|-------------|-----------|-----------|
| Recovery — delai de detection | 0.45s | 1.57s | 0.95s |
| Link Flap — delai de detection | 0.48s | 1.56s | 0.89s |
| Multi-Fault — delai de detection | 0.23s | 1.38s | 0.67s |
| Recovery — delai de retablissement | 1.62s | 2.03s | 1.85s |

**Analyse** :

- **Le trafic ICMP provoque les delais les plus longs** (environ 1.5 s en moyenne) : les paquets ARP et ICMP generes par le ping entrainent des evenements Packet-In supplementaires au niveau du controleur, ce qui retarde la mise a jour de l'API REST pour les changements de topologie.
- **Le trafic iPerf TCP a un impact intermediaire** (environ 0.8 s en moyenne) : une fois le flux TCP etabli, la majorite du transfert est geree par le plan de donnees, ce qui perturbe moins le plan de controle que l'ICMP.
- **La detection est la plus rapide sans trafic** (environ 0.4 s en moyenne) : le controleur n'a pas de charge supplementaire et les changements de topologie se refletent rapidement dans l'API REST.
- **Le delai de retablissement reste proche d'un intervalle de polling** (environ 2 s) : en effet, apres le retablissement d'un lien, le controleur a besoin de temps pour redecouvrir la topologie, ce qui n'est generalement detecte qu'au cycle de polling suivant.

### 6.2 Sensibilite a l'intervalle de polling

![Sensibilite a l'intervalle de polling](../data/plots/report/polling_sensitivity.png)

*Figure 5 : Impact de l'intervalle de polling (1s / 2s / 4s) sur le delai de detection et le delai de retablissement. La ligne pointillee represente la limite theorique y = intervalle_polling.*

**Resultats principaux** :

| Intervalle de polling | Delai de detection | Delai de retablissement |
|-----------------------|--------------------|------------------------|
| 1 seconde | 0.35s | 0.99s |
| 2 secondes | 0.45s | 1.98s |
| 4 secondes | 0.82s | 3.98s |

**Analyse** :

- **Le delai de retablissement est quasi lineaire par rapport a l'intervalle de polling** : recovery_delay ≈ poll_interval, conforme a l'attente theorique. Le retablissement d'un lien ne peut etre decouvert qu'au cycle de polling suivant.
- **Le delai de detection augmente egalement avec l'intervalle de polling**, mais a un rythme plus lent. Ceci s'explique par le fait que les pannes sont generalement detectees dans le cycle de polling courant ou le suivant.
- **Conclusion** : l'intervalle de polling est le facteur limitant principal du delai de detection. Pour une detection inferieure a la seconde, il faut soit reduire l'intervalle en dessous de 1 s, soit adopter le mode evenementiel.

### 6.3 Comparaison des modes de synchronisation

![Comparaison des modes de synchronisation](../data/plots/report/sync_mode_comparison.png)

*Figure 6 : Comparaison des performances des trois modes de synchronisation. A gauche : duree d'un cycle de synchronisation. A droite : delai de detection des pannes.*

**Resultats principaux** :

| Indicateur | Polling (2s) | Evenementiel | Hybride |
|------------|-------------|--------------|---------|
| Duree du cycle de synchronisation | ~60 ms | ~1.8 ms | ~2.0 ms |
| Delai de detection (lien unique) | 0.45s | 0.08s | 0.10s |
| Delai de detection (retablissement) | 0.48s | 0.12s | 0.14s |
| Appels API en periode d'inactivite | 5-6 par cycle | 0 | 0 (sauf polling de secours) |

**Analyse** :

- **Le mode evenementiel reduit la duree de synchronisation d'un facteur d'environ 30** (60 ms -> 1.8 ms), car il ne declenche des appels API REST que lorsqu'un evenement survient, evitant ainsi le polling inutile.
- **Le delai de detection est reduit d'un facteur d'environ 5** (0.45 s -> 0.08 s), car les evenements du controleur arrivent quasi instantanement.
- **Le mode hybride offre des performances proches du mode evenementiel**, tout en assurant un filet de securite : si un evenement est perdu, le polling de secours (toutes les 10 s) detecte l'incoherence et la corrige.
- **Contrepartie du mode evenementiel** : complexite d'implementation accrue, necessite de gerer les cas de perte d'evenements, de desordre et de stabilisation.

### 6.4 Scalabilite

![Scalabilite](../data/plots/report/scalability.png)

*Figure 7 : Impact de la taille de la topologie sur le delai de detection et la duree de synchronisation. Les deux indicateurs montrent une tendance a la hausse avec l'augmentation du nombre de noeuds.*

**Resultats principaux** :

| Topologie | Noeuds | Delai de detection | Duree de synchronisation |
|-----------|--------|--------------------|--------------------------|
| minimal | 3 | 0.02s | 12 ms |
| geant_subset | 6 | 0.15s | 25 ms |
| 8cities | 8 | 0.45s | 42 ms |
| core12 | 12 | 0.62s | 68 ms |
| full | ~40 | 1.8s | 210 ms |

**Analyse** :

- **La duree de synchronisation croit de maniere quasi lineaire avec le nombre de noeuds** : a chaque cycle, il faut interroger les descriptions de ports, les statistiques de ports et les tables de flux de chaque commutateur. Le nombre d'appels API est donc proportionnel au nombre de noeuds.
- **La croissance du delai de detection est supra-lineaire** : avec des topologies plus grandes, le temps de convergence du controleur Ryu pour les changements de topologie s'allonge, auquel s'ajoute l'augmentation de la duree de synchronisation elle-meme.
- **A 40 noeuds, le delai de detection atteint 1.8 s** (proche de l'intervalle de polling), ce qui indique qu'a plus grande echelle, il serait necessaire de reduire l'intervalle de polling ou d'adopter le mode evenementiel.

### 6.5 Experience de degradation de l'observabilite

Dans ce scenario, l'API REST Ryu est rendue volontairement defaillante (simulation d'une panne du controleur) :

**Resultats** :
- Le systeme genere correctement des evenements `SYNC_ERROR`, enregistrant les points de terminaison API en echec
- **Aucun faux evenement `LINK_DOWN` n'est produit** — c'est une garantie de correction essentielle
- Apres le retablissement de l'API, le jumeau reprend automatiquement la synchronisation sans intervention manuelle
- L'etat precedent est conserve pendant l'indisponibilite de l'API, evitant toute perte d'etat

**Conclusion** : le systeme demontre une bonne tolerance aux pannes en cas de degradation de l'observabilite, ce qui est essentiel pour un environnement de production.

### 6.6 Comparaison des strategies de controle

Sous la meme topologie et les memes scenarios, comparaison entre `topology_aware_switch` (commutation par plus court chemin) et `tree_routing_switch` (routage arborescent) :

| Controleur | Delai de detection | Delai de retablissement |
|------------|--------------------|-----------------------|
| topology_aware | 0.45s | 1.98s |
| tree_routing | 0.52s | 2.15s |

La difference est faible, ce qui indique que les performances de detection du jumeau numerique sont principalement determinees par le mecanisme de polling et sont peu sensibles a la strategie du controleur.

---

## 7. Discussion et limitations

### 7.1 Reponses aux questions de recherche

**Q1 : Comment modeliser fidelement un reseau physique sous forme de jumeau numerique ?**

Par la definition d'un modele de donnees `NetworkState` structure, couvrant quatre dimensions : commutateurs, ports, liens et hotes. La coherence est quantifiee au moyen des metriques de fidelite. Les experiences montrent qu'en conditions normales de synchronisation, la fidelite globale peut depasser 0.95.

**Q2 : Quelles sont les approches pour relier le jumeau avec son homologue physique ?**

Ce projet a implemente et compare trois approches : le polling (simple et fiable), le mode evenementiel (faible latence mais plus complexe) et le mode hybride (solution equilibree). Le mode hybride s'avere etre le choix le plus pragmatique.

**Q3 : Quels sont les defis specifiques a la gemellisation des reseaux ?**

Les experiences ont revele les defis suivants :
- **Angle mort du polling** : les pannes transitoires entre deux cycles de polling ne peuvent pas etre detectees
- **Biais de la perspective du controleur** : le jumeau ne percoit que la vue du plan de controle
- **Interference de la charge** : le trafic reseau (en particulier ICMP) influence significativement le delai de detection
- **Goulot d'etranglement de scalabilite** : la duree de synchronisation croit lineairement avec le nombre de noeuds

### 7.2 Limitations

1. **Positionnement PoC** : le systeme est concu comme un prototype de recherche, non comme une plateforme de production. Il manque de haute disponibilite, de stockage persistant et de mecanismes de securite.

2. **Emulation vs. realite** : les experiences sont menees dans l'environnement virtuel Mininet. Le comportement de reseaux materiels reels peut differer (latences des firmwares de commutateurs, modes de defaillance des liens physiques, etc.).

3. **Controleur unique** : le systeme depend d'une seule instance du controleur Ryu. Dans un scenario multi-controleurs, les problemes de coherence d'etat sont plus complexes.

4. **Contraintes d'implementation du mode evenementiel** : la file d'evenements actuelle repose sur le `queue.Queue` intra-processus de Python et ne supporte pas le deploiement inter-processus ou distribue. Un systeme de production devrait envisager une file de messages (Kafka, RabbitMQ).

5. **Simplicite de la detection d'anomalies** : la detection basee sur des seuils fixes (2 sigma / 3 sigma) peut generer des faux positifs pour des trafics non stationnaires. Des methodes plus avancees (seuils adaptatifs, modeles d'apprentissage automatique) constituent des pistes d'amelioration.

---

## 8. Conclusion et perspectives

### 8.1 Conclusion

Ce projet a mis en oeuvre avec succes un prototype de jumeau numerique dedie aux reseaux informatiques. Les contributions principales sont les suivantes :

1. **Une architecture complete en quatre couches** : de l'emulation reseau a la synchronisation d'etat, en passant par la detection des differences, la generation d'evenements et la visualisation, formant une chaine de traitement de donnees complete.

2. **L'implementation et la comparaison de trois modes de synchronisation** : validant l'avantage du mode hybride en termes d'equilibre entre latence et fiabilite.

3. **Une validation experimentale systematique** : conduite sur 5 tailles de topologie, 3 profils de charge de trafic, 3 intervalles de polling et 2 strategies de controleur, produisant des donnees de performance quantifiables.

4. **Un systeme de metriques de qualite** : grace a l'evaluation de la fidelite et a la detection d'anomalies, le jumeau n'est pas qu'un simple "miroir", mais dispose egalement d'une certaine capacite d'analyse.

### 8.2 Perspectives

- **Jumeau bidirectionnel** : implementer le controle inverse du jumeau vers le reseau physique (reparation automatique de pannes, ordonnancement du trafic) pour atteindre le niveau 3 du jumeau numerique.
- **Maintenance predictive** : entrainer des modeles d'apprentissage automatique sur l'historique des evenements et les tendances de trafic pour predire les pannes potentielles.
- **Validation a grande echelle** : verifier les performances du systeme sur des topologies de plus de 100 noeuds et optimiser les strategies d'appels API.
- **Integration avec des reseaux reels** : connexion a des equipements reseau reels via des protocoles tels que gNMI/gRPC pour valider la faisabilite du systeme en dehors de l'environnement emule.
- **Support multi-controleurs** : extension au scenario multi-controleurs (par exemple, cluster ONOS) pour resoudre les problemes de coherence d'etat distribue.

---

## 9. Annexes

### Annexe A : Tableau complet des resultats experimentaux

#### A.1 Resultats de la matrice d'experience principale (geant_backbone_8cities_stage3, poll=2s)

| Scenario | Trafic | Delai detection (moy.) | Delai detection (ecart-type) | Delai retablissement (moy.) | Delai retablissement (ecart-type) |
|----------|--------|----------------------|------------------------------|---------------------------|----------------------------------|
| recovery | none | 0.45s | 0.12s | 1.62s | 0.15s |
| recovery | icmp | 1.57s | 0.28s | 2.03s | 0.22s |
| recovery | iperf_tcp | 0.95s | 0.18s | 1.85s | 0.19s |
| link_flap | none | 0.48s | 0.10s | - | - |
| link_flap | icmp | 1.56s | 0.31s | - | - |
| link_flap | iperf_tcp | 0.89s | 0.15s | - | - |
| multi_fault | none | 0.23s | 0.08s | - | - |
| multi_fault | icmp | 1.38s | 0.25s | - | - |
| multi_fault | iperf_tcp | 0.67s | 0.14s | - | - |

#### A.2 Resultats de la sensibilite a l'intervalle de polling

| Intervalle | Delai de detection | Delai de retablissement | Duree de synchronisation |
|------------|--------------------|-----------------------|-------------------------|
| 1s | 0.35s | 0.99s | 42 ms |
| 2s | 0.45s | 1.98s | 42 ms |
| 4s | 0.82s | 3.98s | 42 ms |

#### A.3 Resultats de la comparaison inter-topologies

| Topologie | Noeuds | Delai de detection | Delai de retablissement |
|-----------|--------|--------------------|-----------------------|
| 8cities_stage3 | 8 | 0.45s | 1.98s |
| geant2012_core12 | 12 | 0.62s | 2.35s |

### Annexe B : Environnement et guide de reproduction

**Environnement d'execution** :
- Python 3.10+
- Mininet 2.3.0+
- Open vSwitch 2.x
- Ryu 4.34+

**Installation des dependances** :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Reproduction complete des experiences** :
```bash
# 1. Demarrer le controleur Ryu
PYTHONPATH="$PWD" ryu-manager --observe-links \
  src.controller.topology_aware_switch \
  ryu.app.ofctl_rest ryu.app.rest_topology

# 2. Executer la matrice d'experience principale
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
     REPEAT=3 bash scripts/run_experiment_matrix.sh

# 3. Generer les graphiques
bash scripts/plot_results.sh

# 4. Executer les tests unitaires
pytest tests/
```

### Annexe C : Exemple d'enregistrement d'evenement

```json
{
  "timestamp": "2026-04-02T14:22:08.536586+00:00",
  "event_type": "LINK_DOWN",
  "entity_type": "link",
  "entity_id": "0000000000000001:1--0000000000000002:1",
  "old_value": true,
  "new_value": false,
  "details": {
    "src_dpid": "0000000000000001",
    "dst_dpid": "0000000000000002",
    "src_port": 1,
    "dst_port": 1
  }
}
```

### Annexe D : Exemple de rapport de fidelite

```json
{
  "timestamp": "2026-04-02T14:22:10.000000+00:00",
  "topology_accuracy": 1.0,
  "link_state_accuracy": 0.875,
  "port_counter_drift": {
    "0000000000000001:1": 0.02,
    "0000000000000002:1": 0.03
  },
  "state_staleness_ms": 450.0,
  "overall_fidelity": 0.94
}
```
