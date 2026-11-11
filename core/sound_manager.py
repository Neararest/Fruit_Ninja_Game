import os
import pygame


class SoundManager:
    def __init__(self, folder_candidates=None, settings=None):
        if folder_candidates is None:
            folder_candidates = ["assets/sounds", "ninja_fruit_sounds"]
        self.folder = ""
        for f in folder_candidates:
            if os.path.exists(f):
                self.folder = f
                break

        self.settings = settings
        self.sounds = {}
        self.current_music_path = None

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                print(f"Warning: pygame.mixer.init gagal ({e})")

        self.load("slash", "slash.mp3")
        self.load("boom", "boom.mp3")
        self.load("levelup", "levelup.mp3")

    def load(self, key, filename):
        if not self.folder or not pygame.mixer.get_init():
            self.sounds[key] = None
            return
        path = os.path.join(self.folder, filename)
        if os.path.exists(path):
            try:
                snd = pygame.mixer.Sound(path)
                if self.settings:
                    snd.set_volume(self.settings.sfx_volume)
                self.sounds[key] = snd
            except Exception as e:
                print(f"Warning: Gagal memuat suara {path}: {e}")
                self.sounds[key] = None
        else:
            self.sounds[key] = None

    def play(self, key):
        if self.settings and not self.settings.sfx_enabled:
            return
        s = self.sounds.get(key)
        if s:
            if self.settings:
                s.set_volume(self.settings.sfx_volume)
            s.play()

    def play_music(self, music_path="assets/sounds/music.mp3", force_restart=False):
        self.current_music_path = music_path
        if not pygame.mixer.get_init():
            return
        if self.settings and not self.settings.bgm_enabled:
            pygame.mixer.music.stop()
            return
        if not os.path.exists(music_path):
            return
        try:
            if force_restart or not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(music_path)
                vol = self.settings.bgm_volume if self.settings else 0.6
                pygame.mixer.music.set_volume(vol)
                pygame.mixer.music.play(-1)
            else:
                vol = self.settings.bgm_volume if self.settings else 0.6
                pygame.mixer.music.set_volume(vol)
        except Exception as e:
            print(f"Warning: gagal memutar musik ({e})")

    def stop_music(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def sync_with_settings(self):
        if not pygame.mixer.get_init() or not self.settings:
            return
        if self.settings.bgm_enabled:
            pygame.mixer.music.set_volume(self.settings.bgm_volume)
            if self.current_music_path and not pygame.mixer.music.get_busy():
                self.play_music(self.current_music_path)
        else:
            pygame.mixer.music.stop()

        for snd in self.sounds.values():
            if snd:
                snd.set_volume(self.settings.sfx_volume)
