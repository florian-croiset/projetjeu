import os
import sys
import json
import datetime

# ============================================================
#  CONFIGURATION — A MODIFIER
# ============================================================

# URL du webhook Discord (obligatoire)
"""
envoyer_logs.py
===============
Capture tout ce qui s'affiche dans la console Python (prints, erreurs)
et l'envoie automatiquement vers un webhook Discord.

INTEGRATION DANS client.py :
==============================

1. Tout en haut de client.py, AVANT tous les autres imports :

    import envoyer_logs
    envoyer_logs.activer_capture()   # démarre la capture console -> fichier .log

2. Le log est envoyé automatiquement à la fermeture/crash du jeu (atexit + excepthook).

3. Pour le bouton manuel (MODE_DEV) dans dessiner_jeu() ou le HUD :
    if envoyer_logs.btn_logs.verifier_clic(event):
        envoyer_logs.envoyer_maintenant()

CONFIGURATION : modifier les constantes ci-dessous.
"""

import os
import sys
import json
import datetime
import atexit
import threading

# ============================================================
#  CONFIGURATION — A MODIFIER
# ============================================================

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1476325807680000264/Ev6bPsEGi2c7FMz-P1mCa3JOuZMMKxngkPOQgONviHVf1v2VSZeu1tkRiOAiKNzhSDL6"

# Chemin du fichier log — toujours dans le même dossier que ce script
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "echo_game.log")

# Nom affiché dans le message Discord
NOM_MACHINE = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "PC inconnu"

# ============================================================


# ---- Classe Tee : écrit dans la console ET dans le fichier simultanément ----

class _Tee:
    """Remplace sys.stdout/stderr : duplique tout vers le fichier log ET la console."""

    def __init__(self, stream_original, fichier_log):
        self._original = stream_original
        self._fichier  = fichier_log

    def write(self, message):
        try:
            self._original.write(message)
            self._original.flush()
        except Exception:
            pass
        try:
            self._fichier.write(message)
            self._fichier.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        try:
            self._fichier.flush()
        except Exception:
            pass

    def fileno(self):
        # Nécessaire pour que pygame ne plante pas
        return self._original.fileno()

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False


# ---- État interne ----

_capture_active  = False
_fichier_log     = None
_envoi_en_cours  = False   # évite les doubles envois


def _rotation_log():
    """
    Lit le fichier log existant, ne garde que la dernière session,
    et réécrit le fichier. Ainsi on conserve toujours les 2 dernières
    sessions (l'ancienne conservée + la nouvelle qui va démarrer).
    """
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            contenu = f.read()

        # Découper par marqueur de session ("=" * 60)
        separateur = "=" * 60
        sessions = contenu.split(separateur)

        # Reconstituer les blocs complets (chaque session = 3 morceaux du split :
        # le séparateur début, le contenu, le séparateur fin)
        # Plus simple : on cherche les positions des marqueurs dans le texte brut
        positions = []
        pos = 0
        while True:
            idx = contenu.find(separateur, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + len(separateur)

        # On veut garder la dernière session complète (2 marqueurs = 1 session)
        # positions[0], positions[1] = début session 1
        # positions[2], positions[3] = début session 2, etc.
        if len(positions) >= 2:
            # Trouver le début de la dernière session = avant-dernier marqueur de début
            # Chaque session commence par 2 séparateurs (début + fin du header)
            # On prend simplement tout ce qui commence au dernier "\n===..." trouvé
            dernier_debut = contenu.rfind("\n" + separateur)
            if dernier_debut > 0:
                derniere_session = contenu[dernier_debut:]
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("[Log: 1 session précédente conservée]\n")
                    f.write(derniere_session)
    except Exception as e:
        # Ne jamais bloquer le jeu pour une rotation de log
        try:
            sys.__stdout__.write("[LOG] Rotation log échouée : {}\n".format(e))
        except Exception:
            pass


def activer_capture():
    """
    Démarre la capture de stdout+stderr vers le fichier log.
    Appelle cette fonction TOUT EN HAUT de client.py avant tout import pygame.

    Enregistre aussi :
      - atexit  : envoi automatique à la fermeture normale
      - excepthook : envoi automatique en cas de crash Python
    """
    global _capture_active, _fichier_log

    if _capture_active:
        return  # déjà actif

    try:
        # Garder seulement les 2 dernières sessions dans le log
        _rotation_log()

        _fichier_log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)

        # Marqueur de session
        separateur = "=" * 60
        _fichier_log.write("\n{}\nSESSION : {}\nMachine : {}\n{}\n".format(
            separateur,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            NOM_MACHINE,
            separateur
        ))
        _fichier_log.flush()

        # Remplacer stdout et stderr par le Tee
        sys.stdout = _Tee(sys.__stdout__, _fichier_log)
        sys.stderr = _Tee(sys.__stderr__, _fichier_log)

        _capture_active = True

        # Envoi automatique à la fermeture normale
        atexit.register(_envoyer_a_la_fermeture)

        # Envoi automatique en cas de crash Python non géré
        _ancien_excepthook = sys.excepthook
        def _excepthook_crash(type_, valeur, tb):
            import traceback
            msg = "".join(traceback.format_exception(type_, valeur, tb))
            print("\n[CRASH] Exception non gérée :\n" + msg)
            _envoyer_a_la_fermeture(raison="CRASH")
            _ancien_excepthook(type_, valeur, tb)
        sys.excepthook = _excepthook_crash

        print("[LOG] Capture console active -> {}".format(LOG_FILE))

    except Exception as e:
        # Ne jamais bloquer le jeu pour ça
        print("[LOG] Impossible d'activer la capture : {}".format(e))


