import math
import os
import time
import pygame


COLOR_SCHEMES = {
    "primary": {
        "bg": (210, 88, 22),
        "bg_hover": (238, 112, 34),
        "border": (255, 210, 105),
        "text": (255, 250, 240),
    },
    "success": {
        "bg": (46, 142, 72),
        "bg_hover": (62, 172, 92),
        "border": (160, 240, 175),
        "text": (255, 250, 240),
    },
    "danger": {
        "bg": (182, 40, 38),
        "bg_hover": (212, 58, 55),
        "border": (255, 160, 150),
        "text": (255, 250, 240),
    },
    "info": {
        "bg": (175, 122, 24),
        "bg_hover": (205, 148, 36),
        "border": (255, 225, 120),
        "text": (255, 250, 240),
    },
    "purple": {
        "bg": (122, 52, 88),
        "bg_hover": (150, 68, 110),
        "border": (235, 165, 200),
        "text": (255, 250, 240),
    },
    "dark": {
        "bg": (64, 42, 26),
        "bg_hover": (88, 58, 38),
        "border": (175, 132, 82),
        "text": (248, 238, 220),
    },
}


class FontCache:
    _cache = {}
    TITLE_FONT_PATH = "assets/font/Gang_of_Three_Regular.ttf"

    @classmethod
    def get_title_font(cls, size: int) -> pygame.font.Font:
        key = ("title", size)
        if key not in cls._cache:
            try:
                cls._cache[key] = pygame.font.Font(cls.TITLE_FONT_PATH, size)
            except Exception:
                cls._cache[key] = pygame.font.SysFont("Segoe UI", size, bold=True)
        return cls._cache[key]

    @classmethod
    def get_ui_font(cls, size: int, bold: bool = True) -> pygame.font.Font:
        key = ("ui", size, bold)
        if key not in cls._cache:
            cls._cache[key] = pygame.font.SysFont("Segoe UI", size, bold=bold)
        return cls._cache[key]


def truncate_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    """
    Memotong teks dengan '...' jika lebarnya melebihi max_width agar tidak pernah keluar dari batas kolom/panel.
    """
    if font.size(text)[0] <= max_width:
        return text
    trimmed = text
    while len(trimmed) > 1 and font.size(trimmed + "...")[0] > max_width:
        trimmed = trimmed[:-1]
    return trimmed + "..."


_PANEL_CACHE = {}
_SHADOW_CACHE = {}


def draw_glass_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    bg_color=(36, 22, 14, 232),
    border_color=(215, 165, 72, 225),
    border_radius: int = 20,
    border_width: int = 3,
    shadow: bool = True,
):
    """
    Menggambar panel bergaya papan Dojo Kayu & Bingkai Emas yang menyatu dengan tema Fruit Ninja.
    Menggunakan cache pygame.Surface agar rendering mencapai 60 FPS stabil tanpa alokasi berulang.
    """
    if shadow:
        s_key = (rect.width + 14, rect.height + 14, border_radius + 4, 130)
        shadow_surf = _SHADOW_CACHE.get(s_key)
        if shadow_surf is None:
            shadow_surf = pygame.Surface((rect.width + 14, rect.height + 14), pygame.SRCALPHA)
            pygame.draw.rect(
                shadow_surf,
                (0, 0, 0, 130),
                pygame.Rect(0, 0, rect.width + 14, rect.height + 14),
                border_radius=border_radius + 4,
            )
            _SHADOW_CACHE[s_key] = shadow_surf
        surface.blit(shadow_surf, (rect.x - 3, rect.y + 7))

    p_key = (rect.width, rect.height, bg_color, border_color, border_radius, border_width)
    panel_surf = _PANEL_CACHE.get(p_key)
    if panel_surf is None:
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(
            panel_surf,
            bg_color,
            pygame.Rect(0, 0, rect.width, rect.height),
            border_radius=border_radius,
        )

        # Garis aksen dalam kayu hangat
        if rect.width > 40 and rect.height > 40:
            inner_rect = pygame.Rect(5, 5, rect.width - 10, rect.height - 10)
            pygame.draw.rect(
                panel_surf,
                (85, 55, 32, 140),
                inner_rect,
                width=1,
                border_radius=max(4, border_radius - 4),
            )

        if border_width > 0:
            pygame.draw.rect(
                panel_surf,
                border_color,
                pygame.Rect(0, 0, rect.width, rect.height),
                width=border_width,
                border_radius=border_radius,
            )
        _PANEL_CACHE[p_key] = panel_surf

    surface.blit(panel_surf, rect.topleft)


