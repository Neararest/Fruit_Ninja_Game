import math
import os
import random
import cv2
import numpy as np
import pygame


def segment_intersects_rect(p1: tuple, p2: tuple, rect: pygame.Rect) -> bool:
    """
    Mengecek apakah garis ayunan dari p1(x1, y1) ke p2(x2, y2) memotong kotak buah `rect`.
    Memastikan ayunan tangan yang cepat tetap memotong buah tanpa terlewat.
    """
    if rect.collidepoint(p1) or rect.collidepoint(p2):
        return True
    return bool(rect.clipline(p1, p2))


class Fruit:
    """
    Representasi buah atau bom yang dilontarkan dari bawah ke atas dengan lintasan parabola.
    """

    def __init__(
        self,
        surf: pygame.Surface,
        is_bomb: bool,
        x: float,
        y: float,
        vx: float,
        vy: float,
        gravity: float,
        color: tuple = (255, 100, 80),
        name: str = "fruit",
        spawn_delay: int = 0,
    ):
        self.base_surf = surf
        self.surf = surf
        self.is_bomb = is_bomb
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.gravity = float(gravity)
        self.color = color
        self.name = name
        self.width = surf.get_width()
        self.height = surf.get_height()

        self.angle = random.uniform(0, 360)
        self.angular_vel = random.uniform(-3.2, 3.2)
        self.spawn_delay = int(spawn_delay)
        self.has_entered_screen = False
        self.alive = True
        self.cut = False
        self.counted = False

    def update(self, screen_w: int, screen_h: int) -> bool:
        """
        Memperbarui posisi parabola buah.
        Mengembalikan True jika buah jatuh melewati batas bawah setelah melambung (terhitung Miss jika bukan bom).
        """
        if not self.alive or self.cut:
            return False

        if self.spawn_delay > 0:
            self.spawn_delay -= 1
            return False

        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.angle = (self.angle + self.angular_vel) % 360

        # Pantulan lembut jika menyentuh tepi kiri/kanan layar
        if self.x < 30 and self.vx < 0:
            self.x = 30
            self.vx = -self.vx * 0.7
        elif self.x + self.width > screen_w - 30 and self.vx > 0:
            self.x = screen_w - 30 - self.width
            self.vx = -self.vx * 0.7

        if self.y < screen_h - 30:
            self.has_entered_screen = True

        # Buah dianggap jatuh keluar layar HANYA saat sedang bergerak turun (vy > 0)
        if self.vy > 0 and self.y > screen_h + 45:
            self.alive = False
            if not self.counted:
                self.counted = True
                return True
        return False

    def draw(self, screen: pygame.Surface):
        if not self.alive or self.cut or self.spawn_delay > 0:
            return
        rotated = pygame.transform.rotate(self.base_surf, self.angle)
        rect = rotated.get_rect(center=(int(self.x + self.width / 2), int(self.y + self.height / 2)))
        screen.blit(rotated, rect.topleft)

    @property
    def is_Targetable(self) -> bool:
        return self.alive and not self.cut and self.spawn_delay <= 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x) + 6,
            int(self.y) + 6,
            max(10, self.width - 12),
            max(10, self.height - 12),
        )


class SlicedFruitHalf:
    """
    Representasi belahan buah (kiri atau kanan) yang terpental dan berputar setelah buah dipotong.
    """

    def __init__(self, surf: pygame.Surface, x: float, y: float, vx: float, vy: float, angular_vel: float):
        self.base_surf = surf
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.angle = 0.0
        self.angular_vel = angular_vel
        self.gravity = 0.50
        self.alpha = 255
        self.alive = True

    def update(self, screen_h: int):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.angle = (self.angle + self.angular_vel) % 360
        self.alpha = max(0, self.alpha - 5)
        if self.y > screen_h + 100 or self.alpha <= 0:
            self.alive = False

    def draw(self, screen: pygame.Surface):
        if not self.alive:
            return
        rotated = pygame.transform.rotate(self.base_surf, self.angle)
        if self.alpha < 255:
            rotated.set_alpha(self.alpha)
        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated, rect.topleft)


