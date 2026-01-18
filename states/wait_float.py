import time
import numpy as np
import cv2
import mss

from state_base import State


class WaitFloatState(State):
    name = "WAIT_FLOAT"

    def enter(self, ctx):
        print("\n[WAIT_FLOAT] enter")
        self.start_time = time.time()
        self.sct = mss.mss()

    def _grab_roi(self, cx, cy, r):
        region = {
            "left": int(cx - r),
            "top": int(cy - r),
            "width": int(r * 2),
            "height": int(r * 2),
        }
        img = self.sct.grab(region)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
        return frame, region

    def _detect_red_float_center(self, frame):
        """
        Возвращает центр поплавка в координатах ROI: (x, y) или None
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower1 = np.array([0, 70, 50])
        upper1 = np.array([10, 255, 255])
        lower2 = np.array([160, 70, 50])
        upper2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower1, upper1)
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # берём самый большой контур (наиболее вероятный поплавок)
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < 40:  # было 20 — сделаем жёстче против мусора
            return None

        x, y, w, h = cv2.boundingRect(c)
        return (x + w // 2, y + h // 2)

    def update(self, ctx):
        if ctx.cast_point is None:
            # на всякий случай
            return "CAST"

        cx, cy = ctx.cast_point
        r = ctx.float_search_radius

        frame, region = self._grab_roi(cx, cy, r)

        center_roi = self._detect_red_float_center(frame)
        if center_roi is not None:
            # ROI -> screen coords
            fx = int(region["left"] + center_roi[0])
            fy = int(region["top"] + center_roi[1])

            ctx.float_point = (fx, fy)
            print(f"🔴 Поплавок найден: {ctx.float_point}")
            return "BITE"

        if time.time() - self.start_time > ctx.float_timeout:
            print("⏰ Поплавок не появился — перезаброс")
            return "CAST"

        time.sleep(0.05)
        return None

    def exit(self, ctx):
        print("[WAIT_FLOAT] exit")
        try:
            self.sct.close()
        except:
            pass
