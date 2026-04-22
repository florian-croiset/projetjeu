# RESEAU.md — Architecture netcode d'Écho

Ce document décrit la couche réseau du jeu **Écho** après la migration vers un
transport hybride TCP + UDP. Il est destiné à l'équipe (et à toute session
Claude Code future) pour diagnostiquer rapidement un problème de connexion,
de latence ou de désynchronisation.

---

## 1. Vue d'ensemble

```
     ┌──────────────────┐                         ┌──────────────────┐
     │    CLIENT        │                         │     SERVEUR       │
     │                  │                         │                  │
     │  TCP  5555  ─────┼─────── handshake ───────┼─→  TCP  5555     │
     │                  │       (id + token)      │                  │
     │                  │                         │                  │
     │  UDP  ephém. ────┼────── gameplay ─────────┼─→  UDP  5556     │
     │                  │   (snapshots + events)  │                  │
     │                  │                         │                  │
     │  TCP keepalive ──┼───── toutes 5 s ────────┼─→ (ignorés)      │
     └──────────────────┘                         └──────────────────┘
```

- **TCP (port 5555)** porte uniquement le handshake initial, le transfert des
  paramètres de session et un keepalive occasionnel. Sert aussi de **fallback**
  intégral si l'UDP échoue.
- **UDP (port 5556 par défaut)** porte tout le gameplay en cours de partie :
  snapshots de positions, état discret, heartbeat, inputs.
- **Relay TCP** (room code) n'est utilisé que pour les connexions via code,
  sans support UDP. Dans ce mode le jeu reste en TCP pur.

Le flag maître `USE_UDP` dans [parametres.py](parametres.py) permet de désactiver
complètement l'UDP pour retomber sur l'ancien chemin TCP.

---

## 2. Format binaire commun

Chaque paquet UDP commence par un **header fixe de 12 octets** (`struct` format
`!IIHBB`) :

| Offset | Taille | Champ      | Rôle                                                     |
|-------:|-------:|------------|----------------------------------------------------------|
|  0     | 4      | `seq`      | Numéro de séquence sortant (uint32, incrémenté à chaque paquet) |
|  4     | 4      | `ack`      | Dernier `seq` reçu du pair                                |
|  8     | 2      | `ack_bits` | Bitfield des 16 `seq` avant `ack` (technique G. Fiedler) |
| 10     | 1      | `channel`  | 0=UNRELIABLE, 1=RELIABLE, 2=CONTROL                      |
| 11     | 1      | `type`     | Sous-type dépendant du canal                              |

Le body qui suit dépend de `channel` + `type`. Voir table §3.

### Exemple hex

Un heartbeat (seq=42, ack=100, ack_bits=0xF0F0, canal=2 CONTROL, type=0x22) :

```
00 00 00 2A  00 00 00 64  F0 F0  02  22
   seq         ack         bits ch type
```

---

## 3. Table des canaux et types

### Canal 0 — UNRELIABLE_SEQUENCED

Fire-and-forget. Drop si le `seq` reçu est plus ancien que le dernier vu.

| Type | Nom                    | Émetteur    | Format body                        | Rôle |
|-----:|------------------------|-------------|------------------------------------|------|
| 0x01 | `TYPE_SNAPSHOT`        | serveur→client | struct : positions joueurs+ennemis | Rendu 30 Hz |
| 0x02 | `TYPE_ETAT_DISCRET`    | (*)            | pickle                             | (réservé, non-utilisé ici) |
| 0x03 | `TYPE_INPUTS_CONTINUS` | client→serveur | pickle du dict clavier             | 60 Hz |

(*) `ETAT_DISCRET` passe aujourd'hui par le canal RELIABLE (cf. ci-dessous).

### Canal 1 — RELIABLE (dedup, livraison au plus une fois)

Retransmission jusqu'à ACK. Livraison "at-most-once" : chaque paquet est
délivré une seule fois, sans garantie d'ordre strict entre types différents.
L'ordre strict est impossible à garantir avec un `seq` global partagé par
les trois canaux (la séquence des paquets RELIABLE peut être 3, 7, 12, …,
jamais 1, 2, 3). Cette limitation est sans impact fonctionnel :

