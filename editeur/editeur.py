# editeur.py
# Classe Editeur — boucle principale Pygame de l'éditeur de niveaux TMX.
# Caméra ZQSD, zoom à la molette, palette latérale, sauvegarde via bouton.

import pygame

from parametres import (
    LARGEUR_ECRAN, HAUTEUR_ECRAN, FPS, TAILLE_TUILE,
    COULEUR_FOND, COULEUR_CYAN, COULEUR_TEXTE, COULEUR_TEXTE_SOMBRE,
    COULEUR_FOND_PANEL,
)
from ui.bouton import Bouton

from editeur import tmx_io, rendu
from editeur.palette import Palette


# ----------------------------------------------------------------------
# Constantes locales à l'éditeur
# ----------------------------------------------------------------------
VITESSE_CAM_PX_S = 800.0      # vitesse caméra à zoom 1 (px/s)
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_PAS = 1.15               # facteur multiplicatif par cran de molette
LARGEUR_PALETTE = 320


class Editeur:
    """Application standalone d'édition de map TMX."""

    def __init__(self, chemin_tmx):
        pygame.init()
        pygame.display.set_caption(f"Éditeur Écho — {chemin_tmx}")
        # Info() ne renvoie la résolution native que tant qu'aucun set_mode
        # n'a été appelé : on capture la valeur ici une bonne fois pour toutes.
        info = pygame.display.Info()
        self._native_w = info.current_w
        self._native_h = info.current_h
        self._taille_fenetree = (1280, 720)
        self._plein_ecran = True
        self.ecran = pygame.display.set_mode(
            (self._native_w, self._native_h),
            pygame.FULLSCREEN,
        )
        self.largeur = self.ecran.get_width()
        self.hauteur = self.ecran.get_height()
        self.horloge = pygame.time.Clock()

        self.donnees = tmx_io.charger_tmx(chemin_tmx)
        self.cache_tuiles = tmx_io.CacheTuiles(self.donnees)

        # Caméra (en pixels-monde) et zoom
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.touches_cam = {'z': False, 'q': False, 's': False, 'd': False}
        self.surbrillance_active = False

        # État d'édition
        if not self.donnees['layers']:
            raise ValueError("Le fichier TMX ne contient aucune couche de tuiles")
        self.layer_actif = 0
        self.gid_actif = self.donnees['tileset_firstgid']
        self.modifie = False
        self.en_peinture = False
        self.message_temp = ""
        self.message_temp_fin = 0

        # Polices
        self.police_ui    = pygame.font.SysFont("Arial", 18)
        self.police_titre = pygame.font.SysFont("Arial", 22, bold=True)
        self.police_petite = pygame.font.SysFont("Arial", 14)

        # Viewport (zone à gauche de la palette)
        self.viewport = pygame.Rect(0, 0, self.largeur - LARGEUR_PALETTE, self.hauteur)

        # Palette latérale
        rect_palette = pygame.Rect(
            self.largeur - LARGEUR_PALETTE, 0,
            LARGEUR_PALETTE, self.hauteur - 80,
        )
        self.palette = Palette(self.cache_tuiles, self.donnees, rect_palette, self.police_ui)

        # Boutons (en bas à droite, sous la palette)
        self._init_boutons()

        # Centre la caméra sur la map
        self._centrer_camera()

    # ------------------------------------------------------------------
    def _init_boutons(self):
        x_panel = self.largeur - LARGEUR_PALETTE
        y = self.hauteur - 70
        largeur = (LARGEUR_PALETTE - 30) // 2
        self.bouton_couche = Bouton(
            x_panel + 10, y, largeur, 50,
            self._libelle_couche(), self.police_ui, style="normal",
        )
        self.bouton_sauver = Bouton(
            x_panel + 20 + largeur, y, largeur, 50,
            "Sauvegarder", self.police_ui, style="confirm",
        )

    def _libelle_couche(self):
        nom = self.donnees['layers'][self.layer_actif]['nom']
        return f"Couche : {nom}"

    def _redimensionner(self, largeur, hauteur):
        self.largeur = largeur
        self.hauteur = hauteur
        # Mémorise la dernière taille fenêtrée pour la restaurer au prochain F11.
        if not self._plein_ecran:
            self._taille_fenetree = (largeur, hauteur)
        self.viewport = pygame.Rect(0, 0, self.largeur - LARGEUR_PALETTE, self.hauteur)
        self.palette.rect = pygame.Rect(
            self.largeur - LARGEUR_PALETTE, 0,
            LARGEUR_PALETTE, self.hauteur - 80,
        )
        self._init_boutons()

    def _basculer_plein_ecran(self):
        self._plein_ecran = not self._plein_ecran
        if self._plein_ecran:
            self.ecran = pygame.display.set_mode(
                (self._native_w, self._native_h),
                pygame.FULLSCREEN,
            )
        else:
            self.ecran = pygame.display.set_mode(
                self._taille_fenetree,
                pygame.RESIZABLE,
            )
        self._redimensionner(self.ecran.get_width(), self.ecran.get_height())

    def _centrer_camera(self):
        largeur_monde = self.donnees['largeur'] * TAILLE_TUILE
        hauteur_monde = self.donnees['hauteur'] * TAILLE_TUILE
        self.cam_x = max(0, (largeur_monde - self.viewport.width / self.zoom) / 2)
        self.cam_y = max(0, (hauteur_monde - self.viewport.height / self.zoom) / 2)

    # ------------------------------------------------------------------
    def lancer(self):
        en_cours = True
        while en_cours:
            dt = self.horloge.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    en_cours = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    en_cours = False
                else:
                    self._gerer_evenement(event)

            self._mettre_a_jour(dt)
            self._dessiner()
            pygame.display.flip()

        pygame.quit()

    # ------------------------------------------------------------------
    def _gerer_evenement(self, event):
        if event.type == pygame.VIDEORESIZE:
            self._redimensionner(event.w, event.h)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self._basculer_plein_ecran()
                return
            if event.key == pygame.K_z:
                self.touches_cam['z'] = True
            elif event.key == pygame.K_q:
                self.touches_cam['q'] = True
            elif event.key == pygame.K_s:
                # Ctrl+S = sauvegarde rapide
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self._sauvegarder()
                else:
                    self.touches_cam['s'] = True
            elif event.key == pygame.K_d:
                self.touches_cam['d'] = True
            elif event.key == pygame.K_a:
                self.surbrillance_active = True
            elif event.key == pygame.K_TAB:
                self._changer_couche()

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_z:
                self.touches_cam['z'] = False
            elif event.key == pygame.K_q:
                self.touches_cam['q'] = False
            elif event.key == pygame.K_s:
                self.touches_cam['s'] = False
            elif event.key == pygame.K_d:
                self.touches_cam['d'] = False
            elif event.key == pygame.K_a:
                self.surbrillance_active = False

        elif event.type == pygame.MOUSEWHEEL:
            # Si la palette consomme l'événement, on n'applique pas de zoom
            if not self.palette.gerer_scroll(event):
                self._zoomer(event.y, pygame.mouse.get_pos())

        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._gerer_clic_souris(event)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.en_peinture = False

        elif event.type == pygame.MOUSEMOTION:
            self.bouton_couche.verifier_survol(event.pos)
            self.bouton_sauver.verifier_survol(event.pos)
            # On ne peint en continu que si le clic a démarré dans le viewport
            # (sinon un drag depuis un bouton UI/palette écraserait des tuiles).
            if (self.en_peinture and event.buttons[0]
                    and self.viewport.collidepoint(event.pos)):
                self._peindre_a_position(event.pos)

    # ------------------------------------------------------------------
    def _gerer_clic_souris(self, event):
        if event.button != 1:
            return

        # Boutons UI prioritaires
        if self.bouton_couche.verifier_clic(event):
            self._changer_couche()
            return
        if self.bouton_sauver.verifier_clic(event):
            self._sauvegarder()
            return

        # Clic dans la palette
        gid = self.palette.gid_a_la_position(event.pos)
        if gid is not None:
            self.gid_actif = gid
            return

        # Clic sur le viewport : peindre la case
        if self.viewport.collidepoint(event.pos):
            self.en_peinture = True
            self._peindre_a_position(event.pos)

    def _peindre_a_position(self, pos_ecran):
        """Convertit pos_ecran en case et écrit gid_actif dans la couche active."""
        x_local = pos_ecran[0] - self.viewport.x
        y_local = pos_ecran[1] - self.viewport.y
        tx, ty = rendu.ecran_vers_case(
            x_local, y_local, self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE
        )
        if 0 <= tx < self.donnees['largeur'] and 0 <= ty < self.donnees['hauteur']:
            ligne = self.donnees['layers'][self.layer_actif]['gids'][ty]
            if ligne[tx] != self.gid_actif:
                ligne[tx] = self.gid_actif
                self.modifie = True

    # ------------------------------------------------------------------
    def _zoomer(self, sens, pos_pivot):
        """Zoom centré sur la position de la souris."""
        if not self.viewport.collidepoint(pos_pivot):
            return
        ancien_zoom = self.zoom
        if sens > 0:
            nouveau = self.zoom * ZOOM_PAS
        else:
            nouveau = self.zoom / ZOOM_PAS
        nouveau = max(ZOOM_MIN, min(ZOOM_MAX, nouveau))
        if nouveau == ancien_zoom:
            return

        # Conserver la position-monde sous le pivot
        x_local = pos_pivot[0] - self.viewport.x
        y_local = pos_pivot[1] - self.viewport.y
        x_monde = self.cam_x + x_local / ancien_zoom
        y_monde = self.cam_y + y_local / ancien_zoom
        self.zoom = nouveau
        self.cam_x = x_monde - x_local / self.zoom
        self.cam_y = y_monde - y_local / self.zoom
        self._clamper_camera()

        # Vide le cache de scaling au-delà d'un seuil pour limiter la mémoire
        rendu.vider_cache_zoom()

    def _changer_couche(self):
        nb = len(self.donnees['layers'])
        self.layer_actif = (self.layer_actif + 1) % nb
        self.bouton_couche.texte = self._libelle_couche()

    def _sauvegarder(self):
        try:
            tmx_io.sauvegarder_tmx(self.donnees)
            self.modifie = False
            self._afficher_message("Sauvegardé !")
        except Exception as e:
            self._afficher_message(f"Erreur : {e}")
            print(f"[EDITEUR] Erreur sauvegarde : {e}")
            import traceback
            traceback.print_exc()

    def _afficher_message(self, texte, duree_ms=2500):
        self.message_temp = texte
        self.message_temp_fin = pygame.time.get_ticks() + duree_ms

    # ------------------------------------------------------------------
    def _mettre_a_jour(self, dt):
        # Mouvement caméra ZQSD à vitesse constante (en pixels-monde)
        vitesse = VITESSE_CAM_PX_S * dt / self.zoom
        if self.touches_cam['z']:
            self.cam_y -= vitesse
        if self.touches_cam['s']:
            self.cam_y += vitesse
        if self.touches_cam['q']:
            self.cam_x -= vitesse
        if self.touches_cam['d']:
            self.cam_x += vitesse
        self._clamper_camera()

    def _clamper_camera(self):
        largeur_monde = self.donnees['largeur'] * TAILLE_TUILE
        hauteur_monde = self.donnees['hauteur'] * TAILLE_TUILE
        marge = 200
        self.cam_x = max(-marge, min(self.cam_x, largeur_monde - self.viewport.width / self.zoom + marge))
        self.cam_y = max(-marge, min(self.cam_y, hauteur_monde - self.viewport.height / self.zoom + marge))

    # ------------------------------------------------------------------
    def _dessiner(self):
        self.ecran.fill(COULEUR_FOND)

        # Carte : image layers, tile layers, grille
        rendu.dessiner_image_layers(
            self.ecran, self.donnees['image_layers'],
            self.cam_x, self.cam_y, self.zoom, self.viewport,
        )
        rendu.dessiner_tile_layers(
            self.ecran, self.donnees['layers'], self.cache_tuiles,
            self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
            self.donnees['largeur'], self.donnees['hauteur'],
            self.viewport, layer_actif=self.layer_actif,
        )
        if self.surbrillance_active:
            rendu.dessiner_surbrillance_couche(
                self.ecran, self.donnees['layers'][self.layer_actif],
                self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
                self.donnees['largeur'], self.donnees['hauteur'], self.viewport,
            )
        rendu.dessiner_grille(
            self.ecran, self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
            self.donnees['largeur'], self.donnees['hauteur'], self.viewport,
        )

        # Curseur sur la case sous la souris
        pos = pygame.mouse.get_pos()
        if self.viewport.collidepoint(pos):
            tx, ty = rendu.ecran_vers_case(
                pos[0] - self.viewport.x, pos[1] - self.viewport.y,
                self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
            )
            apercu_surf = self.cache_tuiles.get(self.gid_actif) if self.gid_actif > 0 else None
            rendu.dessiner_curseur_case(
                self.ecran, tx, ty, self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
                self.donnees['largeur'], self.donnees['hauteur'], self.viewport,
                gid_apercu_surface=apercu_surf,
            )

        # Palette + boutons
        self.palette.dessiner(self.ecran, self.gid_actif)
        self.bouton_couche.dessiner(self.ecran)
        self.bouton_sauver.dessiner(self.ecran)

        # HUD info en haut à gauche du viewport
        self._dessiner_hud()

    def _dessiner_hud(self):
        pos = pygame.mouse.get_pos()
        if self.viewport.collidepoint(pos):
            tx, ty = rendu.ecran_vers_case(
                pos[0] - self.viewport.x, pos[1] - self.viewport.y,
                self.cam_x, self.cam_y, self.zoom, TAILLE_TUILE,
            )
            if 0 <= tx < self.donnees['largeur'] and 0 <= ty < self.donnees['hauteur']:
                couches_ici = [
                    layer['nom']
                    for layer in self.donnees['layers']
                    if layer['gids'][ty][tx] != 0
                ]
                tuile_info = ", ".join(couches_ici) if couches_ici else "aucune tuile"
            else:
                tuile_info = "aucune tuile"
        else:
            tuile_info = "aucune tuile"

        lignes = [
            f"Map : {self.donnees['largeur']}x{self.donnees['hauteur']} tuiles",
            f"Zoom : {int(self.zoom * 100)}%",
            f"Couche active : {self.donnees['layers'][self.layer_actif]['nom']}",
            f"Tuile sélectionnée : gid {self.gid_actif}",
            f"Tuile survolée : {tuile_info}",
        ]
        if self.modifie:
            lignes.append("● MODIFIÉ (non sauvegardé)")

        # Fond semi-transparent
        h_total = 12 + 22 * len(lignes)
        fond = pygame.Surface((360, h_total), pygame.SRCALPHA)
        fond.fill((10, 8, 25, 200))
        pygame.draw.rect(fond, COULEUR_CYAN, fond.get_rect(), 1)
        self.ecran.blit(fond, (10, 10))

        for i, ligne in enumerate(lignes):
            couleur = (255, 200, 60) if ligne.startswith("●") else COULEUR_TEXTE
            surf = self.police_ui.render(ligne, True, couleur)
            self.ecran.blit(surf, (20, 16 + i * 22))

        # Aide en bas
        aide = "ZQSD : déplacer  •  Molette : zoom  •  TAB : couche  •  A (maintenu) : surbrillance  •  Ctrl+S : sauver  •  F11 : plein écran  •  Échap : quitter"
        s = self.police_petite.render(aide, True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(s, (10, self.hauteur - 22))

        # Message temporaire (sauvegardé / erreur)
        if self.message_temp and pygame.time.get_ticks() < self.message_temp_fin:
            surf = self.police_titre.render(self.message_temp, True, COULEUR_CYAN)
            r = surf.get_rect(midtop=(self.viewport.centerx, 30))
            fond_msg = pygame.Surface((r.width + 30, r.height + 16), pygame.SRCALPHA)
            fond_msg.fill((10, 8, 25, 220))
            pygame.draw.rect(fond_msg, COULEUR_CYAN, fond_msg.get_rect(), 1)
            self.ecran.blit(fond_msg, (r.x - 15, r.y - 8))
            self.ecran.blit(surf, r)
