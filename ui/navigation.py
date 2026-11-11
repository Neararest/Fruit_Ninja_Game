import math
import sys
import time
import pygame

from core.settings import SettingsManager
from core.sound_manager import SoundManager
from core.hand_tracker import HandTracker
from core.database import DatabaseManager
from core.dataexcel import GameDataSaver
from game.solo_game import SoloFruitNinjaGame
from game.multi_game import MultiFruitNinjaGame
from ui.components import (
    FontCache,
    ModernButtonManager,
    HandCursorManager,
    TextInputBox,
    draw_glass_panel,
    truncate_text,
)


class MenuApp:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except Exception:
            pass

        self.WIDTH, self.HEIGHT = 1280, 720
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Fruit Ninja")

        self.settings = SettingsManager()
        self.sounds = SoundManager(settings=self.settings)
        self.db = DatabaseManager()
        self.data_saver = GameDataSaver()
        self.hand_tracker = HandTracker(max_hands=1)
        self.btn_mgr = ModernButtonManager()
        self.hand_cursor = HandCursorManager(dwell_time=self.settings.dwell_time)
        self.clock = pygame.time.Clock()

        self.MENU_MUSIC = "assets/sounds/music.mp3"

        self.themes = {
            "kaktus": "assets/themes/1.png",
            "kayu": "assets/themes/2.png",
            "salju": "assets/themes/3.png",
            "sakura": "assets/themes/4.png",
        }
        self.theme_labels = {
            "kaktus": "Gurun Kaktus",
            "kayu": "Dojo Kayu",
            "salju": "Lembah Salju",
            "sakura": "Taman Sakura",
        }
        self.selected_theme = self.settings.selected_theme
        if self.selected_theme not in self.themes:
            self.selected_theme = "kayu"

        self.theme_surfaces_raw = {}
        for name, path in self.themes.items():
            try:
                self.theme_surfaces_raw[name] = pygame.image.load(path).convert()
            except Exception:
                surf = pygame.Surface((1280, 720))
                surf.fill((36, 22, 14))
                self.theme_surfaces_raw[name] = surf

        self.theme_thumbs = {
            name: pygame.transform.smoothscale(surf, (245, 148))
            for name, surf in self.theme_surfaces_raw.items()
        }

        try:
            self.logo_img = pygame.image.load("assets/images2/45.png").convert_alpha()
        except Exception:
            self.logo_img = None

        self._cached_bg_size = None
        self._cached_bg_theme = None
        self.bg_scaled = None

        self.current_user = None
        self.last_p2_name = "Rival"
        self.toast_message = None
        self.toast_color = (115, 245, 145)
        self.toast_time = 0.0

        if self.settings.menu_hand_tracking:
            self.hand_tracker.ensure_camera(self.WIDTH, self.HEIGHT)

    def show_toast(self, message: str, is_error: bool = False):
        self.toast_message = message
        self.toast_color = (255, 110, 100) if is_error else (120, 250, 150)
        self.toast_time = time.time()

    def blit_scaled_background(self):
        w, h = self.screen.get_size()
        self.WIDTH, self.HEIGHT = w, h
        if self._cached_bg_size != (w, h) or self._cached_bg_theme != self.selected_theme:
            raw = self.theme_surfaces_raw.get(self.selected_theme)
            self.bg_scaled = pygame.transform.smoothscale(raw, (w, h))
            self._cached_bg_size = (w, h)
            self._cached_bg_theme = self.selected_theme

        self.screen.blit(self.bg_scaled, (0, 0))
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((16, 10, 6, 85))
        self.screen.blit(overlay, (0, 0))

    def _update_menu_hand_tracking(self):
        if not self.settings.menu_hand_tracking:
            self.hand_cursor.update_pointer(None)
            return None

        ok, cam_frame = self.hand_tracker.read_frame()
        if not ok or cam_frame is None:
            self.hand_cursor.update_pointer(None)
            return None

        pos = self.hand_tracker.get_single_pointer(
            cam_frame,
            self.WIDTH,
            self.HEIGHT,
            finger_mode=self.settings.finger_mode,
            require_raised=False,
        )
        self.hand_cursor.update_pointer(pos, dwell_time=self.settings.dwell_time)
        return cam_frame

    def _draw_overlay_extras(self, cam_frame):
        if self.settings.menu_hand_tracking and self.settings.show_webcam_pip and cam_frame is not None:
            pip_w, pip_h = 185, 122
            ptr = self.hand_cursor.pointer_pos
            norm_pt = (ptr[0] / self.WIDTH, ptr[1] / self.HEIGHT) if ptr else None
            pip_surf = self.hand_tracker.frame_to_pip_surface(cam_frame, (pip_w, pip_h), norm_pt)
            pip_rect = pygame.Rect(self.WIDTH - pip_w - 22, self.HEIGHT - pip_h - 22, pip_w, pip_h)
            draw_glass_panel(self.screen, pip_rect.inflate(10, 10), border_radius=12, shadow=False)
            self.screen.blit(pip_surf, pip_rect.topleft)

        if self.toast_message:
            if time.time() - self.toast_time < 2.6:
                font = FontCache.get_ui_font(18, bold=True)
                surf = font.render(self.toast_message, True, self.toast_color)
                rect = surf.get_rect(center=(self.WIDTH // 2, self.HEIGHT - 36))
                draw_glass_panel(self.screen, rect.inflate(28, 14), border_radius=12, shadow=False)
                self.screen.blit(surf, rect)
            else:
                self.toast_message = None

        if self.settings.menu_hand_tracking:
            self.hand_cursor.draw_cursor(self.screen)

    def fade_transition(self):
        width, height = self.screen.get_size()
        fade = pygame.Surface((width, height))
        fade.fill((14, 8, 4))
        for alpha in range(0, 210, 40):
            fade.set_alpha(alpha)
            self.screen.blit(fade, (0, 0))
            pygame.display.update()
            pygame.time.delay(10)

    def auth_menu(self):
        cx, cy = self.WIDTH // 2, self.HEIGHT // 2
        user_box = TextInputBox(pygame.Rect(cx - 190, cy - 55, 380, 50), placeholder="Masukkan nama akun...")
        pass_box = TextInputBox(pygame.Rect(cx - 190, cy + 30, 380, 50), placeholder="Masukkan kata sandi...", is_password=True)
        user_box.active = True

        running = True
        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                user_box.handle_event(event)
                pass_box.handle_event(event)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                    user_box.active = not user_box.active
                    pass_box.active = not pass_box.active
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            cx, cy = self.WIDTH // 2, self.HEIGHT // 2

            card_rect = pygame.Rect(0, 0, 490, 460)
            card_rect.center = (cx, cy)
            draw_glass_panel(self.screen, card_rect, border_radius=24)

            title_font = FontCache.get_title_font(44)
            sub_font = FontCache.get_ui_font(16, bold=False)

            title_s = title_font.render("AKUN DOJO", True, (255, 215, 75))
            self.screen.blit(title_s, title_s.get_rect(center=(cx, card_rect.top + 48)))

            sub_s = sub_font.render("Masuk untuk menyimpan rekor dan peringkat Anda", True, (220, 195, 160))
            self.screen.blit(sub_s, sub_s.get_rect(center=(cx, card_rect.top + 86)))

            user_box.rect.topleft = (cx - 190, card_rect.top + 132)
            pass_box.rect.topleft = (cx - 190, card_rect.top + 218)
            user_box.draw(self.screen, label="Username", hand_cursor=self.hand_cursor)
            pass_box.draw(self.screen, label="Password", hand_cursor=self.hand_cursor)

            btn_y1 = card_rect.top + 295
            login_rect = pygame.Rect(cx - 190, btn_y1, 184, 50)
            reg_rect = pygame.Rect(cx + 6, btn_y1, 184, 50)
            guest_rect = pygame.Rect(cx - 190, btn_y1 + 64, 380, 46)

            if self.btn_mgr.draw_button(
                self.screen,
                "auth_login",
                "Masuk",
                login_rect,
                scheme="primary",
                icon="user",
                font_size=20,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                ok, msg, user_data = self.db.login_user(user_box.text, pass_box.text)
                self.show_toast(msg, is_error=not ok)
                if ok:
                    self.current_user = user_data
                    self.fade_transition()
                    return

            if self.btn_mgr.draw_button(
                self.screen,
                "auth_register",
                "Daftar Baru",
                reg_rect,
                scheme="success",
                icon="user",
                font_size=20,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                ok, msg, user_data = self.db.register_user(user_box.text, pass_box.text)
                self.show_toast(msg, is_error=not ok)
                if ok:
                    self.current_user = user_data
                    self.fade_transition()
                    return

            if self.btn_mgr.draw_button(
                self.screen,
                "auth_guest",
                "Main Tanpa Akun",
                guest_rect,
                scheme="dark",
                icon="play",
                font_size=19,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.current_user = {"id": None, "username": "Tamu", "is_guest": True}
                self.fade_transition()
                return

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def main_menu(self):
        self.sounds.play_music(self.MENU_MUSIC)

        if self.current_user is None:
            self.auth_menu()

        running = True
        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            w, h = self.WIDTH, self.HEIGHT
            cx = w // 2

            # 1. Bar Kiri Atas: Badge Profil Ringkas + Tombol Ikon Ganti Akun
            stats = self.db.get_user_stats(self.current_user)
            prof_rect = pygame.Rect(22, 20, 235, 62)
            draw_glass_panel(self.screen, prof_rect, border_radius=16)

            u_font = FontCache.get_ui_font(18, bold=True)
            s_font = FontCache.get_ui_font(15, bold=False)
            uname_disp = truncate_text(u_font, self.current_user["username"], 145)
            self.screen.blit(u_font.render(uname_disp, True, (255, 225, 95)), (prof_rect.x + 16, prof_rect.y + 8))
            self.screen.blit(
                s_font.render(f"Rekor: {stats['highscore']}   •   {stats['total_games']}x main", True, (225, 195, 155)),
                (prof_rect.x + 16, prof_rect.y + 34),
            )

            if self.btn_mgr.draw_icon_button(
                self.screen,
                "icon_switch_user",
                "user",
                pygame.Rect(prof_rect.right + 10, 23, 56, 56),
                scheme="dark",
                tooltip="Ganti Akun",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                self.auth_menu()

            # 2. Bar Kanan Atas: Tombol Ikon Navigasi (Leaderboard, Tema, Pengaturan, Keluar)
            icon_size = 56
            icon_gap = 14
            right_start = w - 22 - icon_size

            if self.btn_mgr.draw_icon_button(
                self.screen,
                "icon_exit",
                "exit",
                pygame.Rect(right_start, 22, icon_size, icon_size),
                scheme="danger",
                tooltip="Keluar",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self._shutdown()

            if self.btn_mgr.draw_icon_button(
                self.screen,
                "icon_settings",
                "settings",
                pygame.Rect(right_start - (icon_size + icon_gap), 22, icon_size, icon_size),
                scheme="dark",
                tooltip="Pengaturan",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                self.settings_menu()

            if self.btn_mgr.draw_icon_button(
                self.screen,
                "icon_theme",
                "theme",
                pygame.Rect(right_start - (icon_size + icon_gap) * 2, 22, icon_size, icon_size),
                scheme="success",
                tooltip="Tema Arena",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                self.theme_menu()

            if self.btn_mgr.draw_icon_button(
                self.screen,
                "icon_leaderboard",
                "trophy",
                pygame.Rect(right_start - (icon_size + icon_gap) * 3, 22, icon_size, icon_size),
                scheme="info",
                tooltip="Peringkat",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                self.leaderboard_menu()

            # 3. Logo Tengah dengan animasi mengayun lembut
            float_offset = int(math.sin(time.time() * 2.4) * 6)
            if self.logo_img:
                logo_rect = self.logo_img.get_rect(center=(cx, 175 + float_offset))
                self.screen.blit(self.logo_img, logo_rect.topleft)
            else:
                t_font = FontCache.get_title_font(76)
                t_surf = t_font.render("FRUIT NINJA", True, (255, 215, 65))
                self.screen.blit(t_surf, t_surf.get_rect(center=(cx, 170 + float_offset)))

            # 4. Dua Kartu Mode Utama di Tengah (Main Solo & Duel Multi)
            card_w, card_h = 330, 235
            solo_card = pygame.Rect(cx - card_w - 22, 330, card_w, card_h)
            multi_card = pygame.Rect(cx + 22, 330, card_w, card_h)

            draw_glass_panel(self.screen, solo_card, border_radius=22)
            draw_glass_panel(self.screen, multi_card, border_radius=22)

            mode_title_font = FontCache.get_title_font(34)
            mode_desc_font = FontCache.get_ui_font(16, bold=False)

            # Kartu Solo
            s_t = mode_title_font.render("MODE SOLO", True, (255, 215, 75))
            self.screen.blit(s_t, s_t.get_rect(center=(solo_card.centerx, solo_card.top + 44)))
            s_d1 = mode_desc_font.render("Tebas buah yang melambung,", True, (225, 200, 165))
            s_d2 = mode_desc_font.render("raih combo & hindari bom!", True, (225, 200, 165))
            self.screen.blit(s_d1, s_d1.get_rect(center=(solo_card.centerx, solo_card.top + 88)))
            self.screen.blit(s_d2, s_d2.get_rect(center=(solo_card.centerx, solo_card.top + 114)))

            if self.btn_mgr.draw_button(
                self.screen,
                "main_start_solo",
                "MAIN SOLO",
                pygame.Rect(solo_card.left + 30, solo_card.bottom - 76, card_w - 60, 56),
                scheme="primary",
                icon="solo",
                font_size=24,
                use_title_font=True,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                game = SoloFruitNinjaGame(
                    background_path=self.themes[self.selected_theme],
                    screen=self.screen,
                    settings=self.settings,
                    sounds=self.sounds,
                    hand_tracker=self.hand_tracker,
                    db=self.db,
                    current_user=self.current_user,
                )
                result = game.run()
                pygame.display.set_caption("Fruit Ninja")
                self.sounds.play_music(self.MENU_MUSIC)
                if result == "exit":
                    self._shutdown()
                elif result == "leaderboard":
                    self.leaderboard_menu()

            # Kartu Duel Multi
            m_t = mode_title_font.render("DUEL MULTI", True, (255, 215, 75))
            self.screen.blit(m_t, m_t.get_rect(center=(multi_card.centerx, multi_card.top + 44)))
            m_d1 = mode_desc_font.render("2 Pemain dalam 1 kamera,", True, (225, 200, 165))
            m_d2 = mode_desc_font.render("adu ketangkasan sisi kiri vs kanan!", True, (225, 200, 165))
            self.screen.blit(m_d1, m_d1.get_rect(center=(multi_card.centerx, multi_card.top + 88)))
            self.screen.blit(m_d2, m_d2.get_rect(center=(multi_card.centerx, multi_card.top + 114)))

            if self.btn_mgr.draw_button(
                self.screen,
                "main_start_multi",
                "DUEL MULTI",
                pygame.Rect(multi_card.left + 30, multi_card.bottom - 76, card_w - 60, 56),
                scheme="info",
                icon="multi",
                font_size=24,
                use_title_font=True,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                self.multi_setup_menu()

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def multi_setup_menu(self):
        """
        Modal persiapan singkat sebelum Multiplayer dimulai agar Player 2 memiliki nama/identitas.
        """
        cx, cy = self.WIDTH // 2, self.HEIGHT // 2
        p1_name = self.current_user.get("username", "Ninja 1") if self.current_user else "Ninja 1"
        if p1_name in ("Guest", "Tamu", ""):
            p1_name = "Ninja 1"

        p2_box = TextInputBox(pygame.Rect(cx + 35, cy - 25, 290, 48), placeholder="Ketik nama Pemain 2...")
        p2_box.text = self.last_p2_name
        p2_box.active = True

        existing_users = self.db.get_registered_usernames(exclude_username=p1_name, limit=4)

        running = True
        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                p2_box.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            cx, cy = self.WIDTH // 2, self.HEIGHT // 2

            panel_rect = pygame.Rect(0, 0, 760, 450)
            panel_rect.center = (cx, cy)
            draw_glass_panel(self.screen, panel_rect, border_radius=24)

            title_font = FontCache.get_title_font(44)
            title = title_font.render("PERSIAPAN DUEL", True, (255, 215, 75))
            self.screen.blit(title, title.get_rect(center=(cx, panel_rect.top + 48)))

            # Kotak Pemain 1 (Kiri)
            p1_card = pygame.Rect(panel_rect.left + 38, panel_rect.top + 95, 305, 235)
            p2_card = pygame.Rect(panel_rect.right - 343, panel_rect.top + 95, 305, 235)
            pygame.draw.rect(self.screen, (48, 30, 18), p1_card, border_radius=18)
            pygame.draw.rect(self.screen, (175, 130, 70), p1_card, width=2, border_radius=18)
            pygame.draw.rect(self.screen, (48, 30, 18), p2_card, border_radius=18)
            pygame.draw.rect(self.screen, (175, 130, 70), p2_card, width=2, border_radius=18)

            vs_font = FontCache.get_title_font(34)
            vs_s = vs_font.render("VS", True, (240, 95, 45))
            self.screen.blit(vs_s, vs_s.get_rect(center=(cx, p1_card.centery)))

            h_font = FontCache.get_ui_font(18, bold=True)
            name_font = FontCache.get_title_font(32)
            sub_font = FontCache.get_ui_font(15, bold=False)

            self.screen.blit(h_font.render("PEMAIN 1 • SISI KIRI", True, (215, 180, 130)), (p1_card.x + 22, p1_card.y + 18))
            p1_disp = truncate_text(name_font, p1_name, p1_card.width - 40)
            self.screen.blit(name_font.render(p1_disp, True, (255, 225, 85)), (p1_card.x + 22, p1_card.y + 72))
            self.screen.blit(sub_font.render("Menggunakan akun aktif saat ini", True, (185, 160, 130)), (p1_card.x + 22, p1_card.y + 125))

            # Kotak Pemain 2 (Kanan)
            self.screen.blit(h_font.render("PEMAIN 2 • SISI KANAN", True, (215, 180, 130)), (p2_card.x + 22, p2_card.y + 18))
            p2_box.rect = pygame.Rect(p2_card.x + 20, p2_card.y + 56, p2_card.width - 40, 46)
            p2_box.draw(self.screen, hand_cursor=self.hand_cursor)

            if existing_users:
                self.screen.blit(sub_font.render("Atau pilih akun terdaftar:", True, (200, 175, 140)), (p2_card.x + 22, p2_card.y + 114))
                pill_w = (p2_card.width - 50) // 2
                for idx, uname in enumerate(existing_users[:4]):
                    col = idx % 2
                    row = idx // 2
                    px = p2_card.x + 20 + col * (pill_w + 10)
                    py = p2_card.y + 142 + row * 40
                    u_short = truncate_text(sub_font, uname, pill_w - 16)
                    if self.btn_mgr.draw_button(
                        self.screen,
                        f"pick_p2_{uname}",
                        u_short,
                        pygame.Rect(px, py, pill_w, 34),
                        scheme="info" if p2_box.text.lower() == uname.lower() else "dark",
                        font_size=15,
                        hand_cursor=self.hand_cursor,
                        mouse_clicked_event=mouse_clicked,
                        border_radius=10,
                    ):
                        p2_box.text = uname

            btn_y = panel_rect.bottom - 74
            if self.btn_mgr.draw_button(
                self.screen,
                "duel_back",
                "Batal",
                pygame.Rect(cx - 240, btn_y, 170, 52),
                scheme="dark",
                icon="back",
                font_size=20,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                return

            if self.btn_mgr.draw_button(
                self.screen,
                "duel_start",
                "MULAI DUEL",
                pygame.Rect(cx - 50, btn_y, 290, 52),
                scheme="primary",
                icon="multi",
                font_size=24,
                use_title_font=True,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                chosen_p2 = p2_box.text.strip() if p2_box.text.strip() else "Rival"
                self.last_p2_name = chosen_p2
                self.fade_transition()
                game = MultiFruitNinjaGame(
                    background_path=self.themes[self.selected_theme],
                    screen=self.screen,
                    settings=self.settings,
                    sounds=self.sounds,
                    hand_tracker=self.hand_tracker,
                    db=self.db,
                    current_user=self.current_user,
                    p2_name=chosen_p2,
                )
                result = game.run()
                pygame.display.set_caption("Fruit Ninja")
                self.sounds.play_music(self.MENU_MUSIC)
                if result == "exit":
                    self._shutdown()
                elif result == "leaderboard":
                    self.leaderboard_menu()
                return

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def settings_menu(self):
        dwell_presets = [0.8, 1.2, 1.6]
        running = True

        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            w, h = self.WIDTH, self.HEIGHT
            cx = w // 2

            panel_rect = pygame.Rect(cx - 410, 52, 820, 600)
            draw_glass_panel(self.screen, panel_rect, border_radius=24)

            title_font = FontCache.get_title_font(44)
            title = title_font.render("PENGATURAN", True, (255, 215, 75))
            self.screen.blit(title, title.get_rect(center=(cx, panel_rect.top + 48)))

            lbl_font = FontCache.get_ui_font(21, bold=True)
            sub_font = FontCache.get_ui_font(15, bold=False)

            items = [
                ("Musik Latar", "Putar musik latar selama di menu dan arena", "toggle", "set_bgm", self.settings.bgm_enabled),
                ("Efek Suara", "Suara tebasan pedang, kombo, dan ledakan bom", "toggle", "set_sfx", self.settings.sfx_enabled),
                ("Gesture Jari", "Bagian tangan yang dilacak kamera sebagai pedang", "cycle", "set_finger", f"<  {self.settings.get_finger_label()}  >"),
                ("Navigasi Tangan di Menu", "Gunakan gerakan tangan sejak di menu awal", "toggle", "set_menu_hand", self.settings.menu_hand_tracking),
                ("Waktu Tahan Klik", "Durasi menahan jari pada tombol menu", "cycle", "set_dwell", f"<  {self.settings.dwell_time:.1f} Detik  >"),
                ("Layar Kamera Mini", "Tampilkan pratinjau kamera di sudut kanan bawah", "toggle", "set_pip", self.settings.show_webcam_pip),
            ]

            start_y = panel_rect.top + 98
            row_h = 70

            for i, (title_str, desc_str, kind, btn_id, val) in enumerate(items):
                ry = start_y + i * row_h
                row_bg = pygame.Rect(panel_rect.left + 36, ry, panel_rect.width - 72, 60)
                pygame.draw.rect(self.screen, (52, 32, 20), row_bg, border_radius=14)
                pygame.draw.rect(self.screen, (125, 88, 52), row_bg, width=1, border_radius=14)

                self.screen.blit(lbl_font.render(title_str, True, (250, 240, 225)), (row_bg.left + 20, row_bg.top + 7))
                self.screen.blit(sub_font.render(desc_str, True, (205, 175, 140)), (row_bg.left + 20, row_bg.top + 34))

                if kind == "toggle":
                    sw_rect = pygame.Rect(row_bg.right - 125, row_bg.top + 10, 105, 40)
                    if self.btn_mgr.draw_toggle_switch(
                        self.screen,
                        btn_id,
                        bool(val),
                        sw_rect,
                        hand_cursor=self.hand_cursor,
                        mouse_clicked_event=mouse_clicked,
                    ):
                        if btn_id == "set_bgm":
                            self.settings.bgm_enabled = not self.settings.bgm_enabled
                            self.sounds.sync_with_settings()
                        elif btn_id == "set_sfx":
                            self.settings.sfx_enabled = not self.settings.sfx_enabled
                            self.sounds.sync_with_settings()
                        elif btn_id == "set_menu_hand":
                            self.settings.menu_hand_tracking = not self.settings.menu_hand_tracking
                            if self.settings.menu_hand_tracking:
                                self.hand_tracker.ensure_camera(self.WIDTH, self.HEIGHT)
                        elif btn_id == "set_pip":
                            self.settings.show_webcam_pip = not self.settings.show_webcam_pip
                else:
                    cyc_rect = pygame.Rect(row_bg.right - 220, row_bg.top + 8, 200, 44)
                    if self.btn_mgr.draw_button(
                        self.screen,
                        btn_id,
                        str(val),
                        cyc_rect,
                        scheme="primary" if btn_id == "set_finger" else "info",
                        font_size=18,
                        hand_cursor=self.hand_cursor,
                        mouse_clicked_event=mouse_clicked,
                        border_radius=12,
                    ):
                        if btn_id == "set_finger":
                            self.settings.cycle_finger_mode(1)
                        elif btn_id == "set_dwell":
                            curr = round(self.settings.dwell_time, 1)
                            idx = dwell_presets.index(curr) if curr in dwell_presets else 1
                            self.settings.dwell_time = dwell_presets[(idx + 1) % len(dwell_presets)]

            back_rect = pygame.Rect(cx - 130, panel_rect.bottom - 66, 260, 48)
            if self.btn_mgr.draw_button(
                self.screen,
                "settings_back",
                "Kembali",
                back_rect,
                scheme="dark",
                icon="back",
                font_size=20,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                return

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def leaderboard_menu(self):
        active_tab = "solo"
        running = True

        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            w, h = self.WIDTH, self.HEIGHT
            cx = w // 2

            panel_rect = pygame.Rect(cx - 460, 45, 920, 615)
            draw_glass_panel(self.screen, panel_rect, border_radius=24)

            title_font = FontCache.get_title_font(44)
            title = title_font.render("PAPAN PERINGKAT", True, (255, 215, 75))
            self.screen.blit(title, title.get_rect(center=(cx, panel_rect.top + 44)))

            # Tombol Ikon Export Excel di Pojok Kanan Atas Panel Leaderboard
            export_rect = pygame.Rect(panel_rect.right - 74, panel_rect.top + 22, 48, 48)
            if self.btn_mgr.draw_icon_button(
                self.screen,
                "lb_export_excel",
                "save",
                export_rect,
                scheme="success",
                tooltip="Ekspor ke Excel",
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                solo_rows = self.db.get_solo_leaderboard(limit=50)
                for r in solo_rows:
                    self.data_saver.save_solo(r["highscore"], 0, r["max_level"], username=r["username"])
                self.show_toast("Data peringkat berhasil diekspor ke game_data.xlsx!")

            # Tab Selector Tanpa Tanda Kurung
            tab_w, tab_h = 240, 44
            tab_y = panel_rect.top + 84
            if self.btn_mgr.draw_button(
                self.screen,
                "tab_solo",
                "MODE SOLO",
                pygame.Rect(cx - tab_w - 10, tab_y, tab_w, tab_h),
                scheme="primary" if active_tab == "solo" else "dark",
                icon="trophy",
                font_size=18,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                active_tab = "solo"

            if self.btn_mgr.draw_button(
                self.screen,
                "tab_multi",
                "DUEL MULTI",
                pygame.Rect(cx + 10, tab_y, tab_w, tab_h),
                scheme="info" if active_tab == "multi" else "dark",
                icon="multi",
                font_size=18,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                active_tab = "multi"

            head_font = FontCache.get_ui_font(17, bold=True)
            row_font = FontCache.get_ui_font(17, bold=False)
            table_top = tab_y + 58
            table_left = panel_rect.left + 36
            table_w = panel_rect.width - 72  # 848 px

            head_rect = pygame.Rect(table_left, table_top, table_w, 38)
            pygame.draw.rect(self.screen, (72, 46, 26), head_rect, border_radius=10)
            pygame.draw.rect(self.screen, (165, 122, 68), head_rect, width=1, border_radius=10)

            if active_tab == "solo":
                # Semua offset + lebar kolom dijamin <= 835px sehingga tidak pernah keluar garis!
                cols = [
                    ("RANK", 22, 65),
                    ("NAMA PEMAIN", 105, 220),
                    ("SKOR TERTINGGI", 345, 150),
                    ("LEVEL", 520, 85),
                    ("MAIN", 620, 75),
                    ("WAKTU", 715, 118),
                ]
                for col_name, ox, _ in cols:
                    s = head_font.render(col_name, True, (255, 220, 95))
                    self.screen.blit(s, (table_left + ox, table_top + 7))

                rows = self.db.get_solo_leaderboard(limit=9)
                if not rows:
                    empty_s = head_font.render("Belum ada rekor tercatat. Ayo mulai bermain!", True, (220, 195, 160))
                    self.screen.blit(empty_s, empty_s.get_rect(center=(cx, table_top + 180)))
                else:
                    for idx, r in enumerate(rows):
                        ry = table_top + 44 + idx * 38
                        is_me = self.current_user and r["username"].lower() == self.current_user["username"].lower()
                        bg_c = (68, 82, 46) if is_me else ((52, 34, 20) if idx % 2 == 0 else (42, 26, 15))
                        pygame.draw.rect(self.screen, bg_c, pygame.Rect(table_left, ry, table_w, 34), border_radius=8)

                        txt_col = (255, 225, 85) if r["rank"] <= 3 else (245, 235, 220)
                        date_short = str(r["last_played"])[:10]

                        vals = [
                            (f"#{r['rank']}", 22, 65),
                            (str(r["username"]), 105, 220),
                            (str(r["highscore"]), 385, 110),
                            (f"Lv.{r['max_level']}", 525, 80),
                            (f"{r['total_games']}x", 628, 70),
                            (date_short, 715, 118),
                        ]
                        for val_str, ox, max_w in vals:
                            safe_str = truncate_text(row_font, val_str, max_w)
                            self.screen.blit(row_font.render(safe_str, True, txt_col), (table_left + ox, ry + 5))
            else:
                cols = [
                    ("RANK", 22, 65),
                    ("PERTANDINGAN", 105, 245),
                    ("SKOR AKHIR", 370, 145),
                    ("PEMENANG", 535, 160),
                    ("WAKTU", 715, 118),
                ]
                for col_name, ox, _ in cols:
                    s = head_font.render(col_name, True, (255, 220, 95))
                    self.screen.blit(s, (table_left + ox, table_top + 7))

                rows = self.db.get_multi_leaderboard(limit=9)
                if not rows:
                    empty_s = head_font.render("Belum ada riwayat duel Multiplayer.", True, (220, 195, 160))
                    self.screen.blit(empty_s, empty_s.get_rect(center=(cx, table_top + 180)))
                else:
                    for idx, r in enumerate(rows):
                        ry = table_top + 44 + idx * 38
                        bg_c = (52, 34, 20) if idx % 2 == 0 else (42, 26, 15)
                        pygame.draw.rect(self.screen, bg_c, pygame.Rect(table_left, ry, table_w, 34), border_radius=8)
                        txt_col = (255, 225, 85) if r["rank"] <= 3 else (245, 235, 220)
                        date_short = str(r["played_at"])[:10]

                        vals = [
                            (f"#{r['rank']}", 22, 65),
                            (f"{r['p1_name']} vs {r['p2_name']}", 105, 245),
                            (f"{r['p1_score']} - {r['p2_score']}", 385, 130),
                            (str(r["winner"]), 535, 160),
                            (date_short, 715, 118),
                        ]
                        for val_str, ox, max_w in vals:
                            safe_str = truncate_text(row_font, val_str, max_w)
                            self.screen.blit(row_font.render(safe_str, True, txt_col), (table_left + ox, ry + 5))

            back_rect = pygame.Rect(cx - 130, panel_rect.bottom - 64, 260, 48)
            if self.btn_mgr.draw_button(
                self.screen,
                "lb_back",
                "Kembali",
                back_rect,
                scheme="dark",
                icon="back",
                font_size=20,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                return

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def theme_menu(self):
        running = True
        while running:
            mouse_clicked = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked = True

            self.blit_scaled_background()
            cam_frame = self._update_menu_hand_tracking()
            w, h = self.WIDTH, self.HEIGHT
            cx = w // 2

            title_font = FontCache.get_title_font(52)
            title = title_font.render("TEMA ARENA", True, (255, 215, 75))
            self.screen.blit(title, title.get_rect(center=(cx, 92)))

            num_themes = len(self.themes)
            card_w, card_h = 265, 265
            padding = 24
            total_w = num_themes * card_w + (num_themes - 1) * padding
            start_x = (w - total_w) // 2
            y_card = 190

            for idx, (name, _) in enumerate(self.themes.items()):
                cur_x = start_x + idx * (card_w + padding)
                c_rect = pygame.Rect(cur_x, y_card, card_w, card_h)
                is_selected = name == self.selected_theme

                b_col = (255, 215, 70, 255) if is_selected else (155, 115, 68, 190)
                draw_glass_panel(self.screen, c_rect, border_color=b_col, border_width=4 if is_selected else 2, border_radius=20)

                thumb = self.theme_thumbs[name]
                self.screen.blit(thumb, (cur_x + (card_w - 245) // 2, y_card + 14))

                btn_txt = "AKTIF ✓" if is_selected else self.theme_labels.get(name, name)
                btn_scheme = "success" if is_selected else "primary"
                btn_rect = pygame.Rect(cur_x + 20, c_rect.bottom - 68, card_w - 40, 48)

                if self.btn_mgr.draw_button(
                    self.screen,
                    f"theme_select_{name}",
                    btn_txt,
                    btn_rect,
                    scheme=btn_scheme,
                    font_size=19,
                    hand_cursor=self.hand_cursor,
                    mouse_clicked_event=mouse_clicked,
                ):
                    self.selected_theme = name
                    self.settings.selected_theme = name

            back_rect = pygame.Rect(cx - 130, 535, 260, 52)
            if self.btn_mgr.draw_button(
                self.screen,
                "theme_back",
                "Kembali",
                back_rect,
                scheme="dark",
                icon="back",
                font_size=21,
                hand_cursor=self.hand_cursor,
                mouse_clicked_event=mouse_clicked,
            ):
                self.fade_transition()
                return

            self._draw_overlay_extras(cam_frame)
            pygame.display.flip()
            self.clock.tick(38)

    def _shutdown(self):
        self.hand_tracker.close()
        pygame.quit()
        sys.exit()
