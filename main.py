from context import BotContext

from states.cast import CastState
from states.wait_float import WaitFloatState
from states.bite import BiteState
from states.mini_game import MiniGameState

from grabber import Grabber
from indicator_detector import IndicatorDetector
from received_detector import ReceivedDetector


STATES = {
    "CAST": CastState(),
    "WAIT_FLOAT": WaitFloatState(),
    "BITE": BiteState(),
    "MINI_GAME": MiniGameState(),
}

def main():
    grabber = Grabber()  # ROI мини-игры
    indicator = IndicatorDetector()
    received = ReceivedDetector()

    ctx = BotContext(
        grabber=grabber,
        indicator_detector=indicator,
        received_detector=received,
    )

    current_state = STATES["CAST"]
    current_state.enter(ctx)

    while ctx.running:
        next_state_name = current_state.update(ctx)
        if next_state_name:
            current_state.exit(ctx)
            current_state = STATES[next_state_name]
            current_state.enter(ctx)

if __name__ == "__main__":
    main()
