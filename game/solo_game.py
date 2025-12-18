import cv2
import pygame
import numpy as np
import time
from core.fruit import FruitManager
from core.sound_manager import SoundManager
from core.hand_tracker import HandTracker
from core.dataexcel import GameDataSaver

class SoloFruitNinjaGame:
    def __init__(self, background_path="assets/themes/2.png"):
        pygame.init()
        pygame.mixer.init()
        self.WIDTH, self.HEIGHT = 1280, 720   
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Ninja Fruits - Solo")
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, self.WIDTH)
        self.cap.set(4, self.HEIGHT)
        
        bg_img = cv2.imread(background_path)
        self.background_path = background_path
        self.background = cv2.resize(bg_img, (self.WIDTH, self.HEIGHT)) if bg_img is not None else \
            255 * np.ones((self.HEIGHT, self.WIDTH, 3), dtype=np.uint8)
        
        self.sounds = SoundManager(["assets/sounds", "ninja_fruit_sounds"])
        self.sounds.load("slash", "slash.mp3")
        self.sounds.load("boom", "boom.mp3")
        self.sounds.load("levelup", "levelup.mp3")

        self.FONT = "assets/font/Gang_of_Three_Regular.ttf"
        
        self.hand_tracker = HandTracker(max_hands=1)
        self.fruit_manager = FruitManager(self.WIDTH, self.HEIGHT)
        self.clock = pygame.time.Clock()
        
        self.start_time = time.time()
        self.sliced_fruits = 0
        self.touched_bombs = 0

        self.card_img = pygame.image.load("assets/images2/card.png")
        self.btn1_img = pygame.image.load("assets/images2/1.png")
        self.btn2_img = pygame.image.load("assets/images2/2.png")
        self.btn3_img = pygame.image.load("assets/images2/6.png")

        self.card_img = pygame.transform.scale(self.card_img, (350, 350))
        self.btn1_img = pygame.transform.scale(self.btn1_img, (90, 90))
        self.btn2_img = pygame.transform.scale(self.btn2_img, (90, 90))
        self.btn3_img = pygame.transform.scale(self.btn3_img, (90, 90))
        self.data_saver = GameDataSaver()
        self.save_message = None
        self.save_message_time = 0

        self.reset_game()

    def reset_game(self):
        self.score = 0
        self.missed = 0
        self.level = 1
        self.fruits = [self.fruit_manager.spawn_fruit_solo(1) for _ in range(5)]
        self.x_buffer = []
        self.y_buffer = []
        self.prev_x = None
        self.prev_y = None
        self.pointer_history = []
        self.game_over = False
        self.show_go_screen = False      
        self.go_start_ticks = 0          
        self.GO_DURATION = 2000
        self.game_over_time = None
        self._setup_gameover_ui()

    def _overlay_image(self, bg, fg, x, y):
        h, w = fg.shape[:2]
        if len(fg.shape) == 3 and fg.shape[2] == 3:
            fg = np.dstack((fg, np.ones((h, w), dtype=np.uint8) * 255))
        if x < 0 or y < 0 or x + w > self.WIDTH or y + h > self.HEIGHT:
            return bg
        alpha = fg[:, :, 3] / 255.0
        for c in range(3):
            bg[y:y+h, x:x+w, c] = (alpha * fg[:, :, c] + (1 - alpha) * bg[y:y+h, x:x+w, c]).astype(np.uint8)
        return bg

    def _update_size(self):
        new_w, new_h = self.screen.get_size()
        if new_w != self.WIDTH or new_h != self.HEIGHT:
            self.WIDTH, self.HEIGHT = new_w, new_h
            bg_img = cv2.imread(self.background_path)
            self.background = cv2.resize(bg_img, (self.WIDTH, self.HEIGHT)) if bg_img is not None else \
                255 * np.ones((self.HEIGHT, self.WIDTH, 3), dtype=np.uint8)
            self.fruit_manager.WIDTH = self.WIDTH
            self.fruit_manager.HEIGHT = self.HEIGHT

    def _handle_hand(self, cam_frame, frame, now):
        result = self.hand_tracker.process(cam_frame)
        if not result.multi_hand_landmarks:
            return frame

        cam_h, cam_w = cam_frame.shape[:2]
        scale_x = self.WIDTH / cam_w
        scale_y = self.HEIGHT / cam_h

        for hand_lms in result.multi_hand_landmarks:
            x = int(hand_lms.landmark[8].x * cam_w * scale_x)
            y = int(hand_lms.landmark[8].y * cam_h * scale_y)

            # Smoothing buffer
            self.x_buffer.append(x)
            self.y_buffer.append(y)
            if len(self.x_buffer) > 4:
                self.x_buffer.pop(0)
                self.y_buffer.pop(0)
            x = int(sum(self.x_buffer) / len(self.x_buffer))
            y = int(sum(self.y_buffer) / len(self.y_buffer))

            cv2.circle(frame, (x, y), 20, (0, 140, 255), -1)
            cv2.circle(frame, (x, y), 10, (0, 255, 255), -1)

            # Anti-jitter
            if self.prev_x is not None:
                x = int(self.prev_x * 0.5 + x * 0.5)
                y = int(self.prev_y * 0.5 + y * 0.5)

            self.pointer_history.append((x, y, now))
            self.pointer_history = [p for p in self.pointer_history if now - p[2] < 0.25]

            if self.prev_x is not None and self.prev_y is not None:
                for fruit in self.fruits:
                    if fruit.alive and not fruit.cut:
                        fh, fw = fruit.img.shape[:2]
                        if fruit.x < x < fruit.x + fw and fruit.y < y < fruit.y + fh:
                            fruit.cut = True
                            if fruit.is_bomb and not self.game_over:
                                self.game_over = True
                                self.show_go_screen = True
                                self.go_start_ticks = pygame.time.get_ticks()
                                self.game_over_time = now
                                self.touched_bombs += 1
                                self.sounds.play("boom")
                            else:
                                self.score += 1
                                self.sliced_fruits += 1
                                self.sounds.play("slash")
                                if self.score % 30 == 0:
                                    self.level += 1
                                    self.sounds.play("levelup")

            self.prev_x, self.prev_y = x, y
        return frame

    def _update_fruits(self):
        for fruit in self.fruits:
            if fruit.alive:
                fruit.y += fruit.vy
                if fruit.y > self.HEIGHT and not fruit.counted:
                    fruit.alive = False
                    fruit.counted = True
                    if not fruit.is_bomb:
                        self.missed += 1
                        if self.missed >= 10 and not self.game_over:
                            self.game_over = True
                            self.show_go_screen = True
                            self.go_start_ticks = pygame.time.get_ticks()
                            self.game_over_time = time.time()

        for i in range(len(self.fruits)):
            if not self.fruits[i].alive or self.fruits[i].cut:
                self.fruits[i] = self.fruit_manager.spawn_fruit_solo(self.level)
    
    def _setup_gameover_ui(self):
        cx = self.WIDTH // 2
        cy = self.HEIGHT // 2

        self.card_rect = self.card_img.get_rect(center=(cx, cy - 80))

        y = cy + 165
        self.btn1_rect = self.btn1_img.get_rect(center=(cx - 150, y))
        self.btn2_rect = self.btn2_img.get_rect(center=(cx, y))
        self.btn3_rect = self.btn3_img.get_rect(center=(cx + 150, y))

    def run(self):
        running = True
        while running:
            success, cam = self.cap.read()
            if not success:
                time.sleep(0.05)
                continue

            cam = cv2.flip(cam, 1)
            self._update_size()

            frame = self.background.copy()
            now = time.time()
            self._update_fruits()

            for fruit in self.fruits:
                if fruit.alive:
                    frame = self._overlay_image(
                        frame, fruit.img, int(fruit.x), int(fruit.y)
                    )

            if not self.game_over:
                frame = self._handle_hand(cam, frame, now)

                cv2.putText(frame, f"Score: {self.score}", (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)
                cv2.putText(frame, f"Miss: {self.missed}/10", (30, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
                cv2.putText(frame, f"Level: {self.level}", (30, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,255), 3)
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
            self.screen.blit(surface, (0, 0))

            if self.game_over:

                overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                self.screen.blit(overlay, (0, 0))

                elapsed = pygame.time.get_ticks() - self.go_start_ticks

                if self.show_go_screen and elapsed < self.GO_DURATION:
                    font_go = pygame.font.Font(self.FONT, 96)
                    go_text = font_go.render("GAME OVER", True, (255, 60, 60))
                    go_rect = go_text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
                    self.screen.blit(go_text, go_rect)
                else:
                    self.show_go_screen = False

                    self.screen.blit(self.card_img, self.card_rect)
                    self.screen.blit(self.btn1_img, self.btn1_rect)
                    self.screen.blit(self.btn2_img, self.btn2_rect)
                    self.screen.blit(self.btn3_img, self.btn3_rect)

                    font_score = pygame.font.Font(self.FONT, 36)
                    score_text = font_score.render(f"SCORE : {self.score}", True, (0, 0, 0))
                    level_text = font_score.render(f"LEVEL : {self.level}", True, (0, 0, 0))
                    score_rect = score_text.get_rect(
                        center=(self.card_rect.centerx, self.card_rect.centery - 30)
                    )
                    level_rect = level_text.get_rect(   
                        center=(self.card_rect.centerx, self.card_rect.centery + 30)
                    )
                    self.screen.blit(score_text, score_rect)
                    self.screen.blit(level_text, level_rect)

            if self.save_message:
                if time.time() - self.save_message_time < 2.5:
                    font = pygame.font.Font(self.FONT, 28)
                    text = font.render(self.save_message, True, (0, 255, 0))
                    text_rect = text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2 + 265))
                    self.screen.blit(text, text_rect)
                else:
                    self.save_message = None

            pygame.display.flip()
            self.clock.tick(20)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._cleanup()
                    return "exit"

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._cleanup()
                        return "menu"
                    if self.game_over and event.key == pygame.K_r:
                        self.reset_game()

                if event.type == pygame.MOUSEBUTTONDOWN and self.game_over:
                    mx, my = event.pos
                    if self.btn1_rect.collidepoint(mx, my):
                        self._cleanup()
                        return "menu" 
                    elif self.btn2_rect.collidepoint(mx, my):
                        self.reset_game()
                    elif self.btn3_rect.collidepoint(mx, my):
                        self.data_saver.save_solo(
                            score=self.score,
                            missed=self.missed,
                            level=self.level
                        )
                        self.save_message = "Data solo player berhasil disimpan"
                        self.save_message_time = time.time()

        self._cleanup()
        return "menu"
    
    def _cleanup(self):
        self.cap.release()
        self.hand_tracker.close()
        print("Solo game closed safely.")