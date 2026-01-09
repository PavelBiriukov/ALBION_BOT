import time
import math

class SpotPowerCalibrator:
    def __init__(self):
        self.best_power = None
        self.best_err = 1e9

    @staticmethod
    def dist(a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1])

    def wait_float(self, get_float_center_fn, timeout=5.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            p = get_float_center_fn()
            if p is not None:
                return p
            time.sleep(0.05)
        return None

    def calibrate(self, spot_center, powers, cast_fn, get_float_center_fn):
        """
        spot_center: (x,y) в координатах cropped frame
        powers: список значений удержания
        cast_fn(power) -> делает заброс
        get_float_center_fn() -> возвращает (x,y) поплавка в координатах cropped frame
        """
        self.best_power = None
        self.best_err = 1e9

        for p in powers:
            ok = cast_fn(p)
            if not ok:
                continue

            # ждём поплавок
            float_center = self.wait_float(get_float_center_fn, timeout=5.0)
            if float_center is None:
                print(f"power={p:.2f} ❌ поплавок не найден")
                continue

            err = self.dist(float_center, spot_center)
            print(f"power={p:.2f} err={err:.1f}px float={float_center} spot={spot_center}")

            if err < self.best_err:
                self.best_err = err
                self.best_power = p

            # маленькая пауза, чтобы игра успела “успокоиться”
            time.sleep(0.3)

        return self.best_power, self.best_err
