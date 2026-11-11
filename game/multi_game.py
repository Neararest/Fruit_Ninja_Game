import math
import time
import pygame
from core.fruit import (
    FruitManager,
    JuiceParticle,
    FloatingText,
    segment_intersects_rect,
)
from core.sound_manager import SoundManager
from core.hand_tracker import HandTracker
from core.settings import SettingsManager
from core.database import DatabaseManager
from ui.components import (
    FontCache,
    ModernButtonManager,
    HandCursorManager,
    draw_glass_panel,
    truncate_text,
)


class MultiFruitNinjaGame:
    def __init__(
        self,
        background_path="assets/themes/2.png",
        screen=None,
        settings=None,
        sounds=None,
        hand_tracker=None,
        db=None,
        current_user=None,
        p2_name="Ninja 2",
    ):
        if not pygame.get_init():
            pygame.init()

        self.WIDTH, self.HEIGHT = 1280, 720
        self.owns_resources = hand_tracker is None

        if screen is not None:
            self.screen = screen
            self.WIDTH, self.HEIGHT = self.screen.get_size()
        else:
            self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Fruit Ninja - Duel Multiplayer")

        self.settings = settings if settings is not None else SettingsManager()
        self.sounds = sounds if sounds is not None else SoundManager(settings=self.settings)
        self.db = db if db is not None else DatabaseManager()
        self.current_user = current_user if current_user is not None else {"id": None, "username": "Ninja 1", "is_guest": True}

        self.p1_name = self.current_user.get("username", "Ninja 1")
        if self.p1_name in ("Guest", "Tamu", ""):
            self.p1_name = "Ninja 1"
        self.p2_name = p2_name.strip() if p2_name and p2_name.strip() else "Ninja 2"

        self.hand_tracker = hand_tracker if hand_tracker is not None else HandTracker(max_hands=2)
        self.hand_tracker.set_max_hands(2)
        self.hand_tracker.ensure_camera(self.WIDTH, self.HEIGHT)

        self.background_path = background_path
        self._load_background()

        self.fruit_manager = FruitManager(self.WIDTH, self.HEIGHT)
        self.clock = pygame.time.Clock()
        self.btn_mgr = ModernButtonManager()
        self.hand_cursor = HandCursorManager(dwell_time=self.settings.dwell_time)

        self.reset_game()

    def _load_background(self):
        try:
            raw_bg = pygame.image.load(self.background_path).convert()
            self.background_raw = raw_bg
            self.background = pygame.transform.smoothscale(raw_bg, (self.WIDTH, self.HEIGHT))
        except Exception:
            self.background_raw = None
            self.background = pygame.Surface((self.WIDTH, self.HEIGHT))
            self.background.fill((36, 22, 14))
        self._modal_overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        self._modal_overlay.fill((12, 8, 5, 185))
        self._half_dead_overlay = pygame.Surface((self.WIDTH // 2, self.HEIGHT), pygame.SRCALPHA)
        self._half_dead_overlay.fill((18, 6, 6, 170))
        self._half_flash_overlay = pygame.Surface((self.WIDTH // 2, self.HEIGHT), pygame.SRCALPHA)
        self._half_flash_overlay.fill((220, 35, 30, 135))

    def reset_game(self):
        self.player1 = 0
        self.player2 = 0
        self.p1_missed = 0
        self.p2_missed = 0
        self.p1_streak = 0
        self.p2_streak = 0
        self.p1_alive = True
        self.p2_alive = True
        self.p1_dead_time = 0.0
        self.p2_dead_time = 0.0
        self.p1_dead_reason = ""
        self.p2_dead_reason = ""
        self.p1_prev = None
        self.p2_prev = None
        self.p1_buf = []
        self.p2_buf = []
        self.p1_trail = []
        self.p2_trail = []
        self.level = 1

        self.match_duration = 90.0
        self.remaining_time = self.match_duration
        self.last_frame_time = time.time()

        self.fruits = [self.fruit_manager.spawn_fruit_multi(1, True, True) for _ in range(4)]
        self.sliced_halves = []
        self.particles = []
        self.floating_texts = []

        self.paused = False
        self.game_over = False
        self.show_go_screen = False
        self.go_start_ticks = 0
        self.GO_DURATION = 1400
        self.db_saved_for_round = False

    def _update_size(self):
        new_w, new_h = self.screen.get_size()
        if new_w != self.WIDTH or new_h != self.HEIGHT:
            self.WIDTH, self.HEIGHT = new_w, new_h
            if self.background_raw is not None:
                self.background = pygame.transform.smoothscale(self.background_raw, (self.WIDTH, self.HEIGHT))
            else:
                self.background = pygame.Surface((self.WIDTH, self.HEIGHT))
                self.background.fill((36, 22, 14))
            self._modal_overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
            self._modal_overlay.fill((12, 8, 5, 185))
            self._half_dead_overlay = pygame.Surface((self.WIDTH // 2, self.HEIGHT), pygame.SRCALPHA)
            self._half_dead_overlay.fill((18, 6, 6, 170))
            self._half_flash_overlay = pygame.Surface((self.WIDTH // 2, self.HEIGHT), pygame.SRCALPHA)
            self._half_flash_overlay.fill((220, 35, 30, 135))
            self.fruit_manager.WIDTH = self.WIDTH
            self.fruit_manager.HEIGHT = self.HEIGHT

    @staticmethod
    def _compute_player_multiplier(streak: int, is_p1: bool) -> tuple[int, tuple, tuple]:
        if streak >= 20:
            return 4, (255, 215, 20), (255, 255, 220)
        if streak >= 10:
            return 3, (215, 65, 255), (250, 220, 255)
        if streak >= 5:
            return 2, (65, 245, 135), (220, 255, 230)
        if is_p1:
            return 1, (0, 195, 255), (210, 250, 255)
        return 1, (240, 125, 20), (255, 245, 190)

    def _assign_hands(self, result, cam_w, cam_h):
        p1_hand = None
        p2_hand = None
        any_hand = None

        if result is not None and result.multi_hand_landmarks:
            for hand_lms in result.multi_hand_landmarks:
                if not self.hand_tracker.is_finger_active(
                    hand_lms,
                    finger_mode=self.settings.finger_mode,
                    require_raised=True,
                ):
                    continue

                gx, gy = self.hand_tracker.extract_finger_point(
                    hand_lms,
                    cam_w,
                    cam_h,
                    self.WIDTH,
                    self.HEIGHT,
                    finger_mode=self.settings.finger_mode,
                )
                if any_hand is None:
                    any_hand = (gx, gy)

                if gx < self.WIDTH // 2:
                    if self.p1_alive:
                        p1_hand = (gx, gy)
                else:
                    if self.p2_alive:
                        p2_hand = (gx, gy)

        return p1_hand, p2_hand, any_hand

    @staticmethod
    def _smooth_hand(hand_pos, buf, prev_pos):
        if hand_pos is None:
            buf.clear()
            return None
        return HandTracker.adaptive_smooth(hand_pos, prev_pos)

    def _draw_trail(self, trail, now: float, outer_col, inner_col):
        trail[:] = [p for p in trail if now - p[2] < 0.22]
        if len(trail) < 2:
            return
        n = len(trail)
        for i in range(1, n):
            x1, y1, _ = trail[i - 1]
            x2, y2, _ = trail[i]
            ratio = i / n
            thickness = max(2, int(13 * ratio))
            pygame.draw.line(self.screen, outer_col, (x1, y1), (x2, y2), thickness + 4)
            pygame.draw.line(self.screen, inner_col, (x1, y1), (x2, y2), max(1, thickness - 2))
        lx, ly, _ = trail[-1]
        pygame.draw.circle(self.screen, outer_col, (lx, ly), 12)
        pygame.draw.circle(self.screen, inner_col, (lx, ly), 6)

    def _trigger_game_over(self):
        if self.game_over:
            return
        self.game_over = True
        self.paused = False
        self.show_go_screen = True
        self.go_start_ticks = pygame.time.get_ticks()
        if not self.db_saved_for_round:
            self.db.save_multi_score(
                self.current_user,
                p1_score=self.player1,
                p2_score=self.player2,
                level=self.level,
                p2_name=self.p2_name,
            )
            self.db_saved_for_round = True

    def _spawn_slice_effects(self, fruit, label_text="+1", label_col=(255, 240, 100)):
        cx = fruit.x + fruit.width / 2
        cy = fruit.y + fruit.height / 2
        if not fruit.is_bomb:
            self.sliced_halves.extend(self.fruit_manager.split_fruit_surface(fruit))
            for _ in range(10):
                self.particles.append(JuiceParticle(cx, cy, fruit.color))
            self.floating_texts.append(FloatingText(label_text, cx, cy - 10, color=label_col, size=26))
        else:
            for _ in range(22):
                self.particles.append(JuiceParticle(cx, cy, (255, 70, 20)))
            self.floating_texts.append(FloatingText("GUGUR!", cx, cy, color=(255, 65, 65), size=32))

    def _handle_hands_and_slice(self, cam_frame, now: float):
        _, result = self.hand_tracker.get_latest_result()
        cam_h, cam_w = cam_frame.shape[:2]
        p1_raw, p2_raw, any_hand = self._assign_hands(result, cam_w, cam_h)

        self.hand_cursor.update_pointer(any_hand, dwell_time=self.settings.dwell_time)
        if self.game_over or self.paused:
            return

        smooth_p1 = self._smooth_hand(p1_raw, self.p1_buf, self.p1_prev) if self.p1_alive else None
        smooth_p2 = self._smooth_hand(p2_raw, self.p2_buf, self.p2_prev) if self.p2_alive else None

        p1_start = self.p1_prev if self.p1_prev is not None else smooth_p1
        p2_start = self.p2_prev if self.p2_prev is not None else smooth_p2

        if smooth_p1:
            self.p1_trail.append((smooth_p1[0], smooth_p1[1], now))
        else:
            self.p1_trail.clear()

        if smooth_p2:
            self.p2_trail.append((smooth_p2[0], smooth_p2[1], now))
        else:
            self.p2_trail.clear()

        for fruit in self.fruits:
            if not fruit.is_Targetable:
                continue

            if self.p1_alive and smooth_p1 is not None and p1_start is not None:
                if segment_intersects_rect(p1_start, smooth_p1, fruit.rect):
                    fruit.cut = True
                    if fruit.is_bomb and not self.game_over:
                        self.p1_alive = False
                        self.p1_dead_time = now
                        self.p1_dead_reason = "Menebas Bom!"
                        self.p1_streak = 0
                        self.p1_trail.clear()
                        self.sounds.play("boom")
                        self._spawn_slice_effects(fruit)
                        if not self.p2_alive:
                            self._trigger_game_over()
                    else:
                        self.p1_streak += 1
                        mult1, col1, _ = self._compute_player_multiplier(self.p1_streak, is_p1=True)
                        self.player1 += mult1
                        self.sounds.play("slash")
                        lbl1 = f"+{mult1}" if mult1 == 1 else f"COMBO {mult1}x! +{mult1}"
                        self._spawn_slice_effects(fruit, lbl1, col1)
                        if (self.player1 + self.player2) // 35 + 1 > self.level:
                            self.level = (self.player1 + self.player2) // 35 + 1
                            self.sounds.play("levelup")

            if self.p2_alive and smooth_p2 is not None and p2_start is not None and not fruit.cut:
                if segment_intersects_rect(p2_start, smooth_p2, fruit.rect):
                    fruit.cut = True
                    if fruit.is_bomb and not self.game_over:
                        self.p2_alive = False
                        self.p2_dead_time = now
                        self.p2_dead_reason = "Menebas Bom!"
                        self.p2_streak = 0
                        self.p2_trail.clear()
                        self.sounds.play("boom")
                        self._spawn_slice_effects(fruit)
                        if not self.p1_alive:
                            self._trigger_game_over()
                    else:
                        self.p2_streak += 1
                        mult2, col2, _ = self._compute_player_multiplier(self.p2_streak, is_p1=False)
                        self.player2 += mult2
                        self.sounds.play("slash")
                        lbl2 = f"+{mult2}" if mult2 == 1 else f"COMBO {mult2}x! +{mult2}"
                        self._spawn_slice_effects(fruit, lbl2, col2)
                        if (self.player1 + self.player2) // 35 + 1 > self.level:
                            self.level = (self.player1 + self.player2) // 35 + 1
                            self.sounds.play("levelup")

        self.p1_prev = smooth_p1
        self.p2_prev = smooth_p2

    def _update_fruits_and_effects(self):
        now = time.time()
        dt = max(0.0, min(0.2, now - self.last_frame_time))
        self.last_frame_time = now

        if not self.game_over and not self.paused:
            self.remaining_time = max(0.0, self.remaining_time - dt)
            if self.remaining_time <= 0.0:
                self._trigger_game_over()
                return

            mid_x = self.WIDTH // 2
            for fruit in self.fruits:
                missed_now = fruit.update(self.WIDTH, self.HEIGHT)
                if missed_now and not fruit.is_bomb:
                    cx = fruit.x + fruit.width / 2
                    miss_x = max(75, min(self.WIDTH - 75, cx))
                    if cx < mid_x and self.p1_alive:
                        self.p1_missed += 1
                        self.p1_streak = 0
                        self.floating_texts.append(
                            FloatingText("MISS P1!", miss_x, self.HEIGHT - 45, color=(255, 95, 90), size=24)
                        )
                        if self.p1_missed >= 10:
                            self.p1_alive = False
                            self.p1_dead_time = now
                            self.p1_dead_reason = "10 Buah Terlewat!"
                            self.p1_trail.clear()
                            if not self.p2_alive:
                                self._trigger_game_over()
                    elif cx >= mid_x and self.p2_alive:
                        self.p2_missed += 1
                        self.p2_streak = 0
                        self.floating_texts.append(
                            FloatingText("MISS P2!", miss_x, self.HEIGHT - 45, color=(255, 95, 90), size=24)
                        )
                        if self.p2_missed >= 10:
                            self.p2_alive = False
                            self.p2_dead_time = now
                            self.p2_dead_reason = "10 Buah Terlewat!"
                            self.p2_trail.clear()
                            if not self.p1_alive:
                                self._trigger_game_over()

            target_count = min(4 + self.level, 12)
            while len(self.fruits) < target_count:
                self.fruits.append(self.fruit_manager.spawn_fruit_multi(self.level, self.p1_alive, self.p2_alive))

            for i, fruit in enumerate(self.fruits):
                if not fruit.alive or fruit.cut:
                    self.fruits[i] = self.fruit_manager.spawn_fruit_multi(self.level, self.p1_alive, self.p2_alive)

        if not self.paused:
            for half in self.sliced_halves:
                half.update(self.HEIGHT)
            self.sliced_halves = [h for h in self.sliced_halves if h.alive]

            for pt in self.particles:
                pt.update()
            self.particles = [p for p in self.particles if p.alive]

            for ft in self.floating_texts:
                ft.update()
            self.floating_texts = [f for f in self.floating_texts if f.alive]

    def _draw_eliminated_half(self, side_x: int, side_w: int, player_name: str, reason: str, dead_time: float):
        """
        Menggelapkan separuh layar milik pemain yang sudah GUGUR disertai kilatan merah awal
        dan plakat status besar di tengah areanya agar langsung terlihat jelas.
        """
        now = time.time()
        self.screen.blit(self._half_dead_overlay, (side_x, 0))
        if now - dead_time < 0.45:
            self.screen.blit(self._half_flash_overlay, (side_x, 0))

        # Garis bingkai merah tanda area gugur
        border_rect = pygame.Rect(side_x + 4, 4, side_w - 8, self.HEIGHT - 8)
        pygame.draw.rect(self.screen, (215, 50, 45), border_rect, width=4, border_radius=12)

        cx = side_x + side_w // 2
        cy = self.HEIGHT // 2 + 20
        badge_rect = pygame.Rect(0, 0, 340, 155)
        badge_rect.center = (cx, cy)
        draw_glass_panel(
            self.screen,
            badge_rect,
            bg_color=(32, 12, 12, 238),
            border_color=(235, 75, 70, 240),
            border_radius=20,
            border_width=3,
        )

        f_big = FontCache.get_title_font(46)
        f_med = FontCache.get_ui_font(18, bold=True)
        f_sub = FontCache.get_ui_font(15, bold=False)

        t_gugur = f_big.render("GUGUR!", True, (255, 80, 75))
        self.screen.blit(t_gugur, t_gugur.get_rect(center=(cx, badge_rect.top + 42)))

        safe_name = truncate_text(f_med, player_name, 160)
        reason_str = f"{safe_name} • {reason}" if reason else f"{safe_name} telah gugur"
        t_reason = f_med.render(reason_str, True, (255, 215, 185))
        self.screen.blit(t_reason, t_reason.get_rect(center=(cx, badge_rect.top + 88)))

        t_wait = f_sub.render("Menunggu lawan menyelesaikan duel...", True, (210, 175, 150))
        self.screen.blit(t_wait, t_wait.get_rect(center=(cx, badge_rect.top + 122)))

    def _draw_hud(self, cam_frame, mouse_clicked: bool):
        mid_x = self.WIDTH // 2

        # Gelapkan separuh layar jika salah satu pemain gugur
        if not self.p1_alive:
            self._draw_eliminated_half(0, mid_x, self.p1_name, self.p1_dead_reason, self.p1_dead_time)
        if not self.p2_alive:
            self._draw_eliminated_half(mid_x, self.WIDTH - mid_x, self.p2_name, self.p2_dead_reason, self.p2_dead_time)

        pygame.draw.line(self.screen, (215, 165, 75), (mid_x, 0), (mid_x, self.HEIGHT), 3)

        font_title = FontCache.get_title_font(28)
        font_sub = FontCache.get_ui_font(15, bold=True)

        # Panel P1 (Kiri)
        p1_rect = pygame.Rect(20, 18, 275, 108)
        draw_glass_panel(self.screen, p1_rect, border_radius=16)
        safe_p1_name = truncate_text(font_title, self.p1_name, 165)
        p1_s = font_title.render(f"{safe_p1_name}: {self.player1}", True, (255, 220, 85))
        self.screen.blit(p1_s, (p1_rect.x + 16, p1_rect.y + 8))
        st1 = "AKTIF" if self.p1_alive else "GUGUR"
        col1 = (115, 245, 145) if self.p1_alive else (255, 95, 90)
        mult1, _, _ = self._compute_player_multiplier(self.p1_streak, is_p1=True)
        self.screen.blit(
            font_sub.render(f"Status: {st1}   •   Streak: {self.p1_streak} ({mult1}x)", True, col1),
            (p1_rect.x + 16, p1_rect.y + 46),
        )
        m1_col = (255, 95, 90) if self.p1_missed >= 7 else (225, 185, 140)
        self.screen.blit(
            font_sub.render(f"Terlewat: {self.p1_missed} / 10", True, m1_col),
            (p1_rect.x + 16, p1_rect.y + 74),
        )

        # Panel P2 (Kanan, di sebelah kiri tombol Pause)
        p2_rect = pygame.Rect(self.WIDTH - 365, 18, 275, 108)
        draw_glass_panel(self.screen, p2_rect, border_radius=16)
        safe_p2_name = truncate_text(font_title, self.p2_name, 165)
        p2_s = font_title.render(f"{safe_p2_name}: {self.player2}", True, (255, 200, 85))
        self.screen.blit(p2_s, (p2_rect.x + 16, p2_rect.y + 8))
        st2 = "AKTIF" if self.p2_alive else "GUGUR"
        col2 = (115, 245, 145) if self.p2_alive else (255, 95, 90)
        mult2, _, _ = self._compute_player_multiplier(self.p2_streak, is_p1=False)
        self.screen.blit(
            font_sub.render(f"Status: {st2}   •   Streak: {self.p2_streak} ({mult2}x)", True, col2),
            (p2_rect.x + 16, p2_rect.y + 46),
        )
        m2_col = (255, 95, 90) if self.p2_missed >= 7 else (225, 185, 140)
        self.screen.blit(
            font_sub.render(f"Terlewat: {self.p2_missed} / 10", True, m2_col),
            (p2_rect.x + 16, p2_rect.y + 74),
        )

        # Tombol Ikon Pause (Pojok Kanan Atas)
        pause_rect = pygame.Rect(self.WIDTH - 74, 22, 54, 54)
        if self.btn_mgr.draw_icon_button(
            self.screen,
            "multi_hud_pause",
            "pause",
            pause_rect,
            scheme="dark",
            tooltip="Jeda",
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.paused = True
            self.p1_trail.clear()
            self.p2_trail.clear()

        # Badge Timer Pertandingan & Level di Tengah Atas
        mins = int(self.remaining_time) // 60
        secs = int(self.remaining_time) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        time_col = (255, 90, 85) if self.remaining_time <= 15.0 else (255, 230, 110)

        lvl_rect = pygame.Rect(0, 0, 175, 68)
        lvl_rect.midtop = (mid_x, 16)
        draw_glass_panel(self.screen, lvl_rect, border_radius=16)
        time_surf = font_title.render(time_str, True, time_col)
        self.screen.blit(time_surf, time_surf.get_rect(center=(mid_x, lvl_rect.y + 24)))
        lvl_txt = font_sub.render(f"LEVEL {self.level}", True, (240, 215, 175))
        self.screen.blit(lvl_txt, lvl_txt.get_rect(center=(mid_x, lvl_rect.y + 52)))

        if self.settings.show_webcam_pip and cam_frame is not None:
            pip_w, pip_h = 195, 128
            pip_surf = self.hand_tracker.frame_to_pip_surface(cam_frame, (pip_w, pip_h))
            pip_rect = pygame.Rect(mid_x - pip_w // 2, self.HEIGHT - pip_h - 16, pip_w, pip_h)
            draw_glass_panel(self.screen, pip_rect.inflate(8, 8), border_radius=12, shadow=False)
            self.screen.blit(pip_surf, pip_rect.topleft)

    def _draw_pause_modal(self, mouse_clicked: bool) -> str | None:
        self.screen.blit(self._modal_overlay, (0, 0))

        cx, cy = self.WIDTH // 2, self.HEIGHT // 2
        card_rect = pygame.Rect(0, 0, 500, 430)
        card_rect.center = (cx, cy)
        draw_glass_panel(self.screen, card_rect, border_radius=24)

        title_font = FontCache.get_title_font(44)
        header = title_font.render("PERMAINAN DIJEDA", True, (255, 215, 75))
        self.screen.blit(header, header.get_rect(center=(cx, card_rect.top + 48)))

        lbl_font = FontCache.get_ui_font(20, bold=True)

        r1_y = card_rect.top + 105
        self.screen.blit(lbl_font.render("Musik Latar", True, (245, 230, 205)), (card_rect.left + 45, r1_y + 6))
        if self.btn_mgr.draw_toggle_switch(
            self.screen,
            "mp_pause_bgm",
            self.settings.bgm_enabled,
            pygame.Rect(card_rect.right - 135, r1_y, 90, 40),
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.settings.bgm_enabled = not self.settings.bgm_enabled
            self.sounds.sync_with_settings()

        r2_y = card_rect.top + 160
        self.screen.blit(lbl_font.render("Efek Suara", True, (245, 230, 205)), (card_rect.left + 45, r2_y + 6))
        if self.btn_mgr.draw_toggle_switch(
            self.screen,
            "mp_pause_sfx",
            self.settings.sfx_enabled,
            pygame.Rect(card_rect.right - 135, r2_y, 90, 40),
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.settings.sfx_enabled = not self.settings.sfx_enabled
            self.sounds.sync_with_settings()

        r3_y = card_rect.top + 215
        self.screen.blit(lbl_font.render("Gesture Jari", True, (245, 230, 205)), (card_rect.left + 45, r3_y + 8))
        if self.btn_mgr.draw_button(
            self.screen,
            "mp_pause_finger",
            f"<  {self.settings.get_finger_label()}  >",
            pygame.Rect(card_rect.right - 225, r3_y, 180, 42),
            scheme="info",
            font_size=18,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
            border_radius=12,
        ):
            self.settings.cycle_finger_mode(1)

        btn_y = card_rect.top + 290
        if self.btn_mgr.draw_button(
            self.screen,
            "mp_pause_resume",
            "Lanjutkan Bermain",
            pygame.Rect(cx - 205, btn_y, 410, 52),
            scheme="primary",
            icon="play",
            font_size=21,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.paused = False
            return None

        btn_y2 = btn_y + 64
        if self.btn_mgr.draw_button(
            self.screen,
            "mp_pause_restart",
            "Ulangi",
            pygame.Rect(cx - 205, btn_y2, 198, 48),
            scheme="success",
            icon="replay",
            font_size=19,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.reset_game()
            return None

        if self.btn_mgr.draw_button(
            self.screen,
            "mp_pause_menu",
            "Menu Utama",
            pygame.Rect(cx + 7, btn_y2, 198, 48),
            scheme="dark",
            icon="back",
            font_size=19,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            return "menu"

        return None

    def _draw_gameover_modal(self, mouse_clicked: bool) -> str | None:
        self.screen.blit(self._modal_overlay, (0, 0))

        elapsed = pygame.time.get_ticks() - self.go_start_ticks
        if self.show_go_screen and elapsed < self.GO_DURATION:
            font_go = FontCache.get_title_font(92)
            go_text = font_go.render("GAME OVER", True, (240, 60, 55))
            go_rect = go_text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(go_text, go_rect)
            return None

        self.show_go_screen = False
        cx, cy = self.WIDTH // 2, self.HEIGHT // 2

        card_rect = pygame.Rect(0, 0, 580, 420)
        card_rect.center = (cx, cy)
        draw_glass_panel(self.screen, card_rect, border_radius=24)

        title_font = FontCache.get_title_font(38)
        header = title_font.render("HASIL PERTANDINGAN", True, (255, 215, 75))
        self.screen.blit(header, header.get_rect(center=(cx, card_rect.top + 48)))

        win_font = FontCache.get_ui_font(21, bold=True)
        p1_short = truncate_text(win_font, self.p1_name.upper(), 240)
        p2_short = truncate_text(win_font, self.p2_name.upper(), 240)
        if self.player1 > self.player2:
            win_str = f"PEMENANG: {p1_short}!"
        elif self.player2 > self.player1:
            win_str = f"PEMENANG: {p2_short}!"
        else:
            win_str = "PERTANDINGAN SERI!"

        win_surf = win_font.render(win_str, True, (110, 255, 150))
        self.screen.blit(win_surf, win_surf.get_rect(center=(cx, card_rect.top + 96)))

        info_font = FontCache.get_ui_font(20, bold=True)
        p1_lbl = truncate_text(info_font, f"Skor {self.p1_name}", 250)
        p2_lbl = truncate_text(info_font, f"Skor {self.p2_name}", 250)
        rows = [
            (p1_lbl, f"{self.player1} Poin  (Miss {self.p1_missed}/10)"),
            (p2_lbl, f"{self.player2} Poin  (Miss {self.p2_missed}/10)"),
            ("Level Tercapai", f"Level {self.level}"),
        ]
        start_y = card_rect.top + 145
        for i, (label, val) in enumerate(rows):
            y_pos = start_y + i * 42
            lbl_s = info_font.render(label, True, (215, 190, 155))
            val_s = info_font.render(val, True, (255, 250, 240))
            self.screen.blit(lbl_s, (card_rect.left + 48, y_pos))
            self.screen.blit(val_s, val_s.get_rect(topright=(card_rect.right - 48, y_pos)))

        btn_y = card_rect.bottom - 72
        btn_w, btn_h = 144, 50
        gap = 14

        menu_rect = pygame.Rect(cx - btn_w - gap - btn_w // 2, btn_y, btn_w, btn_h)
        replay_rect = pygame.Rect(cx - btn_w // 2, btn_y, btn_w, btn_h)
        lb_rect = pygame.Rect(cx + btn_w // 2 + gap, btn_y, btn_w, btn_h)

        if self.btn_mgr.draw_button(
            self.screen,
            "go_multi_menu",
            "Menu",
            menu_rect,
            scheme="dark",
            icon="back",
            font_size=19,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            return "menu"

        if self.btn_mgr.draw_button(
            self.screen,
            "go_multi_replay",
            "Main Lagi",
            replay_rect,
            scheme="primary",
            icon="replay",
            font_size=19,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.reset_game()
            return None

        if self.btn_mgr.draw_button(
            self.screen,
            "go_multi_lb",
            "Peringkat",
            lb_rect,
            scheme="info",
            icon="trophy",
            font_size=19,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            return "leaderboard"

        return None

    def run(self):
        running = True
        font_float = FontCache.get_ui_font(26, bold=True)

        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._cleanup()
                    return "exit"
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_p):
                        if not self.game_over:
                            self.paused = not self.paused
                            self.p1_trail.clear()
                            self.p2_trail.clear()
                        else:
                            self._cleanup()
                            return "menu"
                    if self.game_over and event.key == pygame.K_r:
                        self.reset_game()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self._update_size()
            now = time.time()

            ok, cam_frame = self.hand_tracker.read_frame()
            self.screen.blit(self.background, (0, 0))

            if ok and cam_frame is not None:
                self._handle_hands_and_slice(cam_frame, now)
            else:
                self.hand_cursor.update_pointer(None)

            self._update_fruits_and_effects()

            for fruit in self.fruits:
                fruit.draw(self.screen)

            for half in self.sliced_halves:
                half.draw(self.screen)

            for pt in self.particles:
                pt.draw(self.screen)

            for ft in self.floating_texts:
                ft.draw(self.screen, font_float)

            if not self.game_over and not self.paused:
                _, p1_out, p1_in = self._compute_player_multiplier(self.p1_streak, is_p1=True)
                _, p2_out, p2_in = self._compute_player_multiplier(self.p2_streak, is_p1=False)
                self._draw_trail(self.p1_trail, now, p1_out, p1_in)
                self._draw_trail(self.p2_trail, now, p2_out, p2_in)
                self._draw_hud(cam_frame, mouse_clicked)
            elif self.paused:
                self._draw_hud(cam_frame, False)
                action = self._draw_pause_modal(mouse_clicked)
                if action in ("menu", "exit"):
                    self._cleanup()
                    return action
                self.hand_cursor.draw_cursor(self.screen)
            else:
                action = self._draw_gameover_modal(mouse_clicked)
                if action in ("menu", "leaderboard", "exit"):
                    self._cleanup()
                    return action
                self.hand_cursor.draw_cursor(self.screen)

            pygame.display.flip()
            self.clock.tick(60)

        self._cleanup()
        return "menu"

    def _cleanup(self):
        if self.owns_resources:
            self.hand_tracker.close()
        else:
            self.hand_tracker.set_max_hands(1)
        print("Multiplayer game closed safely.")
