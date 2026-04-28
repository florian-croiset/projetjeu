"""ConnexionUDP : gère un pair distant (seq/ack, fiabilité, heartbeat).

Une instance par peer. Côté serveur, une par client. Côté client, une seule
(vers le serveur). N'effectue AUCUN I/O : toutes les émissions passent par
l'``UdpEndpoint`` fourni à l'init, toutes les réceptions sont poussées via
``traiter_paquet_brut``.

Flux typique (dans la boucle principale) :
    endpoint.pomper() -> pour chaque (data, addr) -> conn.traiter_paquet_brut(data)
    conn.tick(now_ms)                             # retransmit + heartbeat
    for (canal, type_, payload) in conn.drainer_recus():
        appliquer(canal, type_, payload)
"""

import pickle
import io
import time

from reseau import udp_protocole as P


# ---------------------------------------------------------------------------
#  Désérialisation sécurisée
# ---------------------------------------------------------------------------
# ``pickle.loads`` permet l'exécution de code arbitraire via ``__reduce__``. Les
# paquets UDP provenant du réseau doivent impérativement passer par cet
# unpickler restreint qui refuse tout global en dehors des types natifs
# (dicts, listes, tuples, scalaires). Les données échangées en jeu ne
# contiennent que des structures simples, cette restriction est donc sans
# impact fonctionnel.
_PICKLE_GLOBAUX_AUTORISES = {
    ('builtins', 'dict'), ('builtins', 'list'), ('builtins', 'tuple'),
    ('builtins', 'set'), ('builtins', 'frozenset'),
    ('builtins', 'int'), ('builtins', 'float'), ('builtins', 'complex'),
    ('builtins', 'str'), ('builtins', 'bytes'), ('builtins', 'bytearray'),
    ('builtins', 'bool'), ('builtins', 'NoneType'),
}


class _UnpicklerSecurise(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in _PICKLE_GLOBAUX_AUTORISES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"pickle: global interdit sur canal réseau -> {module}.{name}"
        )


def _pickle_charger_securise(data: bytes):
    if not data:
        return None
    # Garde-fou sur la taille pour éviter de mobiliser toute la RAM.
    if len(data) > 5_000_000:
        raise ValueError("payload pickle trop grand")
    return _UnpicklerSecurise(io.BytesIO(data)).load()


MAX_ACK_BITS = 16


