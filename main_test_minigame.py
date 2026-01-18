import time
from context import BotContext
from states.mini_game import MiniGameState

from grabber import Grabber
from indicator_detector import IndicatorDetector
from received_detector import ReceivedDetector


def main():
    ctx = BotContext()

    # Подключаем зависимости прямо в ctx
    ctx.grabber = Grabber()
    ctx.indicator_detector = IndicatorDetector()
    ctx.received_detector = ReceivedDetector()

    state = MiniGameState()
    state.enter(ctx)

    print("👉 Тест мини-игры: ты сам закидываешь и подсекаешь, я только играю мини-игру.")
    print("👉 Остановить: Ctrl+C")

    try:
        while True:
            nxt = state.update(ctx)
            if nxt == "CAST":
                # В тесте просто ждём следующую мини-игру
                state.exit(ctx)
                time.sleep(0.2)
                state.enter(ctx)
            time.sleep(0.001)

    except KeyboardInterrupt:
        ctx.release_all()
        try:
            ctx.grabber.close()
        except:
            pass
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