class IconCache:
    """
    Memuat dan menyimpan cache gambar ikon PNG dari folder assets/icons/.
    """

    _raw_cache = {}
    _scaled_cache = {}
    ICON_DIR = "assets/icons"

    @classmethod
    def get_icon(cls, icon_name: str, size: int) -> pygame.Surface | None:
        key = (icon_name, size)
        if key in cls._scaled_cache:
            return cls._scaled_cache[key]

        if icon_name not in cls._raw_cache:
            path = os.path.join(cls.ICON_DIR, f"{icon_name}.png")
            if os.path.exists(path):
                try:
                    cls._raw_cache[icon_name] = pygame.image.load(path).convert_alpha()
                except Exception:
                    cls._raw_cache[icon_name] = None
            else:
                cls._raw_cache[icon_name] = None

        raw = cls._raw_cache[icon_name]
        if raw is None:
            return None

        scaled = pygame.transform.smoothscale(raw, (size, size))
        cls._scaled_cache[key] = scaled
        return scaled


def draw_icon(surface: pygame.Surface, icon_name: str, center: tuple, size: int = 28):
    icon_surf = IconCache.get_icon(icon_name, size)
    if icon_surf is not None:
        rect = icon_surf.get_rect(center=(int(center[0]), int(center[1])))
        surface.blit(icon_surf, rect.topleft)


class HandCursorManager:
    """
    Mengelola posisi kursor tangan dan mekanisme klik tahan jari (Dwell Click) dengan
    anti-flicker & toleransi getaran jari agar sangat mudah menekan tombol menu.
    """

    def __init__(self, dwell_time: float = 1.2):
        self.dwell_time = dwell_time
        self.pointer_pos = None
        self.hovered_id = None
        self.hover_start_time = 0.0
        self.last_hover_seen = 0.0
        self.last_click_time = 0.0
        self.cooldown = 0.65
        self.current_progress = 0.0

    def update_pointer(self, pos, dwell_time: float = None):
        if dwell_time is not None:
            self.dwell_time = dwell_time
        self.pointer_pos = pos
        if pos is None:
            # Beri toleransi 0.22 detik sebelum mereset progress klik jika tangan sempat berkedip
            if self.hovered_id is not None and (time.time() - self.last_hover_seen) > 0.22:
                self.hovered_id = None
                self.current_progress = 0.0

    def check_dwell_click(self, btn_id, rect: pygame.Rect) -> tuple[bool, bool, float]:
        now = time.time()
        if self.pointer_pos is None:
            if self.hovered_id == btn_id and (now - self.last_hover_seen) <= 0.22:
                return True, False, self.current_progress
            return False, False, 0.0

        # Area magnetik tombol diperluas (+22px) agar jari tidak mudah tergelincir keluar tombol
        padded = rect.inflate(22, 22)
        if not padded.collidepoint(self.pointer_pos):
            if self.hovered_id == btn_id:
                if (now - self.last_hover_seen) <= 0.22:
                    # Jari sedikit bergeser keluar sesaat: tahan progress agar tidak langsung hilang ke 0
                    self.hover_start_time += 0.016
                    return True, False, self.current_progress
                self.hovered_id = None
                self.current_progress = 0.0
            return False, False, 0.0

        self.last_hover_seen = now
        if now - self.last_click_time < self.cooldown:
            return True, False, 0.0

        if self.hovered_id != btn_id:
            self.hovered_id = btn_id
            self.hover_start_time = now
            self.current_progress = 0.0
            return True, False, 0.0

        elapsed = max(0.0, now - self.hover_start_time)
        progress = min(1.0, elapsed / max(0.3, self.dwell_time))
        self.current_progress = progress

        if progress >= 1.0:
            self.last_click_time = now
            self.hovered_id = None
            self.current_progress = 0.0
            return True, True, 1.0

        return True, False, progress

    def draw_cursor(self, surface: pygame.Surface, label: str = None):
        if self.pointer_pos is None:
            return

        x, y = int(self.pointer_pos[0]), int(self.pointer_pos[1])

        glow_key = ("cursor_glow", 68)
        glow_surf = _SHADOW_CACHE.get(glow_key)
        if glow_surf is None:
            glow_surf = pygame.Surface((68, 68), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 195, 50, 60), (34, 34), 24)
            _SHADOW_CACHE[glow_key] = glow_surf
        surface.blit(glow_surf, (x - 34, y - 34))

        if self.current_progress > 0.02:
            ring_radius = 24
            arc_rect = pygame.Rect(x - ring_radius, y - ring_radius, ring_radius * 2, ring_radius * 2)
            pygame.draw.circle(surface, (45, 30, 18), (x, y), ring_radius, 5)
            start_angle = math.pi / 2
            end_angle = start_angle + (2 * math.pi * self.current_progress)
            pygame.draw.arc(surface, (95, 245, 130), arc_rect, start_angle, end_angle, 5)

        pygame.draw.circle(surface, (235, 115, 15), (x, y), 12)
        pygame.draw.circle(surface, (255, 240, 150), (x, y), 6)
        pygame.draw.circle(surface, (255, 255, 255), (x, y), 12, 2)


