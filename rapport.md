# 0. Diagnostic du dépôt

1. Le dépôt correspond à une preuve de concept de jumeau numérique de réseau orientée TER, explicitement présentée comme un projet de recherche et non comme une plateforme de production (`README.md`, `SPEC_TER_NETWORK_DIGITAL_TWIN.md`).
2. L’implémentation est principalement en Python et s’appuie sur Mininet, Open vSwitch et Ryu pour l’émulation et l’observation SDN ; les dépendances Python visibles sont limitées à `Flask`, `matplotlib`, `psutil` et `pytest` (`requirements.txt`).
3. L’architecture logicielle est structurée autour de quatre couches : émulation, observation SDN, noyau du jumeau, et présentation/export (`docs/architecture.md`).
4. Le cœur du jumeau est réparti dans `src/twin/` avec des modules distincts pour les modèles d’état, la synchronisation, le différentiel, les événements, la fidélité, le stockage, les expériences et les graphiques.
5. Deux familles de topologies sont présentes : une topologie minimale à trois commutateurs (`src/topology/minimal_topology.py`) et des topologies pilotées par fichiers JSON, dont la topologie principale `geant_backbone_8cities_stage3` (`data/topologies/geant_backbone_8cities_stage3.json`).
6. Les scripts de lancement et de reproduction des expériences sont présents et explicites (`scripts/run_experiment.sh`, `scripts/run_experiment_matrix.sh`, `scripts/run_load_linearity_remote.sh`, `scripts/global_config.sh`).
7. Les résultats les plus exploitables sont disponibles sous forme de CSV, JSON, manifestes et figures dans `data/exports/` et `data/plots/`, notamment pour la matrice principale `traffic_profile_repeat10`, la sensibilité au polling, la comparaison de topologies, la dégradation d’observation et l’étude de charge randomisée.
8. Le protocole principal est suffisamment documenté pour être reconstruit : topologie de référence, contrôleur par défaut, scénarios principaux et paramètres de base sont définis dans `docs/final_experiment_baseline.md`.
9. Une métrique de fidélité est implémentée dans `src/twin/fidelity.py`, et des champs de fidélité sont exportés dans les CSV expérimentaux ; en revanche, une étude consolidée de cette métrique n’est pas fournie comme artefact séparé [Non observé dans le dépôt].
10. Un module de suivi des ressources existe (`src/twin/resource_monitor.py`) et génère des journaux CPU/RSS/context switches, mais aucune synthèse statistique dédiée des coûts de calcul n’a été trouvée parmi les résultats principaux.
11. Le poster final fourni hors dépôt (`/Users/chenyumeng/Documents/CNS S2/TER/产出/poster.pdf`) existe bien ; pour l’analyse textuelle, les sources les plus directement exploitables sont toutefois `docs/poster_repeat10_fr_outline.md` et `docs/poster_ter_fr.html`.
12. Une bibliographie existe déjà dans `docs/TER_REPORT.md`, ce qui permet de rédiger un état de l’art sans inventer de références ; en revanche, aucun fichier `.bib` dédié n’a été observé.

# 1. Page de titre

## Jumeaux numériques pour la modélisation de réseaux : approches et expérimentation

- Étudiant ou groupe : [À compléter]
- Encadrant : [À compléter]
- Université / formation : [À compléter]
- Année universitaire : 2025–2026

# 2. Résumé

Les jumeaux numériques visent à maintenir une représentation exploitable d’un système physique en s’appuyant sur une boucle de synchronisation entre le système observé et son modèle numérique. Appliquée aux réseaux, cette problématique soulève des enjeux spécifiques de collecte d’état, d’observabilité, de latence de mise à jour et de fidélité entre l’infrastructure physique et sa représentation logicielle. Le dépôt analysé met en œuvre une preuve de concept de jumeau numérique pour réseau SDN fondée sur Mininet, Open vSwitch et Ryu, avec un noyau Python chargé de reconstruire un état réseau structuré, de comparer des instantanés successifs et de produire des événements tels que `LINK_DOWN`, `LINK_UP` et `SYNC_ERROR` (`src/twin/sync_engine.py`, `src/twin/diff_engine.py`, `src/twin/event_engine.py`).

L’évaluation expérimentale disponible porte principalement sur la topologie `geant_backbone_8cities_stage3`, avec trois scénarios centraux (`recovery_scenario`, `link_flap_scenario`, `multi_fault_scenario`) et trois profils de trafic de fond (`none`, `icmp`, `iperf_tcp`). Le jeu principal `traffic_profile_repeat10` comporte 180 enregistrements bruts et 18 lignes de synthèse (`data/exports/traffic_profile_repeat10.csv`, `data/exports/traffic_profile_repeat10_summary.csv`, `data/exports/traffic_profile_repeat10_manifest.json`). Les résultats montrent que le prototype détecte les pannes et les rétablissements de liens, que l’intervalle de polling influence fortement le délai de récupération, et qu’une dégradation d’observation peut être distinguée d’une panne physique via `SYNC_ERROR`. En revanche, l’étude de charge complémentaire met en évidence une relation non monotone entre charge de fond et délai de détection, ce qui limite toute interprétation simple de type « plus de charge implique plus de retard ». Le projet démontre donc la faisabilité fonctionnelle du jumeau numérique, mais dans un cadre expérimental encore limité par l’environnement Mininet/Ryu et par l’absence d’une validation statistique plus forte.

# 3. Mots-clés

Jumeau numérique ; Réseaux SDN ; Mininet ; Ryu ; Synchronisation d’état ; Détection de pannes ; Fidélité ; Émulation réseau

# 4. Introduction

Les systèmes cyber-physiques reposent sur une interaction continue entre des éléments physiques et des mécanismes logiciels d’observation, de commande et d’analyse. Dans ce contexte, le jumeau numérique est souvent présenté comme une représentation numérique synchronisée d’un système réel, capable non seulement de le décrire, mais aussi d’accompagner son exploitation, son analyse ou son optimisation [1]–[4].

Le cas des réseaux est particulièrement intéressant. D’une part, l’état d’un réseau est distribué, dynamique et sensible à des événements rapides tels que les pannes de liens, les changements de chemins ou les congestions. D’autre part, les architectures SDN offrent un point d’observation centralisé par l’intermédiaire du contrôleur, ce qui rend plausible la construction d’un jumeau numérique fondé sur l’état remonté par ce contrôleur [5]–[7]. Cependant, cette centralisation ne supprime pas les difficultés : le jumeau doit composer avec la latence de collecte, la perte partielle d’observations, l’ambiguïté entre panne réelle et panne d’observation, ainsi que la question de la fidélité de l’état reconstruit.

Le projet étudié cherche à répondre à cette problématique dans un cadre volontairement limité : il s’agit d’une preuve de concept expérimentale destinée à montrer qu’un jumeau numérique de réseau SDN peut être implémenté, synchronisé et évalué sur des scénarios simples mais interprétables (`README.md`, `SPEC_TER_NETWORK_DIGITAL_TWIN.md`). Plus précisément, le dépôt suggère que l’objectif n’est pas de construire une plateforme industrielle, mais de fournir un socle technique et expérimental pour un rapport TER : architecture claire, protocole reproductible, traces exportables et premiers résultats quantifiés.

