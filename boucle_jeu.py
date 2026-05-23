# boucle_jeu.py
# Mixin pour la boucle de jeu en réseau (input, rendu monde, connexion).

from ui.tutoriel import Tutoriel
from sauvegarde import gestion_parametres

import pygame
import socket
import pickle
import sys
import os
import threading
import time
import copy
import random

from parametres import *
from utils import envoyer_logs, music
from reseau import serveur
from reseau.protocole import recv_complet, send_complet, obtenir_ip_locale
from reseau import udp_protocole as UDP_P
from reseau.udp_endpoint import UdpEndpoint
from reseau.udp_connexion import ConnexionUDP
from ui.camera import calculer_camera, creer_masque_halo
from ui.effets_visuels import appliquer_distortion_echo
from core.carte import Carte
from core.joueur import Joueur
from core.ennemi import Ennemi
from core.demon_slime_boss import DemonSlimeBoss
from core.ame_perdue import AmePerdue
from core.ame_libre import AmeLibre
from core.ame_loot import AmeLoot
from core.cle import Cle
from core.porte import Porte
from core.levier import Levier
from core.mur_payant import MurPayant
from core.orbe_capacite import OrbeCapacite
from core.potion import GestionnairePotions
from core.pancarte_lore import PancarteLore, BulleLore, PopupPaiement, NotificationCapacite, COUT_AMES, COUT_DASH, TEXTE_LETTRE_JONAS
from ui.quete import WidgetQuete, JournalQuete


def _extraire_id_handshake(reponse):
    """Le serveur répond soit un int (mode legacy), soit un dict
    {'id', 'udp_token', 'udp_port'}. On renvoie juste l'ID joueur."""
    if isinstance(reponse, dict):
        return reponse.get('id')
    return reponse