def envoyer_maintenant(raison="Manuel"):
    # Forcer l'écriture du cache sur disque avant lecture
    if _fichier_log:
        try:
            _fichier_log.flush()
            os.fsync(_fichier_log.fileno())
        except Exception:
            pass
    _envoyer_log(raison=raison)


def _envoyer_a_la_fermeture(raison="Fermeture"):
    """Appelé automatiquement par atexit ou excepthook."""
    global _envoi_en_cours
    if _envoi_en_cours:
        return
    _envoi_en_cours = True

    # Flush final pour s'assurer que tout est écrit
    if _fichier_log:
        try:
            _fichier_log.flush()
        except Exception:
            pass

    _envoyer_log(raison=raison)


def _lire_log():
    """Lit le fichier log et retourne son contenu."""
    if not os.path.exists(LOG_FILE):
        return ""
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            contenu = f.read()
        return contenu
    except Exception as e:
        return "[Impossible de lire le log : {}]".format(e)


def _envoyer_log(raison=""):
    """Envoie le fichier log vers Discord (dans un thread séparé pour ne pas bloquer)."""
    def _tache():
        try:
            contenu = _lire_log()

            if not contenu.strip():
                print("[LOG] Log vide — rien à envoyer.")
                return

            _post_discord(contenu, raison)

        except Exception as e:
            # On tente d'écrire directement sur __stderr__ pour ne pas boucler
            try:
                sys.__stderr__.write("[LOG] Erreur envoi Discord : {}\n".format(e))
            except Exception:
                pass

    t = threading.Thread(target=_tache, daemon=True)
    t.start()
    # Si c'est un envoi à la fermeture, attendre que le thread finisse
    if raison in ("Fermeture", "CRASH"):
        t.join(timeout=10)


def _post_discord(contenu, raison=""):
    """Envoie le contenu vers le webhook Discord."""
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
        import requests

    horodatage = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icone = "🔴" if raison == "CRASH" else ("🟡" if raison == "Manuel" else "🟢")

    en_tete = (
        "{} **Echo — Log {}**\n"
        "🖥️ `{}`  |  🕒 `{}`\n"
    ).format(icone, raison, NOM_MACHINE, horodatage)

    MAX_MSG = 1800

    if len(contenu) <= MAX_MSG:
        payload = {"content": en_tete + "```\n{}\n```".format(contenu[-MAX_MSG:])}
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    else:
        # Pièce jointe pour les logs longs
        nom = "log_{}_{}.txt".format(
            NOM_MACHINE,
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        r = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"payload_json": json.dumps({"content": en_tete + "📎 Log complet en pièce jointe :"})},
            files={"file": (nom, contenu.encode("utf-8", errors="replace"), "text/plain")},
            timeout=30
        )

    if r.status_code in (200, 204):
        try:
            sys.__stdout__.write("[LOG] ✅ Envoyé sur Discord ({})\n".format(raison))
        except Exception:
            pass
    else:
        try:
            sys.__stdout__.write("[LOG] ⚠️ Échec Discord : {} {}\n".format(r.status_code, r.text[:100]))
        except Exception:
            pass


# ============================================================
#  BOUTON PYGAME (optionnel, pour le HUD MODE_DEV)
# ============================================================
# Utilisé comme ceci dans dessiner_jeu() de client.py :
#
#   import envoyer_logs
#   if MODE_DEV:
#       envoyer_logs.btn_logs.rect.topleft = (x_fps + 120, y_fps)
#       envoyer_logs.btn_logs.dessiner(surface)
#
# Et dans gerer_evenements_jeu() :
#   if MODE_DEV and envoyer_logs.btn_logs.verifier_clic(event):
#       envoyer_logs.envoyer_maintenant()

def _creer_bouton_logs():
    """Crée le bouton pygame si pygame est disponible, sinon retourne un stub."""
    try:
        import pygame
        from bouton import Bouton
        police = pygame.font.Font(None, 28)
        return Bouton(0, 0, 160, 36, "Envoyer logs", police, style="confirm")
    except Exception:
        class _Stub:
            rect = type('R', (), {'topleft': (0,0), 'x':0, 'y':0})()
            def dessiner(self, *a): pass
            def verifier_clic(self, *a): return False
            def verifier_survol(self, *a): pass
        return _Stub()

# Instancié à la demande (lazy) pour éviter d'importer pygame trop tôt
_btn_logs_instance = None

@property
def _btn_logs_prop():
    global _btn_logs_instance
    if _btn_logs_instance is None:
        _btn_logs_instance = _creer_bouton_logs()
    return _btn_logs_instance

# Accès simple : envoyer_logs.get_bouton()
def get_bouton():
    """Retourne le bouton pygame prêt à l'emploi."""
    global _btn_logs_instance
    if _btn_logs_instance is None:
        _btn_logs_instance = _creer_bouton_logs()
    return _btn_logs_instance


# ============================================================
#  TEST DIRECT
# ============================================================

if __name__ == "__main__":
    if "VOTRE_ID" in DISCORD_WEBHOOK_URL:
        print("Configure DISCORD_WEBHOOK_URL dans envoyer_logs.py !")
        sys.exit(1)

    activer_capture()
    print("Test ligne 1 — ceci doit apparaître dans le log")
    print("Test ligne 2 — machine : {}".format(NOM_MACHINE))
    print("Test ligne 3 — log : {}".format(LOG_FILE))
    envoyer_maintenant(raison="Test")
    import time; time.sleep(3)
    print("Terminé.")