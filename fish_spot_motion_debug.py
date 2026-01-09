import cv2
import numpy as np
import mss
import time

class FishSpotCircleDetector:
    """
    Ищет рыбное место (волны/дуги) по накопленному движению.
    Возвращает best_point в координатах CROPPED-кадра (как у water контуров).
    """

    def __init__(self):
        self.sct = mss.mss()
        monitor = self.sct.monitors[1]

        self.region = {
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"],
        }

        self.prev_gray = None
        self.motion_acc = None

        # стабилизация цели
        self.edge_margin = 25
        self.lock_radius = 100
        self.lock_min_score_ratio = 0.75

        self.locked = None
        self.locked_score = 0.0

        self.smooth_alpha = 0.25
        self.smooth_point = None

        # параметры
        self.diff_thresh = 4
        self.acc_alpha = 0.06
        self.acc_bin_thresh = 15
        self.min_area = 250
        self.max_std = 14
        self.min_radius = 16
        self.max_radius = 260

    def grab(self):
        img = np.array(self.sct.grab(self.region))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def crop_game_area(self, frame):
        h, w, _ = frame.shape
        return frame[150:h - 200, 100:w - 300]

    def water_mask(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([60, 20, 30])
        upper = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask

    def non_green_mask(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        green = cv2.inRange(hsv, lower_green, upper_green)
        return cv2.bitwise_not(green)

    def _inside_edges(self, x, y, w, h):
        m = self.edge_margin
        return (m <= x < w - m) and (m <= y < h - m)

    def _dist(self, a, b):
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))

    def _smooth(self, pt):
        if pt is None:
            self.smooth_point = None
            return None
        if self.smooth_point is None:
            self.smooth_point = (float(pt[0]), float(pt[1]))
        else:
            ax = self.smooth_alpha
            self.smooth_point = (
                self.smooth_point[0] * (1 - ax) + pt[0] * ax,
                self.smooth_point[1] * (1 - ax) + pt[1] * ax,
            )
        return (int(self.smooth_point[0]), int(self.smooth_point[1]))

    def _score_candidate(self, acc, cx, cy, radius, std):
        if radius < self.min_radius or radius > self.max_radius:
            return -1.0
        if std > self.max_std:
            return -1.0

        h, w = acc.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), int(radius), 255, -1)

        vals = acc[mask == 255]
        if vals.size == 0:
            return -1.0

        mean_energy = float(np.mean(vals))
        return mean_energy / (1.0 + float(std))

    def process(self, frame_full=None):
        """
        Если frame_full передан — используем его (чтобы не делать второй grab).
        Возвращает: (debug_frame, acc_gray, best_point)
        """
        if frame_full is None:
            frame_full = self.grab()

        frame = self.crop_game_area(frame_full)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            self.motion_acc = np.zeros_like(gray, dtype=np.float32)
            return frame, None, None

        diff = cv2.absdiff(self.prev_gray, gray)
        self.prev_gray = gray
        _, diff = cv2.threshold(diff, self.diff_thresh, 255, cv2.THRESH_BINARY)

        water = self.water_mask(frame)
        diff = cv2.bitwise_and(diff, water)

        non_green = self.non_green_mask(frame)
        diff = cv2.bitwise_and(diff, non_green)

        cv2.accumulateWeighted(diff.astype(np.float32), self.motion_acc, self.acc_alpha)
        acc = cv2.convertScaleAbs(self.motion_acc)

        acc = cv2.GaussianBlur(acc, (9, 9), 1.5)
        _, acc_bin = cv2.threshold(acc, self.acc_bin_thresh, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(acc_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        debug = frame.copy()
        h, w = acc.shape[:2]

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue

            pts = c.reshape(-1, 2).astype(np.float32)
            center = pts.mean(axis=0)
            cx, cy = int(center[0]), int(center[1])

            if not self._inside_edges(cx, cy, w, h):
                continue

            dists = np.linalg.norm(pts - center, axis=1)
            radius = float(np.mean(dists))
            std = float(np.std(dists))

            score = self._score_candidate(acc, cx, cy, radius, std)
            if score <= 0:
                continue

            candidates.append((score, cx, cy, int(radius), std))

        best_point = None

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, cx, cy, radius, std = candidates[0]
            candidate_point = (cx, cy)

            # lock
            if self.locked is None:
                self.locked = candidate_point
                self.locked_score = best_score
            else:
                d = self._dist(candidate_point, self.locked)
                if d <= self.lock_radius:
                    self.locked = candidate_point
                    self.locked_score = best_score
                elif best_score > self.locked_score / self.lock_min_score_ratio:
                    self.locked = candidate_point
                    self.locked_score = best_score

            best_point = self._smooth(self.locked)

            if best_point:
                bx, by = best_point
                cv2.drawMarker(debug, (bx, by), (0, 255, 0), cv2.MARKER_CROSS, 22, 2)
                cv2.circle(debug, (bx, by), 6, (0, 0, 255), -1)
                cv2.putText(debug, "Fish spot", (max(0, bx - 60), max(20, by - 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            self.locked = None
            self.locked_score = 0.0
            self._smooth(None)

        return debug, acc, best_point
    