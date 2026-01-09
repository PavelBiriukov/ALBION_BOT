import cv2
import numpy as np
import mss
import pyautogui
import time

class CursorTracker:
    def __init__(self, box_size=200):
        self.box_size = box_size
        self.sct = mss.mss()

    def get_region_around_cursor(self):
        x, y = pyautogui.position()
        half = self.box_size // 2

        region = {
            "left": max(0, x - half),
            "top": max(0, y - half),
            "width": self.box_size,
            "height": self.box_size,
        }
        return region

    def grab(self):
        region = self.get_region_around_cursor()
        img = np.array(self.sct.grab(region))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def run_debug(self):
        print("Трекаю курсор (100x100). Ctrl+C для выхода.")
        try:
            while True:
                frame = self.grab()

                # центр курсора для ориентира
                h = self.box_size // 2
                cv2.drawMarker(
                    frame,
                    (h, h),
                    (0, 255, 0),
                    cv2.MARKER_CROSS,
                    20,
                    2
                )

                cv2.imshow("Cursor Tracker 100x100", frame)
                cv2.waitKey(1)

                time.sleep(0.01)
        except KeyboardInterrupt:
            cv2.destroyAllWindows()
            print("Остановлено")


if __name__ == "__main__":
    tracker = CursorTracker(box_size=100)
    tracker.run_debug()
