import cv2
import toml
import time
import pyautogui
import traceback
import sys

from detector import Detector
from controller import Controller
from fishing_bot import FishingBot
from fishing_caster import FishingCaster

def run_fishing_session():
    """Запускает одну сессию рыбалки и возвращает True если успешно завершена"""
    config = toml.load("config.toml")

    indicator_detector = Detector(config)
    controller = Controller(config["bot"]["mouse_button"])
    dead_zone = config["control"]["dead_zone"]

    bot = FishingBot()
    caster = FishingCaster()

    state = "SEARCH_WATER"
    minigame_frames_without_indicator = 0
    last_cast_time = 0
    cast_cooldown = 5
    
    hook_time = 0
    wait_after_hook = 5
    
    waiting_for_minigame = False
    minigame_start_time = 0
    
    session_start_time = time.time()
    max_session_time = 300  # Максимальное время сессии 5 минут

    print("🎣 Начало новой сессии рыбалки")
    
    try:
        while True:
            # Проверяем максимальное время сессии
            if time.time() - session_start_time > max_session_time:
                print("⏰ Максимальное время сессии истекло, перезапуск...")
                return False
            
            water = None
            frame = None
            current_time = time.time()
            
            # ---------- ПОИСК ВОДЫ ----------
            if state == "SEARCH_WATER":
                # Проверяем, можно ли делать заброс
                time_since_hook = current_time - hook_time if hook_time > 0 else wait_after_hook + 1
                
                if time_since_hook < wait_after_hook:
                    remaining = wait_after_hook - time_since_hook
                    if remaining % 5 == 0:
                        print(f"⏳ Жду после подсечки: {int(remaining)} сек...")
                    time.sleep(1)
                    continue
                
                frame = bot.grab()
                if frame is None:
                    time.sleep(0.2)
                    continue
                    
                water = bot.detect_water(frame)
                
                if water is not None:
                    caster.set_water_contour(water)
                    state = "CAST"
                    print("✅ Вода найдена")
                else:
                    time.sleep(1)

            # ---------- ЗАБРОС ----------
            elif state == "CAST":
                frame = bot.grab()
                if frame is None:
                    time.sleep(0.2)
                    continue

                # Передаем кадр для анализа глубоких мест
                if caster.smart_cast(bot.region, frame, game_region=bot.game_region):
                    bot.reset_tracking()
                    bot.float_found_time = time.time()
                    last_cast_time = time.time()
                    state = "WAIT_FLOAT"
                    print("🎯 Заброс выполнен")
                    time.sleep(3)
                else:
                    state = "SEARCH_WATER"
                    time.sleep(1)

            # ---------- ОЖИДАНИЕ ПОПЛАВКА ----------
            elif state == "WAIT_FLOAT":
                frame = bot.grab()
                if frame is None:
                    time.sleep(0.2)
                    continue
                    
                water = bot.detect_water(frame)
                
                if water is None:
                    print("💧 Вода исчезла, перезапуск")
                    state = "SEARCH_WATER"
                    time.sleep(2)
                    continue
                    
                reds, _ = bot.detect_red_in_water(frame, water)
                if reds:
                    bot.red_position = bot.get_main_red_position(reds)
                    bot.float_found_time = time.time()
                    state = "TRACK_BITE"
                    print("🔴 Поплавок найден, начинаю отслеживание")
                    time.sleep(0.5)
                elif time.time() - last_cast_time > 5:  # Ждем 5 секунд
                    # НЕ НАШЛИ ПОПЛАВОК ЗА 5 СЕКУНД - ПОВТОРНЫЙ ЗАБРОС
                    print("⏰ Поплавок не найден за 5 секунд, повторный заброс...")
                    
                    # Увеличиваем силу заброса для надежности
                    caster.cast_power_min = 0.5
                    caster.cast_power_max = 0.7
                    
                    state = "CAST"
                    time.sleep(1)  # Пауза перед повторным забросом
                    
                # Старый таймаут оставляем на случай серьезных проблем
                elif time.time() - last_cast_time > 30:
                    print("⏰ Критический таймаут ожидания поплавка")
                    state = "SEARCH_WATER"

            # ---------- ОТСЛЕЖИВАНИЕ ПОКЛЁВКИ ----------
            elif state == "TRACK_BITE":
                frame = bot.grab()
                if frame is None:
                    time.sleep(0.2)
                    continue
                    
                water = bot.detect_water(frame)
                
                if water is None:
                    print("💧 Вода исчезла во время трекинга")
                    bot.reset_tracking()
                    state = "SEARCH_WATER"
                    time.sleep(2)
                    continue
                    
                reds, _ = bot.detect_red_in_water(frame, water)
                if not reds:
                    print("🔍 Поплавок потерян, перезапуск")
                    bot.reset_tracking()
                    state = "SEARCH_WATER"
                    time.sleep(2)
                    continue
                
                red_pos = bot.get_main_red_position(reds)
                screen_pos = bot.move_to_red(red_pos)

                if screen_pos:
                    bot.float_current_position = screen_pos

                    if bot.float_initial_position is None:
                        bot.float_initial_position = screen_pos
                        bot.float_found_time = time.time()
                        print("📍 Начальная позиция поплавка")

                    bite = bot.check_bite(screen_pos)

                    if bite:
                        print("🎣 ПОКЛЕВКА! Подсекаю...")
                        
                        controller.reset()
                        bot.release_mouse()
                        
                        pyautogui.click(button='left')
                        print("✅ Подсечка выполнена")
                        
                        hook_time = time.time()
                        
                        state = "WAIT_MINIGAME"
                        waiting_for_minigame = True
                        minigame_start_time = time.time()
                        minigame_frames_without_indicator = 0
                        print("⏳ Ожидаю мини-игру...")

            # ---------- ОЖИДАНИЕ МИНИ-ИГРЫ ----------
            elif state == "WAIT_MINIGAME":
                time_waited = time.time() - minigame_start_time
                
                if time_waited > 10:
                    print("⏰ Таймаут ожидания мини-игры")
                    state = "SEARCH_WATER"
                    waiting_for_minigame = False
                    time.sleep(2)
                    continue
                
                position = indicator_detector.detect_indicator_position()
                
                if position is not None:
                    print("🎮 Мини-игра найдена, начинаю...")
                    state = "MINI_GAME"
                    waiting_for_minigame = False
                else:
                    time.sleep(0.5)

            # ---------- МИНИ-ИГРА ----------
            elif state == "MINI_GAME":
                position = indicator_detector.detect_indicator_position()
                
                if position is None:
                    minigame_frames_without_indicator += 1
                    controller.release()
                    
                    if minigame_frames_without_indicator >= 10:
                        print("✅ Мини-игра завершена")
                        controller.reset()
                        
                        # УСПЕШНОЕ ЗАВЕРШЕНИЕ СЕССИИ - возвращаем True
                        print("🎉 Сессия успешно завершена! Перезапуск через 2 секунды...")
                        time.sleep(2)
                        return True
                    else:
                        time.sleep(config["bot"]["delay"])
                else:
                    minigame_frames_without_indicator = 0
                    
                    if position < -dead_zone:
                        controller.press()
                    elif position > dead_zone:
                        controller.release()

                    time.sleep(config["bot"]["delay"])
    
    except Exception as e:
        print(f"❌ Ошибка в сессии: {e}")
        traceback.print_exc()
        return False
    
    finally:
        # Всегда очищаем ресурсы
        controller.reset()
        bot.release_mouse()
        if hasattr(bot, 'sct'):
            bot.sct.close()

def main():
    """Основная функция с бесконечным циклом перезагрузки"""
    session_count = 0
    successful_sessions = 0
    
    print("=" * 50)
    print("🎣 БОТ ДЛЯ РЫБАЛКИ С АВТОПЕРЕЗАГРУЗКОЙ")
    print("=" * 50)
    
    try:
        while True:
            session_count += 1
            print(f"\n{'='*50}")
            print(f"📊 Сессия #{session_count}")
            print(f"{'='*50}")
            
            success = run_fishing_session()
            
            if success:
                successful_sessions += 1
                success_rate = (successful_sessions / session_count) * 100
                print(f"✅ Успешных сессий: {successful_sessions}/{session_count} ({success_rate:.1f}%)")
            
            # Пауза перед следующей сессией
            restart_delay = 2
            print(f"🔄 Перезапуск через {restart_delay} секунды...")
            time.sleep(restart_delay)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*50)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   Всего сессий: {session_count}")
        print(f"   Успешных: {successful_sessions}")
        if session_count > 0:
            print(f"   Процент успеха: {(successful_sessions/session_count)*100:.1f}%")
        print("="*50)
        print("👋 Бот остановлен")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
