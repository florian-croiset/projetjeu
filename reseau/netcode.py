# reseau/netcode.py
# Algorithmes de netcode : prediction cote client, reconciliation serveur,
# interpolation d'entites distantes.

import time
import copy
from collections import deque
from parametres import (
    VITESSE_JOUEUR, FORCE_SAUT, GRAVITE, FORCE_DOUBLE_SAUT,
    DISTANCE_DASH, DUREE_DASH, COOLDOWN_DASH, DASH_EN_AIR_MAX, FPS
)


# ======================================================================
#  PREDICTION COTE CLIENT (Client-Side Prediction)
# ======================================================================

class InputEntry:
    """Un input enregistre avec son numero de sequence et l'etat resultant."""
    __slots__ = ('seq', 'commandes', 'predicted_x', 'predicted_y',
                 'predicted_vel_y', 'predicted_sur_sol', 'timestamp')

    def __init__(self, seq, commandes, px, py, pvy, sur_sol):
        self.seq = seq
        self.commandes = commandes
        self.predicted_x = px
        self.predicted_y = py
        self.predicted_vel_y = pvy
        self.predicted_sur_sol = sur_sol
        self.timestamp = time.time()


class ClientPrediction:
    """Gere la prediction du mouvement local et la reconciliation avec le serveur.

    Principe :
    1. A chaque input, on applique la physique localement (prediction)
    2. On stocke l'input + l'etat predit dans un buffer
    3. Quand le serveur confirme un etat, on compare avec notre prediction
    4. Si divergence : on reset a l'etat serveur et on rejoue tous les
       inputs non-confirmes (reconciliation)
    """

    def __init__(self, rects_collision):
        self.input_buffer = deque(maxlen=256)
        self.next_seq = 0
        self.last_confirmed_seq = -1
        self.rects_collision = rects_collision

        # Etat local du joueur (copie legere pour prediction)
        self.local_x = 0
        self.local_y = 0
        self.local_vel_y = 0
        self.local_sur_sol = False
        self.local_direction = 1
        self.local_saut_precedent = False

        # Dash (pour prediction)
        self.local_est_en_dash = False
        self.local_dash_direction = 0
        self.local_dash_distance = 0
        self.local_dash_debut = 0
        self.local_dernier_dash = 0
        self.local_dash_air = DASH_EN_AIR_MAX
        self.local_a_double_saute = False

        # Capacites
        self.peut_double_saut = False
        self.peut_dash = False

        # Seuil de correction (en pixels) — en dessous, on interpole doucement
        self.correction_threshold = 3.0
        self.snap_threshold = 50.0  # Au-dela, teleportation immediate
        self._smooth_x = 0.0
        self._smooth_y = 0.0

    def init_state(self, x, y, vel_y=0, sur_sol=False):
        """Initialise l'etat local depuis le serveur."""
        self.local_x = x
        self.local_y = y
        self.local_vel_y = vel_y
        self.local_sur_sol = sur_sol
        self._smooth_x = float(x)
        self._smooth_y = float(y)

    def record_and_predict(self, commandes, temps_actuel_ms):
        """Enregistre un input, applique la prediction, retourne (seq, x_predit, y_predit)."""
        seq = self.next_seq
        self.next_seq = (self.next_seq + 1) & 0xFFFF

        # Appliquer la physique localement
        self._apply_input(commandes, temps_actuel_ms)

        entry = InputEntry(seq, commandes,
                           self.local_x, self.local_y,
                           self.local_vel_y, self.local_sur_sol)
        self.input_buffer.append(entry)

        return seq, self.local_x, self.local_y

    def reconcile(self, server_x, server_y, server_vel_y, server_sur_sol,
                  last_processed_seq, server_direction):
        """Reconcilie l'etat predit avec l'etat autoritaire du serveur.

        Retourne (final_x, final_y) apres reconciliation.
        """
        self.last_confirmed_seq = last_processed_seq

        # Supprimer tous les inputs confirmes du buffer
        while self.input_buffer and self._seq_lte(self.input_buffer[0].seq, last_processed_seq):
            self.input_buffer.popleft()

        # Verifier divergence avec la prediction au moment du seq confirme
        # On reset a l'etat serveur
        dx = abs(server_x - self.local_x)
        dy = abs(server_y - self.local_y)

        if dx > self.correction_threshold or dy > self.correction_threshold:
            # Correction necessaire
            self.local_x = server_x
            self.local_y = server_y
            self.local_vel_y = server_vel_y
            self.local_sur_sol = server_sur_sol
            self.local_direction = server_direction

            # Rejouer tous les inputs non-confirmes
            for entry in self.input_buffer:
                self._apply_input(entry.commandes, 0)
                entry.predicted_x = self.local_x
                entry.predicted_y = self.local_y

        # Interpolation douce vers la position predite
        if dx <= self.snap_threshold and dy <= self.snap_threshold:
            lerp_speed = 0.2
            self._smooth_x += (self.local_x - self._smooth_x) * lerp_speed
            self._smooth_y += (self.local_y - self._smooth_y) * lerp_speed
        else:
            # Teleportation
            self._smooth_x = float(self.local_x)
            self._smooth_y = float(self.local_y)

        return int(self._smooth_x), int(self._smooth_y)

    def get_smooth_position(self):
        """Retourne la position lissee pour le rendu."""
        return int(self._smooth_x), int(self._smooth_y)

    def _apply_input(self, commandes, temps_actuel_ms):
        """Applique un input a l'etat local (replique la physique serveur)."""
        clavier = commandes.get('clavier', commandes)
        dx = 0
        dy = 0

        if self.local_est_en_dash:
            vitesse_dash = DISTANCE_DASH / (DUREE_DASH / 1000 * FPS)
            deplacement = min(vitesse_dash, self.local_dash_distance)
            dx = deplacement * self.local_dash_direction
            self.local_dash_distance -= abs(deplacement)
            self.local_vel_y += GRAVITE * 0.3
            if self.local_vel_y > 10:
                self.local_vel_y = 10
            dy = self.local_vel_y

            if self.local_dash_distance <= 0:
                self.local_est_en_dash = False
                self.local_dash_distance = 0
        else:
            # Dash
            if clavier.get('dash') and self.peut_dash:
                peut_dasher = self.local_sur_sol or self.local_dash_air > 0
                if peut_dasher:
                    if clavier.get('droite'):
                        self.local_dash_direction = 1
                    elif clavier.get('gauche'):
                        self.local_dash_direction = -1
                    else:
                        self.local_dash_direction = self.local_direction
                    self.local_est_en_dash = True
                    self.local_dash_distance = DISTANCE_DASH
                    if not self.local_sur_sol:
                        self.local_dash_air -= 1

            # Mouvement horizontal
            if clavier.get('gauche'):
                dx = -VITESSE_JOUEUR
                self.local_direction = -1
            if clavier.get('droite'):
                dx = VITESSE_JOUEUR
                self.local_direction = 1

            # Saut
            saut = clavier.get('saut', False)
            if saut and not self.local_saut_precedent:
                if self.local_sur_sol:
                    self.local_vel_y = -FORCE_SAUT
                    self.local_sur_sol = False
                    self.local_a_double_saute = False
                elif self.peut_double_saut and not self.local_a_double_saute:
                    self.local_vel_y = -FORCE_DOUBLE_SAUT
                    self.local_a_double_saute = True
            self.local_saut_precedent = saut

            self.local_vel_y += GRAVITE
            if self.local_vel_y > 10:
                self.local_vel_y = 10
            dy = self.local_vel_y

        # Collisions
        ancien_sur_sol = self.local_sur_sol
        self.local_sur_sol = False

        # Axe X
        self.local_x += dx
        player_rect = [self.local_x, self.local_y, 25, 58]
        for mur in self.rects_collision:
            if self._collide(player_rect, mur):
                if dx > 0:
                    self.local_x = mur.left - 25
                    if self.local_est_en_dash:
                        self.local_est_en_dash = False
                        self.local_dash_distance = 0
                elif dx < 0:
                    self.local_x = mur.right
                    if self.local_est_en_dash:
                        self.local_est_en_dash = False
                        self.local_dash_distance = 0
                player_rect[0] = self.local_x

        # Axe Y
        self.local_y += dy
        player_rect[1] = self.local_y
        for mur in self.rects_collision:
            if self._collide(player_rect, mur):
                if dy > 0:
                    self.local_y = mur.top - 58
                    self.local_vel_y = 0
                    self.local_sur_sol = True
                elif dy < 0:
                    self.local_y = mur.bottom
                    self.local_vel_y = 0
                player_rect[1] = self.local_y

        if self.local_sur_sol and not ancien_sur_sol:
            self.local_dash_air = DASH_EN_AIR_MAX

    @staticmethod
    def _collide(rect_list, mur):
        """Test AABB simple sans pygame.Rect."""
        x, y, w, h = rect_list
        return (x < mur.right and x + w > mur.left and
                y < mur.bottom and y + h > mur.top)

    @staticmethod
    def _seq_lte(a, b):
        """a <= b en sequence circulaire."""
        if a == b:
            return True
        diff = b - a
        if diff < 0:
            diff += 0x10000
        return diff < 0x8000


