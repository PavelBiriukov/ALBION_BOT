import time
import pyautogui
import keyboard
from state_base import State

class CastState(State):
    name = "CAST"

    def enter(self, ctx):
        print("\n[CAST] enter")

        if ctx.cast_point is None:
            print("👉 Наведи мышь на место заброса и нажми F1")
            while True:
                if keyboard.is_pressed("f1"):
                    ctx.set_cast_point(pyautogui.position())
                    time.sleep(0.3)
                    break

    def update(self, ctx):
        print("🎣 Забрасываю удочку")
        ctx.release_all()
        ctx.cast(hold_time=0.6)
        time.sleep(0.3)
        return "WAIT_FLOAT"

    def exit(self, ctx):
        print("[CAST] exit")