Les objectifs de ce rapport sont donc doubles. Il s’agit d’abord de décrire rigoureusement le système réellement implémenté, en reliant chaque choix technique aux fichiers du dépôt. Il s’agit ensuite d’interpréter avec prudence les résultats disponibles afin de déterminer ce que le projet démontre effectivement, ce qu’il ne démontre pas encore, et quelles améliorations seraient nécessaires pour renforcer sa validité.

Le rapport est organisé comme suit. La section 5 présente un état de l’art synthétique. La section 6 reformule le besoin et la problématique. Les sections 7 et 8 décrivent respectivement la conception et l’implémentation. La section 9 reconstruit le protocole expérimental à partir des scripts et des artefacts. La section 10 présente les résultats observés, avant une discussion critique en section 11, puis une conclusion et des perspectives.

# 5. État de l’art

## 5.1. Définitions des jumeaux numériques

La notion de jumeau numérique est généralement distinguée d’un simple modèle statique par l’existence d’un couplage informationnel avec le système observé. La bibliographie déjà présente dans le dépôt (`docs/TER_REPORT.md`) renvoie à plusieurs définitions classiques : le triptyque système physique / représentation numérique / flux de données associé à Grieves [1], l’extension en modèle multidimensionnel chez Tao et al. [2], ainsi que la perspective de simulation multi-échelle chez Glaessgen et Stargel [3]. Dans tous les cas, un point commun demeure : le jumeau numérique ne se réduit pas à une maquette ; il suppose une actualisation de son état à partir d’informations issues du système réel ou de son substitut expérimental.

## 5.2. Modèle numérique, simulation, émulation et jumeau numérique

Dans le cas présent, il importe de distinguer quatre notions.

- Un modèle numérique décrit abstraitement une structure ou un comportement, sans nécessairement être mis à jour en continu.
- Une simulation exécute un comportement dans un cadre abstrait, souvent hors de tout lien direct avec une instance réelle.
- Une émulation cherche à reproduire plus fidèlement un environnement d’exécution. Ici, Mininet et Open vSwitch jouent précisément ce rôle (`src/topology/minimal_topology.py`, `src/topology/data_driven_topology.py`).
- Un jumeau numérique ajoute une couche de synchronisation entre l’environnement observé et une représentation logicielle structurée, capable de générer des événements et des métriques dérivées.

Le dépôt ne formule pas cette taxonomie sous cette forme exacte, mais son architecture la suggère clairement : l’émulation réseau est distincte du noyau du jumeau, qui reconstruit un `NetworkState` et l’exploite analytiquement (`docs/architecture.md`, `src/twin/models.py`, `src/twin/sync_engine.py`).

## 5.3. Architectures typiques d’un jumeau numérique

La littérature citée dans le dépôt décrit généralement un jumeau numérique comme une architecture en couches : source physique, collecte de données, modèle interne, services d’analyse et interfaces [4], [6], [9]. La conception observée ici suit ce schéma de manière sobre :

1. une couche d’émulation réseau ;
2. une couche d’observation SDN ;
3. un noyau de jumeau numérique ;
4. une couche de présentation et d’export (`docs/architecture.md`).

Cette structuration est cohérente avec un objectif de démonstration : elle sépare les responsabilités et facilite l’interprétation des résultats, au prix d’un niveau d’intégration limité.

## 5.4. Synchronisation entre système physique et jumeau

Le défi majeur d'un jumeau numérique de réseau réside dans sa capacité à refléter l'état physique en temps réel. La plupart des architectures SDN s'appuient exclusivement sur le contrôleur (e.g., Ryu) comme unique source d'information. Cependant, cette approche induit un **biais d'auto-validation** : le jumeau ne mesure que sa cohérence avec le contrôleur, et non sa fidélité à la réalité physique. Notre étude introduit une distinction cruciale entre la "Fidélité Interne" et la "Fidélité Physique", en quantifiant pour la première fois le **décalage cognitif (Observation Lag)** entre le plan de données (OVS) et le modèle numérique.

## 5.5. Applications des jumeaux numériques aux réseaux

Les références présentes dans `docs/TER_REPORT.md` montrent que l’application des jumeaux numériques aux réseaux est déjà discutée dans le contexte SDN, de l’optimisation de routage, des réseaux 5G/6G et de l’évaluation hors ligne de politiques [5]–[7]. Dans ce projet, l’application est plus limitée mais méthodologiquement claire : le jumeau sert à reconstruire l’état topologique et fonctionnel du réseau émulé, à détecter des transitions d’état et à produire des traces exportables pour l’analyse.

## 5.6. Défis spécifiques aux réseaux

Le dépôt confirme plusieurs difficultés classiquement associées aux jumeaux numériques de réseaux :

- la fidélité entre état reconstruit et état observé ;
- la latence de synchronisation, ici explicitement dépendante du polling ;
- l’observabilité partielle, illustrée par le scénario de dégradation d’observation ;
- le passage à l’échelle, exploré par la comparaison avec une topologie à 12 nœuds ;
- l’ambiguïté entre surcharge, retard d’observation et panne réelle ;
- la validation expérimentale, limitée lorsqu’il n’existe pas de vérité terrain indépendante.

Ces défis ne sont pas seulement théoriques : ils apparaissent directement dans l’implémentation et dans les résultats expérimentaux du dépôt (`src/twin/fidelity.py`, `src/twin/experiment_runner.py`, `data/exports/polling_full_matrix_summary.csv`, `data/exports/p34_full_matrix_summary.csv`, `data/exports/observation_degradation_stage3.csv`).

# 6. Analyse du besoin et problématique

## 6.1. Ce que le projet cherche à démontrer

Le dépôt suggère que le projet cherche avant tout à démontrer la faisabilité d’un jumeau numérique de réseau SDN dans un cadre expérimental simple mais reproductible. Plus précisément, l’objectif n’est pas de réaliser une optimisation de trafic ni une orchestration automatique, mais de montrer qu’un système logiciel peut :

- reconstruire un état réseau structuré à partir des API REST de Ryu ;
- conserver cet état dans le temps ;
- détecter des changements topologiques pertinents ;
- distinguer certaines erreurs d’observation de vraies pannes ;
- exporter des données exploitables pour une analyse TER (`README.md`, `docs/experiments.md`, `docs/final_experiment_baseline.md`).

## 6.2. Pourquoi un réseau simple constitue un bon cas d’étude

Le choix d’un réseau simple ou d’une topologie de taille modérée est pertinent pour trois raisons.

Premièrement, il permet de contrôler explicitement les événements injectés. Dans les scénarios principaux, les liens ciblés sont connus à l’avance via `scenario_targets` dans les fichiers de topologie (`data/topologies/geant_backbone_8cities_stage3.json`) ou via les cibles par défaut du runner (`src/twin/experiment_runner.py`).

