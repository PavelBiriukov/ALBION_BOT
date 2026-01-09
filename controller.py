import pyautogui
import time

class Controller:
    def __init__(self, mouse_button="left"):
        self.mouse_button = mouse_button
        self.is_pressed = False
        self.last_action_time = time.time()

    def press(self):
        if not self.is_pressed:
            pyautogui.mouseDown(button=self.mouse_button)
            self.is_pressed = True
            self.last_action_time = time.time()

    def release(self):
        if self.is_pressed:
            pyautogui.mouseUp(button=self.mouse_button)
            self.is_pressed = False
            self.last_action_time = time.time()

    def reset(self):
        self.release()