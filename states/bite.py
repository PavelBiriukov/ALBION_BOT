import time
import numpy as np
import cv2
import mss
import pyautogui

from state_base import State


class BiteState(State):
    name = "BITE"

    def enter(self, ctx):
        print("\n[BITE] enter")
        self.start_time = time.time()
        self.positions = []
        self.stable_start = None
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

    def _find_float_center(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower1 = np.array([0, 70, 50])
        upper1 = np.array([10, 255, 255])
        lower2 = np.array([160, 70, 50])
        upper2 = np.array([180, 255, 255])

        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < 20:
            return None

        x, y, w, h = cv2.boundingRect(c)
        return (x + w // 2, y + h // 2)

    def update(self, ctx):
        # если по какой-то причине поплавок не задан — вернёмся искать
        if ctx.float_point is None:
            return "WAIT_FLOAT"

        cx, cy = ctx.float_point
        r = ctx.float_search_radius

        frame, _ = self._grab_roi(cx, cy, r)
        pos = self._find_float_center(frame)

        now = time.time()

        # --- поплавок не нашли в ROI ---
        if pos is None:
            # если пропал надолго — вернёмся в WAIT_FLOAT (НЕ CAST!)
            if getattr(self, "lost_since", None) is None:
                self.lost_since = now
            elif now - self.lost_since >= ctx.float_lost_timeout:
                print("🔍 Поплавок потерян надолго → снова ищу поплавок")
                return "WAIT_FLOAT"

            time.sleep(0.03)
            return None

        # --- поплавок нашли ---
        self.lost_since = None

        # pos сейчас в координатах ROI, переведём в screen coords и обновим ctx.float_point
        # ROI left = cx-r, top = cy-r
        screen_x = int(cx - r + pos[0])
        screen_y = int(cy - r + pos[1])
        ctx.float_point = (screen_x, screen_y)

        self.positions.append((now, (screen_x, screen_y)))

        # храним только последние 0.5 сек
        self.positions = [p for p in self.positions if now - p[0] < 0.5]
        if len(self.positions) < 5:
            time.sleep(0.03)
            return None

        xs = [p[1][0] for p in self.positions]
        ys = [p[1][1] for p in self.positions]

        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)

        # --- стабилизация ---
        if dx < 2 and dy < 2:
            if self.stable_start is None:
                self.stable_start = now
            # стабилен — просто ждём рывок
            time.sleep(0.03)
            return None

        # --- движение ---
        if self.stable_start is not None:
            dist = max(dx, dy)
            if dist >= ctx.bite_move_threshold:
                print("🎣 ПОКЛЁВКА! Подсекаю")
                pyautogui.click(button="left")
                return "MINI_GAME"

        # если сдвиг был, но рывка недостаточно — продолжаем ждать
        time.sleep(0.03)
        return None


    def exit(self, ctx):
        print("[BITE] exit")
