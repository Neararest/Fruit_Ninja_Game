import cv2
import pygame
import numpy as np
import time
from core.fruit import FruitManager
from core.sound_manager import SoundManager
from core.hand_tracker import HandTracker
from core.dataexcel import GameDataSaver

class MultiFruitNinjaGame:
    def __init__(self, background_path="assets/themes/2.png"):
        pygame.init()
        pygame.mixer.init()
        self.WIDTH, self.HEIGHT = 1280, 720  

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Ninja Fruits - Multiplayer")
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, self.WIDTH)
        self.cap.set(4, self.HEIGHT)
        
        self.background_path = background_path 
        bg_img = cv2.imread(background_path)
        self.background = cv2.resize(bg_img, (self.WIDTH, self.HEIGHT)) if bg_img is not None else \
            255 * np.ones((self.HEIGHT, self.WIDTH, 3), dtype=np.uint8)
        
        self.sounds = SoundManager(["assets/sounds", "ninja_fruit_sounds"])
        self.sounds.load("slash", "slash.mp3")
        self.sounds.load("boom", "boom.mp3")
        self.sounds.load("levelup", "levelup.mp3")
        
        self.FONT = "assets/font/Gang_of_Three_Regular.ttf"
        
        self.hand_tracker = HandTracker(max_hands=2)
        self.fruit_manager = FruitManager(self.WIDTH, self.HEIGHT)
        self.clock = pygame.time.Clock()

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
        self.start_time = time.time()

    def reset_game(self):
        self.player1 = 0
        self.player2 = 0
        self.p1_alive = True
        self.p2_alive = True
        self.p1_prev = None
        self.p2_prev = None
        self.p1_buf = []
        self.p2_buf = []
        self.level = 1
        self.fruits = [self.fruit_manager.spawn_fruit_multi(1, True, True) for _ in range(7)]
        self.last_death_time = None
        self.game_over = False
        self.show_go_screen = False      
        self.go_start_ticks = 0          
        self.GO_DURATION = 2000

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

    def _assign_hands(self, result, cam_w, cam_h):
        p1_hand = None
        p2_hand = None
        
        scale_x = self.WIDTH / cam_w
        scale_y = self.HEIGHT / cam_h
        
        if result.multi_hand_landmarks:
            for hand_landmark in result.multi_hand_landmarks:
                lx = int(hand_landmark.landmark[8].x * cam_w)
                ly = int(hand_landmark.landmark[8].y * cam_h)
                gx = int(lx * scale_x)
                gy = int(ly * scale_y)
                
                if gx < self.WIDTH // 2:
                    if self.p1_alive:
                        p1_hand = (gx, gy)
                else:
                    if self.p2_alive:
                        p2_hand = (gx, gy)
        
        return p1_hand, p2_hand

    def _smooth_hand(self, hand_pos, buf, prev_pos):
        if hand_pos is None:
            return None
        
        x, y = hand_pos
        buf.append((x, y))
        if len(buf) > 5:
            buf.pop(0)
        
        sx = int(sum(px for px, py in buf) / len(buf))
        sy = int(sum(py for px, py in buf) / len(buf))
        
        if prev_pos is not None:
            sx = int(prev_pos[0] * 0.45 + sx * 0.55)
            sy = int(prev_pos[1] * 0.45 + sy * 0.55)
        
        return (sx, sy)

    def _draw_pointer(self, frame, pos, color_outer, color_inner):
        if pos is None:
            return frame
        x, y = pos
        cv2.circle(frame, (x, y), 18, color_outer, -1)
        cv2.circle(frame, (x, y), 9, color_inner, -1)
        return frame

    def _handle_hands_and_slice(self, cam_frame, frame, now):
        result = self.hand_tracker.process(cam_frame)
        cam_h, cam_w = cam_frame.shape[:2]
        
        p1_hand, p2_hand = self._assign_hands(result, cam_w, cam_h)
        
        # Smooth and draw P1 
        if self.p1_alive and p1_hand is not None:
            smooth_p1 = self._smooth_hand(p1_hand, self.p1_buf, self.p1_prev)
            if smooth_p1:
                frame = self._draw_pointer(frame, smooth_p1, (0, 255, 255), (0, 180, 255))
                self.p1_prev = smooth_p1
        
        # Smooth and draw P2   
        if self.p2_alive and p2_hand is not None:
            smooth_p2 = self._smooth_hand(p2_hand, self.p2_buf, self.p2_prev)
            if smooth_p2:
                frame = self._draw_pointer(frame, smooth_p2, (0, 200, 255), (0, 120, 255))
                self.p2_prev = smooth_p2
        
        # Slice detection
        for fruit in self.fruits:
            if not fruit.alive or fruit.cut:
                continue
            
            fx, fy = fruit.x, fruit.y
            fh, fw = fruit.img.shape[:2]
            
            # P1 slice
            if self.p1_alive and self.p1_prev is not None:
                px, py = self.p1_prev
                if fx < px < fx + fw and fy < py < fy + fh:
                    fruit.cut = True
                    if fruit.is_bomb and not self.game_over:
                        self.p1_alive = False
                        self.sounds.play("boom")

                        if not self.p2_alive:
                            self.game_over = True
                            self.show_go_screen = True
                            self.go_start_ticks = pygame.time.get_ticks()
                            self.last_death_time = now
                    else:
                        self.player1 += 1
                        self.sounds.play("slash")
                        if (self.player1 + self.player2) % 30 == 0:
                            self.level += 1
                            self.sounds.play("levelup")
            
            # P2 slice 
            if self.p2_alive and self.p2_prev is not None and not fruit.cut:
                px, py = self.p2_prev
                if fx < px < fx + fw and fy < py < fy + fh:
                    fruit.cut = True
                    if fruit.is_bomb and not self.game_over:
                        self.p2_alive = False
                        self.sounds.play("boom")

                        if not self.p1_alive:
                            self.game_over = True
                            self.show_go_screen = True
                            self.go_start_ticks = pygame.time.get_ticks()
                            self.last_death_time = now
                    else:
                        self.player2 += 1
                        self.sounds.play("slash")
                        if (self.player1 + self.player2) % 30 == 0:
                            self.level += 1
                            self.sounds.play("levelup")
        
        return frame

    def _update_fruits(self):
        # Move fruits
        for fruit in self.fruits:
            if fruit.alive:
                fruit.y += fruit.vy
                if fruit.y > self.HEIGHT + 50:
                    fruit.alive = False
        
        # Respawn fruits 
        target_count = min(7 + self.level // 1, 18)
        while len(self.fruits) < target_count:
            self.fruits.append(self.fruit_manager.spawn_fruit_multi(self.level, self.p1_alive, self.p2_alive))
        
        # Replace dead/cut fruits
        for i, fruit in enumerate(self.fruits):
            if not fruit.alive or fruit.cut:
                self.fruits[i] = self.fruit_manager.spawn_fruit_multi(self.level, self.p1_alive, self.p2_alive)

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

            frame = self._handle_hands_and_slice(cam, frame, now)
            self._update_fruits()
            
            for fruit in self.fruits:
                if fruit.alive:
                    frame = self._overlay_image(frame, fruit.img, int(fruit.x), int(fruit.y))
            
            if not self.game_over:
                cv2.putText(frame, f"Player1: {self.player1}", (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0,255,255), 3)
                cv2.putText(frame, f"Player2: {self.player2}", (30, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0,200,255), 3)
                cv2.putText(frame, f"Level: {self.level}", (30, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
                
                cv2.line(frame, (self.WIDTH//2, 0), (self.WIDTH//2, self.HEIGHT), (30,30,30), 2)
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
            self.screen.blit(surface, (0, 0))

            # Game Over
            if self.game_over:
                # overlay gelap
                overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                self.screen.blit(overlay, (0, 0))

                elapsed = pygame.time.get_ticks() - self.go_start_ticks

                if self.show_go_screen and elapsed < self.GO_DURATION:
                    # FASE 1: hanya teks GAME OVER
                    font_go = pygame.font.Font(self.FONT, 96)
                    go_text = font_go.render("GAME OVER", True, (255, 60, 60))
                    go_rect = go_text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
                    self.screen.blit(go_text, go_rect)
                else:
                    if self.show_go_screen:          # baru pertama kali masuk fase 2
                        self._setup_gameover_ui()
                    self.show_go_screen = False

                    self.screen.blit(self.card_img, self.card_rect)

                    font_score = pygame.font.Font(self.FONT, 36)

                    p1_text = font_score.render(f"P1 : {self.player1}", True, (0, 0, 0))
                    p2_text = font_score.render(f"P2 : {self.player2}", True, (0, 0, 0))
                    level_text = font_score.render(f"LEVEL : {self.level}", True, (0, 0, 0))

                    gap = 35

                    p1_rect = p1_text.get_rect(center=(self.card_rect.centerx, self.card_rect.centery - gap))
                    p2_rect = p2_text.get_rect(center=(self.card_rect.centerx, self.card_rect.centery))
                    level_rect = level_text.get_rect(center=(self.card_rect.centerx, self.card_rect.centery + gap))

                    self.screen.blit(p1_text, p1_rect)
                    self.screen.blit(p2_text, p2_rect)
                    self.screen.blit(level_text, level_rect)

                    self.screen.blit(self.btn1_img, self.btn1_rect)
                    self.screen.blit(self.btn2_img, self.btn2_rect)
                    self.screen.blit(self.btn3_img, self.btn3_rect)

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

            # Event handling
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
                        self.data_saver.save_multiplayer(
                            player1=self.player1,
                            player2=self.player2,
                            level=self.level
                        )
                        self.save_message = "Data multiplayer berhasil disimpan"
                        self.save_message_time = time.time()

        self._cleanup()
        return "menu"

    def _cleanup(self):
        self.cap.release()
        self.hand_tracker.close()
        print("Multiplayer game closed safely.")