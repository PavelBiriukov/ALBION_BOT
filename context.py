# context.py
import pyautogui
import time

class BotContext:
    def __init__(self, grabber=None, indicator_detector=None, received_detector=None):
        self.running = True

        # зависимости (мини-игра)
        self.grabber = grabber  # объект с grab() и crop_game_area(frame)
        self.indicator_detector = indicator_detector  # detect_indicator_position()
        self.received_detector = received_detector  # detect(frame) -> (found, score)

        # CAST
        self.cast_point = None  # (x, y)

        # WAIT_FLOAT
        self.float_search_radius = 120
        self.float_timeout = 6

        # BITE
        self.bite_stable_time = 0.4
        self.bite_move_threshold = 8
        self.bite_max_time = 6

        # MINI_GAME
        self.dead_zone = 10
        self.left_bonus = 1
        self.right_bonus = 1
        self.minigame_end_delay = 1.2

        # чтобы не спамить mouseDown каждый кадр
        self._left_is_down = False

        # позиция поплавка (когда нашли)
        self.float_point = None  # (x, y) screen coords

        # если потеряли поплавок в BITE на N секунд — вернёмся в WAIT_FLOAT
        self.float_lost_timeout = 3.0

    # ---------- common helpers ----------
    def grab_frame(self):
        if self.grabber is None:
            return None
        frame = self.grabber.grab()
        if frame is None:
            return None
        return self.grabber.crop_game_area(frame)

    def left_down(self):
        if not self._left_is_down:
            pyautogui.mouseDown(button="left")
            self._left_is_down = True

    def left_up(self):
        if self._left_is_down:
            pyautogui.mouseUp(button="left")
            self._left_is_down = False

    def release_all(self):
        self.left_up()
        pyautogui.mouseUp(button="right")

    # ---------- cast helpers ----------
    def set_cast_point(self, point):
        self.cast_point = point
        print(f"🎯 Точка заброса сохранена: {point}")

    def move_to_cast_point(self):
        if self.cast_point is None:
            return False
        pyautogui.moveTo(self.cast_point[0], self.cast_point[1], duration=0.1)
        return True

    def cast(self, hold_time=0.6):
        self.move_to_cast_point()
        time.sleep(0.05)
        pyautogui.mouseDown(button="left")
        time.sleep(hold_time)
        pyautogui.mouseUp(button="left")
        self._left_is_down = False
