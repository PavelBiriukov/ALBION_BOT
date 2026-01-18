import time
import pyautogui
from state_base import State


class MiniGameState(State):
    name = "MINI_GAME"

    def enter(self, ctx):
        print("\n[MINI_GAME] enter")
        self.indicator_lost_time = None

    def update(self, ctx):
        # 1) Проверка "получено" (пока заглушка, но логика уже готова)
        frame = ctx.grabber.grab()
        found_received, _ = ctx.received_detector.detect(frame)
        if found_received:
            print("✅ Получено → конец мини-игры")
            pyautogui.mouseUp(button="left")
            return "CAST"

        # 2) Позиция индикатора
        pos = ctx.indicator_detector.detect(frame)
        now = time.time()

        # индикатор пропал -> ждём чуть-чуть, потом считаем конец
        if pos is None:
            if self.indicator_lost_time is None:
                self.indicator_lost_time = now
            elif now - self.indicator_lost_time >= ctx.minigame_end_delay:
                print("✅ Индикатор исчез → конец мини-игры")
                pyautogui.mouseUp(button="left")
                return "CAST"
            return None

        self.indicator_lost_time = None

        left_zone = ctx.dead_zone + ctx.left_bonus
        right_zone = ctx.dead_zone + ctx.right_bonus

        # (по желанию) лог в консоль
        # print(f"🎮 pos={pos:.1f} dead={ctx.dead_zone} L={left_zone} R={right_zone}")

        if pos < -left_zone:
            ctx.left_down()
        elif pos > right_zone:
            ctx.left_up()

        time.sleep(0.015)
        return None

    def exit(self, ctx):
        print("[MINI_GAME] exit")
        ctx.left_up()