class BoucleJeuMixin:
    """Méthodes de la boucle de jeu : boucle principale, input, rendu, réseau, connexion."""

    # ====================================================================
    #  SÉQUENCE DE FIN
    # ====================================================================

    #  ↓ Modifie ces chemins selon tes assets
    FIN_ENDING_IMAGE  = os.path.join(
        sys._MEIPASS if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.abspath(__file__)),
        "assets", "ending.png")
    FIN_TEASER_IMAGE  = os.path.join(
        sys._MEIPASS if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.abspath(__file__)),
        "assets", "teaser_echo2.png")

    def jouer_sequence_fin(self):
        """Cinématique de fin : fade noir → image fin → fade → teaser Echo II → menu."""

        FADE_LONG_MS    = 1500   # fondu initial (jeu → noir)
        FADE_COURT_MS   = 1000   # fondu entre les deux images
        FADEIN_MS       = 800    # fade-in de chaque image
        LOCK_MS         = 3000   # délai avant de pouvoir appuyer

        lw, lh = self.largeur_ecran, self.hauteur_ecran
        can_proceed = [False]    # flag mutable pour la closure

        # ── helpers ────────────────────────────────────────────────────

        def _charger_image(chemin):
            try:
                img = pygame.image.load(chemin).convert()
                ratio = min(lw / img.get_width(), lh / img.get_height())
                nw, nh = int(img.get_width() * ratio), int(img.get_height() * ratio)
                img = pygame.transform.scale(img, (nw, nh))
                return img, (lw - nw) // 2, (lh - nh) // 2
            except Exception:
                # Fallback si l'image est manquante
                surf = pygame.Surface((lw, lh))
                surf.fill((15, 15, 30))
                return surf, 0, 0

        def _pomper_quit():
            """Pompe les events, quitte proprement sur QUIT, renvoie True si on doit sortir."""
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            return False

        def _fade_vers_noir(duree_ms, snapshot=None):
            """Fondu progressif de `snapshot` (ou écran actuel) vers le noir."""
            debut = pygame.time.get_ticks()
            overlay = pygame.Surface((lw, lh), pygame.SRCALPHA)
            while True:
                elapsed = pygame.time.get_ticks() - debut
                t = min(elapsed / duree_ms, 1.0)
                self.ecran.fill((0, 0, 0))
                if snapshot:
                    self.ecran.blit(snapshot, (0, 0))
                overlay.fill((0, 0, 0, int(255 * t)))
                self.ecran.blit(overlay, (0, 0))
                pygame.display.flip()
                _pomper_quit()
                self.horloge.tick(FPS)
                if elapsed >= duree_ms:
                    break

        def _afficher_ecran(image, ix, iy):
            """Fade-in image, attend 3 s de lock puis n'importe quelle touche."""

            # --- Fade-in ---
            debut_fi = pygame.time.get_ticks()
            while True:
                elapsed = pygame.time.get_ticks() - debut_fi
                t = min(elapsed / FADEIN_MS, 1.0)
                self.ecran.fill((0, 0, 0))
                tmp = image.copy()
                tmp.set_alpha(int(255 * t))
                self.ecran.blit(tmp, (ix, iy))
                pygame.display.flip()
                _pomper_quit()
                self.horloge.tick(FPS)
                if elapsed >= FADEIN_MS:
                    break

            # --- Attente + touche ---
            can_proceed[0] = False
            debut_lock = pygame.time.get_ticks()
            pygame.event.clear()

            while True:
                now = pygame.time.get_ticks()
                if not can_proceed[0] and now - debut_lock >= LOCK_MS:
                    can_proceed[0] = True

                self.ecran.fill((0, 0, 0))
                self.ecran.blit(image, (ix, iy))

                if can_proceed[0] and (now // 600) % 2 == 0:
                    surf_hint = self.police_texte.render(
                        "Appuyez sur une touche pour continuer...", True, (180, 180, 180))
                    self.ecran.blit(surf_hint,
                                    surf_hint.get_rect(centerx=lw // 2, bottom=lh - 28))

                pygame.display.flip()
                self.horloge.tick(FPS)

                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    if can_proceed[0] and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                        return   # l'appelant continue

        # ── Séquence ───────────────────────────────────────────────────

        # 1. Capture du dernier frame de jeu + fade to black
        snapshot_jeu = self.ecran.copy()
        _fade_vers_noir(FADE_LONG_MS, snapshot=snapshot_jeu)
        pygame.time.wait(200)

        # 2. Écran de fin
        img1, x1, y1 = _charger_image(self.FIN_ENDING_IMAGE)
        _afficher_ecran(img1, x1, y1)

        # 3. Transition noire
        snapshot_fin = self.ecran.copy()
        _fade_vers_noir(FADE_COURT_MS, snapshot=snapshot_fin)
        pygame.time.wait(200)

        # 4. Teaser Echo II
        img2, x2, y2 = _charger_image(self.FIN_TEASER_IMAGE)
        _afficher_ecran(img2, x2, y2)

        # 5. Fade final + retour menu
        snapshot_teaser = self.ecran.copy()
        _fade_vers_noir(FADE_COURT_MS, snapshot=snapshot_teaser)

        # ── Nettoyage et retour au menu ─────────────────────────────
        self.etat_jeu = "MENU_PRINCIPAL"
        self.nettoyer_connexion()
        self.actualiser_langues_widgets()

    # ==================================================================
    #  BOUCLE PRINCIPALE DE L'APPLICATION
    # ==================================================================

    def lancer_application(self):
        if not self.parametres.get("meta", {}).get("tutoriel_vu", False):
            tuto = Tutoriel(
                self.ecran, self.largeur_ecran, self.hauteur_ecran,
                self.parametres['controles'],
                self.police_titre, self.police_texte,
                self.police_bouton, self.police_petit
            )
            tuto.lancer()
            self.parametres.setdefault("meta", {})["tutoriel_vu"] = True
            gestion_parametres.sauvegarder_parametres(self.parametres)

        while self.running:
            self.temps_anim = pygame.time.get_ticks()
            pos_souris      = pygame.mouse.get_pos()

            if self.etat_jeu == "MENU_PRINCIPAL":
                self.gerer_menu_principal(pos_souris)
                self.dessiner_menu_principal()

            elif self.etat_jeu == "MENU_REJOINDRE":
                self.gerer_menu_rejoindre(pos_souris)
                self.dessiner_menu_rejoindre()

            elif self.etat_jeu in ("MENU_NOUVELLE_PARTIE", "MENU_CONTINUER"):
                self.gerer_menu_slots(pos_souris)
                self.dessiner_menu_slots()

            elif self.etat_jeu == "MENU_CONFIRMATION":
                self.gerer_menu_confirmation(pos_souris)
                self.dessiner_menu_confirmation()

            elif self.etat_jeu == "MENU_PARAMETRES":
                if not self.parametres_temp:
                    self.parametres_temp = copy.deepcopy(self.parametres)
                self.gerer_menu_parametres(pos_souris)
                self.dessiner_menu_parametres()

            elif self.etat_jeu == "MENU_LUMINOSITE":
                self.gerer_menu_luminosite(pos_souris)
                if self.etat_jeu == "MENU_LUMINOSITE":
                    self.dessiner_menu_luminosite()

            elif self.etat_jeu == "EN_JEU":
                if self.etat_jeu_interne != "PAUSE":
                    self.etat_jeu_interne = "JEU"
                self.boucle_jeu_reseau()
                if self.etat_jeu == "MENU_PARAMETRES":
                    self.etat_jeu_precedent = "EN_JEU"
                    self.parametres_temp    = copy.deepcopy(self.parametres)
                elif self.etat_jeu != "EN_JEU":
                    self.etat_jeu = "MENU_PRINCIPAL"
                    self.nettoyer_connexion()
                    self.actualiser_langues_widgets()

            elif self.etat_jeu == "QUITTER":
                self.running = False

            pygame.display.flip()
            self.horloge.tick(FPS)

        pygame.quit()
        sys.exit()

    # ==================================================================
    #  GESTION DES ÉVÉNEMENTS EN JEU
    # ==================================================================

    def _son_attaque(self, joueur):
        """Slash2/Slash3 si un ennemi est dans la portée d'attaque, sinon Slash1."""
        if joueur.direction == 1:
            rect_a = pygame.Rect(joueur.rect.right, joueur.rect.y, PORTEE_ATTAQUE, joueur.rect.height)
        else:
            rect_a = pygame.Rect(joueur.rect.left - PORTEE_ATTAQUE, joueur.rect.y, PORTEE_ATTAQUE, joueur.rect.height)
        for ennemi in self.ennemis_locaux.values():
            if not ennemi.est_mort and rect_a.colliderect(ennemi.rect):
                return random.choice(['slash2', 'slash3'])
        return 'attaque'

    def gerer_evenements_jeu(self):
        commandes = {
            'clavier':        {'gauche': False, 'droite': False,
                            'saut': False, 'attaque': False, 'dash': False},
            'echo':           False,
            'echo_dir':       False,
            'toggle_torche':  False,
            'interagir':      False,
        }

        key = self._codes_touches.get

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                envoyer_logs.envoyer_maintenant()

            if event.type == pygame.KEYDOWN and event.key == self._codes_touches.get('journal'):
                if hasattr(self, 'journal_quete') and self.journal_quete:
                    self.journal_quete.toggle()
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == self._codes_souris.get('journal'):
                if hasattr(self, 'journal_quete') and self.journal_quete:
                    self.journal_quete.toggle()
                continue

            # Laisser la bulle et la popup consommer les events en priorité
            if self.bulle_lore and self.bulle_lore.visible:
                if self.bulle_lore.gerer_event(event):
                    continue
            if self.popup_paiement and self.popup_paiement.visible:
                if self.popup_paiement.gerer_event(event):
                    continue

            # Si le journal est ouvert, bloquer tous les inputs de jeu
            if hasattr(self, 'journal_quete') and self.journal_quete and self.journal_quete.ouvert:
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    try:
                        self._dernier_frame_jeu = self.ecran.copy()
                    except Exception:
                        self._dernier_frame_jeu = None
                    self.etat_jeu_interne = "PAUSE"
                    music.pause()
                if event.key == key('attaque'):
                    commandes['clavier']['attaque'] = True
                    _j = self.joueurs_locaux.get(self.mon_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attaque_local_debut_ms >= COOLDOWN_ATTAQUE:
                        music.jouer_sfx(self._son_attaque(_j) if _j else 'attaque')
                        if _j:
                            _j._attaque_local_debut_ms = now
                if event.key == key('echo'):
                    commandes['echo'] = True
                    music.jouer_sfx('echo')
                    if DISTORTION_ECHO_ACTIVE:
                        _je = self.joueurs_locaux.get(self.mon_id)
                        _now = pygame.time.get_ticks()
                        if _je and _now - getattr(_je, '_dernier_echo_local_ms', -COOLDOWN_ECHO) >= COOLDOWN_ECHO:
                            _je._dernier_echo_local_ms = _now
                            if not hasattr(self, '_distortions_echo'):
                                self._distortions_echo = []
                            self._distortions_echo.append({
                                'start_ms':  _now,
                                'wx':        _je.rect.centerx,
                                'wy':        _je.rect.centery,
                                'rayon_max': PORTEE_ECHO,
                                'duree_ms':  ECHO_DUREE_REVEAL,
                            })
                if event.key == key('dash'):
                    commandes['clavier']['dash'] = True
                    music.jouer_sfx('dash')
                if event.key == key('echo_dir'):
                    commandes['echo_dir'] = True
                    music.jouer_sfx('echo_dir')
                    if DISTORTION_ECHO_ACTIVE:
                        _je = self.joueurs_locaux.get(self.mon_id)
                        _now = pygame.time.get_ticks()
                        if (_je and getattr(_je, 'peut_echo_dir', False)
                                and _now - getattr(_je, '_dernier_echo_dir_local_ms', -COOLDOWN_ECHO_DIR) >= COOLDOWN_ECHO_DIR):
                            _je._dernier_echo_dir_local_ms = _now
                            if not hasattr(self, '_distortions_echo'):
                                self._distortions_echo = []
                            self._distortions_echo.append({
                                'start_ms':  _now,
                                'wx':        _je.rect.centerx,
                                'wy':        _je.rect.centery,
                                'rayon_max': PORTEE_ECHO_DIR,
                                'duree_ms':  int(PORTEE_ECHO_DIR / PORTEE_ECHO * ECHO_DUREE_REVEAL),
                            })
                if event.key == key('torche'):
                    commandes['toggle_torche'] = True
                    if not self.torche.allumee:
                        music.torche_boucle_start()
                    else:
                        music.torche_boucle_stop()

                # Touche interaction (F par défaut)
                if event.key == key('interagir'):
                    mon_joueur = self.joueurs_locaux.get(self.mon_id)
                    if mon_joueur and not self.bulle_lore.visible and not self.popup_paiement.visible:
                        pancarte_proche = None
                        for i, pancarte in self.pancartes_lore_locales.items():
                            dx = mon_joueur.rect.centerx - pancarte.rect.centerx
                            dy = mon_joueur.rect.centery - pancarte.rect.centery
                            if (dx**2 + dy**2) ** 0.5 <= PancarteLore.PORTEE_INTERACTION:
                                pancarte_proche = (i, pancarte)
                                break
                        if pancarte_proche:
                            i, pancarte = pancarte_proche
                            if pancarte.est_debloquee:
                                type_p = getattr(pancarte, 'type_pancarte', 'lore')
                                if type_p == 'lettre':
                                    self.bulle_lore.ouvrir(
                                        TEXTE_LETTRE_JONAS,
                                        titre="✦   Lettre de Jonas   ✦",
                                        sous_titre="— Trouvée dans les profondeurs —",
                                    )
                                elif type_p == 'shop_dash':
                                    from core.pancarte_lore import TEXTE_LORE_DASH
                                    self.bulle_lore.ouvrir(TEXTE_LORE_DASH)
                                else:
                                    self.bulle_lore.ouvrir()
                            else:
                                self._pancarte_active_id = i

                                def _callback_paiement():
                                    self._achat_en_attente = self._pancarte_active_id

                                type_p = getattr(pancarte, 'type_pancarte', 'lore')
                                if type_p == 'shop_dash':
                                    self.popup_paiement._titre_popup = "Fragment de Mémoire"
                                    self.popup_paiement._message_popup = f"Absorber ce souvenir — {COUT_DASH} âmes ?"
                                else:
                                    self.popup_paiement._titre_popup = "Pancarte mystérieuse"
                                    self.popup_paiement._message_popup = f"Payer {COUT_AMES} âmes pour révéler ce secret ?"
                                cout = COUT_DASH if type_p == 'shop_dash' else COUT_AMES
                                self.popup_paiement.ouvrir_confirmation(
                                    mon_joueur.argent,
                                    _callback_paiement,
                                    cout
                                )
                        elif (self.mur_payant_local
                              and not self.mur_payant_debloque):
                            mp = self.mur_payant_local
                            dx = mon_joueur.rect.centerx - (mp.x + TAILLE_TUILE // 2)
                            dy = mon_joueur.rect.centery - (mp.y + TAILLE_TUILE // 2)
                            if dx*dx + dy*dy <= mp.PORTEE_INTERACTION ** 2:
                                self._achat_en_attente = 'mur_payant'

            if event.type == pygame.MOUSEBUTTONDOWN:
                ms = self._codes_souris.get
                if ms('attaque') and event.button == ms('attaque'):
                    commandes['clavier']['attaque'] = True
                    _j = self.joueurs_locaux.get(self.mon_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attaque_local_debut_ms >= COOLDOWN_ATTAQUE:
                        music.jouer_sfx(self._son_attaque(_j) if _j else 'attaque')
                        if _j:
                            _j._attaque_local_debut_ms = now
                if ms('echo') and event.button == ms('echo'):
                    commandes['echo'] = True
                    music.jouer_sfx('echo')
                if ms('dash') and event.button == ms('dash'):
                    commandes['clavier']['dash'] = True
                    music.jouer_sfx('dash')
                if ms('echo_dir') and event.button == ms('echo_dir'):
                    commandes['echo_dir'] = True
                    music.jouer_sfx('echo_dir')

        touches = pygame.key.get_pressed()
        if key('gauche') and touches[key('gauche')]:
            commandes['clavier']['gauche'] = True
        if key('droite') and touches[key('droite')]:
            commandes['clavier']['droite'] = True
        if key('saut') and touches[key('saut')]:
            commandes['clavier']['saut'] = True
        if self._codes_souris:
            souris = pygame.mouse.get_pressed(num_buttons=5)
            for action in ('gauche', 'droite', 'saut'):
                btn = self._codes_souris.get(action)
                if btn and 1 <= btn <= 5 and souris[btn - 1]:
                    commandes['clavier'][action] = True

        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if mon_joueur and mon_joueur.pv <= 0:
            commandes['clavier']       = {'gauche': False, 'droite': False,
                                          'saut': False, 'attaque': False, 'dash': False}
            commandes['echo']          = False
            commandes['echo_dir']      = False
            commandes['toggle_torche'] = False
            commandes['interagir']     = False

        if getattr(self, '_achat_en_attente', None) is not None:
            commandes['interagir'] = True
            self._achat_en_attente = None

        commandes['pseudo'] = getattr(self, '_profil_pseudo', '')
        commandes['skin']   = getattr(self, '_profil_skin', 0)

        return commandes

    # ==================================================================
    #  RENDU DU MONDE DE JEU
    # ==================================================================

    def dessiner_jeu(self):
        self._init_hud_cache()
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur or not self.carte or not self.vis_map_locale:
            self.ecran.fill(COULEUR_FOND)
            return

        zoom = self.zoom_effectif
        lv   = int(self.largeur_ecran / zoom)
        hv   = int(self.hauteur_ecran / zoom)
        if not hasattr(self, '_surface_virtuelle') or self._surface_virtuelle.get_size() != (lv, hv):
            self._surface_virtuelle = pygame.Surface((lv, hv))
        surface_virtuelle = self._surface_virtuelle

        lm = self.carte.largeur_map * TAILLE_TUILE
        hm = self.carte.hauteur_map * TAILLE_TUILE
        camera_offset = calculer_camera(mon_joueur.rect,
                                        self.largeur_ecran, self.hauteur_ecran,
                                        zoom, lm, hm)

        self.carte.dessiner_carte(surface_virtuelle, self.vis_map_locale, camera_offset)

        # --- Fondu progressif des tuiles révélées par écho ---
        if self._fade_surface is not None and ASSOMBRISSEMENT:
            now_fade = pygame.time.get_ticks()

            # Torche allumée : maintient les tuiles de son rayon visibles
            if getattr(self, 'torche', None) and self.torche.allumee:
                tx_world = self.torche.x + TAILLE_TUILE // 2
                ty_world = self.torche.y + TAILLE_TUILE // 2
                r = RAYON_LUMIERE_TORCHE
                t_min_x = max(0, int((tx_world - r) // TAILLE_TUILE))
                t_max_x = min(self.carte.largeur_map - 1, int((tx_world + r) // TAILLE_TUILE))
                t_min_y = max(0, int((ty_world - r) // TAILLE_TUILE))
                t_max_y = min(self.carte.hauteur_map - 1, int((ty_world + r) // TAILLE_TUILE))
                r2 = r * r
                for tty in range(t_min_y, t_max_y + 1):
                    for ttx in range(t_min_x, t_max_x + 1):
                        cx = ttx * TAILLE_TUILE + TAILLE_TUILE // 2
                        cy = tty * TAILLE_TUILE + TAILLE_TUILE // 2
                        if (cx - tx_world) ** 2 + (cy - ty_world) ** 2 <= r2:
                            self.echo_fade_times[(ttx, tty)] = now_fade
                            if not self.vis_map_locale[tty][ttx]:
                                self.vis_map_locale[tty][ttx] = True
                                self.carte._tuiles_a_reveler.append((ttx, tty))
                                self.carte._vis_map_dirty = True

            expirés = []
            for (tx, ty), t_reveal in self.echo_fade_times.items():
                age = now_fade - t_reveal
                if age >= DUREE_FADE_ECHO:
                    expirés.append((tx, ty))
                    alpha = 255
                else:
                    alpha = int(age * 255 / DUREE_FADE_ECHO)
                self._fade_surface.fill(
                    (0, 0, 0, alpha),
                    pygame.Rect(tx * TAILLE_TUILE, ty * TAILLE_TUILE,
                                TAILLE_TUILE, TAILLE_TUILE))
            for tile in expirés:
                del self.echo_fade_times[tile]
            off_x, off_y = camera_offset
            surface_virtuelle.blit(self._fade_surface, (0, 0),
                                   pygame.Rect(off_x, off_y, lv, hv))

        # --- Portes ---
        ticks_render_portes = pygame.time.get_ticks()
        for porte in self.portes_locales.values():
            porte.dessiner(surface_virtuelle, camera_offset, ticks_render_portes)

        # --- Potions ---
        if hasattr(self, 'potions') and self.potions is not None:
            self.potions.dessiner(surface_virtuelle, camera_offset)

        # --- Orbes de capacité ---
        off_x, off_y = camera_offset
        camera_rect = pygame.Rect(off_x, off_y, lv, hv)
        ticks_render = pygame.time.get_ticks()
        for orbe in self.orbes_capacite_locaux.values():
            if orbe.est_ramasse:
                continue
            orbe.mettre_a_jour(ticks_render)
            if not camera_rect.colliderect(orbe.rect):
                continue
            if orbe.capacite == 'double_saut' and getattr(mon_joueur, 'peut_double_saut', False):
                continue
            if orbe.capacite == 'dash' and getattr(mon_joueur, 'peut_dash', False):
                continue
            if orbe.capacite == 'echo_dir' and getattr(mon_joueur, 'peut_echo_dir', False):
                continue
            orbe.dessiner(surface_virtuelle, camera_offset, ticks_render)

        # --- Pancartes de lore ---
        touche_interagir = self.parametres.get('controles', {}).get('interagir', 'f')
        for pancarte in self.pancartes_lore_locales.values():
            pancarte.mettre_a_jour(ticks_render)
            if camera_rect.colliderect(pancarte.rect):
                pancarte.dessiner(surface_virtuelle, camera_offset, ticks_render,
                                  touche_interagir=touche_interagir)

        # --- Joueurs ---
        for joueur in self.joueurs_locaux.values():
            joueur.dessiner(surface_virtuelle, camera_offset)

        temps_ms = pygame.time.get_ticks()

        # --- Ennemis ---
        detection_sq = DISTANCE_DETECTION_ENNEMI * DISTANCE_DETECTION_ENNEMI
        for ennemi in self.ennemis_locaux.values():
            if not camera_rect.colliderect(ennemi.rect):
                continue
            if mon_joueur:
                dx   = ennemi.rect.centerx - mon_joueur.rect.centerx
                dy   = ennemi.rect.centery - mon_joueur.rect.centery
                dist_sq = dx*dx + dy*dy
            else:
                dist_sq = 9999 * 9999

            temps_depuis_flash = temps_ms - getattr(ennemi, 'flash_echo_temps', 0)
            flash_actif        = temps_depuis_flash < DUREE_FLASH_ECHO_ENNEMI
            proche             = dist_sq <= detection_sq

            if proche:
                ennemi.dessiner(surface_virtuelle, camera_offset)

        # --- Boss ---
        if self.boss_local and not getattr(self.boss_local, 'is_dead', False):
            off_x, off_y = camera_offset
            self.boss_local.pos.x -= off_x
            self.boss_local.pos.y -= off_y
            self.boss_local.draw(surface_virtuelle)
            self.boss_local.pos.x += off_x
            self.boss_local.pos.y += off_y

        if mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        # --- Âmes (avec culling caméra) ---
        for ame in self.ames_perdues_locales.values():
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms,
                             argent_max=getattr(ame, '_argent_max', None))
        for ame in self.ames_libres_locales.values():
            ame.mettre_a_jour(temps_ms)
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms)
        for ame in self.ames_loot_locales.values():
            ame.mettre_a_jour_visuels(temps_ms, self.carte)
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Clé (image clé, pas orbe) ---
        if self.cle_locale and not self.cle_locale.est_ramassee:
            self.cle_locale.mettre_a_jour(temps_ms)
            if camera_rect.colliderect(self.cle_locale.rect):
                self.cle_locale.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Torche ---
        self.torche.mettre_a_jour(temps_ms)
        self.torche.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Leviers ---
        for levier in self.leviers_locaux.values():
            levier.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Mur payant ---
        if self.mur_payant_local and not self.mur_payant_debloque:
            self.mur_payant_local.dessiner(surface_virtuelle, camera_offset,
                                           joueur_rect=mon_joueur.rect)

        if self.torche.allumee and mon_joueur:
            dx   = mon_joueur.rect.centerx - self.torche.x
            dy   = mon_joueur.rect.centery - self.torche.y
            dist = (dx**2 + dy**2) ** 0.5
            music.torche_mettre_a_jour_volume(dist)

        # --- Calque obscurité ---
        if mon_joueur and ASSOMBRISSEMENT:
            sz = surface_virtuelle.get_size()
            if not hasattr(self, '_obscurite') or self._obscurite.get_size() != sz:
                self._obscurite = pygame.Surface(sz, pygame.SRCALPHA)
            obscurite = self._obscurite
            lum = self.parametres.get('video', {}).get('luminosite', 0.3)
            alpha_base = int(220 * (1.0 - lum * 0.8))
            if getattr(self, '_halo_alpha_max', None) != alpha_base:
                self._masque_halo_joueur = creer_masque_halo(RAYON_HALO_JOUEUR, HALO_DEGRADE_ETENDUE, alpha_max=alpha_base)
                self._masque_halo_torche = creer_masque_halo(RAYON_LUMIERE_TORCHE, HALO_DEGRADE_ETENDUE, alpha_max=alpha_base)
                self._halo_alpha_max = alpha_base
            obscurite.fill((0, 0, 10, alpha_base))
            rayon = RAYON_HALO_JOUEUR
            cx = mon_joueur.rect.centerx - camera_offset[0]
            cy = mon_joueur.rect.centery - camera_offset[1]
            obscurite.blit(self._masque_halo_joueur,
                           (cx - rayon - 1, cy - rayon - 1),
                           special_flags=pygame.BLEND_RGBA_MIN)
            if self.torche.allumee:
                rayon_t = RAYON_LUMIERE_TORCHE
                tx = self.torche.x + TAILLE_TUILE // 2 - camera_offset[0]
                ty = self.torche.y + TAILLE_TUILE     - camera_offset[1]
                obscurite.blit(self._masque_halo_torche,
                               (tx - rayon_t - 1, ty - rayon_t - 1),
                               special_flags=pygame.BLEND_RGBA_MIN)
            surface_virtuelle.blit(obscurite, (0, 0))

        # --- Distortion d'écho ---
        if DISTORTION_ECHO_ACTIVE and getattr(self, '_distortions_echo', None):
            t_now_dist = pygame.time.get_ticks()
            self._distortions_echo = [
                o for o in self._distortions_echo
                if t_now_dist - o['start_ms'] < o['duree_ms']
            ]
            if self._distortions_echo:
                ondes_ecran = [{
                    'start_ms':  o['start_ms'],
                    'sx':        o['wx'] - camera_offset[0],
                    'sy':        o['wy'] - camera_offset[1],
                    'rayon_max': o['rayon_max'],
                    'duree_ms':  o['duree_ms'],
                } for o in self._distortions_echo]
                appliquer_distortion_echo(surface_virtuelle, ondes_ecran, t_now_dist)

        # --- Badge torche ---
        if self.torche.jamais_utilisee and mon_joueur:
            dx = mon_joueur.rect.centerx - self.torche.x
            dy = mon_joueur.rect.centery - self.torche.y
            if (dx**2 + dy**2)**0.5 <= DISTANCE_TORCHE_ECHO * 3:
                self._dessiner_badge_torche(surface_virtuelle, camera_offset)

        if mon_joueur and mon_joueur.pv <= 0:
            if self._mort_depuis is None:
                music.jouer_sfx('mort')
            self._dessiner_ecran_mort(surface_virtuelle)
        elif mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        surface_zoomee = pygame.transform.scale(
            surface_virtuelle, (self.largeur_ecran, self.hauteur_ecran))
        self.ecran.blit(surface_zoomee, (0, 0))

        # Pseudos rendus directement sur l'écran final (post-scale) pour rester nets.
        for joueur in self.joueurs_locaux.values():
            joueur.dessiner_pseudo_ecran(self.ecran, camera_offset, zoom)

        if MODE_DEV:
            btn = envoyer_logs.get_bouton()
            btn.rect.topleft = (self.largeur_ecran - 175, 140)
            btn.verifier_survol(pygame.mouse.get_pos())
            btn.dessiner(self.ecran)

        self.dessiner_hud()

    # ==================================================================
    #  BOUCLE JEU RÉSEAU
    # ==================================================================

    def _thread_reseau(self):
        """Thread dédié au réseau : envoie les commandes, reçoit l'état du serveur."""
        while self._reseau_actif and self.running:
            try:
                with self._reseau_lock:
                    cmd = copy.copy(self._commandes_a_envoyer)

                send_complet(self.client_socket, cmd)
                donnees = recv_complet(self.client_socket)

                with self._reseau_lock:
                    if self._dernier_etat_serveur is not None and self._nouvel_etat_disponible:
                        ancien_delta = self._dernier_etat_serveur.get('vis_delta')
                        if ancien_delta and donnees.get('vis_map') is None:
                            nouveau_delta = donnees.get('vis_delta')
                            if nouveau_delta is not None:
                                donnees['vis_delta'] = ancien_delta + nouveau_delta
                            else:
                                donnees['vis_delta'] = ancien_delta
                        ancien_full = self._dernier_etat_serveur.get('vis_map')
                        if ancien_full is not None and donnees.get('vis_map') is None:
                            donnees['vis_map'] = ancien_full
                    self._dernier_etat_serveur = donnees
                    self._nouvel_etat_disponible = True

            except (EOFError, socket.timeout, socket.error, OSError) as e:
                with self._reseau_lock:
                    self._erreur_reseau = str(e)
                break
            except (pickle.UnpicklingError, ValueError):
                continue

    def _appliquer_etat_serveur(self, donnees_recues):
        """Applique l'état reçu du serveur aux entités locales."""
        # --- Horloge serveur ---
        t_serveur = donnees_recues.get('t')
        if t_serveur is not None:
            now_ms = int(time.monotonic() * 1000)
            self.udp_offset_serveur_ms = t_serveur - now_ms

        # --- Vis map ---
        if donnees_recues.get('vis_map') is not None:
            self.vis_map_locale = donnees_recues['vis_map']
            if self.carte:
                self.carte._vis_map_dirty = True
        if donnees_recues.get('vis_delta') and self.vis_map_locale:
            now_fade = pygame.time.get_ticks()
            for x, y in donnees_recues['vis_delta']:
                self.vis_map_locale[y][x] = True
                self.echo_fade_times[(x, y)] = now_fade
                if self._fade_surface is not None:
                    self._fade_surface.fill(
                        (0, 0, 0, 0),
                        pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE,
                                    TAILLE_TUILE, TAILLE_TUILE))
            if self.carte and donnees_recues['vis_delta']:
                self.carte._tuiles_a_reveler.extend(donnees_recues['vis_delta'])
                self.carte._vis_map_dirty = True

        # --- Joueurs ---
        ids_serveur = {j['id'] for j in donnees_recues['joueurs']}
        for id_local in list(self.joueurs_locaux.keys()):
            if id_local not in ids_serveur:
                del self.joueurs_locaux[id_local]
        for dj in donnees_recues['joueurs']:
            if dj['id'] not in self.joueurs_locaux:
                self.joueurs_locaux[dj['id']] = Joueur(dj['x'], dj['y'], dj['id'])
            joueur = self.joueurs_locaux[dj['id']]
            if not self.udp_actif and dj['id'] == self.mon_id:
                joueur.set_etat_local(dj)
            else:
                joueur.set_etat(dj)
            # Comptage des âmes récoltées (cumul sur les hausses d'argent)
            if dj['id'] == self.mon_id:
                argent_av = self._argent_joueur_precedent
                if argent_av is not None and joueur.argent > argent_av:
                    self._ames_recoltees_total += joueur.argent - argent_av
                self._argent_joueur_precedent = joueur.argent
            if (not self.udp_actif
                    and t_serveur is not None
                    and hasattr(joueur, 'pousser_snapshot_interp')):
                joueur.pousser_snapshot_interp(t_serveur, dj['x'], dj['y'])

        mon_joueur_local = self.joueurs_locaux.get(self.mon_id)
        if mon_joueur_local:
            for nom_son in mon_joueur_local.sons_a_jouer:
                music.jouer_sfx(nom_son)
            mon_joueur_local.sons_a_jouer.clear()

        # --- Ennemis ---
        ids_e = {e['id'] for e in donnees_recues['ennemis']}
        for id_local in list(self.ennemis_locaux.keys()):
            if id_local not in ids_e:
                del self.ennemis_locaux[id_local]
        for de in donnees_recues['ennemis']:
            if de['id'] not in self.ennemis_locaux:
                self.ennemis_locaux[de['id']] = Ennemi(
                    de['x'], de['y'], de['id'],
                    pv_max=de.get('pv_max', 2))
            ennemi = self.ennemis_locaux[de['id']]
            ennemi.set_etat(de)

            # Comptage kills : on check la donnée brute du serveur
            if de.get('est_mort', False):
                if not hasattr(self, '_ennemis_morts_comptes'):
                    self._ennemis_morts_comptes = set()
                if de['id'] not in self._ennemis_morts_comptes:
                    self._ennemis_morts_comptes.add(de['id'])
                    self._ennemis_tues_total = getattr(self, '_ennemis_tues_total', 0) + 1
                    
        for ennemi_local in self.ennemis_locaux.values():
            for nom_son in ennemi_local.sons_a_jouer:
                music.jouer_sfx(nom_son)
            ennemi_local.sons_a_jouer.clear()

        # --- Âmes perdues ---
        ids_a = {a['id'] for a in donnees_recues.get('ames_perdues', [])}
        for id_local in list(self.ames_perdues_locales.keys()):
            if id_local not in ids_a:
                del self.ames_perdues_locales[id_local]
        for da in donnees_recues.get('ames_perdues', []):
            if da['id'] not in self.ames_perdues_locales:
                ame_new = AmePerdue(da['x'], da['y'], da['id_joueur'], da.get('argent', 0))
                ame_new._argent_max = da.get('argent', 0)
                self.ames_perdues_locales[da['id']] = ame_new
            self.ames_perdues_locales[da['id']].set_etat(da)

        # --- Âmes libres ---
        ids_al = {a['id'] for a in donnees_recues.get('ames_libres', [])}
        for id_local in list(self.ames_libres_locales.keys()):
            if id_local not in ids_al:
                del self.ames_libres_locales[id_local]
        for dal in donnees_recues.get('ames_libres', []):
            if dal['id'] not in self.ames_libres_locales:
                self.ames_libres_locales[dal['id']] = AmeLibre(
                    dal['x'], dal['y'], dal.get('valeur'))
            self.ames_libres_locales[dal['id']].set_etat(dal)

        # --- Âmes loot ---
        ids_loot = {a['id'] for a in donnees_recues.get('ames_loot', [])}
        for id_local in list(self.ames_loot_locales.keys()):
            if id_local not in ids_loot:
                del self.ames_loot_locales[id_local]
        for dl in donnees_recues.get('ames_loot', []):
            if dl['id'] not in self.ames_loot_locales:
                self.ames_loot_locales[dl['id']] = AmeLoot(dl['x'], dl['y'], dl.get('valeur', 1))
            self.ames_loot_locales[dl['id']].set_etat(dl)

        # --- Orbes de capacité ---
        ids_orbes = {o['id'] for o in donnees_recues.get('orbes_capacite', [])}
        for id_local in list(self.orbes_capacite_locaux.keys()):
            if id_local not in ids_orbes:
                del self.orbes_capacite_locaux[id_local]
        for do in donnees_recues.get('orbes_capacite', []):
            orbe_avant    = self.orbes_capacite_locaux.get(do['id'])
            etait_ramasse = orbe_avant.est_ramasse if orbe_avant else False
            if do['id'] not in self.orbes_capacite_locaux:
                self.orbes_capacite_locaux[do['id']] = OrbeCapacite(
                    do['x'], do['y'], do['capacite'])
            self.orbes_capacite_locaux[do['id']].set_etat(do)
            if not etait_ramasse and do.get('est_ramasse'):
                cap = do.get('capacite', '')
                if cap == 'double_saut' and hasattr(self, 'notif_capacite') and self.notif_capacite:
                    touche = self.parametres.get('controles', {}).get('saut', 'ESPACE')
                    self.notif_capacite.notifier('double_saut', touche)

        # --- Pancartes lore ---
        for dp in donnees_recues.get('pancartes_lore', []):
            idx = dp.get('id', 0)
            if idx not in self.pancartes_lore_locales:
                self.pancartes_lore_locales[idx] = PancarteLore(dp['x'], dp['y'])
            pancarte = self.pancartes_lore_locales[idx]
            etait_debloquee = pancarte.est_debloquee
            pancarte.set_etat(dp)
            if not etait_debloquee and dp['est_debloquee']:
                if getattr(self, '_pancarte_active_id', None) == idx:
                    type_p = dp.get('type_pancarte', 'lore')
                    if type_p == 'shop_dash':
                        from core.pancarte_lore import TEXTE_LORE_DASH
                        self.bulle_lore.ouvrir(TEXTE_LORE_DASH)
                        if self.notif_capacite:
                            touche = self.parametres.get('controles', {}).get('dash', 'LSHIFT')
                            self.notif_capacite.notifier('dash', touche)
                    else:
                        self.bulle_lore.ouvrir()
                    self._pancarte_active_id = None

        # --- Portes ---
        if not hasattr(self, '_portes_etaient_en_ouverture'):
            self._portes_etaient_en_ouverture = {}

        data_portes = donnees_recues.get('portes', [])
        ids_serveur = set(range(len(data_portes)))
        for k in list(self.portes_locales.keys()):
            if k not in ids_serveur:
                del self.portes_locales[k]
        for i, data_porte in enumerate(data_portes):
            if i not in self.portes_locales:
                self.portes_locales[i] = Porte(data_porte['x'], data_porte['y'])
            porte = self.portes_locales[i]
            porte.set_etat(data_porte)

            etait_en_ouverture = self._portes_etaient_en_ouverture.get(i, False)
            if not etait_en_ouverture and porte.en_ouverture:
                music.jouer_sfx('porte')
            self._portes_etaient_en_ouverture[i] = porte.en_ouverture

            # Mettre à jour le journal et l'icône dès qu'une porte s'ouvre ou est ouverte
            if hasattr(self, 'widget_quete') and self.widget_quete:
                self.widget_quete.mettre_a_jour(self.cle_locale, porte, self.boss_local)
            if hasattr(self, 'journal_quete') and self.journal_quete:
                self.journal_quete.mettre_a_jour(self.cle_locale, porte, self.boss_local)

            if hasattr(self, 'widget_quete') and self.widget_quete:
                self.widget_quete.mettre_a_jour(
                    self.cle_locale, porte, self.boss_local,
                    ennemis_tues=self._ennemis_tues_total,
                    ames=self._ames_recoltees_total)
            if hasattr(self, 'journal_quete') and self.journal_quete:
                self.journal_quete.mettre_a_jour(
                    self.cle_locale, porte, self.boss_local,
                    ennemis_tues=self._ennemis_tues_total,
                    ames=self._ames_recoltees_total)
            # Récompense quête complète : bonus d'âmes unique à l'ouverture de la première porte
            if (not getattr(self, '_recompense_fin_quete_donnee', False)
                    and (porte.en_ouverture or porte.est_ouverte)
                    and i == 0):
                self._recompense_fin_quete_donnee = True
                mon_j = self.joueurs_locaux.get(self.mon_id)
                if mon_j:
                    mon_j.argent += 100
                    music.jouer_sfx('checkpoint')
                if hasattr(self, 'notif_capacite') and self.notif_capacite:
                    # Réutilise le système de notification pour afficher la récompense
                    self.notif_capacite._queue.append({
                        'capacite': '__fin__',
                        'titre':    'Quêtes accomplies !',
                        'sous':     '+100 âmes — merci d\'avoir joué',
                        'touche':   '',
                    })
        # --- Boss ---
        data_boss = donnees_recues.get('boss_room')
        if data_boss and not data_boss['boss_defeated']:
            if self.boss_local is None:
                _base = (sys._MEIPASS if getattr(sys, 'frozen', False)
                         else os.path.dirname(os.path.abspath(__file__)))
                self.boss_local = DemonSlimeBoss(
                    x=0, y=0,
                    json_path=os.path.join(_base, "demon_slime.json"),
                    png_path =os.path.join(_base, "assets", "demon_slime.png"))
            self.boss_local.set_etat(data_boss['boss'])
            etat_boss_actuel = data_boss['boss']['state']
            frame_actuelle   = data_boss['boss'].get('frame_index', 0)
            if (etat_boss_actuel == 'CLEAVE'
                    and self._boss_frame_precedent < DemonSlimeBoss.CLEAVE_ACTIVE_FRAME_START
                    and frame_actuelle >= DemonSlimeBoss.CLEAVE_ACTIVE_FRAME_START):
                music.jouer_sfx('slash_boss')
            self._boss_etat_precedent  = etat_boss_actuel
            self._boss_frame_precedent = frame_actuelle if etat_boss_actuel == 'CLEAVE' else 0

        # --- Clé ---
        data_cle = donnees_recues.get('cle')
        if data_cle:
            if self.cle_locale is None:
                self.cle_locale = Cle(data_cle['x'], data_cle['y'])
            self.cle_locale.set_etat(data_cle)

        # --- Torche ---
        torche_serveur = donnees_recues.get('torche_allumee', False)
        if torche_serveur != self.torche.allumee:
            self.torche.allumee = torche_serveur
            if torche_serveur:
                self.torche.particules = []

        # --- Leviers / passage ---
        for i, data in enumerate(donnees_recues.get('leviers', [])):
            if i not in self.leviers_locaux:
                self.leviers_locaux[i] = Levier(data['x'] // TAILLE_TUILE,
                                                data['y'] // TAILLE_TUILE)
            self.leviers_locaux[i].set_etat(data)

        passage_serveur = donnees_recues.get('passage_ouvert', False)
        if passage_serveur and not self.passage_ouvert:
            self._ouvrir_passage_local()
        self.passage_ouvert = passage_serveur

        # Mur payant
        data_mp = donnees_recues.get('mur_payant')
        if data_mp is not None:
            if self.mur_payant_local is None:
                self.mur_payant_local = MurPayant(85, 10, 25, "25 ames pour acceder")
            self.mur_payant_local.set_etat(data_mp)
            if data_mp.get('debloque') and not self.mur_payant_debloque:
                self._detruire_mur_payant_local()
            self.mur_payant_debloque = data_mp.get('debloque', False)

        # Mur clé
        mur_cle_serveur = donnees_recues.get('mur_cle_detruit', False)
        if mur_cle_serveur and not self.mur_cle_detruit:
            self._detruire_mur_cle_local()
        self.mur_cle_detruit = mur_cle_serveur

        # --- Potions ---
        if hasattr(self, 'potions') and self.potions is not None:
            self.potions.set_etat(donnees_recues.get('potions', []))

        # --- Données boss pour HUD ---
        self._derniere_data_boss = donnees_recues.get('boss_room')

    _TUILES_PASSAGE    = [(68,49),(69,49),(70,49),(68,50),(69,50),(70,50)]
    _TUILES_MUR_PAYANT = [(82,11),(83,11),(84,11),(85,11),(86,11),(87,11),(88,11),(89,11),(90,11)]
    _TUILES_MUR_CLE    = [(93,18),(93,19),(93,20)]

    def _effacer_tuiles_locales(self, tuiles):
        """Supprime map_data et les GIDs du layer Wall.1 uniquement."""
        if not self.carte:
            return
        layers_gids = getattr(self.carte, 'layers_gids', [])
        layers_noms = getattr(self.carte, 'layers_noms', [])
        for tx, ty in tuiles:
            if 0 <= tx < self.carte.largeur_map and 0 <= ty < self.carte.hauteur_map:
                self.carte.map_data[ty][tx] = 0
                for i, layer in enumerate(layers_gids):
                    if i < len(layers_noms) and layers_noms[i] == 'Wall.1':
                        layer[ty][tx] = 0
        self.carte._vis_map_dirty = True
        if hasattr(self.carte, '_grille_collision'):
            self.carte.construire_grille_collision()

    def _detruire_mur_payant_local(self):
        self._effacer_tuiles_locales(self._TUILES_MUR_PAYANT)

    def _detruire_mur_cle_local(self):
        self._effacer_tuiles_locales(self._TUILES_MUR_CLE)

    def _ouvrir_passage_local(self):
        self._effacer_tuiles_locales(self._TUILES_PASSAGE)

    def boucle_jeu_reseau(self):
        if not self.client_socket:
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        music.demarrer()

        self._reseau_lock = threading.Lock()
        self._reseau_actif = True
        self._commandes_a_envoyer = {
            'clavier': {'gauche': False, 'droite': False,
                        'saut': False, 'attaque': False, 'dash': False},
            'echo': False,
            'interagir': False,
        }
        self._dernier_etat_serveur = None
        self._nouvel_etat_disponible = False
        self._erreur_reseau = None

        udp_actif = getattr(self, 'udp_actif', False)
        self._dernier_keepalive_tcp = time.monotonic()

        thread_reseau = None
        if not udp_actif:
            thread_reseau = threading.Thread(target=self._thread_reseau, daemon=True)
            thread_reseau.start()

        while self.etat_jeu == "EN_JEU" and self.running:
            en_plein_ecran = self.parametres.get('video', {}).get('plein_ecran', False)
            if en_plein_ecran:
                pygame.mouse.set_visible(self.etat_jeu_interne in ("PAUSE", "PARAMETRES_JEU", "LUMINOSITE_JEU"))

            pos_souris = pygame.mouse.get_pos()
            commandes_a_envoyer = {
                'clavier': {'gauche': False, 'droite': False,
                            'saut': False, 'attaque': False, 'dash': False},
                'echo': False,
                'interagir': False,
            }

            if self.etat_jeu_interne == "JEU":
                commandes_a_envoyer = self.gerer_evenements_jeu()
            elif self.etat_jeu_interne == "PAUSE":
                self.gerer_evenements_pause(pos_souris)
            elif self.etat_jeu_interne == "PARAMETRES_JEU":
                if not self.parametres_temp:
                    self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu_precedent = "_RETOUR_PAUSE"
                self.gerer_menu_parametres(pos_souris)
                if self.etat_jeu == "_RETOUR_PAUSE":
                    self.etat_jeu = "EN_JEU"
                    self.etat_jeu_interne = "PAUSE"
            elif self.etat_jeu_interne == "LUMINOSITE_JEU":
                self.gerer_menu_luminosite(pos_souris)

            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            if udp_actif:
                one_shot = {
                    'echo':           commandes_a_envoyer.get('echo', False),
                    'echo_dir':       commandes_a_envoyer.get('echo_dir', False),
                    'toggle_torche':  commandes_a_envoyer.get('toggle_torche', False),
                    'interagir':      commandes_a_envoyer.get('interagir', False),
                }
                if commandes_a_envoyer.get('interagir'):
                    print(f"[DEBUG CLIENT] Envoi interagir=True via UDP")
                self._udp_envoyer_inputs(commandes_a_envoyer, one_shot)
                if time.monotonic() - self._dernier_keepalive_tcp > 5.0:
                    try:
                        send_complet(self.client_socket, {})
                    except Exception as e:
                        self._erreur_reseau = f"TCP keepalive: {e}"
                    self._dernier_keepalive_tcp = time.monotonic()
                self._udp_pomper_et_appliquer()
            else:
                with self._reseau_lock:
                    self._commandes_a_envoyer = commandes_a_envoyer

            with self._reseau_lock:
                erreur = self._erreur_reseau

            if erreur:
                print(f"[CLIENT] Erreur réseau: {erreur}")
                self.message_erreur_connexion = "Connexion perdue."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break

            if not udp_actif:
                with self._reseau_lock:
                    donnees_recues = self._dernier_etat_serveur if self._nouvel_etat_disponible else None
                    self._nouvel_etat_disponible = False

                if donnees_recues:
                    self._appliquer_etat_serveur(donnees_recues)

            self._mettre_a_jour_interpolations(int(time.monotonic() * 1000))

            # Dessiner le monde
            self.dessiner_jeu()
            if self.etat_jeu_interne == "PAUSE":
                self.dessiner_menu_pause()
            elif self.etat_jeu_interne == "PARAMETRES_JEU":
                self.dessiner_menu_parametres()
            elif self.etat_jeu_interne == "LUMINOSITE_JEU":
                self.dessiner_menu_luminosite()

            # UI pancarte sur l'écran final (au-dessus du zoom)
            if self.bulle_lore and self.bulle_lore.visible:
                self.bulle_lore.dessiner(self.ecran)
            if self.popup_paiement and self.popup_paiement.visible:
                self.popup_paiement.dessiner(self.ecran)

            # --- Journal de quête (parchemin plein écran) ---
            if hasattr(self, 'journal_quete') and self.journal_quete:
                self.journal_quete.mettre_a_jour(
                    self.cle_locale,
                    next(iter(self.portes_locales.values()), None),
                    self.boss_local,
                    ennemis_tues=getattr(self, '_ennemis_tues_total', 0),
                    ames=getattr(self, '_ames_recoltees_total', 0),)
                touche_journal = self.parametres.get('controles', {}).get('journal', 'i')
                self.journal_quete.dessiner(self.ecran, touche_journal=touche_journal)

            pygame.display.flip()

            # ── Déclenchement séquence de fin ──────────────────────────
            if (not getattr(self, '_sequence_fin_declenchee', False)
                    and self.portes_locales.get(0) is not None
                    and self.portes_locales[0].est_ouverte):
                self._sequence_fin_declenchee = True
                self.jouer_sequence_fin()
                return   # on sort de boucle_jeu_reseau proprement
            
            self.horloge.tick(FPS)

        self._reseau_actif = False

    # ==================================================================
    #  LANCEMENT ET CONNEXION
    # ==================================================================

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement  = "nouvelle" if est_nouvelle_partie else "charger"
        self._serveur_instance = None

        def _demarrer_serveur():
            self._serveur_instance = serveur.creer_serveur(
                id_slot, type_lancement)
            self._serveur_instance.demarrer()

        thread_serveur = threading.Thread(target=_demarrer_serveur, daemon=True)
        thread_serveur.start()
        connecte = False
        for _ in range(6):
            time.sleep(0.5)
            connecte = self.connecter(obtenir_ip_locale())
            if connecte:
                break
        if connecte:
            self.etat_jeu = "EN_JEU"
        else:
            self.etat_jeu = "MENU_PRINCIPAL"

    def _initier_udp_si_dispo(self, reponse_handshake, hote_tcp: str) -> bool:
        self.udp_actif      = False
        self.udp_endpoint   = None
        self.udp_conn       = None
        self.udp_offset_serveur_ms = None

        if not USE_UDP or not isinstance(reponse_handshake, dict):
            return False
        token = reponse_handshake.get('udp_token')
        port_udp = reponse_handshake.get('udp_port')
        if not token or not port_udp:
            return False

        try:
            _probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                _probe.connect((hote_tcp, port_udp))
                bind_local = _probe.getsockname()[0]
            finally:
                _probe.close()
        except OSError:
            bind_local = "127.0.0.1"

        try:
            self.udp_endpoint = UdpEndpoint(bind_host=bind_local, bind_port=0)
        except OSError as exc:
            print(f"[CLIENT] Impossible d'ouvrir un socket UDP: {exc}")
            return False

        addr_serveur = (hote_tcp, port_udp)
        self.udp_conn = ConnexionUDP(self.udp_endpoint, addr_serveur,
                                     heartbeat_ms=UDP_HEARTBEAT_INTERVAL_MS,
                                     timeout_ms=UDP_CONNECTION_TIMEOUT_MS)

        self.udp_conn.envoyer_control(UDP_P.TYPE_HANDSHAKE_UDP, {'token': token})

        deadline = time.monotonic() + UDP_HANDSHAKE_TIMEOUT_MS / 1000.0
        intervalle_rtx = 0.2
        prochain_renvoi = time.monotonic() + intervalle_rtx
        while time.monotonic() < deadline:
            for data, addr in self.udp_endpoint.pomper():
                if addr != addr_serveur:
                    continue
                self.udp_conn.traiter_paquet_brut(data)
            for canal, type_, payload in self.udp_conn.drainer_recus():
                if canal == UDP_P.CANAL_CONTROL and type_ == UDP_P.TYPE_HANDSHAKE_ACK:
                    self.udp_actif = True
                    print(f"[CLIENT] UDP handshake validé (port local {self.udp_endpoint.bind_port})")
                    return True
            if time.monotonic() >= prochain_renvoi:
                self.udp_conn.envoyer_control(UDP_P.TYPE_HANDSHAKE_UDP, {'token': token})
                prochain_renvoi = time.monotonic() + intervalle_rtx
            time.sleep(0.02)

        print(f"[CLIENT] UDP handshake échoué après {UDP_HANDSHAKE_TIMEOUT_MS} ms, bascule TCP")
        try:
            self.udp_endpoint.fermer()
        except Exception:
            pass
        self.udp_endpoint = None
        self.udp_conn     = None
        self.udp_actif    = False
        return False

    def _udp_envoyer_inputs(self, commandes: dict, one_shot_commandes: dict):
        if not self.udp_actif or self.udp_conn is None:
            return
        payload_continus = dict(commandes.get('clavier', {}))
        payload_continus['pseudo'] = commandes.get('pseudo', '')
        payload_continus['skin']   = commandes.get('skin', 0)
        last = getattr(self, '_inputs_pickle_cache', None)
        if last is not None and last[0] == payload_continus:
            data_pickle = last[1]
        else:
            data_pickle = pickle.dumps(payload_continus)
            self._inputs_pickle_cache = (payload_continus, data_pickle)
        self.udp_conn.envoyer_unreliable(UDP_P.TYPE_INPUTS_CONTINUS, data_pickle)
        if any(one_shot_commandes.values()):
            self.udp_conn.envoyer_reliable(UDP_P.TYPE_INPUT_ONESHOT, one_shot_commandes)

    def _udp_pomper_et_appliquer(self):
        if not self.udp_actif or self.udp_conn is None or self.udp_endpoint is None:
            return
        for data, addr in self.udp_endpoint.pomper():
            if addr != self.udp_conn.addr_pair:
                continue
            self.udp_conn.traiter_paquet_brut(data)

        now_ms = int(time.monotonic() * 1000)
        self.udp_conn.tick(now_ms)
        if not self.udp_conn.actif:
            with self._reseau_lock:
                self._erreur_reseau = "Connexion UDP perdue (timeout)"
            return

        for canal, type_, payload in self.udp_conn.drainer_recus():
            if canal == UDP_P.CANAL_UNRELIABLE and type_ == UDP_P.TYPE_SNAPSHOT:
                self._appliquer_snapshot_udp(payload, now_ms)
            elif canal == UDP_P.CANAL_RELIABLE and type_ == UDP_P.TYPE_ETAT_DISCRET:
                if isinstance(payload, dict):
                    self._appliquer_etat_serveur(payload)

    def _appliquer_snapshot_udp(self, snap: dict, now_ms: int):
        t_serveur = snap.get('t', 0)
        self.udp_offset_serveur_ms = t_serveur - now_ms

        for jd in snap.get('joueurs', []):
            jid = jd['id']
            joueur = self.joueurs_locaux.get(jid)
            if joueur is None:
                continue
            if jid == self.mon_id:
                joueur.rect.x = int(jd['x'])
                joueur.rect.y = int(jd['y'])
            else:
                if hasattr(joueur, 'pousser_snapshot_interp'):
                    joueur.pousser_snapshot_interp(t_serveur, jd['x'], jd['y'])

        for ed in snap.get('ennemis', []):
            ennemi = self.ennemis_locaux.get(ed['id'])
            if ennemi is None:
                continue
            if hasattr(ennemi, 'pousser_snapshot_interp'):
                ennemi.pousser_snapshot_interp(t_serveur, ed['x'], ed['y'])

        boss_data = snap.get('boss')
        if boss_data and self.boss_local is not None:
            self.boss_local.pos.x = boss_data['x']
            self.boss_local.pos.y = boss_data['y']

    def _mettre_a_jour_interpolations(self, now_ms: int):
        if self.udp_offset_serveur_ms is None:
            return
        t_render = now_ms + self.udp_offset_serveur_ms - INTERP_DELAY_MS
        for jid, joueur in self.joueurs_locaux.items():
            if self.udp_actif and jid == self.mon_id:
                continue
            if hasattr(joueur, 'mettre_a_jour_interp'):
                joueur.mettre_a_jour_interp(t_render)
        for ennemi in self.ennemis_locaux.values():
            if hasattr(ennemi, 'mettre_a_jour_interp'):
                ennemi.mettre_a_jour_interp(t_render)

    def _finaliser_connexion(self):
        """Initialise les données locales après un handshake réussi."""
        if getattr(sys, 'frozen', False):
            dossier_script = sys._MEIPASS
        else:
            dossier_script = os.path.dirname(os.path.abspath(__file__))
        chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
        self.carte                  = Carte(chemin_map)
        Porte.charger_assets(os.path.join(dossier_script, "assets", "porte_sheet.png"))
        self.vis_map_locale         = self.carte.creer_carte_visibilite_vierge()
        self.echo_fade_times        = {}
        map_w = self.carte.largeur_map * TAILLE_TUILE
        map_h = self.carte.hauteur_map * TAILLE_TUILE
        self._fade_surface          = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        self._fade_surface.fill((0, 0, 0, 255))
        self.joueurs_locaux         = {}
        self.ennemis_locaux         = {}
        self.ames_perdues_locales   = {}
        self.ames_libres_locales    = {}
        self.ames_loot_locales      = {}
        self.orbes_capacite_locaux  = {}
        self.pancartes_lore_locales = {}
        self.portes_locales         = {}
        self.leviers_locaux         = {}
        self.passage_ouvert         = False
        self.mur_payant_local       = None
        self.mur_payant_debloque    = False
        self.mur_cle_detruit        = False
        self.cle_locale             = None
        self._ennemis_tues_total   = 0
        self._ennemis_morts_comptes = set()
        self._ames_recoltees_total = 0
        self._argent_joueur_precedent = None
        self.potions                = GestionnairePotions()
        self.bulle_lore             = BulleLore(self.largeur_ecran, self.hauteur_ecran)
        self.popup_paiement         = PopupPaiement(self.largeur_ecran, self.hauteur_ecran)
        self._pancarte_active_id    = None
        # --- Icône journal (widget HUD) + journal parchemin ---
        self.widget_quete  = WidgetQuete(self.police_bouton, self.police_petit)
        self.journal_quete = JournalQuete(
            self.largeur_ecran, self.hauteur_ecran,
            self.police_titre, self.police_texte, self.police_petit,)
        self.notif_capacite = NotificationCapacite(self.largeur_ecran, self.hauteur_ecran)
        profil = self.parametres.get('profil', {})
        self._profil_pseudo = profil.get('pseudo', 'Joueur')
        self._profil_skin   = profil.get('skin', 0)
        self._sequence_fin_declenchee = False

    def connecter(self, hote):
        try:
            print(f"[CLIENT] Tentative de connexion vers {hote}:{PORT_SERVEUR}...")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((hote, PORT_SERVEUR))
            print(f"[CLIENT] Connexion TCP établie avec {hote}:{PORT_SERVEUR}")
            self.client_socket.settimeout(10.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = _extraire_id_handshake(reponse)
            print(f"[CLIENT] Connecté avec succès (ID joueur : {self.mon_id})")
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            self._initier_udp_si_dispo(reponse, hote)
            return True

        except socket.timeout:
            self.message_erreur_connexion = f"Timeout : {hote}:{PORT_SERVEUR} ne répond pas.\nVérifiez le pare-feu et la redirection de port."
            self.client_socket = None
            return False
        except ConnectionRefusedError:
            self.message_erreur_connexion = f"Connexion refusée : {hote}:{PORT_SERVEUR}\nLe serveur n'est pas démarré."
            self.client_socket = None
            return False
        except socket.gaierror:
            self.message_erreur_connexion = f"Adresse invalide : '{hote}'"
            self.client_socket = None
            return False
        except socket.error:
            self.message_erreur_connexion = f"Impossible de se connecter\nau serveur : {hote}"
            self.client_socket = None
            return False

    def connecter_relay(self, code_room, relay_host=None, relay_port=None):
        from reseau.relay_client import relay_rejoindre
        host = relay_host or RELAY_HOST
        port = relay_port or RELAY_PORT
        try:
            print(f"[CLIENT] Connexion relay ({host}:{port}) avec code '{code_room}'...")
            self.client_socket = relay_rejoindre(host, port, code_room)
            self.client_socket.settimeout(15.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu via relay : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = _extraire_id_handshake(reponse)
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            self.udp_actif = False
            return True

        except ConnectionError as e:
            self.message_erreur_connexion = str(e).replace("Relay: ", "")
            self.client_socket = None
            return False
        except socket.timeout:
            self.message_erreur_connexion = "Timeout : le serveur ne répond pas\nvia le relay."
            self.client_socket = None
            return False
        except Exception as e:
            self.message_erreur_connexion = f"Échec connexion relay :\n{e}"
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        pygame.mouse.set_visible(True)
        endpoint_udp = getattr(self, 'udp_endpoint', None)
        if endpoint_udp is not None:
            try:
                endpoint_udp.fermer()
            except Exception:
                pass
        self.udp_endpoint = None
        self.udp_conn     = None
        self.udp_actif    = False
        self.udp_offset_serveur_ms = None
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        srv = getattr(self, '_serveur_instance', None)
        if srv:
            try:
                srv.running = False
                srv.serveur_socket.close()
            except Exception:
                pass
            try:
                if getattr(srv, 'pathfinding', None) is not None:
                    srv.pathfinding.arreter()
            except Exception:
                pass
        music.torche_boucle_stop()
        if hasattr(self, 'torche') and self.torche:
            self.torche.allumee = False
        self.client_socket          = None
        self.mon_id                 = -1
        self.code_room              = None
        self._serveur_instance      = None
        self.joueurs_locaux         = {}
        self.ennemis_locaux         = {}
        self.ames_perdues_locales   = {}
        self.ames_libres_locales    = {}
        self.ames_loot_locales      = {}
        self.orbes_capacite_locaux  = {}
        self.pancartes_lore_locales = {}
        self.portes_locales         = {}
        self.leviers_locaux         = {}
        self.passage_ouvert         = False
        self.mur_payant_local       = None
        self.mur_payant_debloque    = False
        self.mur_cle_detruit        = False
        self.cle_locale             = None
        self._ennemis_tues_total   = 0
        self._ennemis_morts_comptes = set()
        self._ames_recoltees_total = 0
        self._argent_joueur_precedent = None
        self.carte                  = None
        self.vis_map_locale         = None
        self._fade_surface          = None
        self.echo_fade_times        = {}
        self.boss_local             = None
        self._portes_etaient_en_ouverture = {}
        self._fin_message_depuis          = None
        self._boss_etat_precedent         = None
        self._boss_frame_precedent        = 0
        self.etat_jeu_interne             = "JEU"
        self.bulle_lore          = None
        self.popup_paiement      = None
        self._pancarte_active_id = None
        # --- Reset journal et icône quête ---
        self.widget_quete  = None
        self.journal_quete = None
        self.notif_capacite = None
        self._recompense_fin_quete_donnee = False
        self._sequence_fin_declenchee = False
