import cv2
import numpy as np

class IndicatorDetector:
    def __init__(self, min_area=18):
        self.min_area = min_area

    def detect(self, frame):
        """Единый контракт: None или float (смещение от центра ROI)"""
        return self.detect_position(frame)

    def detect_position(self, frame):
        """
        return:
          None  - если индикатор не найден
          float - смещение от центра ROI в пикселях (влево -, вправо +)
        """
        if frame is None:
            return None

        h, w = frame.shape[:2]
        cx = w // 2

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower = np.array([12, 2, 196], dtype=np.uint8)
        upper = np.array([32, 102, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower, upper)

        k = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < self.min_area:
            return None

        x, y, bw, bh = cv2.boundingRect(cnt)
        indicator_x = x + bw / 2.0

        return float(indicator_x - cx)
