import random
import cv2
import os

class Fruit:
    def __init__(self, img, is_bomb, x, y, vy):
        self.img = img
        self.is_bomb = is_bomb
        self.x = x
        self.y = y
        self.vy = vy
        self.alive = True
        self.cut = False
        self.counted = False

class FruitManager:
    def __init__(self, width, height, image_folder="assets/images", min_size=70, max_size=120):
        self.WIDTH = width
        self.HEIGHT = height
        self.min_size = min_size
        self.max_size = max_size

        self.fruit_images = []
        for f in os.listdir(image_folder):
            if f.endswith(".png"):
                self.fruit_images.append({
                    "img": cv2.imread(os.path.join(image_folder, f), cv2.IMREAD_UNCHANGED),
                    "is_bomb": "bomb" in f.lower()
                })

        if not self.fruit_images:
            raise Exception("Tidak ada file PNG di folder 'images'!")

        self.cache = {}

    def _resize_cached(self, base, size, is_bomb):
        key = (size, is_bomb)
        if key not in self.cache:
            try:
                self.cache[key] = cv2.resize(base, (size, size))
            except Exception:
                self.cache[key] = base.copy()
        return self.cache[key]

    def spawn_fruit_solo(self, level):
        f = random.choice(self.fruit_images)
        base = f["img"]
        size = random.randint(self.min_size, self.max_size)
        img = self._resize_cached(base, size, f["is_bomb"]).copy()

        x = random.randint(100, self.WIDTH - 150)
        y = -random.randint(100, 800)
        vy = random.uniform(6 + level, 9 + level)

        return Fruit(img, f["is_bomb"], x, y, vy)

    def spawn_fruit_multi(self, level, p1_alive=True, p2_alive=True):
        import random
        f = random.choice(self.fruit_images)
        base = f["img"]
        size = random.randint(self.min_size, self.max_size)
        img = self._resize_cached(base, size, f["is_bomb"]).copy()

        left_min = 60
        left_max = max(120, self.WIDTH // 2 - 120)
        right_min = min(self.WIDTH // 2 + 40, self.WIDTH - 300)
        right_max = self.WIDTH - 120

        if p1_alive and p2_alive:
            x = random.randint(left_min, left_max) if random.random() < 0.5 else random.randint(right_min, right_max)
        elif p1_alive and not p2_alive:
            x = random.randint(left_min, left_max)
        elif not p1_alive and p2_alive:
            x = random.randint(right_min, right_max)
        else:
            x = random.randint(left_min, right_max)

        y = -random.randint(80, 600)
        vy = random.uniform(5 + level * 0.6, 9 + level * 1.0)

        return Fruit(img, f["is_bomb"], x, y, vy)
