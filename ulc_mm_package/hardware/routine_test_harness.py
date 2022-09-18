from time import perf_counter
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
import cv2

def initial_cell_check(mscope):
    # Autobrightness
    ab_routine = autobrightnessRoutine(mscope)
    ab_routine.send(None)
    for img in mscope.cam.yieldImages():
        _displayImage(img)
        try:
            ab_routine.send(img)
        except StopIteration as e:
            final_brightness = e.value
            print(final_brightness)
            break

    # Pull, check for cells
    find_cells = find_cells_routine(mscope)
    find_cells.send(None)
    for img in mscope.cam.yieldImages():
        _displayImage(img)
        try:
            find_cells.send(img)
        except StopIteration as e:
            res = e.value
            if isinstance(res, bool):
                print("Unable to find cells")
                break
            elif isinstance(res, int):
                print(f"Motor pos: {res}")
                break

    # Cells found, perform SSAF w/ the motor at the position returned above
    if isinstance(res, int):
        mscope.motor.move_abs(res)
        ssaf = singleShotAutofocusRoutine(mscope, None)
        ssaf.send(None)
        for img in mscope.cam.yieldImages():
            _displayImage(img)
            try:
                ssaf.send(img)
            except StopIteration as e:
                print(f"SSAF complete, motor moved by: {e.value} steps")
                break

    # Continue for another 10 seconds just to view what's going on
    start = perf_counter()
    for img in mscope.cam.yieldImages():
        _displayImage(img)
        if perf_counter() - start > 10:
            break

def _displayImage(img: np.ndarray) -> None:
    cv2.imshow("Display", img)
    cv2.waitKey(2)

if __name__ == "__main__":
    mscope = MalariaScope()
    initial_cell_check(mscope)