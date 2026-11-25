# end_crystal_sequence.py
# Ending cutscene of the game, played by GameLoopMixin.play_sequence_end().
# FLOW:
# 1. Fade to black from the last game frame
# 2. Intact crystal screen -> the player mashes K to break it
# 3. Explosion animation (5 Destruction_Solaris_* images)
# 4. Black background + "You got out..." message
# 5. ending.png + teaser_echo2.png sequence

import sys
import pygame
from utils.paths import asset_path
from utils.i18n import get_text



# Paths of the 5 destruction frames (in assets/)
END_CRYSTAL_FRAMES = [
    asset_path("Destruction_Solaris_1_-_Instabilité.png"),
    asset_path("Destruction_Solaris_2_-_Fissures.png"),
    asset_path("Destruction_Solaris_3_-_Explosion.png"),
    asset_path("Destruction_Solaris_4_-_Aftermath.png"),
    asset_path("Destruction_Solaris_5_-_Noir.png"),
]


def play_sequence_end(self):
    """
    Ending cutscene:
    1. Fade to black (from the game)
    2. Intact crystal image - mash the K key to break it
    3. 5-frame destruction animation
    4. Black background + exit text
    5. ending.png -> teaser_echo2.png -> back to the menu
    """
    from utils import music          # local import to avoid circular imports
    FPS        = 60
    lw, lh     = self.width_screen, self.height_screen


    font_medium = pygame.font.Font(None, int(lh * 0.038))
    
    # -- Shared helpers ----------------------------------------------------------

    def _poll_quit():
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

    def _load_image(path):
        try:
            img = pygame.image.load(path).convert()
        except Exception:
            img = pygame.Surface((lw, lh))
            img.fill((10, 10, 20))
        ratio = min(lw / img.get_width(), lh / img.get_height())
        nw = int(img.get_width()  * ratio)
        nh = int(img.get_height() * ratio)
        img = pygame.transform.scale(img, (nw, nh))
        return img, (lw - nw) // 2, (lh - nh) // 2

    def _fade_to_black(duration_ms, snapshot=None):
        start   = pygame.time.get_ticks()
        overlay = pygame.Surface((lw, lh), pygame.SRCALPHA)
        while True:
            elapsed = pygame.time.get_ticks() - start
            t = min(elapsed / duration_ms, 1.0)
            self.screen.fill((0, 0, 0))
            if snapshot:
                self.screen.blit(snapshot, (0, 0))
            overlay.fill((0, 0, 0, int(255 * t)))
            self.screen.blit(overlay, (0, 0))
            pygame.display.flip()
            _poll_quit()
            self.clock.tick(FPS)
            if elapsed >= duration_ms:
                break

    def _show_image_with_waiting(image, ix, iy,
                                     fadein_ms=800, lock_ms=3000,
                                     hint="Appuyez sur une touche pour continuer…"):
        """Fade an image in, then wait for a key press (after lock_ms)."""
        start_fi = pygame.time.get_ticks()
        while True:
            elapsed = pygame.time.get_ticks() - start_fi
            t = min(elapsed / fadein_ms, 1.0)
            self.screen.fill((0, 0, 0))
            tmp = image.copy()
            tmp.set_alpha(int(255 * t))
            self.screen.blit(tmp, (ix, iy))
            pygame.display.flip()
            _poll_quit()
            self.clock.tick(FPS)
            if elapsed >= fadein_ms:
                break

        start_lock = pygame.time.get_ticks()
        pygame.event.clear()
        while True:
            now = pygame.time.get_ticks()
            can_continue = now - start_lock >= lock_ms
            self.screen.fill((0, 0, 0))
            self.screen.blit(image, (ix, iy))
            if can_continue and (now // 600) % 2 == 0:
                surf = self.font_text.render(hint, True, (180, 180, 180))
                self.screen.blit(surf, surf.get_rect(centerx=lw // 2, bottom=lh - 28))
            pygame.display.flip()
            self.clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if can_continue and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return

    # -- STEP 1: fade to black from the game -------------------------------------
    snapshot_game = self.screen.copy()
    _fade_to_black(1500, snapshot=snapshot_game)
    pygame.time.wait(300)

    music.start()   # background music for the whole cutscene

    # -- STEP 2: intact crystal - mash K to break it ----------------------------

    img_crystal, cx, cy = _load_image(END_CRYSTAL_FRAMES[0])

    # Mash bar parameters
    PRESSES_REQUIRED   = 30      # number of K presses required
    DECAY_PER_SEC        = 0.08    # the bar slowly drops when the player stops
    BAR_W, BAR_H         = int(lw * 0.55), 22
    bar_x = (lw - BAR_W) // 2
    bar_y = lh - 80

    progress = 0.0   # 0.0 -> 1.0
    presses   = 0
    k_code      = pygame.K_k
    t_last   = pygame.time.get_ticks()
    shake_frames = 0   # remaining shake frames after a press

    pygame.event.clear()

    # Preload frame 2 (cracks) for visual anticipation
    img_cracks, fx, fy = _load_image(END_CRYSTAL_FRAMES[1])

    # Short fade-in of the crystal
    start_fi = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start_fi < 1000:
        t = min((pygame.time.get_ticks() - start_fi) / 1000, 1.0)
        self.screen.fill((0, 0, 0))
        tmp = img_crystal.copy()
        tmp.set_alpha(int(255 * t))
        self.screen.blit(tmp, (cx, cy))
        pygame.display.flip()
        _poll_quit()
        self.clock.tick(FPS)

    while progress < 1.0:
        now = pygame.time.get_ticks()
        dt  = (now - t_last) / 1000.0
        t_last = now

        # Passive decay (very light)
        progress = max(0.0, progress - DECAY_PER_SEC * dt)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == k_code:
                presses   += 1
                progress  = min(1.0, progress + 1.0 / PRESSES_REQUIRED)
                shake_frames = 6   # small vibration

        # Crystal image: switches to the cracks at 50 %
        if progress >= 0.5:
            img_background, bx, bz = img_cracks, fx, fy
        else:
            img_background, bx, bz = img_crystal, cx, cy

        # Screen shake
        off_x = off_y = 0
        if shake_frames > 0:
            import random
            intensity = int(4 * (shake_frames / 6))
            off_x = random.randint(-intensity, intensity)
            off_y = random.randint(-intensity, intensity)
            shake_frames -= 1

        self.screen.fill((0, 0, 0))
        self.screen.blit(img_background, (bx + off_x, bz + off_y))

        # -- Progress bar --
        # Bar background
        pygame.draw.rect(self.screen, (40, 30, 20),
                         (bar_x - 2, bar_y - 2, BAR_W + 4, BAR_H + 4), border_radius=4)
        # Fill (warm gradient)
        fill_w = int(BAR_W * progress)
        if fill_w > 0:
            # Color going from amber to white at 100 %
            r = min(255, int(180 + 75 * progress))
            g = min(255, int(90  + 165 * progress))
            b = int(20  * (1 - progress))
            pygame.draw.rect(self.screen, (r, g, b),
                             (bar_x, bar_y, fill_w, BAR_H), border_radius=3)
        # Border
        pygame.draw.rect(self.screen, (220, 180, 80),
                         (bar_x - 2, bar_y - 2, BAR_W + 4, BAR_H + 4),
                         2, border_radius=4)

        # -- Instruction --
        if (now // 500) % 2 == 0 or progress > 0.1:
            hint_surf = font_medium.render(
                "[ K ]  —  Brisez le cristal", True, (230, 200, 120))
            self.screen.blit(hint_surf,
                            hint_surf.get_rect(centerx=lw // 2, bottom=bar_y - 18))

        pygame.display.flip()
        self.clock.tick(FPS)

    # -- STEP 3: explosion animation (5 frames) --------------------------------
    DURATION_PER_FRAME_MS = [
        120,   # frame 1 -> 2
        200,   # frame 2 -> 3
        400,   # frame 3 (explosion peak) - longer
        600,   # frame 4 (aftermath)
        800,   # frame 5 (progressive black)
    ]

    try:
        music.play_sfx('explosion')   # explosion sound if available
    except Exception:
        pass

    frames_explosion = []
    for path in END_CRYSTAL_FRAMES:
        img, ix, iy = _load_image(path)
        frames_explosion.append((img, ix, iy))

    for i, (img_exp, ix, iy) in enumerate(frames_explosion):
        duration = DURATION_PER_FRAME_MS[i]
        start = pygame.time.get_ticks()

        # Intense shake on frames 2-3
        shake = 8 if i in (1, 2) else (4 if i == 0 else 0)

        while pygame.time.get_ticks() - start < duration:
            import random
            ox = random.randint(-shake, shake) if shake else 0
            oy = random.randint(-shake, shake) if shake else 0
            self.screen.fill((0, 0, 0))
            self.screen.blit(img_exp, (ix + ox, iy + oy))
            pygame.display.flip()
            _poll_quit()
            self.clock.tick(FPS)

    # -- STEP 4: black background + exit message --------------------------------
    # Fade to black from the last explosion frame
    snap_explo = self.screen.copy()
    _fade_to_black(1200, snapshot=snap_explo)
    pygame.time.wait(600)

    # Show the message
    LINES_MESSAGE = get_text("end_message")

    def _show_message_black(lines, duration_total_ms=5000):
        """Reveal the lines one by one, then wait."""
        surfaces = []
        for line in lines:
            if line:
                s = font_medium.render(line, True, (200, 190, 170))
            else:
                s = pygame.Surface((1, self.font_text.get_height()), pygame.SRCALPHA)
            surfaces.append(s)

        height_block = sum(s.get_height() + 8 for s in surfaces)
        y_start = (lh - height_block) // 2
        start = pygame.time.get_ticks()
        delay_per_line = 600

        pygame.event.clear()
        while True:
            now = pygame.time.get_ticks()
            elapsed = now - start
            self.screen.fill((0, 0, 0))

            y = y_start
            for idx, s in enumerate(surfaces):
                if elapsed >= idx * delay_per_line:
                    age = elapsed - idx * delay_per_line
                    alpha = min(255, int(age / 400 * 255))
                    tmp = s.copy()
                    tmp.set_alpha(alpha)
                    self.screen.blit(tmp, tmp.get_rect(centerx=lw // 2, top=y))
                y += s.get_height() + 8

            if elapsed >= duration_total_ms:
                # Blinking hint
                if (now // 600) % 2 == 0:
                    h = self.font_text.render(
                        "Appuyez sur une touche pour continuer…",
                        True, (120, 110, 100))
                    self.screen.blit(h, h.get_rect(centerx=lw // 2, bottom=lh - 30))

            pygame.display.flip()
            self.clock.tick(FPS)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if elapsed >= duration_total_ms and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return

    _show_message_black(LINES_MESSAGE, duration_total_ms=5500)

    # -- STEP 5: fade -> ending.png ---------------------------------------------
    _fade_to_black(800)
    pygame.time.wait(200)

    img_ending, ex, ey = _load_image(self.END_ENDING_IMAGE)
    _show_image_with_waiting(img_ending, ex, ey)

    # Transition
    snap_ending = self.screen.copy()
    _fade_to_black(1000, snapshot=snap_ending)
    pygame.time.wait(200)

    # -- STEP 6: teaser_echo2.png -----------------------------------------------
    img_teaser, tx, ty = _load_image(self.END_TEASER_IMAGE)
    _show_image_with_waiting(img_teaser, tx, ty)

    snap_teaser = self.screen.copy()
    _fade_to_black(1000, snapshot=snap_teaser)

    pygame.mixer.music.stop()

    # -- Back to the menu -------------------------------------------------------
    self.game_state = "MENU_MAIN"
    self.cleanup_connection()
    self.refresh_languages_widgets()