- `TYPE_ETAT_DISCRET` utilise la clé `cle_latest='etat_discret'` pour que
  seule la dernière version en vol soit retransmise.
- `TYPE_INPUT_ONESHOT` est idempotent : rejouer "attaque" ou "echo" deux
  fois par erreur serait perceptible, mais le dédoublonnage par `seq`
  l'empêche.

| Type | Nom                  | Émetteur    | Format body | Rôle                                 |
|-----:|----------------------|-------------|-------------|--------------------------------------|
| 0x02 | `TYPE_ETAT_DISCRET`  | serveur→client | pickle    | État complet (hors positions) 10 Hz |
| 0x10 | `TYPE_INPUT_ONESHOT` | client→serveur | pickle    | echo / echo_dir / torche / interagir |
| 0x11 | `TYPE_VIS_MAP_FULL`  | (réservé)      | —         | envoi initial d'une `vis_map`        |
| 0x12 | `TYPE_EVENT_SON`     | (réservé)      | —         | déclencheur SFX dédié                |

Remarque : les sons transitent aujourd'hui dans `TYPE_ETAT_DISCRET`
(listes `sons` dans chaque joueur/ennemi). Le type 0x12 est prévu pour
une évolution future où on voudra découpler les SFX du snapshot d'état.

### Canal 2 — CONTROL

| Type | Nom                  | Sens            | Rôle |
|-----:|----------------------|-----------------|------|
| 0x20 | `TYPE_HANDSHAKE_UDP` | client→serveur | Preuve de possession du token remis via TCP |
| 0x21 | `TYPE_HANDSHAKE_ACK` | serveur→client | Confirme que l'endpoint client est enregistré |
| 0x22 | `TYPE_HEARTBEAT`     | ↔              | 1 Hz si aucun autre paquet envoyé |
| 0x23 | `TYPE_DISCONNECT`    | ↔              | Fermeture propre |

---

## 4. Format du snapshot

`TYPE_SNAPSHOT` body :

```
uint32 t_serveur_ms                 # pygame.time.get_ticks() côté serveur
uint8  nb_joueurs
  pour chaque :
    int8   id
    float32 x
    float32 y
    float32 vx        # 0.0 aujourd'hui (positions seules suffisent)
    float32 vy
    uint8   flags     # cf. table ci-dessous
uint8  nb_ennemis
  pour chaque :
    uint16  id
    float32 x
    float32 y
    uint8   flags
```

### Flags joueur

| Bit | Nom                       |
|----:|---------------------------|
| 0   | `JFLAG_EN_DASH`           |
| 1   | `JFLAG_EN_ATTAQUE`        |
| 2   | `JFLAG_EST_MORT`          |
| 3   | `JFLAG_DIRECTION_DROITE`  |

### Flags ennemi

| Bit | Nom                |
|----:|--------------------|
| 0   | `EFLAG_EST_MORT`   |
| 1   | `EFLAG_CLIGNOTE`   |

Taille typique pour 2 joueurs + 10 ennemis : **~180 octets**. À 30 Hz ça fait
~5 kB/s par client, contre ~60 kB/s avec l'ancien pickle TCP.

---

## 5. Algorithme ACK + bitfield

Technique décrite par Glenn Fiedler (gafferongames.com).

1. À chaque paquet **envoyé**, le header porte `(ack, ack_bits)` = ce qu'on a
   reçu du pair.
2. À chaque paquet **reçu**, on met à jour notre propre `(ack, ack_bits)` :
   - Si le `seq` reçu est plus récent que notre `ack` courant, on décale le
     bitfield de `(seq - ack)` positions et on positionne le bit
     correspondant à l'ancien `ack`.
   - Si c'est plus ancien (hors ordre), on active directement le bit
     approprié dans le bitfield.
