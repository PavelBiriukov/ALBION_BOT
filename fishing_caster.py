import pyautogui
import time
import random
import numpy as np
import cv2
import math


class FishingCaster:
    """Класс для автоматического заброса удочки с акцентом на центр воды"""
    
    def __init__(self, water_contour=None):
        self.water_contour = water_contour
        self.cast_power_min = 0.2  # Минимальное время зажатия - 0.4 сек
        self.cast_power_max = 0.9  # Максимальное время зажатия
        
        # История забросов для разнообразия
        self.last_cast_points = []
        self.max_history = 5
        
        # Типы забросов с весами - больше центральных забросов
        self.cast_types = {
            "center_area": 0.6,      # Центральная область воды (60%)
            "center_water": 0.25,    # Точный центр (25%)
        }
        
    def set_water_contour(self, water_contour):
        """Устанавливает контур воды для заброса"""
        self.water_contour = water_contour
        print("🎯 Контур воды установлен для заброса")
        
    def wait_for_minigame_completion(self, indicator_detector, controller, dead_zone, delay):
        """Ждет завершения мини-игры"""
        print("🎮 Мини-игра начата...")

        no_indicator_count = 0
        required_checks = 3

        while True:
            position = indicator_detector.detect_indicator_position()

            if position is None:
                no_indicator_count += 1

                if no_indicator_count >= required_checks:
                    print("✅ Мини-игра завершена!")
                    controller.release()
                    return True
            else:
                no_indicator_count = 0

                if position < -dead_zone:
                    controller.press()
                elif position > dead_zone:
                    controller.release()

            time.sleep(delay)
            
    def ensure_mouse_released(self):
        """Гарантированно отпускает кнопку мыши"""
        try:
            for _ in range(3):
                pyautogui.mouseUp(button='left')
                time.sleep(0.03)
            return True
        except Exception as e:
            print(f"⚠️  Не удалось отпустить кнопку мыши: {e}")
            return False
    
    def get_center_area_point(self, frame_shape):
        """Получает точку в центральной области воды (в радиусе 1/3 от центра)"""
        if self.water_contour is None or frame_shape is None:
            return None

        height, width = frame_shape[:2]
            
        # Получаем центр воды
        M = cv2.moments(self.water_contour)
        if M["m00"] == 0:
            return None
            
        center_x = int(M["m10"] / M["m00"])
        center_y = int(M["m01"] / M["m00"])
        
        # Получаем bounding box воды для определения размера
        x, y, w, h = cv2.boundingRect(self.water_contour)
        
        # Радиус центральной области - 1/3 от минимального размера воды
        radius = min(w, h) // 3
        
        # Создаем маску воды
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(mask, [self.water_contour], -1, 255, -1)
        
        # Ищем точки в центральной области
        center_points = []
        
        # Проверяем несколько случайных точек в радиусе
        for _ in range(200):  # Пробуем 200 раз найти точку
            # Генерируем точку в круге радиуса radius
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius * 0.8)  # 80% от радиуса чтобы точно внутри
            px = int(center_x + distance * math.cos(angle))
            py = int(center_y + distance * math.sin(angle))
            
            # Проверяем, что точка в воде
            if 0 <= px < width and 0 <= py < height:
                if mask[py, px] == 255:
                    center_points.append((px, py))
                    
                    # Если нашли достаточно точек, выбираем случайную
                    if len(center_points) >= 30:
                        break
        
        if center_points:
            return random.choice(center_points)
        
        # Если не нашли точки в центральной области, возвращаем центр
        return (center_x, center_y)
    
    def get_far_corner_point(self, frame_shape):
        """Получает точку в дальнем углу воды, но не слишком близко к краю"""
        if self.water_contour is None or frame_shape is None:
            return None

        height, width = frame_shape[:2]
            
        # Получаем bounding box воды
        x, y, w, h = cv2.boundingRect(self.water_contour)
        
        # Выбираем один из 4 углов, но не самые края
        margin = min(30, w // 4, h // 4)  # Отступ от края
        
        corners = [
            (x + margin, y + margin),              # Левый верхний
            (x + w - margin, y + margin),          # Правый верхний
            (x + margin, y + h - margin),          # Левый нижний
            (x + w - margin, y + h - margin)       # Правый нижний
        ]
        
        # Проверяем, какие углы внутри воды
        valid_corners = []
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(mask, [self.water_contour], -1, 255, -1)
        
        for corner in corners:
            if 0 <= corner[0] < width and 0 <= corner[1] < height:
                if mask[corner[1], corner[0]] == 255:
                    valid_corners.append(corner)
        
        if valid_corners:
            return random.choice(valid_corners)
        
        # Если углы не подходят, берем точку из центральной области
        return self.get_center_area_point(frame_shape)
    
    def get_deep_spot_point(self, frame):
        """Находит предполагаемо глубокое место, но в центральной области"""
        if self.water_contour is None or frame is None:
            return self.get_center_area_point(frame.shape if frame is not None else None)
            
        # Создаем маску воды
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [self.water_contour], -1, 255, -1)
        
        # Получаем центр воды
        M = cv2.moments(self.water_contour)
        if M["m00"] == 0:
            return self.get_center_area_point(frame.shape)
            
        center_x = int(M["m10"] / M["m00"])
        center_y = int(M["m01"] / M["m00"])
        
        # Определяем радиус поиска (1/3 от размера воды)
        x, y, w, h = cv2.boundingRect(self.water_contour)
        radius = min(w, h) // 3
        
        # Преобразуем в grayscale для поиска темных участков
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Применяем маску воды
        water_gray = cv2.bitwise_and(gray, gray, mask=mask)
        
        # Создаем маску центральной области
        center_mask = np.zeros_like(mask)
        cv2.circle(center_mask, (center_x, center_y), radius, 255, -1)
        center_mask = cv2.bitwise_and(center_mask, mask)
        
        # Находим самые темные пиксели в центральной области воды
        if np.any(center_mask):
            water_center_gray = cv2.bitwise_and(water_gray, water_gray, mask=center_mask)
            if np.any(water_center_gray > 0):
                dark_threshold = np.percentile(water_center_gray[water_center_gray > 0], 30)  # Нижние 30%
                dark_mask = (water_center_gray < dark_threshold) & (center_mask > 0)
                
                # Если нашли темные участки в центральной области
                if np.any(dark_mask):
                    points_y, points_x = np.where(dark_mask)
                    idx = random.randint(0, len(points_x) - 1)
                    return (points_x[idx], points_y[idx])
        
        # Если не нашли темные участки, берем точку из центральной области
        return self.get_center_area_point(frame.shape)
    
    def get_center_point(self):
        """Получает точный центр воды"""
        if self.water_contour is None:
            return None
            
        M = cv2.moments(self.water_contour)
        if M["m00"] == 0:
            return None
            
        center_x = int(M["m10"] / M["m00"])
        center_y = int(M["m01"] / M["m00"])
        
        return (center_x, center_y)
    
    def choose_cast_point(self, frame=None):
        """Выбирает точку для заброса - в основном центральную область"""
        frame_shape = frame.shape if frame is not None else None
        cast_type = random.choices(
            list(self.cast_types.keys()),
            weights=list(self.cast_types.values())
        )[0]
        
        print(f"🎯 Тип заброса: {cast_type}")
        
        if cast_type == "center_area":
            point = self.get_center_area_point(frame_shape) if frame_shape else self.get_center_point()
        elif cast_type == "center_water":
            point = self.get_center_point()
        elif cast_type == "far_corner":
            point = self.get_far_corner_point(frame_shape) if frame_shape else self.get_center_point()
        elif cast_type == "deep_spot":
            point = self.get_deep_spot_point(frame) if frame is not None else self.get_center_point()
        else:
            point = self.get_center_area_point(frame_shape) if frame_shape else self.get_center_point()  # По умолчанию центральная область
        
        # Если не удалось получить точку, используем центральную область
        if point is None:
            point = self.get_center_area_point(frame_shape) if frame_shape else self.get_center_point()
        
        # Избегаем недавние точки (но с меньшей строгостью)
        if point and len(self.last_cast_points) > 0:
            for last_point in self.last_cast_points[-2:]:
                if last_point and self.distance(point, last_point) < 30:  # 30px минимальное расстояние
                    # Слишком близко к предыдущей точке, берем другую центральную точку
                    point = self.get_center_area_point(frame_shape) if frame_shape else self.get_center_point()
                    break
        
        # Добавляем в историю
        if point:
            self.last_cast_points.append(point)
            if len(self.last_cast_points) > self.max_history:
                self.last_cast_points.pop(0)
        
        return point
    
    def distance(self, point1, point2):
        """Расстояние между двумя точками"""
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def get_random_power(self):
        """Получает случайную силу заброса - всегда от 0.4 секунды"""
        # Распределение: чаще средняя сила, реже экстремальные
        distribution = random.choices(
            ["medium", "strong", "very_strong"],  # Убрали легкие забросы
            weights=[0.5, 0.3, 0.2]  # 50% средних, 30% сильных, 20% очень сильных
        )[0]
        
        if distribution == "medium":
            # Средняя сила: 0.4 - 0.6 секунды
            return random.uniform(0.4, 0.6)
        elif distribution == "strong":
            # Сильная: 0.6 - 0.75 секунды
            return random.uniform(0.6, 0.75)
        else:  # very_strong
            # Очень сильная: 0.75 - 0.8 секунды
            return random.uniform(0.75, self.cast_power_max)
    
    def smart_cast(self, screen_region, frame=None, game_region=None):
        """Умный заброс с акцентом на центр воды"""
        if self.water_contour is None:
            return False

        if game_region is None:
            game_crop_offset = (100, 150)
        else:
            game_crop_offset = (
                game_region["left"] - screen_region["left"],
                game_region["top"] - screen_region["top"]
            )

        try:
            # Отпускаем кнопку мыши
            self.ensure_mouse_released()
            
            # Выбираем точку для заброса (в основном центр)
            target_point = self.choose_cast_point(frame)
            if target_point is None:
                print("❌ Не удалось найти точку для заброса")
                return False
            
            target_x, target_y = target_point
            
            # Преобразуем координаты в экранные
            screen_x = screen_region["left"] + game_crop_offset[0] + target_x
            screen_y = screen_region["top"] + game_crop_offset[1] + target_y
            
            # Сохраняем текущую позицию курсора
            original_pos = pyautogui.position()
            
            print(f"🎯 Заброс в точку: ({target_x}, {target_y})")
            
            # Упрощенные движения - меньше рандома для стабильности
            move_duration = random.uniform(0.2, 0.3)  # Быстрое движение
            
            # Перемещаемся к точке (прямая траектория)
            pyautogui.moveTo(screen_x, screen_y, duration=move_duration)
            time.sleep(0.05)  # Короткая пауза
            
            # Сила заброса (всегда от 0.4 сек)
            cast_power = self.get_random_power()
            
            # Гарантируем отпускание перед зажатием
            for _ in range(2):
                pyautogui.mouseUp(button='left')
                time.sleep(0.02)
            
            # Зажимаем для заброса
            pyautogui.mouseDown(button='left')
            print(f"🎣 Заброс на {cast_power:.2f} сек...")
            
            # Без микропауз для стабильности
            time.sleep(cast_power)
            
            # Отпускаем кнопку
            pyautogui.mouseUp(button='left')
            print("✅ Заброс выполнен!")
            
            # Дополнительные отпускания для надежности
            for _ in range(2):
                pyautogui.mouseUp(button='left')
                time.sleep(0.02)
            
            # Быстро возвращаем курсор в исходную позицию
            pyautogui.moveTo(original_pos, duration=0.15)
            
            return True
          
        except Exception as e:
            print(f"❌ Ошибка при забросе: {e}")
            self.ensure_mouse_released()
            return False
    
    def simple_cast(self, screen_region, game_region=None):
        """Простой заброс (обратная совместимость) - всегда в центр"""
        return self.smart_cast(screen_region, None, game_region=game_region)
    def rescue_cast(self, screen_region, game_region=None):
        """Спасательный заброс - всегда в центр с хорошей силой"""
        if self.water_contour is None:
            return False

        if game_region is None:
            game_crop_offset = (100, 150)
        else:
            game_crop_offset = (
                game_region["left"] - screen_region["left"],
                game_region["top"] - screen_region["top"]
            )
        
        try:
            # Отпускаем кнопку мыши
            self.ensure_mouse_released()
            
            # Всегда в центр
            M = cv2.moments(self.water_contour)
            if M["m00"] == 0:
                return False
            
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
            
            # Преобразуем координаты в экранные
            screen_x = screen_region["left"] + game_crop_offset[0] + center_x
            screen_y = screen_region["top"] + game_crop_offset[1] + center_y
            
            print(f"🎯 СПАСАТЕЛЬНЫЙ заброс в центр: ({center_x}, {center_y})")
            
            # Быстрое движение к точке
            pyautogui.moveTo(screen_x, screen_y, duration=0.2)
            time.sleep(0.05)
            
            # Хорошая средняя сила (0.55 сек)
            cast_power = 0.55
            
            # Заброс
            pyautogui.mouseDown(button='left')
            print(f"🎣 Заброс на {cast_power:.2f} сек...")
            time.sleep(cast_power)
            pyautogui.mouseUp(button='left')
            
            print("✅ Спасательный заброс выполнен!")
            
            # Дополнительные отпускания для надежности
            for _ in range(2):
                pyautogui.mouseUp(button='left')
                time.sleep(0.02)
            
            return True
        
        except Exception as e:
            print(f"❌ Ошибка cast_to_point: {e}")
            self.ensure_mouse_released()
            return False
          
    def _point_in_water(self, pt):
        """Проверка: точка внутри water_contour"""
        if self.water_contour is None or pt is None:
            return False
        x, y = int(pt[0]), int(pt[1])
        return cv2.pointPolygonTest(self.water_contour, (x, y), False) >= 0

    def cast_to_point(self, screen_region, target_point, power=None, game_region=None):
        """Заброс в конкретную точку (если она в воде), иначе fallback на обычный"""
        if self.water_contour is None or target_point is None:
            return False

        if game_region is None:
            game_crop_offset = (100, 150)
        else:
            game_crop_offset = (
                game_region["left"] - screen_region["left"],
                game_region["top"] - screen_region["top"]
            )

        if not self._point_in_water(target_point):
            # точка не в воде — обычный заброс
            return self.smart_cast(screen_region, frame=None, game_region=game_region)

        try:
            self.ensure_mouse_released()

            tx, ty = int(target_point[0]), int(target_point[1])
            screen_x = screen_region["left"] + game_crop_offset[0] + tx
            screen_y = screen_region["top"] + game_crop_offset[1] + ty

            original_pos = pyautogui.position()

            pyautogui.moveTo(screen_x, screen_y, duration=random.uniform(0.2, 0.3))
            time.sleep(0.05)

            cast_power = float(power) if power is not None else float(self.get_random_power())

            pyautogui.mouseUp(button="left")
            time.sleep(0.02)

            pyautogui.mouseDown(button="left")
            time.sleep(cast_power)
            pyautogui.mouseUp(button="left")

            # доп. отпускание
            pyautogui.mouseUp(button="left")
            time.sleep(0.02)

            pyautogui.moveTo(original_pos, duration=0.15)
            return True

        except Exception as e:
            print(f"❌ Ошибка cast_to_point: {e}")
            self.ensure_mouse_released()
            return False

    
