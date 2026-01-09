import cv2
import numpy as np
import mss
import time
import pyautogui
import math
from fishing_caster import FishingCaster


class FishingBot:
    def __init__(self):
        self.sct = mss.mss()
        monitor = self.sct.monitors[1]
        self.is_busy = False
        self.last_successful_grab = 0

        self.region = {
            "left": monitor["left"],
            "top": monitor["top"],
            "width": min(monitor["width"], 1920),  # Ограничиваем размер
            "height": min(monitor["height"], 1080), # для стабильности
        }
        self.game_region = {
            "left": self.region["left"] + 100,
            "top": self.region["top"] + 150,
            "width": self.region["width"] - 100,
            "height": self.region["height"] - 350,  # 150 сверху + 200 снизу
        }
        
        self.grab_attempts = 0
        self.max_grab_attempts = 100

        self.float_search_start_time = 0  # Когда начали искать поплавок
        self.float_search_timeout = 5     # Через сколько секунд перезабросить (5 сек)
        self.max_retry_attempts = 3       # Максимальное количество попыток перезаброса
        self.retry_count = 0              # Счетчик попыток
        
        # Инициализируем кастер
        self.caster = FishingCaster()
        
        # Состояние бота
        self.state = "SEARCHING_WATER"  # SEARCHING_WATER, CASTING, WAITING_FLOAT, TRACKING_FLOAT
        self.last_cast_time = 0
        self.cast_cooldown = 2  # Секунды между забросами
        self.wait_after_cast = 3  # Ждать после заброса
        self.float_found = False
        self.red_position = None
        self.skip_frames = 0
        # Система детекции поклевки (новая версия)
        self.float_initial_position = None  # Начальная позиция поплавка
        self.float_current_position = None  # Текущая позиция
        self.bite_detected = False
        self.last_bite_time = 0
        self.bite_cooldown = 1.0  # Защита от повторных срабатываний
        
        # Параметры детекции поклевки
        self.FLOAT_STABILIZE_TIME = 0.5  # Время стабилизации поплавка (сек)
        self.BITE_DISTANCE_THRESHOLD = 6  # Дистанция поклевки (пикселей)
        self.STABILITY_RADIUS = 3  # Радиус стабильного положения (пикселей)
        
        self.float_found_time = 0  # Когда поплавок был найден
        self.float_stable = False  # Поплавок стабилизировался
        self.stable_positions = []  # История стабильных позиций
        
        print("🎣 Бот для рыбалки с отслеживанием относительного движения поплавка")

    def release_mouse(self):
        """Отпускает все кнопки мыши"""
        try:
            pyautogui.mouseUp(button='left')
            pyautogui.mouseUp(button='right')
            pyautogui.mouseUp(button='middle')
            time.sleep(0.05)
            return True
        except:
            return False
    def grab(self, fast=False):
        
        if self.skip_frames > 0:
            self.skip_frames -= 1
            time.sleep(0.03)
            return None

        if fast:
            try:
                img = self.sct.grab(self.game_region)
                return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
            except:
                return None
        """Захват экрана с автоматическим восстановлением при ошибках"""
        if self.skip_frames > 0:
            self.skip_frames -= 1
            time.sleep(0.03)
            return None
        
        # Пробуем несколько методов захвата
        for attempt in range(3):
            try:
                # Метод 1: MSS с упрощенным регионом
                try:
                    safe_region = {
                        "left": self.region["left"] + 100,  # Смещаем от края
                        "top": self.region["top"] + 100,
                        "width": min(self.region["width"] - 200, 1200),
                        "height": min(self.region["height"] - 200, 800),
                    }
                    
                    img = self.sct.grab(safe_region)
                    img_array = np.array(img)
                    
                    if img_array is not None and img_array.size > 0:
                        return cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
                except:
                    pass
                
                # Метод 2: PyAutoGUI как запасной вариант
                try:
                    screenshot = pyautogui.screenshot()
                    img_array = np.array(screenshot)
                    if img_array is not None and img_array.size > 0:
                        return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                except:
                    pass
                
                # Метод 3: Попробовать полный экран
                try:
                    img = self.sct.grab(self.sct.monitors[0])
                    img_array = np.array(img)
                    if img_array is not None and img_array.size > 0:
                        return cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
                except:
                    pass
                
            except Exception as e:
                if attempt == 2:  # Последняя попытка
                    # Восстанавливаем MSS соединение
                    try:
                        self.sct = mss.mss()
                    except:
                        pass
                    time.sleep(0.1)
                continue
            
        return None

    def crop_game_area(self, frame):
        h, w, _ = frame.shape
        return frame[150:h - 200, 100:w - 0]

    def detect_water(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower_water = np.array([50, 10, 20])
        upper_water = np.array([140, 255, 255])

        mask = cv2.inRange(hsv, lower_water, upper_water)

        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < 20000:
            return None

        return cnt
    
    def fast_detect_red(self, frame):
        """Очень быстрый поиск красного без контуров"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower_red1 = np.array([0, 120, 70])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 120, 70])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            return None

        return (int(xs.mean()), int(ys.mean()))
    
    def detect_red_in_water(self, frame, water_contour):
        water_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.drawContours(water_mask, [water_contour], -1, 255, -1)
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        lower_red1 = np.array([0, 100, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 50])
        upper_red2 = np.array([180, 255, 255])
        
        red_mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        red_mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        
        red_in_water_mask = cv2.bitwise_and(red_mask, water_mask)
        
        kernel = np.ones((3, 3), np.uint8)
        red_in_water_mask = cv2.morphologyEx(red_in_water_mask, cv2.MORPH_CLOSE, kernel)
        red_in_water_mask = cv2.morphologyEx(red_in_water_mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(red_in_water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_area = 25
        red_contours = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                contour_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.drawContours(contour_mask, [contour], -1, 255, -1)
                
                intersection = cv2.bitwise_and(contour_mask, water_mask)
                
                if np.count_nonzero(intersection) > area * 0.8:
                    red_contours.append(contour)
        
        return red_contours, red_in_water_mask
    
    def get_main_red_position(self, red_contours):
        if not red_contours:
            return None
        
        largest_contour = max(red_contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        center_x = x + w // 2
        center_y = y + h // 2
        
        return (center_x, center_y, w, h)
    
    def move_to_red(self, red_position):
        if red_position is None:
            return None
        
        try:
            center_x, center_y, w, h = red_position
            screen_x = self.region["left"] + 100 + center_x
            screen_y = self.region["top"] + 150 + center_y
            
            pyautogui.moveTo(screen_x, screen_y, duration=0.01)
            return (screen_x, screen_y)  # Возвращаем экранные координаты
            
        except Exception as e:
            print(f"Ошибка перемещения: {e}")
            return None
    
    def check_bite(self, current_pos):
        """Проверяет поклевку на основе расстояния от начальной точки"""
        current_time = time.time()
        
        # Проверяем кулдаун
        if current_time - self.last_bite_time < self.bite_cooldown:
            return False
        
        if self.float_initial_position is None or current_pos is None:
            return False
        
        # Вычисляем расстояние от начальной точки
        dist = math.sqrt(
            (current_pos[0] - self.float_initial_position[0])**2 +
            (current_pos[1] - self.float_initial_position[1])**2
        )
        
        # Если поплавок уже стабилизировался и ушел далеко - это поклевка
        if self.float_stable and dist > self.BITE_DISTANCE_THRESHOLD:
            self.last_bite_time = current_time
            print(f"🎣 ПОКЛЕВКА! Дистанция: {dist:.1f}px > {self.BITE_DISTANCE_THRESHOLD}px")
            return True
        
        # Если поплавок еще не стабилизировался, проверяем стабильность
        if not self.float_stable and self.float_found_time > 0:
            time_since_found = current_time - self.float_found_time
            
            # Добавляем текущую позицию в историю
            self.stable_positions.append(current_pos)
            if len(self.stable_positions) > 30:  # Ограничиваем историю
                self.stable_positions.pop(0)
            
            # Проверяем стабильность
            if len(self.stable_positions) >= 10 and time_since_found > self.FLOAT_STABILIZE_TIME:
                # Проверяем, что поплавок держится в радиусе стабильности
                is_stable = True
                for pos in self.stable_positions[-10:]:  # Последние 10 позиций
                    pos_dist = math.sqrt(
                        (pos[0] - current_pos[0])**2 +
                        (pos[1] - current_pos[1])**2
                    )
                    if pos_dist > self.STABILITY_RADIUS:
                        is_stable = False
                        break
                
                if is_stable:
                    self.float_stable = True
                    self.float_initial_position = current_pos  # Обновляем начальную точку
                    print(f"✅ Поплавок стабилизировался на позиции {current_pos}")
        
        return False
    
    def hook_fish(self):
        """Подсечка рыбы"""
        print("🎣 ПОДСЕЧКА!")
        try:
            # Нажимаем левую кнопку мыши для подсечки
            pyautogui.mouseDown(button='left')
            time.sleep(0.15)  # Немного дольше для надежности
            pyautogui.mouseUp(button='left')
            
            # После подсечки ждем и перезабрасываем
            time.sleep(2.0)
            self.reset_tracking()
            self.state = "SEARCHING_WATER"
            
            return True
        except Exception as e:
            print(f"Ошибка при подсечке: {e}")
            return False
    
    def reset_tracking(self):
        """Сброс трекинга поплавка"""
        self.float_initial_position = None
        self.float_current_position = None
        self.float_stable = False
        self.float_found_time = 0
        self.stable_positions = []
        self.bite_detected = False
        self.float_search_start_time = 0  # Сбрасываем таймер поиска
        self.retry_count = 0              # Сбрасываем счетчик попыток
    
    def reset_tracking(self):
        """Сброс трекинга поплавка"""
        self.float_initial_position = None
        self.float_current_position = None
        self.float_stable = False
        self.float_found_time = 0
        self.stable_positions = []
        self.bite_detected = False
        self.float_search_start_time = 0  # Сбрасываем таймер поиска
        self.retry_count = 0              # Сбрасываем счетчик попыток

    def update_state(self, water_found, red_found):
        """Обновляет состояние бота с логикой повторного заброса"""
        current_time = time.time()
        
        if self.state == "SEARCHING_WATER":
            if water_found:
                print("✅ Вода найдена, перехожу к забросу")
                self.state = "CASTING"
                self.last_cast_time = current_time
                self.retry_count = 0  # Сбрасываем счетчик при новом поиске воды
                
        elif self.state == "CASTING":
            if current_time - self.last_cast_time > 0.5:
                print("🎣 Выполняю заброс...")
                if self.caster.simple_cast(self.region):
                    print("✅ Заброс выполнен успешно")
                    self.state = "WAITING_FLOAT"
                    self.last_cast_time = current_time
                    self.float_search_start_time = current_time  # Запускаем таймер поиска
                    self.reset_tracking()  # Сбрасываем трекинг
                else:
                    print("❌ Ошибка заброса, пробую снова")
                    time.sleep(1)  # Пауза перед повторной попыткой
                    self.state = "SEARCHING_WATER"
                
        elif self.state == "WAITING_FLOAT":
            # Проверяем, не истекло ли время поиска поплавка
            frame = self.grab(fast=True)
            if frame is None:
                return

            # если grab(fast=True) теперь возвращает уже "игровую область", crop делать не надо
            time_since_cast = current_time - self.last_cast_time

            red_found = False
            if time_since_cast < 1.5:
                fast_red = self.fast_detect_red(frame)
                if fast_red:
                    red_found = True
                    # сохраняем позицию поплавка (в координатах кадра)
                    self.red_position = (fast_red[0], fast_red[1], 8, 8)
            
            if red_found:
                print("🎯 Поплавок найден, начинаю трекинг")
                self.state = "TRACKING_FLOAT"
                self.float_found = True
                self.float_found_time = current_time
                self.retry_count = 0  # Сбрасываем счетчик при успешном нахождении
                
            elif time_since_cast > self.float_search_timeout:
                # Не нашли поплавок за отведенное время
                self.retry_count += 1
                
                if self.retry_count <= self.max_retry_attempts:
                    print(f"⏰ Поплавок не найден за {time_since_cast:.1f} сек")
                    print(f"🔄 Повторный заброс #{self.retry_count}/{self.max_retry_attempts}")
                    
                    # Пробуем другой тип заброса
                    if self.retry_count == 1:
                        # Первая попытка - пробуем точный центр
                        print("🎯 Пробую заброс в точный центр...")
                        # Здесь можно добавить специальный метод для точного заброса
                        self.state = "CASTING"
                        self.last_cast_time = current_time
                    elif self.retry_count == 2:
                        # Вторая попытка - пробуем с другой силой
                        print("🎯 Пробую заброс с другой силой...")
                        # Временно изменяем параметры кастера
                        self.caster.cast_power_min = 0.5
                        self.caster.cast_power_max = 0.7
                        self.state = "CASTING"
                        self.last_cast_time = current_time
                    else:
                        # Третья и последующие попытки
                        print("🎯 Пробую случайный заброс...")
                        self.state = "CASTING"
                        self.last_cast_time = current_time
                    
                    # Ждем немного перед повторным забросом
                    time.sleep(1)
                else:
                    # Превысили максимальное количество попыток
                    print(f"❌ Превышено максимальное количество попыток ({self.max_retry_attempts})")
                    print("🔄 Начинаю с начала - поиск воды")
                    self.state = "SEARCHING_WATER"
                    self.retry_count = 0
                    time.sleep(2)  # Даем время на восстановление
                    
            elif current_time - self.last_cast_time > 30:  # Общий таймаут 30 сек
                print("⏰ Общий таймаут ожидания поплавка")
                self.state = "SEARCHING_WATER"
                self.retry_count = 0
                    
        elif self.state == "TRACKING_FLOAT":
            if not red_found:
                print("🔍 Поплавок потерян...")
                self.float_found = False
                
                # Проверяем, не потерялся ли поплавок из-за неудачного заброса
                time_since_cast = current_time - self.last_cast_time
                if time_since_cast < 10:  # Если потеряли поплавок в первые 10 секунд
                    print("⚠️ Поплавок потерян вскоре после заброса")
                    self.retry_count += 1
                    
                    if self.retry_count <= self.max_retry_attempts:
                        print(f"🔄 Пробую повторный заброс #{self.retry_count}")
                        self.state = "CASTING"
                        self.last_cast_time = current_time
                        time.sleep(1)
                    else:
                        print("🔄 Начинаю с начала - поиск воды")
                        self.state = "SEARCHING_WATER"
                        self.retry_count = 0
                elif current_time - self.last_cast_time > 60:  # Общий таймаут 1 минута
                    print("🔄 Перезабрасываю удочку")
                    self.state = "SEARCHING_WATER"
                    self.retry_count = 0
            else:
                # В состоянии трекинга продолжаем отслеживать
                pass

    def run(self):
        print("🎣 Бот для рыбалки с отслеживанием относительного движения поплавка")
        print(f"Дистанция поклевки: {self.BITE_DISTANCE_THRESHOLD}px")
        print(f"Время стабилизации: {self.FLOAT_STABILIZE_TIME}сек")
        print("ESC — выход, SPACE — пауза, R — сброс, B — подсечка вручную")
        
        frame_count = 0
        paused = False
        tracking_enabled = True
        bite_detection_enabled = True

        while True:
            if not paused:
                frame = self.grab()
                frame = self.crop_game_area(frame)
                debug = frame.copy()
                
                water_area_display = np.zeros_like(frame)
                
                water = self.detect_water(frame)
                red_position = None
                reds = []
                mouse_pos = None
                
                if water is not None:
                    # Обновляем кастер
                    self.caster.set_water_contour(water)
                    
                    # Отображаем воду
                    cv2.drawContours(water_area_display, [water], -1, (100, 100, 255), -1)
                    cv2.addWeighted(debug, 0.7, water_area_display, 0.3, 0, debug)
                    cv2.drawContours(debug, [water], -1, (255, 100, 0), 2)
                    
                    # Ищем красный
                    time_since_cast = time.time() - self.last_cast_time
                    red_mask = None

                    if time_since_cast < 1.5:
                        fast_red = self.fast_detect_red(frame)
                        if fast_red:
                            red_position = (fast_red[0], fast_red[1], 8, 8)
                            self.red_position = red_position

                            cv2.drawMarker(debug, (fast_red[0], fast_red[1]), (0, 255, 0),
                                           cv2.MARKER_CROSS, 20, 2)
                            cv2.circle(debug, (fast_red[0], fast_red[1]), 8, (0, 255, 255), 2)

                            # сразу можно переходить в трекинг
                            if self.state == "WAITING_FLOAT":
                                self.state = "TRACKING_FLOAT"
                                self.float_found_time = time.time()

                    else:
                        reds, red_mask = self.detect_red_in_water(frame, water)
                        if reds:
                            red_position = self.get_main_red_position(reds)
                            self.red_position = red_position

                    # Показываем маску красного
                    if red_mask is not None:
                        red_mask_display = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)
                        red_mask_display[:, :, 0] = 0
                        red_mask_display[:, :, 1] = 0
                        cv2.addWeighted(debug, 0.8, red_mask_display, 0.2, 0, debug)
                    
                    if reds:
                        red_position = self.get_main_red_position(reds)
                        
                        if red_position:
                            center_x, center_y, w, h = red_position
                            self.red_position = red_position
                            
                            # Рисуем поплавок
                            cv2.rectangle(debug, 
                                        (center_x - w//2, center_y - h//2),
                                        (center_x + w//2, center_y + h//2), 
                                        (0, 0, 255), 3)
                            cv2.drawMarker(debug, (center_x, center_y), 
                                         (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
                            cv2.circle(debug, (center_x, center_y), 8, (0, 255, 255), 2)
                            
                            # Наводим мышку если включен трекинг
                            if tracking_enabled and self.state == "TRACKING_FLOAT":
                                mouse_pos = self.move_to_red(red_position)
                                
                                # Если это первое обнаружение поплавка, устанавливаем начальную точку
                                if mouse_pos and self.float_initial_position is None:
                                    self.float_initial_position = mouse_pos
                                    self.float_current_position = mouse_pos
                                    print(f"📍 Начальная точка установлена: {mouse_pos}")
                                
                                # Обновляем текущую позицию
                                if mouse_pos:
                                    self.float_current_position = mouse_pos
                                    
                                    # Проверяем поклевку
                                    if bite_detection_enabled and self.check_bite(mouse_pos):
                                        print("🎣 ПОКЛЕВКА ОБНАРУЖЕНА!")
                                        self.hook_fish()
                
                # Обновляем состояние
                self.update_state(water is not None, red_position is not None)
                
                # Рисуем все красные контуры
                for r in reds:
                    x, y, w, h = cv2.boundingRect(r)
                    cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 165, 255), 1)
                
                # Рисуем информацию о трекинге
                if self.state == "TRACKING_FLOAT" and self.float_initial_position and self.float_current_position:
                    # Вычисляем расстояние
                    if self.float_initial_position and self.float_current_position:
                        dist = math.sqrt(
                            (self.float_current_position[0] - self.float_initial_position[0])**2 +
                            (self.float_current_position[1] - self.float_initial_position[1])**2
                        )
                        
                        # Отображаем расстояние
                        dist_text = f"Distance: {dist:.1f}px"
                        if dist > self.BITE_DISTANCE_THRESHOLD:
                            cv2.putText(debug, dist_text, (debug.shape[1] - 200, 120),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        else:
                            cv2.putText(debug, dist_text, (debug.shape[1] - 200, 120),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                        
                        # Рисуем круг дистанции
                        if self.float_initial_position:
                            # Преобразуем экранные координаты обратно в координаты кадра
                            frame_x = self.float_initial_position[0] - self.region["left"] - 100
                            frame_y = self.float_initial_position[1] - self.region["top"] - 150
                            
                            # Рисуем начальную точку
                            cv2.circle(debug, (int(frame_x), int(frame_y)), 
                                     self.BITE_DISTANCE_THRESHOLD, (0, 255, 0), 1)
                            cv2.circle(debug, (int(frame_x), int(frame_y)), 
                                     3, (0, 255, 0), -1)
                            cv2.putText(debug, "Start", (int(frame_x) + 5, int(frame_y) - 5),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                            
                            # Рисуем линию до текущей позиции
                            if self.float_current_position:
                                current_frame_x = self.float_current_position[0] - self.region["left"] - 100
                                current_frame_y = self.float_current_position[1] - self.region["top"] - 150
                                cv2.line(debug, (int(frame_x), int(frame_y)),
                                        (int(current_frame_x), int(current_frame_y)),
                                        (255, 255, 0), 2)
            
            # Отображение информации
            info_texts = [
                f"State: {self.state}",
                f"Frame: {frame_count}",
                f"Paused: {'Yes' if paused else 'No'}",
                f"Tracking: {'ON' if tracking_enabled else 'OFF'}",
                f"Bite Detect: {'ON' if bite_detection_enabled else 'OFF'}",
                f"Water: {'Yes' if water is not None else 'No'}",
                f"Float: {'Yes' if red_position else 'No'}",
                f"Stable: {'Yes' if self.float_stable else 'No'}",
                f"Distance: {'-' if self.float_initial_position is None else '...'}"
            ]
            
            y_offset = 30
            for text in info_texts:
                color = (255, 255, 255)
                if "State:" in text:
                    if self.state == "TRACKING_FLOAT":
                        color = (0, 255, 0)
                    elif self.state == "CASTING":
                        color = (255, 255, 0)
                    elif self.state == "WAITING_FLOAT":
                        color = (255, 165, 0)
                elif "Bite Detect:" in text and bite_detection_enabled:
                    color = (0, 255, 0)
                elif "Stable:" in text and self.float_stable:
                    color = (0, 255, 0)
                
                cv2.putText(debug, text, (10, y_offset), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
                y_offset += 25
            
            # Легенда состояний
            cv2.putText(debug, "SEARCHING_WATER: Ищу воду", 
                      (debug.shape[1] - 250, 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 1)
            cv2.putText(debug, "CASTING: Забрасываю удочку", 
                      (debug.shape[1] - 250, 50),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.putText(debug, "WAITING_FLOAT: Жду поплавок", 
                      (debug.shape[1] - 250, 70),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
            cv2.putText(debug, "TRACKING_FLOAT: Следую за поплавком", 
                      (debug.shape[1] - 250, 90),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Инструкции
            cv2.putText(debug, "ESC: Exit | SPACE: Pause | R: Reset | B: Manual Hook", 
                      (10, debug.shape[0] - 10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1)

            cv2.imshow("Fishing Bot - Relative Distance Tracking", debug)
            
            # Обработка клавиш
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == 32:  # SPACE
                paused = not paused
                print(f"⏸️  Пауза: {'ВКЛ' if paused else 'ВЫКЛ'}")
                time.sleep(0.2)
            elif key == ord('r'):  # R - сброс
                self.state = "SEARCHING_WATER"
                self.reset_tracking()
                print("🔄 Сброс состояния бота")
            elif key == ord('b'):  # B - ручная подсечка
                print("🎣 Ручная подсечка!")
                self.hook_fish()
            elif key == ord('d'):  # D - отладка позиции
                if self.float_initial_position and self.float_current_position:
                    dist = math.sqrt(
                        (self.float_current_position[0] - self.float_initial_position[0])**2 +
                        (self.float_current_position[1] - self.float_initial_position[1])**2
                    )
                    print(f"📍 Отладка: Начальная: {self.float_initial_position}, Текущая: {self.float_current_position}, Дистанция: {dist:.1f}px")

            frame_count += 1
            time.sleep(0.03)

        cv2.destroyAllWindows()
        print("\n🎣 Бот остановлен")


if __name__ == "__main__":
    FishingBot().run()