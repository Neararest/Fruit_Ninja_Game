import json
import os

FINGER_MODES = [
    ("index", "Telunjuk"),
    ("middle", "Jari Tengah"),
    ("thumb", "Jempol"),
    ("ring", "Jari Manis"),
    ("pinky", "Kelingking"),
    ("palm", "Telapak"),
]

FINGER_MODE_LABELS = dict(FINGER_MODES)


class SettingsManager:
    DEFAULT_SETTINGS = {
        "bgm_enabled": True,
        "sfx_enabled": True,
        "bgm_volume": 0.6,
        "sfx_volume": 0.85,
        "menu_hand_tracking": True,
        "dwell_time": 1.2,
        "finger_mode": "index",
        "show_webcam_pip": True,
        "selected_theme": "kayu",
    }

    def __init__(self, filepath="settings.json"):
        self.filepath = filepath
        self.data = dict(self.DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k, v in self.DEFAULT_SETTINGS.items():
                        if k in loaded and type(loaded[k]) is type(v):
                            self.data[k] = loaded[k]
                        elif k in loaded and isinstance(v, float) and isinstance(loaded[k], (int, float)):
                            self.data[k] = float(loaded[k])
                    if self.data["finger_mode"] not in FINGER_MODE_LABELS:
                        self.data["finger_mode"] = "index"
            except Exception as e:
                print(f"Warning: Gagal memuat settings.json ({e}), menggunakan default.")

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Warning: Gagal menyimpan settings.json ({e}).")

    @property
    def bgm_enabled(self) -> bool:
        return bool(self.data.get("bgm_enabled", True))

    @bgm_enabled.setter
    def bgm_enabled(self, val: bool):
        self.data["bgm_enabled"] = bool(val)
        self.save()

    @property
    def sfx_enabled(self) -> bool:
        return bool(self.data.get("sfx_enabled", True))

    @sfx_enabled.setter
    def sfx_enabled(self, val: bool):
        self.data["sfx_enabled"] = bool(val)
        self.save()

    @property
    def bgm_volume(self) -> float:
        return float(self.data.get("bgm_volume", 0.6))

    @bgm_volume.setter
    def bgm_volume(self, val: float):
        self.data["bgm_volume"] = max(0.0, min(1.0, float(val)))
        self.save()

    @property
    def sfx_volume(self) -> float:
        return float(self.data.get("sfx_volume", 0.85))

    @sfx_volume.setter
    def sfx_volume(self, val: float):
        self.data["sfx_volume"] = max(0.0, min(1.0, float(val)))
        self.save()

    @property
    def menu_hand_tracking(self) -> bool:
        return bool(self.data.get("menu_hand_tracking", True))

    @menu_hand_tracking.setter
    def menu_hand_tracking(self, val: bool):
        self.data["menu_hand_tracking"] = bool(val)
        self.save()

    @property
    def dwell_time(self) -> float:
        return float(self.data.get("dwell_time", 1.2))

    @dwell_time.setter
    def dwell_time(self, val: float):
        self.data["dwell_time"] = max(0.5, min(3.0, float(val)))
        self.save()

    @property
    def finger_mode(self) -> str:
        mode = self.data.get("finger_mode", "index")
        return mode if mode in FINGER_MODE_LABELS else "index"

    @finger_mode.setter
    def finger_mode(self, val: str):
        if val in FINGER_MODE_LABELS:
            self.data["finger_mode"] = val
            self.save()

    def cycle_finger_mode(self, step=1) -> str:
        keys = [k for k, _ in FINGER_MODES]
        idx = keys.index(self.finger_mode)
        new_idx = (idx + step) % len(keys)
        self.finger_mode = keys[new_idx]
        return self.finger_mode

    def get_finger_label(self) -> str:
        return FINGER_MODE_LABELS.get(self.finger_mode, "Jari Telunjuk")

    @property
    def show_webcam_pip(self) -> bool:
        return bool(self.data.get("show_webcam_pip", True))

    @show_webcam_pip.setter
    def show_webcam_pip(self, val: bool):
        self.data["show_webcam_pip"] = bool(val)
        self.save()

    @property
    def selected_theme(self) -> str:
        return str(self.data.get("selected_theme", "kayu"))

    @selected_theme.setter
    def selected_theme(self, val: str):
        self.data["selected_theme"] = str(val)
        self.save()