3. En lisant le `(ack, ack_bits)` du pair dans ses paquets, on retire de
   notre file `_en_vol` tous les seq confirmés, et on met à jour le RTT
   par EWMA (α = 0.125).
4. Tout paquet reliable non confirmé après `max(RTT*1.5, 200ms)` est
   retransmis (avec le même `seq`). Le timeout double (back-off) si retry.

Implémentation : [reseau/udp_connexion.py](reseau/udp_connexion.py).

---

## 6. Interpolation client

Le joueur distant est **toujours rendu 100 ms dans le passé** (`INTERP_DELAY_MS`).
Pour chaque snapshot reçu :

1. On pousse `(t_serveur_ms, x, y)` dans un buffer circulaire (4 entrées).
2. On calcule un offset d'horloge : `offset = t_serveur - now_client_monotonic`.
3. À chaque frame, on calcule `t_render = now_client + offset - 100ms`.
4. On cherche les deux snapshots encadrant `t_render` et on fait un
   `lerp((x1,y1), (x2,y2), α)` avec `α = (t_render - t1) / (t2 - t1)`.
5. Si `t_render` est hors plage (paquet en retard), on snap sur le snapshot
   le plus récent.

Le **joueur local** saute ce mécanisme : il reçoit sa position directement
du snapshot (ou, en mode TCP fallback, via l'état discret). Pas d'interp
pour éviter d'ajouter 100 ms de lag d'input.

Implémentation : `pousser_snapshot_interp` / `mettre_a_jour_interp` dans
[core/joueur.py](core/joueur.py) et [core/ennemi.py](core/ennemi.py).

---

## 7. Flux d'une session

### Hôte
1. `Serveur.__init__` bind TCP `:5555` et UDP `:5556`.
2. Thread `boucle_jeu_serveur` tourne à 60 Hz. Par itération :
   - `_udp_pomper()` draine l'endpoint, route par `(ip, port)`.
   - Physique + IA + combat (inchangé).
   - Si une connexion UDP est active, envoie **snapshot** (30 Hz) et
     **état discret reliable** (10 Hz).
   - `_udp_tick()` gère retransmissions + heartbeat.

### Client
1. `connecter()` ouvre TCP, reçoit `{id, udp_token, udp_port}`.
2. `_initier_udp_si_dispo()` : ouvre un socket UDP éphémère, envoie
   `HANDSHAKE_UDP {token}` au serveur. Attend `HANDSHAKE_ACK` jusqu'à
   `UDP_HANDSHAKE_TIMEOUT_MS` (3 s). Retransmet toutes les 200 ms.
3. Si ACK : `self.udp_actif = True`.
4. Sinon : on ferme le socket UDP, on reste en TCP pur (fallback).
5. Dans `boucle_jeu_reseau`, si UDP actif :
   - Envoie inputs continus (unreliable) et one-shot (reliable) par UDP.
   - TCP : un simple `{}` toutes les 5 s comme keepalive.
   - `_udp_pomper_et_appliquer()` applique les snapshots + l'état discret.
   - `_mettre_a_jour_interpolations()` avant `dessiner_jeu()`.

---

## 8. Diagnostic pannes

| Symptôme | Cause probable | Où regarder |
|----------|---------------|-------------|
| Partenaire saccade en WAN | Snapshots perdus, interp buffer vide | Stats `ConnexionUDP.retransmissions`, RTT. Augmenter `INTERP_DELAY_MS`. |
| Partenaire "dans le passé" | `INTERP_DELAY_MS` trop grand | Réduire à 80 ms. |
| Dégât/pickup non appliqué | État discret non ACKé | Vérifier `conn._en_vol` côté serveur, firewall UDP sortant client. |
| Jeu démarre mais reste en TCP | UDP handshake échoué | Log `"UDP handshake échoué"`. Vérifier firewall port 5556, routeur, NAT. Tester direct LAN avant Tailscale. |
| Déconnexion après 5 s de jeu | Timeout UDP (pas de paquet reçu) | Vérifier que le heartbeat circule. Vérifier `UDP_CONNECTION_TIMEOUT_MS`. |
| Input ghost (action répétée) | One-shot retransmis en double | Vérifier la clé `_attendu_reliable` du récepteur ; bug potentiel si on dépasse 2^32 seq. |
| CPU client à 100 % | `pomper()` en boucle sans yield | Confirmer que `horloge.tick(FPS)` est bien atteint dans la boucle Pygame. |

Pour simuler les conditions WAN :

```bash
sudo tc qdisc add dev lo root netem delay 80ms loss 3%
# ... jouer ...
sudo tc qdisc del dev lo root
```

Pour forcer le fallback TCP :

```bash
sudo iptables -A INPUT -p udp --dport 5556 -j DROP
# ... lancer partie, vérifier log "UDP handshake échoué" ...
sudo iptables -D INPUT -p udp --dport 5556 -j DROP
```

---

## 9. Où lire quoi dans le code

| Sujet | Fichier |
|-------|---------|
| Header binaire + format snapshot | [reseau/udp_protocole.py](reseau/udp_protocole.py) |
| Socket non-bloquant + `pomper()` | [reseau/udp_endpoint.py](reseau/udp_endpoint.py) |
| Seq/ack, fiabilité, heartbeat, RTT | [reseau/udp_connexion.py](reseau/udp_connexion.py) |
| Handshake UDP + diffusion serveur | [reseau/serveur.py](reseau/serveur.py) (`_udp_pomper`, `_udp_diffuser_snapshot`, `_udp_diffuser_etat_discret`) |
| Setup UDP client + pompage/intégration Pygame | [boucle_jeu.py](boucle_jeu.py) (`_initier_udp_si_dispo`, `_udp_pomper_et_appliquer`) |
| Interpolation distante | [core/joueur.py](core/joueur.py), [core/ennemi.py](core/ennemi.py) (`mettre_a_jour_interp`) |
| Constantes et flag maître | [parametres.py](parametres.py) (`USE_UDP`, `PORT_UDP`, `TICK_RATE_SNAPSHOT_UDP`, `INTERP_DELAY_MS`, `UDP_HANDSHAKE_TIMEOUT_MS`) |

---

## 10. Sécurité

Un netcode UDP artisanal expose plusieurs surfaces d'attaque. Voici ce qui
est en place aujourd'hui, et ce qui reste du ressort de l'opérateur.

### Mesures déjà implémentées

| # | Menace                                    | Mitigation |
|---|-------------------------------------------|------------|
| 1 | **RCE via `pickle.loads`**                | Tous les payloads reçus du réseau passent par `_pickle_charger_securise` (`reseau/udp_connexion.py`). Un `Unpickler` restreint refuse tout global en dehors des types natifs (int, float, str, bool, list, dict, tuple, bytes, None). Un payload hostile (`__reduce__` → `os.system`) lève `UnpicklingError`. |
| 2 | **Spoofing de token UDP (force brute)**   | Token de 128 bits (`secrets.token_hex(32)`, 64 caractères hex). Au rythme de 10 tentatives / 10 s par IP (voir #3), l'espace est inatteignable. |
| 3 | **Flood de HANDSHAKE_UDP / DoS amplifié** | Rate-limit par IP : `UDP_MAX_HANDSHAKE_PAR_IP = 10` tentatives par fenêtre glissante de 10 s. Au-delà, les paquets sont droppés silencieusement. |
| 4 | **Payload géant / OOM**                   | Header vérifié (12 o mini, 65 535 o maxi = MTU IP). Payload handshake ≤ 512 o. `_pickle_charger_securise` refuse > 5 MB. `recv_complet` TCP capé à 10 MB. |
| 5 | **Token usé plusieurs fois (replay)**     | Token consommé à la première validation (`self.udp_tokens.pop(token)`). |
| 6 | **Token non utilisé qui traîne**          | Expiration automatique après `UDP_TOKEN_TTL_MS = 30 s`. |
| 7 | **Paquet UDP non-sollicité sur un slot**  | Un pair inconnu ne peut pas injecter autre chose qu'un `HANDSHAKE_UDP`. Toute autre paire `(canal, type)` d'une adresse non enregistrée est ignorée. |
| 8 | **Snapshot corrompu**                     | Décodeur `struct` encapsulé dans try/except (retourne `None`), le paquet est droppé sans tuer la boucle. |

### Limitations assumées

- **Pas de chiffrement.** Tout le trafic UDP est en clair. Un attaquant
  MITM peut lire les positions, les sons, l'état de la map — et modifier
  n'importe quel champ s'il peut injecter des paquets dans le flux. Pour
  du jeu student-project en LAN/Tailscale c'est acceptable ; un vrai
  déploiement public devrait envelopper la couche dans DTLS (e.g.
  [pyOpenSSL + DTLS](https://pypi.org/project/dtls/)) ou passer par un
  VPN (Tailscale, WireGuard) qui apporte déjà le chiffrement.
- **Pas d'authentification du pair au-delà du handshake.** Une fois l'IP
  enregistrée, tout paquet de cette IP est accepté. Un attaquant qui
  peut **spoofer** l'adresse IP source de l'hôte légitime (rare sur
  Internet moderne avec BCP38, trivial sur LAN) peut injecter de faux
  inputs. Le HMAC ou DTLS règlerait ça.
- **Le relay TCP n'authentifie pas les clients.** Quiconque connaît un
  code de room peut rejoindre. Codes de 6 caractères alphanumériques =
  36⁶ ≈ 2 milliards, mais les rooms durent 5 min, et un attaquant peut
  brute-forcer à la vitesse du relay. Ajouter un mot de passe optionnel
  serait simple.
- **Le client-serveur de confiance est côté hôte.** Un hôte malveillant
  peut tricher à volonté (visibilité, dégâts, items). C'est acceptable
  pour un jeu coop où l'hôte = "le MJ". En compétitif il faudrait un
  serveur dédié.
- **Pickle restreint ≠ JSON.** `_pickle_charger_securise` bloque le RCE
  mais un attaquant peut toujours construire des structures complexes
  (deeply nested dicts) pour consommer du CPU. Un switch vers JSON
  (plus lent mais plus simple à borner) est une évolution possible.

### Audit rapide (checklist opérateur)

Avant d'exposer le serveur sur un port publiquement accessible :

1. Bloquer le port 5556 UDP au pare-feu et n'ouvrir que vers des IPs
   connues (whitelist).
2. Désactiver `MODE_DEV` (sinon les orbes/capacités se débloquent toutes
   seules et le bouton "envoyer logs" est visible).
3. Exécuter derrière un VPN (Tailscale, WireGuard) pour cumuler le
   chiffrement.
4. Surveiller les logs `"[SERVEUR] UDP handshake"` : un pic suggère un
   scan ; le rate-limiter les droppera mais ça indique l'adversaire.
5. Ne jamais réutiliser le même Python entre `USE_UDP=True` et des
   clients non-fiables : le niveau de durcissement actuel est
   "raisonnable pour un projet étudiant", pas "production Internet".

---

## 11. Limites connues / pistes futures

- Pas de relay UDP : les parties par room-code restent en TCP pur.
- Snapshot ne transporte pas `vx/vy` réels (toujours à 0) ; l'interpolation
  lerp entre deux positions suffit tant que 30 Hz est tenu. Pour extrapoler
  sur gap important, il faudrait calculer la vitesse côté serveur.
- Aucun lissage pour le joueur local (pas de client-side prediction ni
  reconciliation). À la latence extrême l'input reste snappy mais le
  personnage peut bondir si le serveur corrige fortement.
- Les sons sont dans `etat_discret` (reliable), donc jamais perdus mais
  déclenchés avec le délai du canal reliable (~100 ms worst case).
- Les clients se comptent jusqu'à 3 (`_ids_pool = range(3)`), mais tous les
  tests UDP ont été faits avec 2.