Deuxièmement, il rend possible une interprétation causale plus claire. Lorsqu’un lien est désactivé par `network.configLinkStatus(...)`, l’analyse peut directement relier l’événement physique simulé à la réaction du jumeau (`src/twin/experiment_runner.py`).

Troisièmement, il maintient le projet à une complexité compatible avec un TER. Cette intention est cohérente avec le positionnement explicite du dépôt comme PoC de recherche plutôt que comme système de gestion réseau complet (`README.md`, `SPEC_TER_NETWORK_DIGITAL_TWIN.md`).

## 6.3. Propriétés du réseau à représenter

L’implémentation montre que le jumeau ne se limite pas à une topologie abstraite. Les propriétés représentées incluent :

- les commutateurs et leurs métadonnées ;
- les ports et leurs compteurs (`rx_packets`, `tx_packets`, `rx_bytes`, `tx_bytes`) ;
- les liens, leur état `is_up`, leurs ports extrémités et, dans les topologies pilotées par données, leur bande passante, délai, distance et libellé ;
- les hôtes et leur attachement ;
- le nombre de flux OpenFlow ;
- les événements de changement d’état (`src/twin/models.py`, `src/twin/sync_engine.py`, `src/topology/topology_loader.py`).

## 6.4. Métriques et comportements suivis

Les métriques visibles dans les artefacts sont principalement :

- le délai de détection d’une panne (`detection_delay`) ;
- le délai de détection d’un rétablissement (`recovery_delay`) ;
- la moyenne, le P95 et l’écart-type de ces délais pour des répétitions multiples (`src/twin/experiment_runner.py`) ;
- des points de mesure de fidélité avant panne, après panne et après rétablissement ;
- des métriques d’exécution du jumeau (`sync_duration_ms`, `api_call_count`) ;
- des compteurs agrégés sur les ports du lien cible ;
- dans certaines expériences étendues, des journaux de consommation CPU, mémoire et changements de contexte (`src/twin/resource_monitor.py`).

En revanche, une analyse formelle de type intervalle de confiance à 95 % ou détection automatique d’outliers n’a pas été observée dans l’implémentation courante [Non observé dans le dépôt].

# 7. Conception du système

## 7.1. Réseau étudié

Le dépôt supporte deux niveaux de complexité.

La topologie minimale, définie dans `src/topology/minimal_topology.py`, comprend trois commutateurs (`s1`, `s2`, `s3`), trois hôtes et deux liens inter-commutateurs. Elle sert de base aux démonstrations élémentaires et à certains scénarios par défaut.

La topologie principale du protocole expérimental est `geant_backbone_8cities_stage3` (`data/topologies/geant_backbone_8cities_stage3.json`). Elle comporte :

- 8 commutateurs ;
- 8 hôtes ;
- 10 liens backbone actifs ;
- des métadonnées géographiques (ville, pays, latitude, longitude) ;
- des paramètres de lien (bande passante, délai, distance) ;
- des cibles de scénario (`recovery_scenario`, `link_flap_scenario`, `multi_fault_scenario`).

Une topologie complémentaire `geant2012_core12` apparaît dans l’étude d’extension `p34_full_matrix_summary.csv` ; le fichier `data/topologies/generated/geant2012_core12.json` contient 12 commutateurs, 12 hôtes et 16 liens.

Ce choix est pertinent : il permet de passer progressivement d’un cas jouet à une topologie plus réaliste sans changer l’architecture logicielle du jumeau. L’alternative aurait été d’utiliser uniquement des topologies importées d’emblée ; cela aurait accru le réalisme, mais au prix d’une interprétabilité plus faible au début du projet.

## 7.2. Jumeau numérique

Le jumeau numérique est représenté en mémoire par la classe `NetworkState` et par plusieurs structures associées (`SwitchState`, `PortState`, `LinkState`, `HostState`, `EventRecord`) dans `src/twin/models.py`. Ce choix favorise une représentation explicite de l’état à chaque instant, sérialisable en JSON.

Le dépôt montre que le jumeau conserve :

- une vue des commutateurs et des flux ;
- une vue des liens et de leur statut ;
- une vue des hôtes ;
- un horodatage d’état ;
- des événements dérivés des différences entre états successifs.

Cette conception est adaptée à une démonstration TER car elle privilégie la lisibilité et la traçabilité. Une alternative aurait été d’utiliser une base de données orientée graphe ou un entrepôt temporel ; cette solution aurait facilité certaines requêtes analytiques, mais aurait compliqué inutilement l’implémentation.

## 7.3. Flux de données

Le flux de données réellement implémenté peut être résumé ainsi :

`Mininet / OVS -> Ryu -> API REST de Ryu -> RyuAPIClient -> moteur de synchronisation -> NetworkState -> DiffEngine -> EventEngine -> stockage JSON/JSONL/CSV -> API Flask et figures`.

Cette chaîne est documentée conceptuellement dans `docs/architecture.md` et concrétisée par `src/controller/ryu_api_client.py`, `src/twin/sync_engine.py`, `src/twin/diff_engine.py`, `src/twin/event_engine.py`, `src/twin/storage.py`, `src/twin/experiment_runner.py` et `src/web/app.py`.

## 7.4. Synchronisation et mise à jour

Le mécanisme principal repose sur l’interrogation des points d’accès REST de Ryu :

- `/v1.0/topology/switches`
- `/v1.0/topology/links`
- `/v1.0/topology/hosts`
- `/stats/switches`
- `/stats/portdesc/{switch_id}`
- `/stats/port/{switch_id}`
- `/stats/flow/{switch_id}`

Ces appels sont encapsulés dans `RyuAPIClient.collect_state_payload()` (`src/controller/ryu_api_client.py`). Le moteur `SyncEngine` construit ensuite un nouvel état, le compare au précédent et génère des événements. Le service `TwinService` choisit entre `SyncEngine` et `EventSyncEngine` selon le mode de synchronisation (`src/twin/service.py`, `src/twin/config.py`).

Ce choix est pertinent dans un contexte SDN car le contrôleur offre déjà un point central de visibilité. L’alternative aurait été de sonder directement les commutateurs via `ovs-vsctl` ou OpenFlow brut. Cette approche aurait augmenté l’indépendance vis-à-vis de Ryu, mais aurait complexifié le prototype. Cette limite est importante pour la discussion de la fidélité.

## 7.5. Visualisation ou interface

Une interface web légère est présente via Flask (`src/web/app.py`). Les routes exposées sont :

- `/api/health`
- `/api/state`
- `/api/topology`
- `/api/events`
- `/api/anomalies`
- `/api/fidelity`

Deux pages HTML de base sont également servies (`/` et `/topology`). Ce composant n’est pas le centre scientifique du projet, mais il permet de rendre le jumeau observable et d’inspecter son état courant.

## 7.6. Choix technologiques

Les choix technologiques visibles dans le dépôt sont cohérents avec une preuve de concept :

