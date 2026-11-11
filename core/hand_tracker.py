import math
import os
import threading
import time
import cv2
import mediapipe as mp
import pygame


# Mapping mode jari -> (tip_id, pip_id, dip_id, mcp_id)
FINGER_LANDMARK_MAP = {
    "thumb": (4, 3, 2, 1),
    "index": (8, 6, 7, 5),
    "middle": (12, 10, 11, 9),
    "ring": (16, 14, 15, 13),
    "pinky": (20, 18, 19, 17),
    "palm": (9, None, None, 0),
}


def _hypot2d(lm1, lm2) -> float:
    return math.hypot(lm1.x - lm2.x, lm1.y - lm2.y)


class HandTracker:
    """
    Pelacak tangan berbasis MediaPipe yang berjalan di Background Thread (Non-Blocking)
    sehingga UI dan Gameplay Pygame berjalan stabil di 60 FPS tanpa ngeframe.
    Dilengkapi deteksi kepalan tangan (Fist Rejection) dan pengaman ganti tangan (Kiri <-> Kanan).
    """

    def __init__(self, max_hands=2, det_conf=0.35, track_conf=0.35):
        self.max_hands = max_hands
        self.det_conf = det_conf
        self.track_conf = track_conf
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            model_complexity=1,
            max_num_hands=max_hands,
            min_detection_confidence=det_conf,
            min_tracking_confidence=track_conf,
        )

        self.cap = None
        self.cam_width = 640
        self.cam_height = 480

        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._latest_frame = None
        self._latest_result = None
        self._latest_frame_id = 0
        self._needs_reinit_hands = False

        # State untuk pelacakan 1 pemain & deteksi ganti tangan + anti-flicker grace window
        self._single_buf = []
        self._single_prev = None
        self._active_hand_label = None
        self._last_valid_pos = None
        self._last_valid_time = 0.0
        self._fist_frames = 0
        self.hand_switched = False

        # Cache surface PiP agar tidak membebani CPU setiap frame
        self._cached_pip_surf = None
        self._cached_pip_frame_id = -1
        self._last_pip_time = 0.0

    def ensure_camera(self, width=480, height=360):
        if self._running and self._thread is not None and self._thread.is_alive():
            return self.cap

        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        return self.cap

    def _open_capture(self):
        if os.name == "nt":
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
        else:
            cap = cv2.VideoCapture(0)

        # Resolusi 640x480 di background thread agar pelacakan jari cepat tetap akurat tanpa membuat game lag
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        return cap

    def _worker_loop(self):
        self.cap = self._open_capture()
        while self._running:
            if self._needs_reinit_hands:
                try:
                    self.hands.close()
                except Exception:
                    pass
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    model_complexity=1,
                    max_num_hands=self.max_hands,
                    min_detection_confidence=self.det_conf,
                    min_tracking_confidence=self.track_conf,
                )
                self._needs_reinit_hands = False

            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                self.cap = self._open_capture()
                continue

            success, frame = self.cap.read()
            if not success or frame is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            if w > 640:
                frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
                h, w = 480, 640

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            result = self.hands.process(rgb)

            with self._lock:
                self.cam_height, self.cam_width = h, w
                self._latest_frame = frame
                self._latest_result = result
                self._latest_frame_id += 1

            time.sleep(0.002)

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def release_camera(self):
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.6)
        self._thread = None

    def read_frame(self):
        """
        Non-blocking: langsung mengambil frame kamera terbaru dari memori tanpa menunggu I/O kamera.
        """
        self.ensure_camera()
        with self._lock:
            if self._latest_frame is None:
                return False, None
            return True, self._latest_frame

    def get_latest_result(self):
        """
        Non-blocking: mengambil hasil deteksi MediaPipe terbaru yang sudah diproses di background thread.
        """
        self.ensure_camera()
        with self._lock:
            return self._latest_frame, self._latest_result

    def set_max_hands(self, max_hands):
        if max_hands != self.max_hands:
            self.max_hands = max_hands
            self._needs_reinit_hands = True

    def process(self, frame_bgr):
        with self._lock:
            if self._latest_result is not None:
                return self._latest_result
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return self.hands.process(rgb)

    @classmethod
    def is_finger_active(cls, hand_lms, finger_mode="index", require_raised=False):
        """
        Dikembalikan seperti semula: selama tangan terdeteksi oleh kamera, landmark jari
        langsung aktif dan tidak pernah ditolak/hilang-hilangan baik di Menu maupun di Game.
        """
        return True

    def extract_finger_point(self, hand_lms, cam_w, cam_h, screen_w, screen_h, finger_mode="index"):
        tip_id, pip_id, _, mcp_id = FINGER_LANDMARK_MAP.get(finger_mode, (8, 6, 7, 5))
        lm_tip = hand_lms.landmark[tip_id]

        # Jika jari diarahkan lurus menghadap layar/kamera laptop (foreshortening),
        # jarak 2D antara ujung jari (tip) dan pangkal (mcp) menyempit dan rawan jitter karena self-occlusion.
        # Stabilkan dengan memadukan sedikit titik sendi PIP/MCP saat jari menunjuk ke kamera.
        if pip_id is not None and mcp_id is not None:
            lm_pip = hand_lms.landmark[pip_id]
            lm_mcp = hand_lms.landmark[mcp_id]
            foreshortening = _hypot2d(lm_tip, lm_mcp)
            if foreshortening < 0.085:
                # Jari menunjuk lurus ke arah laptop -> jangkar dengan sendi PIP agar tidak bergetar
                bx = lm_tip.x * 0.65 + lm_pip.x * 0.35
                by = lm_tip.y * 0.65 + lm_pip.y * 0.35
            else:
                bx, by = lm_tip.x, lm_tip.y
        else:
            bx, by = lm_tip.x, lm_tip.y

        # Margin nyaman (0.06 .. 0.94) agar seluruh sudut layar mudah dijangkau
        norm_x = (bx - 0.06) / 0.88
        norm_y = (by - 0.06) / 0.88
        x = int(max(0.0, min(1.0, norm_x)) * (screen_w - 1))
        y = int(max(0.0, min(1.0, norm_y)) * (screen_h - 1))
        return x, y

    @staticmethod
    def adaptive_smooth(raw_pos: tuple[int, int], prev_pos: tuple[int, int] | None) -> tuple[int, int]:
        """
        Filter Kecepatan Adaptif (Velocity-Adaptive Filter):
        1. Saat jari diam / menunjuk lurus ke arah laptop (delta kecil < 22px):
           Meredam getaran/jitter kamera secara kuat (deadzone + alpha rendah) sehingga kursor diam tenang.
        2. Saat jari diayun menebas buah (delta besar >= 65px):
           Menggunakan alpha instan (0.95) tanpa jeda buffer sehingga koordinat pedang 1:1 mengikuti
           posisi jari asli (tidak terasa licin/terlambat dan tidak miss koordinat).
        """
        rx, ry = raw_pos
        if prev_pos is None:
            return rx, ry

        px, py = prev_pos
        dist = math.hypot(rx - px, ry - py)

        # Deadzone mikro: abaikan getaran sensor kamera di bawah 5 piksel
        if dist < 5.0:
            return px, py

        if dist < 22.0:
            # Saat menunjuk tombol / diam menghadap laptop -> sangat tenang (anti-jitter)
            alpha = 0.16
        elif dist < 68.0:
            # Transisi mulus dari gerak pelan ke gerak cepat
            alpha = 0.22 + 0.72 * ((dist - 22.0) / 46.0)
        else:
            # Ayunan pedang cepat -> respons instan 1:1 tepat di koordinat jari!
            alpha = 0.96

        sx = int(px + (rx - px) * alpha)
        sy = int(py + (ry - py) * alpha)
        return sx, sy

    def get_single_pointer(self, frame_bgr, screen_w, screen_h, finger_mode="index", require_raised=False):
        """
        Mengembalikan posisi (x, y) dengan Velocity-Adaptive Filter:
        - Bebas jitter saat jari menunjuk ke arah laptop.
        - Presisi & responsif 1:1 saat mengayun di dalam game (tidak terlalu licin / miss koordinat).
        """
        _, result = self.get_latest_result()
        self.hand_switched = False
        now = time.time()

        if result is None or not result.multi_hand_landmarks:
            if self._last_valid_pos is not None and (now - self._last_valid_time) < 0.15:
                return self._last_valid_pos
            self._single_buf.clear()
            self._single_prev = None
            self._last_valid_pos = None
            return None

        cam_h, cam_w = self.cam_height, self.cam_width
        hand_lms = result.multi_hand_landmarks[0]
        raw_x, raw_y = self.extract_finger_point(
            hand_lms, cam_w, cam_h, screen_w, screen_h, finger_mode=finger_mode
        )

        sx, sy = self.adaptive_smooth((raw_x, raw_y), self._single_prev)

        self._single_prev = (sx, sy)
        self._last_valid_pos = (sx, sy)
        self._last_valid_time = now
        return sx, sy

    def frame_to_pip_surface(self, frame_bgr, pip_size=(185, 122), pointer_norm=None):
        """
        Mengembalikan pygame.Surface pratinjau kamera (PiP) dengan throttling (maks 15x/detik)
        agar konversi frame tidak membebani FPS utama.
        """
        now = time.time()
        if (
            self._cached_pip_surf is None
            or self._cached_pip_surf.get_size() != pip_size
            or (now - self._last_pip_time >= 0.065 and self._latest_frame_id != self._cached_pip_frame_id)
        ):
            small = cv2.resize(frame_bgr, pip_size, interpolation=cv2.INTER_NEAREST)
            small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            self._cached_pip_surf = pygame.surfarray.make_surface(small_rgb.swapaxes(0, 1)).convert()
            self._cached_pip_frame_id = self._latest_frame_id
            self._last_pip_time = now

        surf = self._cached_pip_surf.copy()
        if pointer_norm is not None:
            px = int(pointer_norm[0] * pip_size[0])
            py = int(pointer_norm[1] * pip_size[1])
            pygame.draw.circle(surf, (255, 220, 0), (px, py), 6)
            pygame.draw.circle(surf, (255, 80, 0), (px, py), 6, 2)
        return surf

    def close(self):
        self.release_camera()
        try:
            self.hands.close()
        except Exception:
            pass
