import cv2
import mediapipe as mp
import pygame


# Mapping mode jari -> (tip_landmark_id, pip_landmark_id, dip_landmark_id)
FINGER_LANDMARK_MAP = {
    "thumb": (4, 2, 3),
    "index": (8, 6, 7),
    "middle": (12, 10, 11),
    "ring": (16, 14, 15),
    "pinky": (20, 18, 19),
    "palm": (9, None, None),
}


class HandTracker:
    def __init__(self, max_hands=2, det_conf=0.45, track_conf=0.45):
        self.max_hands = max_hands
        self.det_conf = det_conf
        self.track_conf = track_conf
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=det_conf,
            min_tracking_confidence=track_conf,
        )
        self.cap = None
        self.cam_width = 640
        self.cam_height = 480
        self._single_buf = []
        self._single_prev = None

    def ensure_camera(self, width=1280, height=720):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        return self.cap

    def release_camera(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def read_frame(self):
        self.ensure_camera()
        if self.cap is None or not self.cap.isOpened():
            return False, None
        success, frame = self.cap.read()
        if not success or frame is None:
            return False, None
        frame = cv2.flip(frame, 1)
        self.cam_height, self.cam_width = frame.shape[:2]
        return True, frame

    def set_max_hands(self, max_hands):
        if max_hands != self.max_hands:
            self.max_hands = max_hands
            try:
                self.hands.close()
            except Exception:
                pass
            self.hands = self.mp_hands.Hands(
                max_num_hands=self.max_hands,
                min_detection_confidence=self.det_conf,
                min_tracking_confidence=self.track_conf,
            )

    def process(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return self.hands.process(rgb)

    def is_finger_active(self, hand_lms, finger_mode="index", require_raised=True):
        if not require_raised or finger_mode == "palm":
            return True

        tip_id, pip_id, dip_id = FINGER_LANDMARK_MAP.get(finger_mode, (8, 6, 7))
        if pip_id is None:
            return True

        if finger_mode == "thumb":
            # Jempol aktif jika ujungnya lebih tinggi dari sendi MCP (2) atau cukup terbuka secara horizontal terhadap pergelangan/telapak
            wrist = hand_lms.landmark[0]
            tip = hand_lms.landmark[4]
            mcp = hand_lms.landmark[2]
            index_mcp = hand_lms.landmark[5]
            dist_horiz = abs(tip.x - index_mcp.x)
            return (tip.y < mcp.y) or (dist_horiz > 0.06)

        tip_y = hand_lms.landmark[tip_id].y
        pip_y = hand_lms.landmark[pip_id].y
        dip_y = hand_lms.landmark[dip_id].y if dip_id is not None else pip_y
        return (tip_y < pip_y) or (tip_y < dip_y)

    def extract_finger_point(self, hand_lms, cam_w, cam_h, screen_w, screen_h, finger_mode="index"):
        tip_id, _, _ = FINGER_LANDMARK_MAP.get(finger_mode, (8, 6, 7))
        lm = hand_lms.landmark[tip_id]
        x = int(lm.x * screen_w)
        y = int(lm.y * screen_h)
        x = max(0, min(screen_w - 1, x))
        y = max(0, min(screen_h - 1, y))
        return x, y

    def get_single_pointer(self, frame_bgr, screen_w, screen_h, finger_mode="index", require_raised=False):
        """
        Mengembalikan posisi (x, y) yang sudah diperhalus (smoothed) untuk 1 tangan (misal di Menu atau Solo Game).
        Jika tidak ada tangan yang terdeteksi/aktif, mengembalikan None.
        """
        result = self.process(frame_bgr)
        if not result.multi_hand_landmarks:
            self._single_buf.clear()
            self._single_prev = None
            return None

        cam_h, cam_w = frame_bgr.shape[:2]
        for hand_lms in result.multi_hand_landmarks:
            if self.is_finger_active(hand_lms, finger_mode=finger_mode, require_raised=require_raised):
                raw_x, raw_y = self.extract_finger_point(
                    hand_lms, cam_w, cam_h, screen_w, screen_h, finger_mode=finger_mode
                )
                self._single_buf.append((raw_x, raw_y))
                if len(self._single_buf) > 4:
                    self._single_buf.pop(0)
                avg_x = sum(p[0] for p in self._single_buf) / len(self._single_buf)
                avg_y = sum(p[1] for p in self._single_buf) / len(self._single_buf)

                if self._single_prev is not None:
                    sx = int(self._single_prev[0] * 0.45 + avg_x * 0.55)
                    sy = int(self._single_prev[1] * 0.45 + avg_y * 0.55)
                else:
                    sx, sy = int(avg_x), int(avg_y)

                self._single_prev = (sx, sy)
                return sx, sy

        self._single_buf.clear()
        self._single_prev = None
        return None

    @staticmethod
    def frame_to_pip_surface(frame_bgr, pip_size=(210, 140), pointer_norm=None):
        """
        Mengubah frame BGR OpenCV menjadi pygame.Surface berukuran kecil untuk Picture-in-Picture (PiP).
        """
        small = cv2.resize(frame_bgr, pip_size)
        small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        surf = pygame.surfarray.make_surface(small_rgb.swapaxes(0, 1)).convert()
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