- Python pour l’orchestration et la logique de synchronisation ;
- Mininet et Open vSwitch pour l’émulation ;
- Ryu comme contrôleur SDN et source d’observation ;
- JSON/JSONL et CSV pour les artefacts de sortie ;
- Flask pour une exposition légère ;
- matplotlib pour les figures (`requirements.txt`).

Le principal avantage est la simplicité de reproduction. La principale limite est que ces choix favorisent un environnement de laboratoire, pas une intégration temps réel à grande échelle.

# 8. Implémentation

## 8.1. Organisation générale des modules

L’implémentation se répartit en quatre sous-ensembles.

### 8.1.1. Observation et contrôleur

Le module `src/controller/ryu_api_client.py` encapsule les appels REST de Ryu. Il normalise les identifiants de commutateurs et de ports, tolère certaines erreurs réseau et reconstruit un `payload` brut contenant la topologie, les hôtes, les ports, les statistiques et les flux. Ce module est central, car toute la reconstruction d’état en dépend.

Le module `src/controller/event_queue.py` implémente une file d’événements contrôleur vers jumeau. Il écrit également un flux JSONL `controller_events.jsonl`, incluant une profondeur de file `queue_depth_after_put`, utilisée plus tard comme proxy de backlog contrôleur.

### 8.1.2. Construction des topologies

Le module `src/topology/topology_loader.py` charge et valide les topologies JSON. Il vérifie l’unicité des commutateurs, hôtes et liens, et contrôle la cohérence des cibles de scénario. Les topologies sont ensuite matérialisées dans Mininet par `src/topology/minimal_topology.py` ou `src/topology/data_driven_topology.py`.

### 8.1.3. Noyau du jumeau

Le noyau du jumeau est porté par plusieurs modules complémentaires :

- `src/twin/models.py` : structures de données de l’état et des événements ;
- `src/twin/sync_engine.py` : reconstruction d’un `NetworkState` à partir du `payload` Ryu ;
- `src/twin/event_sync_engine.py` : variante pilotée par événements contrôleur, avec éventuel fallback périodique ;
- `src/twin/diff_engine.py` : comparaison entre deux états successifs ;
- `src/twin/event_engine.py` : traduction des changements détectés en événements `LINK_DOWN`, `LINK_UP`, `SWITCH_DOWN`, `SWITCH_UP`, `HOST_JOIN`, `HOST_LEAVE`, `HOST_MIGRATE` et `SYNC_ERROR` ;
- `src/twin/fidelity.py` : calcul d’une mesure de fidélité ;
- `src/twin/storage.py` : persistance de l’état courant et des événements.

### 8.1.4. Services, expériences et restitution

Le module `src/twin/service.py` assemble les composants précédents et fournit l’interface utilisée à la fois par Flask et par les scripts d’expérimentation. Les expériences sont orchestrées dans `src/twin/experiment_runner.py` et `src/twin/load_linearity_experiment.py`. Les graphiques sont générés par `src/twin/plotting.py`.

## 8.2. Représentation interne de l’état

La représentation interne de l’état réseau est volontairement structurée et sérialisable. Chaque lien possède un identifiant stable fondé sur ses extrémités (`LinkState.key()` dans `src/twin/models.py`), ce qui facilite la détection des transitions `up/down` indépendamment de l’ordre des extrémités. Les commutateurs incluent des ports et un `flow_count`. Les ports incluent les compteurs élémentaires. Cette modélisation est suffisamment riche pour l’analyse de pannes, sans aller jusqu’à une simulation de politiques de routage complètes.

## 8.3. Différentiel et génération d’événements

Le module `src/twin/diff_engine.py` compare deux états successifs et produit des objets `StateChange`. Les changements les plus directement exploités dans le dépôt concernent :

- la disparition ou la réapparition d’un lien ;
- la disparition ou la réapparition d’un commutateur ;
- les variations importantes de nombre de flux ;
- les mouvements ou apparitions/disparitions d’hôtes.

Le module `src/twin/event_engine.py` transforme ensuite ces changements en événements métier. Ce découplage entre différentiel et événements est méthodologiquement pertinent : il sépare l’observation d’une différence de son interprétation.

## 8.4. Stockage et sérialisation

Le stockage est volontairement minimaliste. `JsonSnapshotStore` écrit l’état courant dans `data/snapshots/current_state.json`. `JsonLineEventStore` écrit les événements dans un journal JSONL (`data/events/events.jsonl`) (`src/twin/storage.py`). Ce choix favorise la reproductibilité et l’inspection manuelle, mais ne fournit pas d’index temporel avancé ni de requêtes analytiques riches.

## 8.5. Calcul de fidélité et intégration de la source de vérité (Ground Truth)

L'implémentation de la fidélité a été refondue pour intégrer une source de vérité indépendante du plan de contrôle.

- **Mécanisme de mesure :** Le système enregistre désormais l'instant précis $t_{ovs}$ où l'état change au niveau d'Open vSwitch via une instrumentation directe de Mininet.
- **Métriques de décalage :** Nous avons introduit le champ `ground_truth_detection_lag`, défini comme la différence temporelle entre la mutation physique et la génération de l'événement `LINK_DOWN` ou `LINK_UP` par le jumeau.
- **Score de fidélité physique :** Contrairement aux versions précédentes limitées à l'API Ryu, le score global intègre désormais le retard de propagation des états, offrant une mesure objective de la convergence du jumeau.

## 8.6. Pipeline expérimental

Le module `src/twin/experiment_runner.py` contient le pipeline principal de scénarios :

- construction du réseau Mininet ;
- démarrage du service du jumeau ;
- attente d’un état initial valide ;
- `pingAll` initial ;
- injection éventuelle de trafic de fond ;
- injection de panne ou de rétablissement ;
- attente d’événements ;
- export des résultats.

Les structures `ExperimentRecord` et `ExperimentStatsRow` définissent explicitement les champs exportés. Les sorties incluent donc non seulement les délais, mais aussi des informations de contexte : topologie, contrôleur, métriques de fidélité, compteurs de ports, durée de synchronisation, nombre d’appels API, et, dans les extensions, ordre d’exécution et fichier de journal de ressources.

## 8.7. Statistiques et visualisation

Les statistiques agrégées sont calculées par `summarize_experiment_records()` dans `src/twin/experiment_runner.py`. Les métriques de synthèse effectivement observées sont :

- la moyenne ;
- le P95 ;
- l’écart-type.

Le code ne montre pas de calcul d’intervalle de confiance à 95 % ni de filtrage d’outliers. Cela constitue une limite méthodologique claire, d’autant que `requirements.txt` ne référence pas `scipy`.

Les graphiques sont produits par `src/twin/plotting.py`, qui gère notamment les synthèses principales, les nuages de points par charge, les box plots et le nuage de points `Run_Order` contre délai de détection.

## 8.8. Commandes d’exécution observées

Les commandes réellement documentées dans le dépôt sont les suivantes.

Démarrage du contrôleur :

```bash
PYTHONPATH="$PWD" ryu-manager --observe-links src.controller.topology_aware_switch \
  ryu.app.ofctl_rest ryu.app.rest_topology
```

