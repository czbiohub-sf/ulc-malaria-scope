from time import perf_counter
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
import cv2

def _displayImage(img: np.ndarray) -> None:
    """Convenince wrapper to display an image using opencv"""

    cv2.imshow("Display", img)
    cv2.waitKey(2)

def initial_cell_check(mscope):
    """Test the cell finding routine and subsequent autofocus
    
    Steps
    -----
    1. Autobrightness
    2. Run find_cells_routine (will return False or an int of the motor position where
    cells were most likely found)
    3. Run the single-shot autofocus once (using a batch of AF_BATCH_SIZE images (see
    image_processing.processing_constants.py file))
    4. Continue streaming images to the display for another 10 seconds to validate
    how things look.
    """


    # Autobrightness
    print(f"Running Autobrightness...")
    ab_routine = autobrightnessRoutine(mscope)
    ab_routine.send(None)
    for img in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            ab_routine.send(img)
        except StopIteration as e:
            final_brightness = e.value
            print(f"Mean pixel val: {final_brightness}")
            break

    # Pull, check for cells
    print("Initiating `find_cells_routine`")
    find_cells = find_cells_routine(mscope)
    find_cells.send(None)
    for img in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            find_cells.send(img)
        except StopIteration as e:
            res = e.value
            if isinstance(res, bool):
                print("Unable to find cells")
                break
            elif isinstance(res, int):
                print(f"Cells found @ motor pos: {res}")
                break

    # Cells found, perform SSAF w/ the motor at the position returned above
    if isinstance(res, int):
        print(f"Moving motor to {res}")
        mscope.motor.move_abs(res)

        print("Initiating SSAF")
        ssaf = singleShotAutofocusRoutine(mscope, None)
        ssaf.send(None)
        for img in mscope.camera.yieldImages():
            _displayImage(img)
            try:
                ssaf.send(img)
            except StopIteration as e:
                print(f"SSAF complete, motor moved by: {e.value} steps")
                break

    # Do an initial fast flow to get roughly to the target flowrate
    fast_flow_routine = fastFlowRoutine(mscope, None)
    fast_flow_routine.send(None)
    for img in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            fast_flow_routine.send(img)
        except StopIteration as e:
            flow_val = e.value
            if isinstance(flow_val, bool):
                print("Unable to achieve flowrate - syringe at max position but flowrate is below target.")
            elif isinstance(flow_val, float):
                print(f"Flowrate: {flow_val}")
            break

    # Display for another 10 seconds
    start = perf_counter()
    for img in mscope.camera.yieldImages():
        _displayImage(img)
        if perf_counter() - start > 10:
            break

if __name__ == "__main__":
    mscope = MalariaScope()
    initial_cell_check(mscope)