# Affiche académique - version REPEAT=10

## Titre

Jumeau numérique de réseau pour SDN :
validation expérimentale après extension du protocole à REPEAT=10

## Message central

Le projet démontre un PoC de jumeau numérique capable de maintenir un état réseau structuré, de détecter les changements de liens et de distinguer une panne physique d'une dégradation d'observation. L'extension du protocole principal à `repeat=10` renforce la crédibilité statistique des tendances déjà observées.

## Fil directeur retenu pour l'affiche

### 1. Problème de recherche

- Un jumeau numérique utile doit maintenir une image structurée et historisée du réseau
- Il faut mesurer non seulement la détection des pannes, mais aussi le délai, la reprise et la robustesse sémantique

### 2. Architecture du système

- Émulation : Mininet + Open vSwitch
- Observation : API REST de Ryu
- Noyau jumeau : synchronisation, différentiel, génération d'événements
- Sorties : CSV, JSON, graphiques et support web

### 3. Protocole expérimental

- Topologie principale : `geant_backbone_8cities_stage3`
- Trois scénarios : `recovery`, `link_flap`, `multi_fault`
- Trois trafics : `none`, `icmp`, `iperf_tcp`
- Configuration principale : `polling = 2.0 s`
- Mise à jour clé : `repeat=10`, soit 180 enregistrements bruts et 18 lignes de synthèse

### 4. Résultats principaux

- Le système détecte de manière stable les pannes et les reprises
- Le trafic de fond ralentit surtout la détection
- Dans `recovery_scenario`, la détection passe de `0.458 s` sans trafic à `1.144 s` sous `icmp`
- Les délais de reprise restent proches de `1.8-1.9 s`
- Les scénarios `link_flap` et `multi_fault` montrent que le système suit plusieurs transitions successives

### 5. Résultats complémentaires

- Plus l'intervalle de polling est long, plus la reprise est confirmée tardivement
- `recovery mean` : `0.968 s` à `1 s`, `1.958 s` à `2 s`, `3.874 s` à `4 s`
- Sur une topologie plus complexe, détection et reprise deviennent plus lentes
- En cas d'échec d'observation, le système produit `SYNC_ERROR` au lieu d'un faux `LINK_DOWN`

### 6. Discussion et conclusion

- `repeat=10` transforme des indices initiaux en tendances mieux étayées
- Le projet présente une boucle expérimentale cohérente et interprétable
- Les limites restent liées à l'environnement `Mininet + Ryu` et au faible nombre de répétitions pour les expériences étendues

## Choix éditoriaux

- Affiche en portrait
- Langue intégralement en français
- Style institutionnel sobre, sans effets décoratifs
- Lecture en trois colonnes : question, méthode, preuves, conclusion