class JuiceParticle:
    """
    Partikel cipratan jus buah atau percikan api bom saat objek tertebas.
    """

    def __init__(self, x: float, y: float, color: tuple):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2.5, 9.5)
        self.x = float(x)
        self.y = float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - random.uniform(1.0, 3.0)
        self.gravity = 0.35
        self.radius = random.randint(4, 9)
        self.color = color
        self.alpha = 255
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.alpha -= 9
        if self.alpha <= 0:
            self.alive = False

    def draw(self, screen: pygame.Surface):
        if not self.alive:
            return
        r = max(2, int(self.radius * (self.alpha / 255.0)))
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.color[:3], max(0, min(255, self.alpha))), (r + 1, r + 1), r)
        screen.blit(surf, (int(self.x) - r, int(self.y) - r))


class FloatingText:
    """
    Teks melayang saat memotong buah (+1, COMBO x3!, dll).
    """

    def __init__(self, text: str, x: float, y: float, color=(255, 235, 70), size: int = 28):
        self.text = text
        self.x = float(x)
        self.y = float(y)
        self.vy = -2.2
        self.color = color
        self.size = size
        self.alpha = 255
        self.alive = True

    def update(self):
        self.y += self.vy
        self.alpha -= 7
        if self.alpha <= 0:
            self.alive = False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        if not self.alive:
            return
        txt_surf = font.render(self.text, True, self.color)
        if self.alpha < 255:
            txt_surf.set_alpha(max(0, self.alpha))
        rect = txt_surf.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(txt_surf, rect.topleft)


