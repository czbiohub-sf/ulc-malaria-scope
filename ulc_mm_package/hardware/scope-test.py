from os import mkdir
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
import cv2

def focusTest(mscope: MalariaScope):
    # Phase 1 - autobrightness
    ab_routine = autobrightnessCoroutine(mscope)
    ab_routine.send(None)
    for img in mscope.camera.yieldImages():
        cv2.imshow("autobrightness", img)
        cv2.waitKey(2)
        try:
            ab_routine.send(img)
        except StopIteration as e:
            final_brightness = e.value
            print(final_brightness)
            cv2.destroyAllWindows()
            break
    mscope.camera.stopAcquisition()

    # Phase 2 - get focus bounds
    focus_bound_routine = getFocusBoundsCoroutine(mscope)
    focus_bound_routine.send(None)
    try:
        mkdir("focus_bounds/")
    except Exception as e:
        print(e)
    counter = 0
    for img in mscope.camera.yieldImages():
        cv2.imwrite(f"focus_bounds/{counter}.png")
        counter += 1
        cv2.imshow("bounds", img)
        cv2.waitKey(2)
        print(mscope.motor.pos)
        try:
            focus_bound_routine.send(img)
        except StopIteration as e:
            cv2.destroyAllWindows()
            lower, upper = e.value
            break

    mscope.camera.stopAcquisition()

    # Phase 3 - fine focus adjustment
    print(lower, upper)
    focus_coroutine = focusCoroutine(mscope, lower, upper)
    focus_coroutine.send(None)
    for img in mscope.camera.yieldImages():
        print(mscope.motor.pos)
        cv2.imshow("focus", img)
        cv2.waitKey(2)
        try:
            focus_coroutine.send(img)
        except StopIteration as e:
            break
    mscope.camera.stopAcquisition()

if __name__ == "__main__":
    mscope = MalariaScope()
    focusTest(mscope)