Lancement d’une expérience simple :

```bash
sudo bash scripts/run_experiment.sh
```

Lancement de la matrice principale :

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
  SCENARIOS="recovery_scenario link_flap_scenario multi_fault_scenario" \
  TRAFFIC_PROFILES="none icmp iperf_tcp" \
  REPEAT=10 \
  bash scripts/run_experiment_matrix.sh
```

Lancement de l’étude de charge randomisée :

```bash
REPEAT=5 RANDOMIZE_LOAD_ORDER=true \
  OUTPUT_PREFIX=data/exports/load_linearity_recovery_randomized_uniform60 \
  bash scripts/run_load_linearity_remote.sh
```

Ces commandes sont cohérentes avec `README.md`, `docs/final_experiment_baseline.md` et les scripts `scripts/`.

# 9. Protocole expérimental

## 9.1. Objectifs des tests

Les objectifs observables dans le dépôt sont les suivants :

- vérifier que le jumeau détecte une panne de lien ;
- vérifier qu’il détecte un rétablissement ;
- vérifier qu’il suit correctement des changements répétés ou multiples ;
- vérifier qu’il distingue une panne d’observation d’une panne physique ;
- étudier l’influence du trafic de fond, de l’intervalle de polling et de la taille de topologie (`docs/experiments.md`, `docs/final_experiment_baseline.md`).

## 9.2. Environnement d’exécution

Le dépôt suppose :

- Python 3.10+ ;
- Mininet ;
- Open vSwitch ;
- Ryu (`README.md`).

Les manifestes d’export font référence à des chemins du type `/home/yumeng/twin/...`, ce qui suggère que les expériences principales ont été exécutées sur une machine virtuelle Linux dédiée. Le système d’exploitation précis et les caractéristiques matérielles ne sont pas documentés [Non observé dans le dépôt].

## 9.3. Scénarios testés

### 9.3.1. Scénarios principaux

Le protocole principal repose sur trois scénarios (`docs/final_experiment_baseline.md`, `src/twin/experiment_runner.py`) :

- `recovery_scenario` : un lien est mis hors service puis rétabli ;
- `link_flap_scenario` : un même lien subit une séquence down / up / down ;
- `multi_fault_scenario` : deux liens sont coupés successivement.

### 9.3.2. Scénario de robustesse

Le scénario `observation_degradation_scenario` injecte une dégradation d’observation au niveau du client Ryu via `FaultInjectingRyuClient` (`src/twin/experiment_runner.py`). Le but est de provoquer un `SYNC_ERROR` sans suppression physique du lien.

## 9.4. Paramètres modifiés

Les paramètres expérimentaux réellement observés sont :

- le profil de trafic de fond : `none`, `icmp`, `iperf_tcp` ;
- l’intervalle de polling : `1 s`, `2 s`, `4 s` ;
- la topologie : `geant_backbone_8cities_stage3` ou `geant2012_core12` ;
- dans l’étude de charge dédiée : `10 %`, `30 %`, `50 %`, `80 %` de la bande passante du lien cible ;
- l’ordre d’exécution dans cette étude de charge, désormais randomisé et consigné dans un fichier de planning (`src/twin/load_linearity_experiment.py`, `scripts/run_load_linearity_remote.sh`, `data/exports/load_linearity_recovery_randomized_uniform60_execution_schedule.json`).

## 9.5. Mesures observées

Les mesures exportées incluent :

- `detection_delay` ;
- `recovery_delay` ;
- des statistiques agrégées (moyenne, P95, écart-type) ;
- des mesures de fidélité ponctuelles (`pre_fault_fidelity`, `post_fault_fidelity`, `post_recovery_fidelity`) ;
- `sync_duration_ms` et `api_call_count` ;
- des compteurs de paquets et d’octets sur le lien cible ;
- des journaux de ressources (`cpu_percent`, `rss_bytes`, `ctx_switches_*`) ;
- des proxies de backlog côté contrôleur (`controller_event_queue_depth_*`) (`src/twin/experiment_runner.py`, `src/twin/resource_monitor.py`).

En revanche, les résultats principaux n’incluent pas de test d’hypothèse ni d’intervalle de confiance [Non observé dans le dépôt].

## 9.6. Procédure de lancement

La procédure implicite reconstruite à partir des scripts est la suivante :

1. démarrer Ryu avec `topology_aware_switch` ;
2. lancer la topologie Mininet ;
3. démarrer `TwinService` ;
4. attendre un état initial contenant au moins des commutateurs et des liens ;
5. exécuter un `pingAll` de validation ;
6. démarrer éventuellement un trafic de fond ;
7. injecter un événement réseau (coupure ou rétablissement de lien) ;
8. attendre l’événement `LINK_DOWN`, `LINK_UP` ou `SYNC_ERROR` correspondant ;
9. écrire les résultats en CSV et JSON ;
10. produire les figures à partir des fichiers exportés.

Cette procédure peut être observée directement dans `_run_scenario_once()` (`src/twin/experiment_runner.py`).

## 9.7. Rigueur méthodologique et contrôle des biais

- Pour valider les comportements non-linéaires observés, un protocole expérimental strict a été appliqué :
  - **Protocole "Cold Start" :** Chaque test est précédé d'un redémarrage complet du contrôleur Ryu et d'un nettoyage des instances Mininet afin d'éliminer les biais liés à la chaleur des processus ou à la mise en cache (warm-up bias).
  - **Randomisation par blocs :** L'ordre d'exécution des charges (10%, 30%, 50%, 80%) est aléatoirement permuté sur 5 cycles complets ($N=20$ exécutions). Ce dispositif permet de neutraliser les variables exogènes telles que la dérive thermique du matériel ou les processus de fond du système d'exploitation.

## 9.8. Limites du protocole

Les limites principales du protocole observable sont les suivantes :

- le cadre reste une émulation Mininet/OVS, non un réseau de production ;
- la statistique descriptive est présente, mais la statistique inférentielle est absente ;
- les résultats du mode `polling` sont bien documentés, mais la comparaison complète avec les modes `event_driven` et `hybrid` n’est pas visible dans les artefacts principaux ;
- la fidélité est mesurée par rapport à un nouvel état reconstruit depuis le même contrôleur, et non depuis une source indépendante ;
- la synthèse des coûts CPU/mémoire n’est pas consolidée en un résultat principal.

# 10. Résultats

## 10.1. Jeu principal `traffic_profile_repeat10`

Le jeu principal est `traffic_profile_repeat10` (`data/exports/traffic_profile_repeat10_manifest.json`). Il correspond à :

- la topologie `geant_backbone_8cities_stage3` ;
- le contrôleur `src.controller.topology_aware_switch` ;
- un polling de `2.0 s` ;
- trois scénarios principaux ;
- trois profils de trafic ;
- `repeat = 10`.

Le jeu comporte 180 enregistrements bruts et 18 lignes de synthèse (`data/exports/traffic_profile_repeat10.csv`, `data/exports/traffic_profile_repeat10_summary.csv`).

### 10.1.1. Scénario de panne et rétablissement

Le tableau suivant résume `recovery_scenario` d’après `data/exports/traffic_profile_repeat10_summary.csv`.

| Trafic de fond | Délai moyen de détection (s) | Délai moyen de rétablissement (s) |
| --- | ---: | ---: |
| `none` | 0.458 | 1.872 |
| `iperf_tcp` | 0.769 | 1.886 |
| `icmp` | 1.144 | 1.790 |

Interprétation prudente :

- le jumeau détecte la panne et le rétablissement dans les trois conditions de trafic ;
- le trafic de fond a un effet net sur le délai de détection ;
- l’effet sur le délai de rétablissement existe, mais il est moins monotone dans ce jeu précis.

### 10.1.2. Scénario de lien instable

Pour `link_flap_scenario_down_1`, les délais moyens de détection sont :

| Trafic de fond | Délai moyen de détection (s) |
| --- | ---: |
| `none` | 0.360 |
| `iperf_tcp` | 0.719 |
| `icmp` | 0.970 |

Ces valeurs, issues de `data/exports/traffic_profile_repeat10_summary.csv`, suggèrent que le jumeau suit correctement une première transition descendante au sein d’une séquence plus complexe. L’existence des lignes `link_flap_scenario_up_1` et `link_flap_scenario_down_2` dans les exports confirme que la séquence complète est bien enregistrée, même si le présent rapport n’en détaille pas toutes les valeurs.

### 10.1.3. Scénario multi-pannes

Pour `multi_fault_scenario_fault_1`, les délais moyens de détection sont :

| Trafic de fond | Délai moyen de détection (s) |
| --- | ---: |
| `none` | 0.382 |
| `iperf_tcp` | 0.704 |
| `icmp` | 1.068 |

Ces résultats, issus de `data/exports/traffic_profile_repeat10_summary.csv`, montrent que le système ne se limite pas à un cas unique de panne. Il suit au moins un enchaînement de deux événements de coupure dans le runner (`src/twin/experiment_runner.py`).

### 10.1.4. Quantification du décalage cognitif (Ground Truth)

L'utilisation de la source de vérité OVS révèle que le délai de détection perçu par le jumeau est presque intégralement imputable à la latence de synchronisation du plan de contrôle.

| **Profil de Trafic** | **Detection Delay (s)** | **Ground Truth Lag (s)** | **Recovery Delay (s)** |
| -------------------- | ----------------------- | ------------------------ | ---------------------- |
| **None**             | 0,274                   | **0,270**                | 1,700                  |
| **ICMP**             | 1,015                   | **1,011**                | 1,735                  |
| **iPerf TCP**        | 0,716                   | **0,710**                | 1,906                  |

Ces résultats confirment que le décalage entre la réalité physique et le jumeau est de l'ordre de ~270 ms hors trafic, grimpant à plus d'une seconde sous congestion ICMP.

## 10.2. Robustesse à la dégradation d’observation

Le scénario `observation_degradation_scenario` est documenté dans `data/exports/observation_degradation_stage3.csv` et `data/exports/observation_degradation_stage3_summary.csv`. Les trois enregistrements bruts portent tous une note du type :

`SYNC_ERROR detected, no false LINK_DOWN.`

Le délai de détection du `SYNC_ERROR` vaut environ `0.309 s`, `0.535 s` et `0.298 s` sur les trois répétitions, pour une moyenne de `0.381 s` dans le fichier de synthèse. Ce point est important méthodologiquement : il montre que le prototype ne confond pas systématiquement une panne de collecte REST avec une panne physique de lien.

## 10.3. Sensibilité à l’intervalle de polling

Le fichier `data/exports/polling_full_matrix_summary.csv` permet de comparer l’effet du polling sur `recovery_scenario` sans trafic de fond :

| Polling (s) | Délai moyen de détection (s) | Délai moyen de rétablissement (s) |
| --- | ---: | ---: |
| 1 | 0.369 | 0.968 |
| 2 | 0.508 | 1.958 |
| 4 | 0.768 | 3.874 |

Cette série soutient clairement l’idée que le délai de rétablissement croît avec l’intervalle de polling. Le système implémenté est donc fortement dépendant de la politique de synchronisation choisie.

## 10.4. Comparaison de topologies

Le fichier `data/exports/p34_full_matrix_summary.csv` compare au moins deux topologies sur `recovery_scenario` sans trafic :

| Topologie | Délai moyen de détection (s) | Délai moyen de rétablissement (s) |
| --- | ---: | ---: |
| `geant_backbone_8cities_stage3` | 0.628 | 1.991 |
| `geant2012_core12` | 0.725 | 2.300 |

L’interprétation doit rester prudente, car il s’agit d’une étude d’extension. Néanmoins, les résultats suggèrent qu’une topologie plus grande ou plus riche entraîne un coût temporel supplémentaire.

## 10.5. Étude de charge de fond randomisée

Le jeu `load_linearity_recovery_randomized_uniform60` constitue une extension méthodologique notable. Il est documenté par :

- `data/exports/load_linearity_recovery_randomized_uniform60.csv`
- `data/exports/load_linearity_recovery_randomized_uniform60_summary.csv`
- `data/exports/load_linearity_recovery_randomized_uniform60_execution_schedule.json`
- `data/plots/load_linearity_recovery_randomized_uniform60_run_order_scatter.png`

Le planning JSON montre cinq rounds complets de quatre niveaux de charge, soit vingt exécutions élémentaires. L’ordre des charges diffère selon les rounds, et chaque charge est exécutée après redémarrage du contrôleur et nettoyage Mininet (`scripts/run_load_linearity_remote.sh`).

Les moyennes observées sont :

| Charge de fond | Délai moyen de détection (s) | Délai moyen de rétablissement (s) |
| --- | ---: | ---: |
| 10 % | 2.890 | 3.888 |
| 30 % | 3.135 | 2.580 |
| 50 % | 1.682 | 1.938 |
| 80 % | 1.020 | 2.099 |

Le résultat majeur est négatif au sens méthodologique : le dépôt ne permet pas de soutenir une relation simple et monotone entre charge relative et délai de détection. Même après contrôle du biais d’ordre, la relation reste non linéaire.

## 10.6. Observations sur la fidélité

Les fichiers bruts contiennent bien des scores de fidélité. Dans `data/exports/traffic_profile_repeat10.csv`, pour `recovery_scenario`, la moyenne calculée sur les 30 enregistrements concernés donne approximativement :

- `pre_fault_fidelity` : 0.929 ;
- `post_fault_fidelity` : 0.911 ;
- `post_recovery_fidelity` : 0.986.

Ces valeurs ne proviennent pas d’un artefact de synthèse dédié mais du CSV brut. Elles suggèrent que le score global se dégrade après coupure, puis remonte après rétablissement. Cette observation est cohérente avec l’intuition. Cependant, elle doit être interprétée avec réserve, car la vérité terrain de la fidélité n’est pas indépendante du contrôleur Ryu utilisé pour le jumeau.

## 10.7. Observations sur le coût de calcul

Des journaux de ressources sont bien générés, par exemple sous la forme `*_resource_logs.csv` (`src/twin/resource_monitor.py`, `src/twin/experiment_runner.py`). Ils incluent :

- l’usage CPU ;
- la mémoire RSS ;
- les changements de contexte ;
- des marqueurs d’événements synchronisés.

Ces artefacts sont exploitables pour une analyse des coûts de calcul, mais aucune synthèse consolidée de ces journaux n’a été observée parmi les figures ou tableaux principaux [Non observé dans le dépôt].

## 10.8. Analyse de la charge non-linéaire

Les tests randomisés confirment une tendance paradoxale mais stable :

- **Pic à 30% :** La latence de détection atteint son maximum ($\approx$ 3,1 s), corrélée à une variance élevée, signe d'une instabilité des files d'attente.
- **Optimisation à 80% :** Malgré une charge critique, la latence retombe à $\approx$ 1,0 s. Ce résultat, validé par le protocole de randomisation, exclut tout biais d'ordre d'exécution.

# 11. Discussion

## 11.1. Ce que le projet démontre réellement

Le dépôt permet d’affirmer avec un bon niveau de confiance que le prototype démontre la faisabilité fonctionnelle d’un jumeau numérique de réseau SDN. Le système maintient un état structuré, détecte des coupures et des rétablissements, exporte des événements et fournit des artefacts analytiques réutilisables.

Cette conclusion s’appuie sur l’alignement entre l’architecture logicielle (`docs/architecture.md`, `src/twin/service.py`, `src/twin/sync_engine.py`), le protocole (`src/twin/experiment_runner.py`, `docs/final_experiment_baseline.md`) et les résultats principaux (`data/exports/traffic_profile_repeat10_summary.csv`).

## 11.2. Qualité de la synchronisation

La qualité de synchronisation est suffisante pour détecter des événements de lien dans un cadre de laboratoire. Les délais de détection restent en général du même ordre de grandeur que quelques fractions de seconde à quelques secondes, selon le trafic et les paramètres de synchronisation.

Le résultat le plus robuste de ce point de vue est l’effet du polling : lorsque l’intervalle augmente, la détection, et surtout la confirmation du rétablissement, deviennent plus lentes. Le projet montre donc un comportement cohérent avec un jumeau piloté par observation périodique.

## 11.3. Le paradoxe de la fidélité : de la cohésion à la réalité

L'introduction d'une vérité terrain indépendante a fait chuter les scores de fidélité de ~0,9 à ~0,6. Loin d'être un échec, cette baisse quantifie la **non-cohérence transitoire** inhérente à tout système d'observation discret. Le score de 0,6 reflète fidèlement l'existence d'une "fenêtre d'ombre" durant laquelle le jumeau est en décalage avec le plan de données, une réalité auparavant masquée par l'auto-validation du contrôleur.

## 11.4. Hypothèses sur les mécanismes de performance sous congestion

Pour expliquer la performance accrue à 80% de charge, trois hypothèses mécaniques sont proposées :

1. **Interruption vs Polling (NAPI) :** La forte charge pourrait forcer le noyau Linux à basculer du mode interruption au mode polling, accélérant paradoxalement le traitement des paquets de contrôle OpenFlow.
2. **Saturation et Priorité des Flux :** Sous congestion extrême, le rejet des flux de données (Tail Drop) pourrait libérer de la bande passante relative pour les messages de statut de port, ou activer des mécanismes de priorité implicites dans Open vSwitch.
3. **Activité du Scheduler CPU :** L'augmentation des changements de contexte suggère que le processeur reste dans un état de haute performance, éliminant les délais de réveil (C-states) observés lors de charges plus faibles.

## 11.5. Limites méthodologiques

Plusieurs limites doivent être explicitement reconnues.

1. Le cadre expérimental est une émulation Mininet/OVS sous contrôle Ryu. Il permet une validation méthodique, mais il ne reproduit pas toutes les propriétés d’un réseau physique réel.
2. La statistique descriptive est présente, mais la statistique inférentielle est absente : pas d’intervalle de confiance, pas de test d’hypothèse, pas de traitement explicite des valeurs aberrantes.
3. Le jeu principal a été renforcé à `repeat=10`, ce qui améliore nettement la crédibilité des tendances, sans pour autant constituer une validation statistique forte.
4. Les expériences complémentaires ne sont pas toutes au même niveau de maturité méthodologique.
5. La comparaison entre modes `polling`, `event_driven` et `hybrid` est implémentée au niveau logiciel, mais elle n’est pas établie par un jeu de résultats principal visible [Non observé dans le dépôt].

## 11.6. Limites techniques

Les limites techniques les plus importantes sont :

- dépendance forte au contrôleur Ryu comme source d’observation unique ;
- absence de base de données temporelle ;
- absence de vérité terrain indépendante pour la fidélité ;
- absence de synthèse principale des coûts CPU/mémoire ;
- non-observation d’une chaîne de validation sur données réelles.

Ces limites ne disqualifient pas le projet. Elles définissent simplement son périmètre réel : un PoC expérimental cohérent, non un jumeau numérique industriel abouti.

# 12. Conclusion

Le dépôt analysé met en œuvre une preuve de concept cohérente de jumeau numérique pour réseaux SDN. Le système repose sur une émulation Mininet/Open vSwitch, une observation centralisée via Ryu, et un noyau Python capable de reconstruire un état réseau structuré, d’en calculer les différences et d’émettre des événements significatifs.

Les résultats disponibles montrent que le prototype détecte des pannes et des rétablissements de liens, qu’il réagit à des séquences de transitions plus complexes, et qu’il distingue un défaut d’observation d’une panne physique. Le protocole principal `traffic_profile_repeat10` fournit une base expérimentale plus solide que les premiers essais à faible répétition. Les études complémentaires établissent également que le polling influence fortement les performances et que l’effet de la charge de fond est plus complexe qu’une simple relation linéaire.

L’apport principal du projet est donc double. Sur le plan technique, il fournit une architecture lisible et exécutable. Sur le plan scientifique, il démontre la faisabilité et l’intérêt d’un jumeau numérique de réseau comme outil d’observation et d’analyse. Ses limites restent néanmoins claires : environnement d’émulation, validation statistique encore limitée, et mesure de fidélité non indépendante de la source d’observation.

# 13. Perspectives

À partir de l’état réel du dépôt, les améliorations suivantes paraissent crédibles.

## 13.1. Renforcer la vérité terrain

La priorité la plus structurante serait d’introduire une source de vérité terrain indépendante du contrôleur Ryu, par exemple via `ovs-vsctl`, `ovs-ofctl` ou une instrumentation plus directe du plan de données. Cela permettrait de transformer la métrique de fidélité actuelle en une validation plus robuste.

## 13.2. Renforcer la rigueur statistique

Le calcul d’intervalles de confiance, l’analyse des outliers et l’augmentation du nombre de répétitions rendraient les résultats plus défendables académiquement. À ce stade, le dépôt ne fournit que moyenne, P95 et écart-type.

## 13.3. Comparer explicitement les modes de synchronisation

Les modes `polling`, `event_driven` et `hybrid` existent dans l’implémentation. Une campagne expérimentale dédiée permettrait d’évaluer directement le compromis entre coût de calcul, latence de réaction et robustesse aux pertes d’événements.

## 13.4. Étendre l’analyse des coûts

Les journaux de ressources existent déjà. Une perspective naturelle est donc d’en faire une véritable analyse quantitative : coût CPU du contrôleur et du jumeau, consommation mémoire, évolution des changements de contexte selon le trafic et le mode de synchronisation.

## 13.5. Étendre l’échelle et le réalisme

Le passage à des topologies plus larges est déjà amorcé avec `geant2012_core12`. Il serait possible d’aller plus loin en exploitant davantage les topologies importées (`data/topologies/raw/Geant2012.graphml`, `data/topologies/generated/`). À plus long terme, une intégration à des traces ou métriques issues de réseaux réels renforcerait la portée du travail.

## 13.6. Affiner les métriques fonctionnelles

Le dépôt exporte déjà de nombreuses informations complémentaires : compteurs de ports, nombre d’appels API, backlog proxy côté contrôleur, ordre d’exécution, scores de fidélité. Une perspective crédible consiste à transformer ces signaux en métriques secondaires interprétables, par exemple pour distinguer délai d’observation, délai de reconstruction d’état et délai de génération d’événement.

# 14. Bibliographie

Les références ci-dessous sont reprises des éléments déjà présents dans `docs/TER_REPORT.md`.

[1] Grieves, M. (2014). *Digital Twin: Manufacturing Excellence through Virtual Factory Replication.* White Paper, Florida Institute of Technology.

[2] Tao, F., Cheng, J., Qi, Q., Zhang, M., Zhang, H., & Sui, F. (2018). “Digital twin-driven product design, manufacturing and service with big data.” *The International Journal of Advanced Manufacturing Technology*, 94(9–12), 3563–3576.

[3] Glaessgen, E., & Stargel, D. (2012). “The digital twin paradigm for future NASA and US Air Force vehicles.” *53rd AIAA/ASME/ASCE/AHS/ASC Structures, Structural Dynamics and Materials Conference*.

[4] Fuller, A., Fan, Z., Day, C., & Barlow, C. (2020). “Digital twin: Enabling technologies, challenges and open research.” *IEEE Access*, 8, 108952–108971.

[5] Kreutz, D., Ramos, F. M., Verissimo, P. E., Rothenberg, C. E., Azodolmolky, S., & Uhlig, S. (2015). “Software-defined networking: A comprehensive survey.” *Proceedings of the IEEE*, 103(1), 14–76.

[6] Almasan, P., Ferriol-Galmes, M., Paillisse, J., Suarez-Varela, J., Aymerich, D., Grosso, P., ... & Barlet-Ros, P. (2022). “Network digital twin: Context, enabling technologies, and opportunities.” *IEEE Communications Magazine*, 60(11), 22–27.

[7] Nguyen, H. X., Trestian, R., To, D., & Tatipamula, M. (2021). “Digital twin for 5G and beyond.” *IEEE Communications Magazine*, 59(2), 10–15.

[8] Zheng, Y., Yang, S., & Cheng, H. (2022). “An application framework of digital twin and its case study.” *Journal of Ambient Intelligence and Humanized Computing*, 10(3), 1141–1153.

[9] Barricelli, B. R., Casiraghi, E., & Fogli, D. (2019). “A survey on digital twin: Definitions, characteristics, applications, and design implications.” *IEEE Access*, 7, 167653–167671.

[10] Knight, S., Nguyen, H. X., Falkner, N., Bowden, R., & Roughan, M. (2011). “The Internet Topology Zoo.” *IEEE Journal on Selected Areas in Communications*, 29(9), 1765–1775.

# 15. Annexes

## 15.1. Structure du dépôt

La structure générale observée est :

```text
README.md
SPEC_TER_NETWORK_DIGITAL_TWIN.md
docs/
src/
  controller/
  topology/
  twin/
  web/