class ModernButtonManager:
    """
    Menggambar tombol teks, tombol simbol/ikon bulat, serta sakelar toggle modern.
    """

    def __init__(self):
        self.anim_scales = {}

    def draw_button(
        self,
        surface: pygame.Surface,
        btn_id: str,
        text: str,
        rect: pygame.Rect,
        scheme: str = "primary",
        icon: str = None,
        font_size: int = 24,
        use_title_font: bool = False,
        hand_cursor: HandCursorManager = None,
        mouse_clicked_event: bool = False,
        border_radius: int = 16,
    ) -> bool:
        colors = COLOR_SCHEMES.get(scheme, COLOR_SCHEMES["primary"])
        mouse_pos = pygame.mouse.get_pos()
        mouse_hover = rect.collidepoint(mouse_pos)

        hand_hover, hand_clicked, dwell_prog = (False, False, 0.0)
        if hand_cursor is not None:
            hand_hover, hand_clicked, dwell_prog = hand_cursor.check_dwell_click(btn_id, rect)

        is_hover = mouse_hover or hand_hover

        curr_scale = self.anim_scales.get(btn_id, 1.0)
        target_scale = 1.04 if is_hover else 1.0
        curr_scale = curr_scale + (target_scale - curr_scale) * 0.22
        self.anim_scales[btn_id] = curr_scale

        draw_w = int(rect.width * curr_scale)
        draw_h = int(rect.height * curr_scale)
        draw_rect = pygame.Rect(0, 0, draw_w, draw_h)
        draw_rect.center = rect.center

        shadow_rect = draw_rect.copy()
        shadow_rect.y += 4
        s_key = (shadow_rect.width, shadow_rect.height, border_radius, 125)
        shadow_surf = _SHADOW_CACHE.get(s_key)
        if shadow_surf is None:
            shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 125), shadow_surf.get_rect(), border_radius=border_radius)
            _SHADOW_CACHE[s_key] = shadow_surf
        surface.blit(shadow_surf, shadow_rect.topleft)

        bg_col = colors["bg_hover"] if is_hover else colors["bg"]
        pygame.draw.rect(surface, bg_col, draw_rect, border_radius=border_radius)

        if dwell_prog > 0.02:
            fill_w = max(8, int(draw_rect.width * dwell_prog))
            prog_surf = pygame.Surface((fill_w, draw_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                prog_surf,
                (255, 255, 255, 75),
                pygame.Rect(0, 0, fill_w, draw_rect.height),
                border_radius=border_radius,
            )
            surface.blit(prog_surf, draw_rect.topleft)

        border_w = 3 if is_hover else 2
        border_col = (255, 245, 200) if is_hover else colors["border"]
        pygame.draw.rect(surface, border_col, draw_rect, width=border_w, border_radius=border_radius)

        font = FontCache.get_title_font(font_size) if use_title_font else FontCache.get_ui_font(font_size, bold=True)
        txt_surf = font.render(text, True, colors["text"])

        if icon:
            icon_size = min(30, max(22, int(draw_h * 0.56)))
            icon_space = icon_size + 10
            total_w = icon_space + txt_surf.get_width()
            start_x = draw_rect.centerx - total_w // 2
            icon_center = (start_x + icon_size // 2, draw_rect.centery)
            draw_icon(surface, icon, icon_center, size=icon_size)
            txt_rect = txt_surf.get_rect(midleft=(start_x + icon_space, draw_rect.centery))
        else:
            txt_rect = txt_surf.get_rect(center=draw_rect.center)

        surface.blit(txt_surf, txt_rect)

        if (mouse_hover and mouse_clicked_event) or hand_clicked:
            return True
        return False

    def draw_icon_button(
        self,
        surface: pygame.Surface,
        btn_id: str,
        icon: str,
        rect: pygame.Rect,
        scheme: str = "dark",
        tooltip: str = None,
        hand_cursor: HandCursorManager = None,
        mouse_clicked_event: bool = False,
    ) -> bool:
        """
        Menggambar tombol bulat/ikon saja (seperti tombol Settings, Leaderboard, Tema, Pause di pojok layar).
        """
        colors = COLOR_SCHEMES.get(scheme, COLOR_SCHEMES["dark"])
        mouse_pos = pygame.mouse.get_pos()
        mouse_hover = rect.collidepoint(mouse_pos)

        hand_hover, hand_clicked, dwell_prog = (False, False, 0.0)
        if hand_cursor is not None:
            hand_hover, hand_clicked, dwell_prog = hand_cursor.check_dwell_click(btn_id, rect)

        is_hover = mouse_hover or hand_hover
        curr_scale = self.anim_scales.get(btn_id, 1.0)
        target_scale = 1.08 if is_hover else 1.0
        curr_scale = curr_scale + (target_scale - curr_scale) * 0.25
        self.anim_scales[btn_id] = curr_scale

        draw_w = int(rect.width * curr_scale)
        draw_h = int(rect.height * curr_scale)
        draw_rect = pygame.Rect(0, 0, draw_w, draw_h)
        draw_rect.center = rect.center
        radius = min(draw_w, draw_h) // 2

        shadow_rect = draw_rect.copy()
        shadow_rect.y += 4
        s_key = (shadow_rect.width, shadow_rect.height, radius, 130)
        shadow_surf = _SHADOW_CACHE.get(s_key)
        if shadow_surf is None:
            shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 130), shadow_surf.get_rect(), border_radius=radius)
            _SHADOW_CACHE[s_key] = shadow_surf
        surface.blit(shadow_surf, shadow_rect.topleft)

        bg_col = colors["bg_hover"] if is_hover else colors["bg"]
        pygame.draw.rect(surface, bg_col, draw_rect, border_radius=radius)

        if dwell_prog > 0.02:
            arc_r = radius - 2
            arc_rect = pygame.Rect(draw_rect.centerx - arc_r, draw_rect.centery - arc_r, arc_r * 2, arc_r * 2)
            pygame.draw.arc(surface, (110, 255, 145), arc_rect, math.pi / 2, math.pi / 2 + 2 * math.pi * dwell_prog, 4)

        border_col = (255, 240, 180) if is_hover else colors["border"]
        pygame.draw.rect(surface, border_col, draw_rect, width=3 if is_hover else 2, border_radius=radius)

        draw_icon(surface, icon, draw_rect.center, size=int(min(draw_w, draw_h) * 0.62))

        if is_hover and tooltip:
            tip_font = FontCache.get_ui_font(14, bold=True)
            tip_surf = tip_font.render(tooltip, True, (255, 240, 195))
            tip_y = draw_rect.bottom + 8 if draw_rect.bottom + 32 < surface.get_height() else draw_rect.top - 28
            tip_rect = tip_surf.get_rect(midtop=(draw_rect.centerx, tip_y))
            bg_tip = tip_rect.inflate(14, 6)
            pygame.draw.rect(surface, (28, 18, 10), bg_tip, border_radius=8)
            pygame.draw.rect(surface, (195, 150, 70), bg_tip, width=1, border_radius=8)
            surface.blit(tip_surf, tip_rect)

        if (mouse_hover and mouse_clicked_event) or hand_clicked:
            return True
        return False

    def draw_toggle_switch(
        self,
        surface: pygame.Surface,
        btn_id: str,
        is_on: bool,
        rect: pygame.Rect,
        hand_cursor: HandCursorManager = None,
        mouse_clicked_event: bool = False,
    ) -> bool:
        """
        Menggambar sakelar geser ON/OFF bergaya game modern tanpa teks kurung seperti 'AKTIF (ON)'.
        """
        mouse_pos = pygame.mouse.get_pos()
        mouse_hover = rect.collidepoint(mouse_pos)

        hand_hover, hand_clicked, dwell_prog = (False, False, 0.0)
        if hand_cursor is not None:
            hand_hover, hand_clicked, dwell_prog = hand_cursor.check_dwell_click(btn_id, rect)

        is_hover = mouse_hover or hand_hover
        radius = rect.height // 2

        track_col = (48, 155, 78) if is_on else (72, 48, 34)
        if is_hover:
            track_col = (62, 180, 95) if is_on else (92, 62, 44)
        border_col = (165, 245, 180) if is_on else (160, 120, 82)

        pygame.draw.rect(surface, track_col, rect, border_radius=radius)
        if dwell_prog > 0.02:
            fill_w = max(8, int(rect.width * dwell_prog))
            prog_surf = pygame.Surface((fill_w, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(prog_surf, (255, 255, 255, 70), pygame.Rect(0, 0, fill_w, rect.height), border_radius=radius)
            surface.blit(prog_surf, rect.topleft)

        pygame.draw.rect(surface, border_col, rect, width=2, border_radius=radius)

        knob_r = radius - 5
        knob_x = rect.right - radius if is_on else rect.left + radius
        knob_y = rect.centery
        pygame.draw.circle(surface, (255, 250, 240), (knob_x, knob_y), knob_r)

        lbl_font = FontCache.get_ui_font(16, bold=True)
        lbl_str = "ON" if is_on else "OFF"
        lbl_s = lbl_font.render(lbl_str, True, (255, 255, 255) if is_on else (210, 185, 160))
        lbl_x = rect.left + (rect.width - knob_r * 2) // 2 if is_on else rect.left + knob_r * 2 + (rect.width - knob_r * 2) // 2 - 4
        surface.blit(lbl_s, lbl_s.get_rect(center=(lbl_x, rect.centery)))

        if (mouse_hover and mouse_clicked_event) or hand_clicked:
            return True
        return False


class TextInputBox:
    def __init__(self, rect: pygame.Rect, placeholder: str = "", is_password: bool = False):
        self.rect = rect
        self.placeholder = placeholder
        self.is_password = is_password
        self.text = ""
        self.active = False

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                pass
            else:
                if len(self.text) < 18 and event.unicode and event.unicode.isprintable():
                    self.text += event.unicode

    def draw(self, surface: pygame.Surface, label: str = "", hand_cursor: HandCursorManager = None):
        if hand_cursor is not None:
            _, hand_clicked, _ = hand_cursor.check_dwell_click(f"input_{label}_{self.placeholder}", self.rect)
            if hand_clicked:
                self.active = True

        if label:
            lbl_font = FontCache.get_ui_font(17, bold=True)
            lbl_surf = lbl_font.render(label, True, (240, 220, 180))
            surface.blit(lbl_surf, (self.rect.x + 4, self.rect.y - 25))

        bg_col = (54, 34, 20) if self.active else (32, 20, 12)
        border_col = (255, 200, 75) if self.active else (145, 105, 65)
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=12)
        pygame.draw.rect(surface, border_col, self.rect, width=2 if not self.active else 3, border_radius=12)

        font = FontCache.get_ui_font(21, bold=False)
        if self.text:
            disp_str = "•" * len(self.text) if self.is_password else self.text
            txt_color = (255, 250, 240)
        else:
            disp_str = self.placeholder
            txt_color = (150, 125, 98)

        txt_surf = font.render(disp_str, True, txt_color)
        txt_rect = txt_surf.get_rect(midleft=(self.rect.x + 16, self.rect.centery))
        surface.blit(txt_surf, txt_rect)

        if self.active and int(time.time() * 2) % 2 == 0:
            caret_x = txt_rect.right + 3 if self.text else self.rect.x + 16
            pygame.draw.line(
                surface,
                (255, 210, 80),
                (caret_x, self.rect.y + 12),
                (caret_x, self.rect.bottom - 12),
                2,
            )
