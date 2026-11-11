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
)


class SoloFruitNinjaGame:
    def __init__(
        self,
        background_path="assets/themes/2.png",
        screen=None,
        settings=None,
        sounds=None,
        hand_tracker=None,
        db=None,
        current_user=None,
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
        pygame.display.set_caption("Fruit Ninja - Solo Mode")

        self.settings = settings if settings is not None else SettingsManager()
        self.sounds = sounds if sounds is not None else SoundManager(settings=self.settings)
        self.db = db if db is not None else DatabaseManager()
        self.current_user = current_user if current_user is not None else {"id": None, "username": "Tamu", "is_guest": True}

        self.hand_tracker = hand_tracker if hand_tracker is not None else HandTracker(max_hands=1)
        self.hand_tracker.set_max_hands(1)
        self.hand_tracker.ensure_camera(self.WIDTH, self.HEIGHT)

        self.background_path = background_path
        self._load_background()

        self.fruit_manager = FruitManager(self.WIDTH, self.HEIGHT)
        self.clock = pygame.time.Clock()
        self.btn_mgr = ModernButtonManager()
        self.hand_cursor = HandCursorManager(dwell_time=self.settings.dwell_time)

        user_stats = self.db.get_user_stats(self.current_user)
        self.personal_best = user_stats.get("highscore", 0)

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

    def reset_game(self):
        self.score = 0
        self.missed = 0
        self.level = 1
        self.streak = 0
        self.max_streak = 0
        self.multiplier = 1
        self.fruits = [self.fruit_manager.spawn_fruit_solo(1) for _ in range(3)]
        self.sliced_halves = []
        self.particles = []
        self.floating_texts = []

        self.prev_pos = None
        self.pointer_history = []
        self.last_slice_time = 0.0
        self.combo_count = 0

        self.paused = False
        self.game_over = False
        self.show_go_screen = False
        self.go_start_ticks = 0
        self.GO_DURATION = 1400
        self.db_saved_for_round = False
        self.is_new_highscore = False

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
            self.fruit_manager.WIDTH = self.WIDTH
            self.fruit_manager.HEIGHT = self.HEIGHT

    def _trigger_game_over(self):
        if self.game_over:
            return
        self.game_over = True
        self.paused = False
        self.show_go_screen = True
        self.go_start_ticks = pygame.time.get_ticks()
        self.pointer_history.clear()
        self.prev_pos = None

        if not self.db_saved_for_round:
            res = self.db.save_solo_score(
                self.current_user,
                score=self.score,
                missed=self.missed,
                level=self.level,
            )
            self.is_new_highscore = res.get("is_new_highscore", False)
            self.personal_best = max(self.personal_best, res.get("highscore", self.score))
            self.db_saved_for_round = True

    @staticmethod
    def _compute_multiplier(streak: int) -> tuple[int, str, tuple, tuple]:
        """
        Mengembalikan (multiplier, tier_label, outer_blade_color, inner_blade_color) berdasarkan streak.
        """
        if streak >= 20:
            return 4, "FRENZY 4x!", (255, 210, 20), (255, 255, 220)
        if streak >= 10:
            return 3, "SUPER 3x!", (215, 65, 255), (250, 220, 255)
        if streak >= 5:
            return 2, "HOT 2x!", (0, 215, 255), (215, 252, 255)
        return 1, "", (235, 115, 20), (255, 248, 200)

    def _spawn_slice_effects(self, fruit, pts_gained: int = 1, bonus_text=None):
        cx = fruit.x + fruit.width / 2
        cy = fruit.y + fruit.height / 2

        if not fruit.is_bomb:
            halves = self.fruit_manager.split_fruit_surface(fruit)
            self.sliced_halves.extend(halves)
            for _ in range(10):
                self.particles.append(JuiceParticle(cx, cy, fruit.color))
            _, _, outer_col, _ = self._compute_multiplier(self.streak)
            pt_col = (255, 240, 115) if pts_gained == 1 else outer_col
            self.floating_texts.append(FloatingText(f"+{pts_gained}", cx, cy - 10, color=pt_col, size=26))
            if bonus_text:
                self.floating_texts.append(FloatingText(bonus_text, cx, cy - 46, color=(110, 255, 155), size=28))
        else:
            for _ in range(22):
                self.particles.append(JuiceParticle(cx, cy, (255, 80, 20)))
            self.floating_texts.append(FloatingText("BOOM!", cx, cy, color=(255, 65, 65), size=38))

    def _draw_blade_trail(self, now: float):
        self.pointer_history = [p for p in self.pointer_history if now - p[2] < 0.20]
        if len(self.pointer_history) < 2:
            return

        _, _, outer_col, inner_col = self._compute_multiplier(self.streak)
        n = len(self.pointer_history)
        for i in range(1, n):
            x1, y1, _ = self.pointer_history[i - 1]
            x2, y2, _ = self.pointer_history[i]
            ratio = i / n
            thickness = max(2, int(14 * ratio))
            pygame.draw.line(self.screen, outer_col, (x1, y1), (x2, y2), thickness + 4)
            pygame.draw.line(self.screen, inner_col, (x1, y1), (x2, y2), max(1, thickness - 2))

        lx, ly, _ = self.pointer_history[-1]
        pygame.draw.circle(self.screen, outer_col, (lx, ly), 13)
        pygame.draw.circle(self.screen, inner_col, (lx, ly), 6)

    def _handle_gameplay_hand(self, pointer_pos, now: float):
        if pointer_pos is None or self.hand_tracker.hand_switched:
            self.pointer_history.clear()
            self.prev_pos = None
            if pointer_pos is None:
                return

        x, y = pointer_pos
        self.pointer_history.append((x, y, now))
        p1 = self.prev_pos if self.prev_pos is not None else (x, y)
        p2 = (x, y)

        # Hindari menebas buah jika tangan sedang berada di atas tombol Pause di pojok kanan atas
        pause_zone = pygame.Rect(self.WIDTH - 95, 0, 95, 90)
        if pause_zone.collidepoint(p2):
            self.prev_pos = (x, y)
            return

        for fruit in self.fruits:
            if fruit.is_Targetable:
                if segment_intersects_rect(p1, p2, fruit.rect):
                    fruit.cut = True
                    if fruit.is_bomb and not self.game_over:
                        self.sounds.play("boom")
                        self._spawn_slice_effects(fruit)
                        self._trigger_game_over()
                        break
                    else:
                        self.streak += 1
                        self.max_streak = max(self.max_streak, self.streak)
                        self.multiplier, tier_lbl, _, _ = self._compute_multiplier(self.streak)

                        pts = self.multiplier
                        self.score += pts
                        self.sounds.play("slash")

                        if now - self.last_slice_time < 0.32:
                            self.combo_count += 1
                        else:
                            self.combo_count = 1
                        self.last_slice_time = now

                        bonus_txt = None
                        if self.combo_count >= 2:
                            slash_bonus = min(6, self.combo_count)
                            self.score += slash_bonus
                            if self.combo_count == 2:
                                bonus_txt = f"DOUBLE SLASH! +{slash_bonus}"
                            elif self.combo_count == 3:
                                bonus_txt = f"TRIPLE SLASH! +{slash_bonus}"
                            else:
                                bonus_txt = f"MULTI SLASH x{self.combo_count}! +{slash_bonus}"
                        elif self.streak in (5, 10, 20):
                            bonus_txt = f"STREAK {self.streak}! {tier_lbl}"

                        if self.streak > 0 and self.streak % 20 == 0 and self.missed > 0:
                            self.missed = max(0, self.missed - 1)
                            bonus_txt = "FRENZY BONUS! NYAWA +1"

                        self._spawn_slice_effects(fruit, pts_gained=pts, bonus_text=bonus_txt)

                        if self.score > self.personal_best:
                            self.personal_best = self.score

                        if self.score // 30 + 1 > self.level:
                            self.level = self.score // 30 + 1
                            self.sounds.play("levelup")
                            self.floating_texts.append(
                                FloatingText(
                                    f"LEVEL {self.level}!",
                                    self.WIDTH // 2,
                                    140,
                                    color=(255, 225, 80),
                                    size=36,
                                )
                            )

        self.prev_pos = (x, y)

    def _update_fruits_and_effects(self):
        if not self.game_over and not self.paused:
            for fruit in self.fruits:
                missed_now = fruit.update(self.WIDTH, self.HEIGHT)
                if missed_now and not fruit.is_bomb:
                    self.missed += 1
                    miss_x = max(80, min(self.WIDTH - 80, fruit.x))
                    if self.streak >= 5:
                        self.floating_texts.append(
                            FloatingText(f"STREAK {self.streak} PUTUS!", miss_x, self.HEIGHT - 78, color=(255, 145, 50), size=24)
                        )
                    self.streak = 0
                    self.multiplier = 1
                    self.floating_texts.append(
                        FloatingText("MISS!", miss_x, self.HEIGHT - 45, color=(255, 90, 85), size=24)
                    )
                    if self.missed >= 10 and not self.game_over:
                        self._trigger_game_over()

            target_fruits = min(3 + (self.level - 1) // 2, 8)
            while len(self.fruits) < target_fruits:
                self.fruits.append(self.fruit_manager.spawn_fruit_solo(self.level))

            for i in range(len(self.fruits)):
                if not self.fruits[i].alive or self.fruits[i].cut:
                    self.fruits[i] = self.fruit_manager.spawn_fruit_solo(self.level)

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

    def _draw_hud(self, cam_frame, pointer_pos, mouse_clicked: bool):
        hud_rect = pygame.Rect(20, 18, 255, 118)
        draw_glass_panel(self.screen, hud_rect, border_radius=16)

        font_big = FontCache.get_title_font(34)
        font_med = FontCache.get_ui_font(18, bold=True)

        score_surf = font_big.render(f"SCORE: {self.score}", True, (255, 220, 75))
        self.screen.blit(score_surf, (hud_rect.x + 18, hud_rect.y + 10))

        best_surf = font_med.render(f"Rekor: {self.personal_best}   •   Lv.{self.level}", True, (240, 215, 165))
        self.screen.blit(best_surf, (hud_rect.x + 18, hud_rect.y + 52))

        miss_col = (255, 95, 90) if self.missed >= 7 else (225, 180, 130)
        miss_surf = font_med.render(f"Terlewat: {self.missed} / 10", True, miss_col)
        self.screen.blit(miss_surf, (hud_rect.x + 18, hud_rect.y + 80))

        # Badge Combo Streak Aktif (Tampil jika streak >= 3)
        if self.streak >= 3:
            mult, tier_lbl, outer_col, _ = self._compute_multiplier(self.streak)
            streak_rect = pygame.Rect(20, 144, 255, 44)
            draw_glass_panel(
                self.screen,
                streak_rect,
                border_color=(*outer_col, 240),
                border_radius=14,
                border_width=2,
            )
            st_txt = f"STREAK {self.streak}  •  {tier_lbl}" if tier_lbl else f"STREAK {self.streak}  •  1x"
            st_surf = font_med.render(st_txt, True, outer_col)
            self.screen.blit(st_surf, st_surf.get_rect(center=streak_rect.center))

        # Tombol Ikon Pause di Pojok Kanan Atas
        pause_rect = pygame.Rect(self.WIDTH - 76, 20, 54, 54)
        if self.btn_mgr.draw_icon_button(
            self.screen,
            "solo_hud_pause",
            "pause",
            pause_rect,
            scheme="dark",
            tooltip="Jeda",
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
        ):
            self.paused = True
            self.pointer_history.clear()

        if self.settings.show_webcam_pip and cam_frame is not None:
            pip_w, pip_h = 195, 130
            norm_pt = (pointer_pos[0] / self.WIDTH, pointer_pos[1] / self.HEIGHT) if pointer_pos else None
            pip_surf = self.hand_tracker.frame_to_pip_surface(cam_frame, (pip_w, pip_h), norm_pt)
            pip_rect = pygame.Rect(self.WIDTH - pip_w - 20, self.HEIGHT - pip_h - 20, pip_w, pip_h)
            draw_glass_panel(self.screen, pip_rect.inflate(10, 10), border_radius=12, shadow=False)
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

        # Pengaturan cepat di dalam Pause
        r1_y = card_rect.top + 105
        self.screen.blit(lbl_font.render("Musik Latar", True, (245, 230, 205)), (card_rect.left + 45, r1_y + 6))
        if self.btn_mgr.draw_toggle_switch(
            self.screen,
            "pause_bgm",
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
            "pause_sfx",
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
            "pause_finger",
            f"<  {self.settings.get_finger_label()}  >",
            pygame.Rect(card_rect.right - 225, r3_y, 180, 42),
            scheme="info",
            font_size=18,
            hand_cursor=self.hand_cursor,
            mouse_clicked_event=mouse_clicked,
            border_radius=12,
        ):
            self.settings.cycle_finger_mode(1)

        # Tombol aksi Pause
        btn_y = card_rect.top + 290
        if self.btn_mgr.draw_button(
            self.screen,
            "pause_resume",
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
            "pause_restart",
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
            "pause_menu",
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

        card_rect = pygame.Rect(0, 0, 520, 420)
        card_rect.center = (cx, cy)
        draw_glass_panel(self.screen, card_rect, border_radius=24)

        title_font = FontCache.get_title_font(46)
        header = title_font.render("HASIL PERMAINAN", True, (255, 215, 75))
        self.screen.blit(header, header.get_rect(center=(cx, card_rect.top + 48)))

        if self.is_new_highscore:
            badge_font = FontCache.get_ui_font(18, bold=True)
            badge = badge_font.render("REKOR BARU TERCAPAI!", True, (110, 255, 150))
            self.screen.blit(badge, badge.get_rect(center=(cx, card_rect.top + 88)))

        info_font = FontCache.get_ui_font(21, bold=True)
        rows = [
            ("Pemain", self.current_user.get("username", "Tamu")),
            ("Skor Akhir", str(self.score)),
            ("Skor Tertinggi", str(self.personal_best)),
            ("Streak Terbaik", f"{self.max_streak} Buah"),
            ("Level Tercapai", f"Level {self.level}"),
        ]
        start_y = card_rect.top + 120
        for i, (label, val) in enumerate(rows):
            y_pos = start_y + i * 36
            lbl_s = info_font.render(label, True, (215, 190, 155))
            val_s = info_font.render(val, True, (255, 250, 240))
            self.screen.blit(lbl_s, (card_rect.left + 55, y_pos))
            self.screen.blit(val_s, val_s.get_rect(topright=(card_rect.right - 55, y_pos)))

        btn_y = card_rect.bottom - 72
        btn_w, btn_h = 144, 50
        gap = 14

        menu_rect = pygame.Rect(cx - btn_w - gap - btn_w // 2, btn_y, btn_w, btn_h)
        replay_rect = pygame.Rect(cx - btn_w // 2, btn_y, btn_w, btn_h)
        lb_rect = pygame.Rect(cx + btn_w // 2 + gap, btn_y, btn_w, btn_h)

        if self.btn_mgr.draw_button(
            self.screen,
            "go_solo_menu",
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
            "go_solo_replay",
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
            "go_solo_lb",
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
        font_float = FontCache.get_ui_font(28, bold=True)

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
                            self.pointer_history.clear()
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
            pointer_pos = None
            if ok and cam_frame is not None:
                pointer_pos = self.hand_tracker.get_single_pointer(
                    cam_frame,
                    self.WIDTH,
                    self.HEIGHT,
                    finger_mode=self.settings.finger_mode,
                    require_raised=True,
                )

            self.hand_cursor.update_pointer(pointer_pos, dwell_time=self.settings.dwell_time)

            self.screen.blit(self.background, (0, 0))
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
                self._handle_gameplay_hand(pointer_pos, now)
                self._draw_blade_trail(now)
                self._draw_hud(cam_frame, pointer_pos, mouse_clicked)
            elif self.paused:
                self._draw_hud(cam_frame, pointer_pos, False)
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
        print("Solo game closed safely.")
