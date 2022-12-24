from datetime import datetime
from time import perf_counter, sleep
from os import listdir

from ulc_mm_package.scope_constants import (
    EXPERIMENT_METADATA_KEYS,
    PER_IMAGE_METADATA_KEYS,
    SSD_DIR,
)
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.processing_constants import FLOWRATE

from ulc_mm_package.image_processing.cell_finder import LowDensity

import cv2


def _displayImage(img: np.ndarray) -> None:
    """Convenince wrapper to display an image using opencv"""

    cv2.imshow("Display", img)
    cv2.waitKey(2)


def _displayForNSeconds(seconds: int):
    start = perf_counter()
    for img, _ in mscope.camera.yieldImages():
        _displayImage(img)
        if perf_counter() - start > seconds:
            break


def autobrightness_wrappper(mscope: MalariaScope):
    print(f"Running Autobrightness...")
    ab_routine = autobrightnessRoutine(mscope)
    ab_routine.send(None)
    for img, _ in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            ab_routine.send(img)
        except StopIteration as e:
            final_brightness = e.value
            print(f"Mean pixel val: {final_brightness}")
            break
        except BrightnessTargetNotAchieved as e:
            print(
                f"Brightness not quite at target, but still ok. Mean pixel val: {e.value}"
            )
            break
        except BrightnessCriticallyLow:
            raise
        except LEDNoPower:
            print(f"LED is not working.")
            raise


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

    print("Running `find_cells_routine`")
    find_cells = find_cells_routine(mscope)
    find_cells.send(None)
    for img, _ in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            find_cells.send(img)
        except NoCellsFound:
            print("Unable to find cells")
            res = -1
            break
        except StopIteration as e:
            res = e.value
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

    print("Running SSAF")
    ssaf = continuousSSAFRoutine(mscope, None)
    ssaf.send(None)
    for img, _ in mscope.camera.yieldImages():
        _displayImage(img)
        steps_from_focus = ssaf.send(img)
        if isinstance(steps_from_focus, int):
            print(f"SSAF complete, motor moved by: {steps_from_focus} steps")
            break


def fast_flow_wrapper(mscope: MalariaScope):
    print("Running fast_flow_routine")
    fast_flow_routine = fastFlowRoutine(mscope, None, FLOWRATE.FAST.value)
    fast_flow_routine.send(None)
    for img, timestamp in mscope.camera.yieldImages():
        _displayImage(img)
        try:
            fast_flow_routine.send((img, timestamp))
        except CantReachTargetFlowrate:
            print(
                "Unable to achieve flowrate - syringe at max position but flowrate is below target."
            )
            flow_val = -1
            break
        except LowConfidenceCorrelations:
            print("Too many recent low confidence xcorr calculations.")
            flow_val = -1
            break
        except StopIteration as e:
            flow_val = e.value
            print(f"Flowrate: {flow_val}")
            break
        except Exception as e:
            print(e)

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

    if find_cells_res != -1:
        # SSAF and fast flow
        ssaf_wrapper(mscope, find_cells_res)

        # Do an initial fast flow to get roughly to the target flowrate
        fast_flow_res = fast_flow_wrapper(mscope)

        if fast_flow_res != -1:
            # Collect data for 5 mins w/ SSAF and flow control
            main_acquisition_loop(mscope)
        else:
            print("Target flowrate couldn't be achieved, so I'm throwing in the towel.")
            _displayForNSeconds(10)
    else:
        print("No cells were found so I'm throwing in the towel.")
        _displayForNSeconds(10)


def main_acquisition_loop(mscope: MalariaScope):
    """Run the main acquisition loop for 5 mins"""

    start = perf_counter()
    prev_print_time = perf_counter()
    stop_time_s = 1 * 60

    fake_exp_metadata = {k: k for k in EXPERIMENT_METADATA_KEYS}
    fake_per_img_metadata = {k: k for k in PER_IMAGE_METADATA_KEYS}

    # Get SSD directory
    try:
        self.ext_dir = SSD_DIR + listdir(SSD_DIR)[0] + "/"
    except (FileNotFoundError, IndexError) as e:
        print(
            f"Could not find any folders within {SSD_DIR}. Check that the SSD is plugged in."
        )
        sys.exit(1)

    mscope.data_storage.createNewExperiment(
        self.ext_dir,
        "",
        datetime.now().strftime(DATETIME_FORMAT),
        fake_exp_metadata,
        fake_per_img_metadata,
    )

    periodic_ssaf = periodicAutofocusWrapper(mscope, None)
    periodic_ssaf.send(None)

    flow_control = flowControlRoutine(mscope, FLOWRATE.FAST.value, None)
    flow_control.send(None)

    cell_density = cell_density_routine(None)
    cell_density.send(None)

    for i, (img, timestamp) in enumerate(mscope.camera.yieldImages()):
        # Display
        _displayImage(img)

        # Periodically adjust focus using single shot autofocus
        steps_from_focus = periodic_ssaf.send(img)
        if isinstance(steps_from_focus, int):
            print(f"SSAF: Motor move - {steps_from_focus} steps")

        prev_results = count_parasitemia(mscope, img)

        density_start_time = perf_counter()
        try:
            count = cell_density.send(img)
        except LowDensity as e:
            print(e)
            cell_density = cell_density_routine(None)
            cell_density.send(None)
        print(f"Cell density : {count}, {perf_counter() - density_start_time}")

        try:
            flow_val = flow_control.send((img, timestamp))
            if isinstance(flow_val, float):
                print(f"Flow control: Flow val - {flow_val}")
        except CantReachTargetFlowrate:
            print("Can't reach target flowrate.")

        # Save data
        fake_per_img_metadata["timestamp"] = timestamp
        fake_per_img_metadata["motor_pos"] = mscope.motor.pos
        fake_per_img_metadata["pressure_hpa"], _ = mscope.pneumatic_module.getPressure()
        fake_per_img_metadata[
            "syringe_pos"
        ] = mscope.pneumatic_module.getCurrentDutyCycle()
        fake_per_img_metadata["flowrate"] = flow_val
        fake_per_img_metadata["temperature"] = mscope.ht_sensor.getTemperature()
        fake_per_img_metadata["humidity"] = mscope.ht_sensor.getRelativeHumidity()
        mscope.data_storage.writeData(img, fake_per_img_metadata, i)

        # Timed stop condition
        if perf_counter() - start > stop_time_s:
            break
        elif perf_counter() - prev_print_time >= 10:
            print(f"{perf_counter() - start:.1f}s elapsed out of ({stop_time_s}s)")
            prev_print_time = perf_counter()

    mscope.data_storage.save_uniform_sample()
    closing_file_future = mscope.data_storage.close()
    mscope.pneumatic_module.setDutyCycle(mscope.pneumatic_module.getMaxDutyCycle())

    print("Waiting for the file to finish closing...")
    while not closing_file_future.done():
        sleep(1)

    print("Successfully closed file.")


if __name__ == "__main__":
    try:
        mscope = MalariaScope()
        initial_cell_check(mscope)
    finally:
        mscope.shutoff()