# ======================================================================
#  INTERPOLATION D'ENTITES (Entity Interpolation)
# ======================================================================

class EntitySnapshot:
    """Un instantane de l'etat d'une entite a un moment donne."""
    __slots__ = ('timestamp', 'x', 'y', 'state')

    def __init__(self, timestamp, x, y, state=None):
        self.timestamp = timestamp
        self.x = x
        self.y = y
        self.state = state  # dict complet pour les autres champs


class EntityInterpolator:
    """Interpole les positions des entites distantes entre deux snapshots.

    On maintient un buffer de ~100ms de retard pour avoir toujours
    deux snapshots entre lesquels interpoler. Cela donne un mouvement
    fluide meme avec des paquets irreguliers.
    """

    def __init__(self, interpolation_delay=0.1):
        self.delay = interpolation_delay  # 100ms par defaut
        self.buffers = {}  # entity_id -> deque de EntitySnapshot
        self.max_buffer = 30  # ~1 seconde a 30 Hz

    def push_state(self, entity_id, x, y, state=None, timestamp=None):
        """Ajoute un nouvel etat recu du serveur."""
        if timestamp is None:
            timestamp = time.time()

        if entity_id not in self.buffers:
            self.buffers[entity_id] = deque(maxlen=self.max_buffer)

        self.buffers[entity_id].append(EntitySnapshot(timestamp, x, y, state))

    def get_interpolated(self, entity_id, render_time=None):
        """Retourne (x, y, state) interpole pour le moment de rendu.

        render_time = time.time() - self.delay (on regarde dans le passe)
        """
        if entity_id not in self.buffers:
            return None

        buf = self.buffers[entity_id]
        if not buf:
            return None

        if render_time is None:
            render_time = time.time() - self.delay

        # Trouver les deux snapshots qui encadrent render_time
        # buf est ordonne chronologiquement
        before = None
        after = None

        for i in range(len(buf) - 1, -1, -1):
            if buf[i].timestamp <= render_time:
                before = buf[i]
                if i + 1 < len(buf):
                    after = buf[i + 1]
                break

        if before is None:
            # Tous les snapshots sont dans le futur — utiliser le plus ancien
            snap = buf[0]
            return snap.x, snap.y, snap.state

        if after is None:
            # Pas de snapshot futur — extrapoler legerement ou utiliser le dernier
            return before.x, before.y, before.state

        # Interpolation lineaire
        total_dt = after.timestamp - before.timestamp
        if total_dt <= 0:
            return after.x, after.y, after.state

        t = (render_time - before.timestamp) / total_dt
        t = max(0.0, min(1.0, t))

        ix = before.x + (after.x - before.x) * t
        iy = before.y + (after.y - before.y) * t

        # Pour l'etat, on prend le plus recent des deux qui est <= render_time
        state = after.state if t > 0.5 else before.state

        return int(ix), int(iy), state

    def remove_entity(self, entity_id):
        """Supprime une entite du buffer d'interpolation."""
        self.buffers.pop(entity_id, None)

    def cleanup(self, active_ids):
        """Supprime les entites qui ne sont plus dans la liste active."""
        dead = [eid for eid in self.buffers if eid not in active_ids]
        for eid in dead:
            del self.buffers[eid]

    def get_latest_state(self, entity_id):
        """Retourne le dernier etat brut recu (sans interpolation)."""
        if entity_id in self.buffers and self.buffers[entity_id]:
            snap = self.buffers[entity_id][-1]
            return snap.x, snap.y, snap.state
        return None


