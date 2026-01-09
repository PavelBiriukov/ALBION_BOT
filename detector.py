import cv2
import numpy as np
import mss
import toml

class Detector:
    def __init__(self, config):
        self.config = config
        self.sct = mss.mss()
        self.region = {
            "left": config["screen"]["region"][0],
            "top": config["screen"]["region"][1],
            "width": config["screen"]["region"][2],
            "height": config["screen"]["region"][3],
        }
        self.previous_position = None

    def grab(self):
        img = np.array(self.sct.grab(self.region))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def detect_indicator_position(self):
        img = self.grab()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Маска для индикатора
        mask_indicator = cv2.inRange(
            hsv,
            np.array(self.config["indicator"]["lower"]),
            np.array(self.config["indicator"]["upper"])
        )
        
        # Улучшаем маску
        kernel = np.ones((3, 3), np.uint8)
        mask_indicator = cv2.morphologyEx(mask_indicator, cv2.MORPH_CLOSE, kernel)
        mask_indicator = cv2.morphologyEx(mask_indicator, cv2.MORPH_OPEN, kernel)
        
        # Находим контуры индикатора
        contours, _ = cv2.findContours(mask_indicator, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Берем самый большой контур
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Находим центр индикатора
            M = cv2.moments(largest_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Центр области захвата
                frame_center_x = self.region["width"] // 2
                
                # Отладочная визуализация
                debug_img = img.copy()
                cv2.drawContours(debug_img, [largest_contour], -1, (0, 255, 0), 2)
                cv2.circle(debug_img, (cx, cy), 5, (0, 0, 255), -1)
                cv2.line(debug_img, (frame_center_x, 0), (frame_center_x, self.region["height"]), (255, 0, 0), 2)
                
                cv2.imshow("Indicator Position", debug_img)
                cv2.waitKey(1)
                
                # Возвращаем положение индикатора относительно центра
                position_relative_to_center = cx - frame_center_x
                return position_relative_to_center
        
        # Если индикатор не найден
        cv2.imshow("Indicator Position", img)
        cv2.waitKey(1)
        return None