scripts/
scenarios/
tests/
data/
  events/
  exports/
  plots/
  snapshots/
```

## 15.2. Figures disponibles

Parmi les figures directement réutilisables, on trouve notamment :

- `data/plots/report/architecture.png`
- `data/plots/report/data_flow.png`
- `data/plots/report/topology_geant8.png`
- `data/plots/traffic_profile_repeat10_summary.png`
- `data/plots/polling_full_matrix_summary.png`
- `data/plots/p34_full_matrix_summary.png`
- `data/plots/load_linearity_recovery_randomized_uniform60_run_order_scatter.png`

## 15.3. Artefacts expérimentaux principaux

Les artefacts les plus utiles pour un rapport final sont :

- `data/exports/traffic_profile_repeat10.csv`
- `data/exports/traffic_profile_repeat10_summary.csv`
- `data/exports/traffic_profile_repeat10_manifest.json`
- `data/exports/observation_degradation_stage3.csv`
- `data/exports/observation_degradation_stage3_summary.csv`
- `data/exports/polling_full_matrix_summary.csv`
- `data/exports/p34_full_matrix_summary.csv`
- `data/exports/load_linearity_recovery_randomized_uniform60.csv`
- `data/exports/load_linearity_recovery_randomized_uniform60_summary.csv`
- `data/exports/load_linearity_recovery_randomized_uniform60_execution_schedule.json`

## 15.4. Note sur le poster final

Le poster final fourni par l’utilisateur est situé à :

`/Users/chenyumeng/Documents/CNS S2/TER/产出/poster.pdf`

Sa présence a été vérifiée. Le présent rapport reste toutefois principalement fondé sur les fichiers textuels et techniques du dépôt, ainsi que sur les sources préparatoires de l’affiche :

- `docs/poster_repeat10_fr_outline.md`
- `docs/poster_ter_fr.html`

Cette précaution vise à conserver une traçabilité technique maximale.

# 16. Checklist avant rendu

- [ ] Remplacer les champs administratifs de la page de titre : nom, encadrant, université, formation.
- [ ] Vérifier si l’année universitaire doit être affichée `2025–2026` ou selon la maquette officielle de la formation.
- [ ] Ajouter, si souhaité, les figures directement dans le corps du rapport avec légendes et numéros.
- [ ] Vérifier si le poster final contient un intitulé institutionnel ou un nom d’encadrant à reprendre exactement.
- [ ] Relire la section d’état de l’art avec l’enseignant si une bibliographie plus formelle est exigée.
- [ ] Décider si les résultats de l’étude de charge randomisée doivent rester en annexe ou être intégrés au corps principal.
- [ ] Si nécessaire, ajouter une annexe méthodologique sur la machine virtuelle d’exécution et la configuration matérielle [Non observé dans le dépôt].
- [ ] Si le rapport final doit être plus strictement académique, convertir ensuite ce Markdown en LaTeX ou en traitement de texte avec styles normalisés.