# ======================================================================
#  JITTER BUFFER (pour reguler la reception des paquets)
# ======================================================================

class JitterBuffer:
    """Buffer qui regulise le flux de paquets entrants.

    Stocke les paquets recus et les delivre a intervalle regulier
    meme si l'arrivee est irreguliere (jitter reseau).
    """

    def __init__(self, target_delay_ms=50, max_size=60):
        self.target_delay = target_delay_ms / 1000.0
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self._last_deliver_time = 0

    def push(self, server_tick, data):
        """Ajoute un paquet au buffer."""
        self.buffer.append((time.time(), server_tick, data))

    def pop(self):
        """Retourne le prochain paquet pret a etre delivre, ou None."""
        if not self.buffer:
            return None

        recv_time, tick, data = self.buffer[0]
        now = time.time()

        # Delivrer si assez de temps s'est ecoule depuis la reception
        if now - recv_time >= self.target_delay:
            self.buffer.popleft()
            return (tick, data)

        return None

    def pop_all_ready(self):
        """Retourne tous les paquets prets."""
        results = []
        while True:
            item = self.pop()
            if item is None:
                break
            results.append(item)
        return results

    def flush(self):
        """Vide le buffer et retourne tout."""
        items = [(tick, data) for _, tick, data in self.buffer]
        self.buffer.clear()
        return items
