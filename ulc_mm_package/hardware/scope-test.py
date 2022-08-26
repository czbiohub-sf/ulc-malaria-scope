from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
import cv2

def focusTest(mscope: MalariaScope):
    # Phase 1 - get focus bounds
    focus_bound_routine = getFocusBoundsCoroutine(mscope)
    focus_bound_routine.send(None)
    for img in mscope.camera.yieldImages():
        cv2.imshow("bounds", img)
        cv2.waitKey(2)
        try:
            focus_bound_routine.send(img)
        except StopIteration as e:
            lower, upper = e.value

    mscope.camera.stopAcquisition()

    focus_coroutine = focusCoroutine(mscope, lower, upper)
    focus_coroutine.send(None)
    for img in mscope.camera.yieldImages():
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