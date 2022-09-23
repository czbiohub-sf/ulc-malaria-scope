from time import perf_counter
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS, PER_IMAGE_METADATA_KEYS, TARGET_FLOWRATE

import cv2

def _displayImage(img: np.ndarray) -> None:
    """Convenince wrapper to display an image using opencv"""

    cv2.imshow("Display", img)
    cv2.waitKey(2)

def autobrightness_wrappper(mscope: MalariaScope):
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

def find_cells_wrapper(mscope: MalariaScope):
    """Wrapper for the find_cells_routine

    Parameters
    ----------
    mscope: MalariaScope

    Returns
    -------
    bool / int: result of whether cells were found
        int returns the motor position w/ the highest cross correlation
        bool returns False, indicating 
    """
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
    return res

def ssaf_wrapper(mscope: MalariaScope, motor_pos: int):
    """Wrapper for SSAF
    
    Parameters
    ----------
    motor_pos: int
        Motor position to move to before starting SSAF
    
    mscope: MalariaScope
    """

    # Cells found, perform SSAF w/ the motor at the position returned above
    print(f"Moving motor to {motor_pos}")
    mscope.motor.move_abs(motor_pos)

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

def fast_flow_wrapper(mscope: MalariaScope):
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

    return flow_val

def initial_cell_check(mscope: MalariaScope):
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
    autobrightness_wrappper(mscope)

    # Pull, check for cells
    find_cells_res = find_cells_wrapper(mscope)

    if isinstance(find_cells_res, int):
        # SSAF and fast flow
        ssaf_wrapper(mscope, find_cells_res)

        # Do an initial fast flow to get roughly to the target flowrate
        fast_flow_res = fast_flow_wrapper(mscope)

        if isinstance(fast_flow_res, float):
            # Collect data for 5 mins w/ SSAF and flow control
            main_acquisition_loop(mscope)
    
    else:
        # Display for another 10 seconds
        start = perf_counter()
        for img in mscope.camera.yieldImages():
            _displayImage(img)
            if perf_counter() - start > 10:
                break

def main_acquisition_loop(mscope: MalariaScope):
    """Run the main acquisition loop for 5 mins"""

    start = perf_counter()
    stop_time_s = 5*60

    fake_exp_metadata = {
        k: k for k in EXPERIMENT_METADATA_KEYS
    }
    fake_per_img_metadata = {
        k: k for k in PER_IMAGE_METADATA_KEYS
    }

    mscope.data_storage.createNewExperiment("", fake_exp_metadata, fake_per_img_metadata)

    periodic_ssaf = periodicAutofocusWrapper(mscope, None)
    periodic_ssaf.send(None)

    flow_control = flowControlRoutine(mscope, TARGET_FLOWRATE, None)
    flow_control.send(None)

    for img in mscope.camera.yieldImages():
        # Save data
        mscope.data_storage.writeData(img, fake_per_img_metadata)

        # Periodically adjust focus using single shot autofocus
        periodic_ssaf.send(img)

        # Adjust the flow
        flow_control.send(img)
        
        # Timed stop condition
        if perf_counter() - start > stop_time_s:
            break

    closing_file_future = mscope.data_storage.close()

    while not closing_file_future.done():
        print("Waiting for the file to finish closing...")
        sleep(1)

    print("Successfully closed file.")
        


if __name__ == "__main__":
    mscope = MalariaScope()
    initial_cell_check(mscope)