class _PaquetEnVol:
    __slots__ = ('seq', 'canal', 'type_', 'data', 'envoye_ms', 'prochain_rtx_ms', 'essais')

    def __init__(self, seq, canal, type_, data, envoye_ms):
        self.seq = seq
        self.canal = canal
        self.type_ = type_
        self.data = data
        self.envoye_ms = envoye_ms
        self.prochain_rtx_ms = envoye_ms + 200
        self.essais = 1


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class ConnexionUDP:
    def __init__(self, endpoint, addr_pair: tuple, heartbeat_ms: int = 1000, timeout_ms: int = 5000):
        self.endpoint = endpoint
        self.addr_pair = addr_pair
        self.heartbeat_ms = heartbeat_ms
        self.timeout_ms = timeout_ms

        # Émission
        self._seq_sortant = 0
        self._en_vol = {}           # seq -> _PaquetEnVol (reliable uniquement)
        # Canal RELIABLE_SEQUENCED implicite : on ne garde qu'un paquet "latest"
        # par (canal, type_) pour certains flux (état discret). Clé -> seq.
        self._latest_par_cle = {}

        # Réception
        self._dernier_seq_recu = 0   # max seq jamais vu
        self._ack_bits = 0           # bitfield des 16 seq avant _dernier_seq_recu

        # Canal unreliable_sequenced : on mémorise le dernier seq traité par type
        # pour ignorer les paquets arrivés hors ordre.
        self._dernier_seq_par_type_unreliable = {}

        # Canal reliable : au-lieu d'une livraison strictement ordonnée (impossible
        # puisque le ``seq`` du header est GLOBAL à tous les canaux), on fait du
        # "deliver-once" (dédoublonnage). Pour nos usages actuels — état discret
        # remplacé en entier via ``cle_latest``, inputs one-shot idempotents — l'ordre
        # strict entre différents types reliable n'est pas requis.
        self._reliable_dedupe = set()

        # File d'événements à drainer par l'appelant.
        self._recus = []             # liste de (canal, type_, payload)

        # Heartbeat / liveness
        now = _now_ms()
        self._dernier_paquet_envoye_ms = now
        self._dernier_paquet_recu_ms = now

        # Stats
        self.rtt_ms = 0.0
        self._rtt_echantillons = 0
        self.paquets_envoyes = 0
        self.paquets_recus = 0
        self.retransmissions = 0

        self.actif = True

    # ------------------------------------------------------------------
    #  ÉMISSION
    # ------------------------------------------------------------------

    def _envoyer_raw(self, canal: int, type_: int, data: bytes) -> int:
        self._seq_sortant = (self._seq_sortant + 1) & 0xFFFFFFFF
        seq = self._seq_sortant
        header = P.encoder_header(seq, self._dernier_seq_recu, self._ack_bits, canal, type_)
        paquet = header + data
        self.endpoint.envoyer(paquet, self.addr_pair)
        self.paquets_envoyes += 1
        self._dernier_paquet_envoye_ms = _now_ms()
        return seq

    def envoyer_unreliable(self, type_: int, data: bytes) -> int:
        return self._envoyer_raw(P.CANAL_UNRELIABLE, type_, data)

    def envoyer_control(self, type_: int, payload=None):
        data = b'' if payload is None else pickle.dumps(payload)
        return self._envoyer_raw(P.CANAL_CONTROL, type_, data)

    def envoyer_reliable(self, type_: int, payload, cle_latest=None):
        """Émet un paquet reliable. ``cle_latest`` : si non-None, les paquets
        antérieurs portant la même clé sont retirés de la file (on ne retransmet
        que la dernière version)."""
        data = pickle.dumps(payload)
        seq = self._envoyer_raw(P.CANAL_RELIABLE, type_, data)
        envol = _PaquetEnVol(seq, P.CANAL_RELIABLE, type_, data, self._dernier_paquet_envoye_ms)
        self._en_vol[seq] = envol

        if cle_latest is not None:
            ancien = self._latest_par_cle.get(cle_latest)
            if ancien is not None and ancien != seq:
                self._en_vol.pop(ancien, None)
            self._latest_par_cle[cle_latest] = seq

        return seq

    # ------------------------------------------------------------------
    #  RÉCEPTION
    # ------------------------------------------------------------------

    def traiter_paquet_brut(self, data: bytes):
        try:
            seq, ack, ack_bits, canal, type_, payload = P.decoder_header(data)
        except ValueError:
            return

        self._dernier_paquet_recu_ms = _now_ms()
        self.paquets_recus += 1

        # Mise à jour ACK sortants (pour annoncer au pair ce qu'on a reçu).
        self._mettre_a_jour_ack_recv(seq)

        # Mise à jour ACK entrants (ce que le pair nous confirme).
        self._traiter_acks_distants(ack, ack_bits)

        # Délivrance au niveau canal
        if canal == P.CANAL_UNRELIABLE:
            dernier = self._dernier_seq_par_type_unreliable.get(type_, 0)
            if dernier and not P.seq_plus_recent(seq, dernier):
                return   # hors séquence : drop
            self._dernier_seq_par_type_unreliable[type_] = seq
            payload_obj = self._decoder_payload(canal, type_, payload)
            self._recus.append((canal, type_, payload_obj))

        elif canal == P.CANAL_CONTROL:
            payload_obj = self._decoder_payload(canal, type_, payload) if payload else None
            self._recus.append((canal, type_, payload_obj))

        elif canal == P.CANAL_RELIABLE:
            if seq in self._reliable_dedupe:
                return   # doublon d'une retransmission, on n'empile rien
            self._reliable_dedupe.add(seq)
            if len(self._reliable_dedupe) > 2048:
                # On garde les 1024 seqs les plus récents et on jette le reste.
                plus_recents = sorted(self._reliable_dedupe, reverse=True)[:1024]
                self._reliable_dedupe = set(plus_recents)
            payload_obj = self._decoder_payload(canal, type_, payload)
            self._recus.append((canal, type_, payload_obj))

    def _decoder_payload(self, canal, type_, payload):
        if canal == P.CANAL_UNRELIABLE and type_ == P.TYPE_SNAPSHOT:
            try:
                return P.decoder_snapshot(payload)
            except Exception:
                return None
        if not payload:
            return None
        try:
            return _pickle_charger_securise(payload)
        except Exception:
            return None

    def _mettre_a_jour_ack_recv(self, seq: int):
        """Met à jour _dernier_seq_recu / _ack_bits (ACK qu'on renvoie)."""
        if self._dernier_seq_recu == 0:
            self._dernier_seq_recu = seq
            self._ack_bits = 0
            return
        if P.seq_plus_recent(seq, self._dernier_seq_recu):
            shift = (seq - self._dernier_seq_recu) & 0xFFFFFFFF
            if shift >= MAX_ACK_BITS:
                self._ack_bits = 0
            else:
                self._ack_bits = ((self._ack_bits << shift) | (1 << (shift - 1))) & 0xFFFF
            self._dernier_seq_recu = seq
        else:
            diff = (self._dernier_seq_recu - seq) & 0xFFFFFFFF
            if 1 <= diff <= MAX_ACK_BITS:
                self._ack_bits |= (1 << (diff - 1))
                self._ack_bits &= 0xFFFF

    def _traiter_acks_distants(self, ack: int, ack_bits: int):
        """Le pair nous dit qu'il a reçu ``ack`` et ``ack_bits`` avant."""
        if ack == 0 and ack_bits == 0:
            return
        now = _now_ms()
        self._confirmer(ack, now)
        for i in range(MAX_ACK_BITS):
            if ack_bits & (1 << i):
                seq_confirme = (ack - (i + 1)) & 0xFFFFFFFF
                if seq_confirme == 0:
                    continue
                self._confirmer(seq_confirme, now)

    def _confirmer(self, seq: int, now_ms: int):
        envol = self._en_vol.pop(seq, None)
        if envol is None:
            return
        rtt = max(0, now_ms - envol.envoye_ms)
        if self._rtt_echantillons == 0:
            self.rtt_ms = float(rtt)
        else:
            self.rtt_ms = 0.125 * rtt + 0.875 * self.rtt_ms
        self._rtt_echantillons += 1

        # Nettoyage latest
        for cle, s in list(self._latest_par_cle.items()):
            if s == seq:
                del self._latest_par_cle[cle]

    # ------------------------------------------------------------------
    #  TICK (appelé chaque frame)
    # ------------------------------------------------------------------

    def tick(self, now_ms: int = None):
        if now_ms is None:
            now_ms = _now_ms()

        # Retransmissions
        if self._en_vol:
            seuil = max(int(self.rtt_ms * 1.5), 200)
            for envol in list(self._en_vol.values()):
                if now_ms >= envol.prochain_rtx_ms:
                    header = P.encoder_header(envol.seq, self._dernier_seq_recu,
                                              self._ack_bits, envol.canal, envol.type_)
                    self.endpoint.envoyer(header + envol.data, self.addr_pair)
                    envol.essais += 1
                    envol.prochain_rtx_ms = now_ms + min(seuil * envol.essais, 2000)
                    self.retransmissions += 1
                    self._dernier_paquet_envoye_ms = now_ms

        # Heartbeat
        if now_ms - self._dernier_paquet_envoye_ms >= self.heartbeat_ms:
            self.envoyer_control(P.TYPE_HEARTBEAT)

        # Timeout
        if now_ms - self._dernier_paquet_recu_ms >= self.timeout_ms:
            self.actif = False

    # ------------------------------------------------------------------
    #  DRAIN
    # ------------------------------------------------------------------

    def drainer_recus(self):
        out = self._recus
        self._recus = []
        return out
