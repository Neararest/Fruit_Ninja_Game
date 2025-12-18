import pygame
import sys
from game.solo_game import SoloFruitNinjaGame
from game.multi_game import MultiFruitNinjaGame

class MenuApp:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        self.MENU_MUSIC = "assets/sounds/music.mp3"
        self.WIDTH, self.HEIGHT = 1280, 720
        self.BUTTON_SIZE = (320, 120)
        self.FONT = "assets/font/Gang_of_Three_Regular.ttf"

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Ninja Fruits Navigation")

        self.font_big = pygame.font.Font(self.FONT, 60)

        self.themes = {
            "kaktus": "assets/themes/1.png",
            "kayu": "assets/themes/2.png",
            "salju": "assets/themes/3.png",
            "sakura": "assets/themes/4.png",
        }
        self.selected_theme = "kayu"

        self.bg_main = pygame.image.load(self.themes[self.selected_theme])
        self.bg_main = pygame.transform.scale(self.bg_main, (self.WIDTH, self.HEIGHT))

        self.button_anim_state = {}

        self.theme_icons = {
            "kaktus": "assets/images2/kaktus.png",
            "kayu": "assets/images2/kayu.png",
            "salju": "assets/images2/salju.png",
            "sakura": "assets/images2/sakura.png",
        }
        
        self.back_img = pygame.image.load("assets/images2/kembali.png")
        self.back_img = pygame.transform.scale(self.back_img, (200, 90))

    def lerp(self, a, b, t):
        return a + (b - a) * t

    def blit_scaled_background(self):
        w, h = self.screen.get_size()
        bg_scaled = pygame.transform.scale(self.bg_main, (w, h))
        self.screen.blit(bg_scaled, (0, 0))

    def reset_layar(self):
        pygame.display.quit()
        pygame.display.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Ninja Fruits Navigation")
        self.bg_main = pygame.image.load(self.themes[self.selected_theme])
        self.bg_main = pygame.transform.scale(self.bg_main, (self.WIDTH, self.HEIGHT))

    def fade_transition(self):
        width, height = self.screen.get_size()
        fade = pygame.Surface((width, height))
        fade.fill((0, 0, 0))
        for alpha in range(0, 255, 12):
            fade.set_alpha(alpha)
            self.screen.blit(fade, (0, 0))
            pygame.display.update()
            pygame.time.delay(18)

    def wait_release(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
    
            if not pygame.mouse.get_pressed()[0]:
                break
            
            pygame.time.delay(10)

    def draw_image_button(self, image_path, pos, scale=None, anim_speed=0.15):
        if scale is None:
            scale = self.BUTTON_SIZE

        img = pygame.image.load(image_path)
        btn_id = (image_path, pos)
        if btn_id not in self.button_anim_state:
            self.button_anim_state[btn_id] = 1.0

        base_rect = pygame.Rect(pos[0], pos[1], scale[0], scale[1])
        mouse = pygame.mouse.get_pos()
        click = pygame.mouse.get_pressed()

        is_hover = base_rect.collidepoint(mouse)
        target = 1.12 if is_hover else 1.0
        self.button_anim_state[btn_id] = self.lerp(self.button_anim_state[btn_id], target, anim_speed)

        s = self.button_anim_state[btn_id]
        new_w = int(scale[0] * s)
        new_h = int(scale[1] * s)

        img = pygame.transform.smoothscale(img, (new_w, new_h))
        rect = img.get_rect(center=base_rect.center)

        self.screen.blit(img, rect.topleft)

        if is_hover and click[0]:
            pygame.time.wait(150)
            return True
        return False

    def main_menu(self):
        self.reset_layar()
        try:
            pygame.mixer.music.load(self.MENU_MUSIC)
            pygame.mixer.music.play(-1)
        except:
            print("Warning: gagal memuat musik menu.")

        running = True
        while running:
            self.blit_scaled_background()
            width, height = self.screen.get_size()

            image = pygame.image.load("assets/images2/45.png").convert_alpha()
            self.screen.blit(image, image.get_rect(center=(width // 2, 150)).topleft)

            btn_w, btn_h = (220,220)
            center_x = width // 2 - btn_w // 2
            play_y = 300
            exit_y = play_y + btn_h + 10

            if self.draw_image_button("assets/images2/play.png", (center_x, play_y), scale=(150,150)):
                self.wait_release()
                self.fade_transition()
                self.mode_menu()

            exit_x = 20
            exit_y = 20
            if self.draw_image_button("assets/images2/exit.png", (exit_x, exit_y),scale=(70,70)):
                self.wait_release()
                pygame.quit()
                sys.exit()

            pygame.display.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

    # Menu mode
    def mode_menu(self):
        self.reset_layar()
        running = True
        while running:
            self.blit_scaled_background()
            width, height = self.screen.get_size()

            title = self.font_big.render("Select Mode", True, (255, 255, 0))
            self.screen.blit(title, (width // 2 - title.get_width() // 2, 80))

            btn_w, btn_h = self.BUTTON_SIZE
            center_x = width // 2 - btn_w // 2
            solo_y = 220
            multi_y = solo_y + btn_h + 10
            theme_y = multi_y + btn_h + 10

            if self.draw_image_button("assets/images2/solo.png", (center_x, solo_y)):
                self.wait_release()
                self.fade_transition()
                game = SoloFruitNinjaGame(self.themes[self.selected_theme])
                result = game.run()
                if result == "menu":
                    self.reset_layar()
                    pygame.mixer.music.load(self.MENU_MUSIC)
                    pygame.mixer.music.play(-1)
                    self.fade_transition()
                    return
                elif result == "exit":
                    pygame.quit()
                    sys.exit()

            if self.draw_image_button("assets/images2/multi.png", (center_x, multi_y)):
                self.wait_release()
                self.fade_transition()
                game = MultiFruitNinjaGame(self.themes[self.selected_theme])
                result = game.run()
                if result == "menu":
                    self.reset_layar()
                    pygame.mixer.music.load(self.MENU_MUSIC)
                    pygame.mixer.music.play(-1)
                    self.fade_transition()
                    return
                elif result == "exit":
                    pygame.quit()
                    sys.exit()

            if self.draw_image_button("assets/images2/tema.png", (center_x, theme_y)):
                self.wait_release()
                self.fade_transition()
                self.theme_menu()
            
            exit_x = 20
            exit_y = 20
            if self.draw_image_button("assets/images2/1.png", (exit_x, exit_y),scale=(70,70)):
                self.wait_release()
                self.fade_transition()
                return 

            pygame.display.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

    def theme_menu(self):
        running = True
        while running:
            WIDTH, HEIGHT = self.screen.get_size()
            bg = pygame.image.load(self.themes[self.selected_theme])
            bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))
            self.screen.blit(bg, (0, 0))

            title = self.font_big.render("Pilih tema", True, (255, 255, 0))
            self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))

            num_themes = len(self.themes)
            img_w, img_h = 260, 160
            padding = 60
            total_w = num_themes * img_w + (num_themes - 1) * padding
            start_x = (WIDTH - total_w) // 2
            y_img = 240
            y_icon = y_img + img_h + 25

            mouse_pos = pygame.mouse.get_pos()
            click = pygame.mouse.get_pressed()[0]
            current_x = start_x

            for name, path in self.themes.items():
                img = pygame.image.load(path)
                img = pygame.transform.scale(img, (img_w, img_h))
                img_rect = pygame.Rect(current_x, y_img, img_w, img_h)
                self.screen.blit(img, img_rect.topleft)

                if name == self.selected_theme:
                    pygame.draw.rect(self.screen, (255, 215, 0), img_rect.inflate(10, 10), 4)

                icon_path = self.theme_icons.get(name)
                if icon_path:
                    icon = pygame.image.load(icon_path)
                    if img_rect.collidepoint(mouse_pos):
                        icon = pygame.transform.scale(icon, (165, 165))
                    else:
                        icon = pygame.transform.scale(icon, (140, 140))
                    icon_rect = icon.get_rect(center=(current_x + img_w // 2, y_icon + 35))
                    self.screen.blit(icon, icon_rect.topleft)

                if click and (img_rect.collidepoint(mouse_pos) or icon_rect.collidepoint(mouse_pos)):
                    self.selected_theme = name
                    self.bg_main = pygame.image.load(self.themes[self.selected_theme])
                    self.fade_transition()
                    return

                current_x += img_w + padding

            back_rect = self.back_img.get_rect(center=(WIDTH // 2, 600))
            self.screen.blit(self.back_img, back_rect.topleft)

            if back_rect.collidepoint(mouse_pos) and click:
                self.wait_release()
                self.fade_transition()
                return

            pygame.display.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()