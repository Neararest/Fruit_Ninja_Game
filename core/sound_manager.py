import os
import pygame

class SoundManager:
    def __init__(self, folder_candidates):
        self.folder = ""
        for f in folder_candidates:
            if os.path.exists(f):
                self.folder = f
                break

        self.sounds = {}

    def load(self, key, filename):
        if not self.folder:
            self.sounds[key] = None
            return
        path = os.path.join(self.folder, filename)
        if os.path.exists(path):
            self.sounds[key] = pygame.mixer.Sound(path)
        else:
            self.sounds[key] = None

    def play(self, key):
        s = self.sounds.get(key)
        print(f"Playing: {key}")
        if s:
            s.play()
        else:
            print(f"Sound {key} not found!")