class FruitManager:
    def __init__(self, width, height, image_folder="assets/images", min_size=75, max_size=115):
        self.WIDTH = width
        self.HEIGHT = height
        self.min_size = min_size
        self.max_size = max_size

        self.fruit_templates = []
        for idx, f in enumerate(sorted(os.listdir(image_folder))):
            if f.lower().endswith(".png"):
                full_path = os.path.join(image_folder, f)
                cv_img = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
                if cv_img is None:
                    continue
                is_bomb = "bomb" in f.lower()
                dom_color = self._extract_dominant_color(cv_img, is_bomb)
                py_surf = self._cv_bgra_to_surface(cv_img)
                self.fruit_templates.append(
                    {
                        "id": idx,
                        "name": os.path.splitext(f)[0],
                        "surf": py_surf,
                        "is_bomb": is_bomb,
                        "color": dom_color,
                    }
                )

        if not self.fruit_templates:
            raise Exception("Tidak ada file PNG di folder 'assets/images'!")

        self.cache = {}

    @staticmethod
    def _cv_bgra_to_surface(cv_img: np.ndarray) -> pygame.Surface:
        if len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
            rgba = cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA)
            surf = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
            return surf.convert_alpha()
        else:
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            surf = pygame.image.frombuffer(rgb.tobytes(), (rgb.shape[1], rgb.shape[0]), "RGB")
            return surf.convert_alpha()

    @staticmethod
    def _extract_dominant_color(cv_img: np.ndarray, is_bomb: bool) -> tuple:
        if is_bomb:
            return (255, 90, 30)
        if len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
            mask = cv_img[:, :, 3] > 100
            if np.any(mask):
                bgr = cv_img[mask][:, :3]
                mean_bgr = np.mean(bgr, axis=0)
                return (
                    min(255, int(mean_bgr[2] * 1.2)),
                    min(255, int(mean_bgr[1] * 1.2)),
                    min(255, int(mean_bgr[0] * 1.2)),
                )
        return (255, 120, 80)

    def _resize_cached(self, template: dict, size: int) -> pygame.Surface:
        quant_size = (size // 5) * 5
        key = (template["id"], quant_size)
        if key not in self.cache:
            self.cache[key] = pygame.transform.smoothscale(template["surf"], (quant_size, quant_size))
        return self.cache[key]

    @staticmethod
    def split_fruit_surface(fruit: Fruit) -> list[SlicedFruitHalf]:
        w, h = fruit.width, fruit.height
        half_w = max(1, w // 2)

        left_surf = pygame.Surface((half_w, h), pygame.SRCALPHA)
        left_surf.blit(fruit.base_surf, (0, 0), pygame.Rect(0, 0, half_w, h))

        right_surf = pygame.Surface((w - half_w, h), pygame.SRCALPHA)
        right_surf.blit(fruit.base_surf, (0, 0), pygame.Rect(half_w, 0, w - half_w, h))

        cx = fruit.x + w / 2
        cy = fruit.y + h / 2

        left_half = SlicedFruitHalf(
            left_surf,
            x=cx - half_w / 2,
            y=cy,
            vx=fruit.vx - random.uniform(2.8, 5.2),
            vy=min(-2.5, fruit.vy * 0.25 - 3.0),
            angular_vel=random.uniform(4.5, 9.5),
        )
        right_half = SlicedFruitHalf(
            right_surf,
            x=cx + half_w / 2,
            y=cy,
            vx=fruit.vx + random.uniform(2.8, 5.2),
            vy=min(-2.5, fruit.vy * 0.25 - 3.0),
            angular_vel=-random.uniform(4.5, 9.5),
        )
        return [left_half, right_half]

    def _compute_parabolic_launch(self, min_x: int, max_x: int, level: int):
        """
        Menghitung posisi awal bawah (x, y), kecepatan lontaran atas (vx, vy), dan gravitasi
        agar buah terlempar melengkung dari bawah ke atas sesuai level.
        """
        start_x = random.randint(min_x, max(min_x + 10, max_x))
        start_y = self.HEIGHT + random.randint(15, 55)

        # Gravitasi bertambah seiring kenaikan level sehingga lemparan & jatuhnya makin cepat
        gravity = 0.36 + min(0.32, (level - 1) * 0.04)

        # Target ketinggian puncak lemparan (antara 9% s/d 38% dari bagian atas layar)
        peak_y = random.randint(int(self.HEIGHT * 0.09), int(self.HEIGHT * 0.38))
        travel_h = max(220, start_y - peak_y)

        # Kecepatan vertikal awal ke atas (bernilai negatif karena sumbu Y ke atas = negatif)
        vy = -math.sqrt(2.0 * gravity * travel_h)

        # Waktu total melayang di udara (naik + turun) dalam satuan frame
        total_frames = max(35.0, (2.0 * abs(vy)) / gravity)

        # Target titik jatuh horizontal tetap berada di dalam zona aman [min_x, max_x]
        target_x = random.randint(min_x, max(min_x + 10, max_x))
        vx = (target_x - start_x) / total_frames
        vx = max(-5.5, min(5.5, vx))

        delay = random.randint(0, 28)
        return start_x, start_y, vx, vy, gravity, delay

    def spawn_fruit_solo(self, level: int) -> Fruit:
        f = random.choice(self.fruit_templates)
        size = random.randint(self.min_size, self.max_size)
        surf = self._resize_cached(f, size)

        min_x = 90
        max_x = max(160, self.WIDTH - 160)
        x, y, vx, vy, gravity, delay = self._compute_parabolic_launch(min_x, max_x, level)

        return Fruit(
            surf,
            f["is_bomb"],
            x,
            y,
            vx,
            vy,
            gravity,
            color=f["color"],
            name=f["name"],
            spawn_delay=delay,
        )

    def spawn_fruit_multi(self, level: int, p1_alive: bool = True, p2_alive: bool = True) -> Fruit:
        f = random.choice(self.fruit_templates)
        size = random.randint(self.min_size, self.max_size)
        surf = self._resize_cached(f, size)

        left_min = 55
        left_max = max(130, self.WIDTH // 2 - 135)
        right_min = min(self.WIDTH // 2 + 35, self.WIDTH - 250)
        right_max = max(right_min + 20, self.WIDTH - 125)

        if p1_alive and p2_alive:
            if random.random() < 0.5:
                min_x, max_x = left_min, left_max
            else:
                min_x, max_x = right_min, right_max
        elif p1_alive and not p2_alive:
            min_x, max_x = left_min, left_max
        elif not p1_alive and p2_alive:
            min_x, max_x = right_min, right_max
        else:
            min_x, max_x = left_min, right_max

        x, y, vx, vy, gravity, delay = self._compute_parabolic_launch(min_x, max_x, level)

        return Fruit(
            surf,
            f["is_bomb"],
            x,
            y,
            vx,
            vy,
            gravity,
            color=f["color"],
            name=f["name"],
            spawn_delay=delay,
        )
