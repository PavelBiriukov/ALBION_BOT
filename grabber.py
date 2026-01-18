import mss
import numpy as np
import cv2


class Grabber:
    def __init__(self, roi=None, monitor_index=1):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[monitor_index]

        # ROI мини-игры (ОБЯЗАТЕЛЬНО подстрой под свой экран)
        # left/top — абсолютные координаты экрана
        self.roi = roi or {
            "left": self.monitor["left"] + 820,
            "top": self.monitor["top"] + 530,
            "width": 280,
            "height": 70,
        }

    def grab(self):
        img = self.sct.grab(self.roi)
        return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)

    def close(self):
        try:
            self.sct.close()
        except:
            pass
