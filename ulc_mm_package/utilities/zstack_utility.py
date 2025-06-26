import argparse
from datetime import datetime
import logging
from functools import partial
import socket
from time import sleep
from pathlib import Path

import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ulc_mm_package.hardware.camera import AVTCamera
from ulc_mm_package.hardware.hardware_constants import MIN_PRESSURE_DIFF
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT
from ulc_mm_package.hardware.scope_routines import CellFinder, NoCellsFound
from ulc_mm_package.scope_constants import CAMERA_SELECTION
from ulc_mm_package.scope_constants import SSD_DIR, SSD_NAME

PNEUMATIC_PULL_TIME_S = 7
LED_BRIGHTNESS_PERC = 0.15
MIN_ACCEPTABLE_MOTOR_POS = 200
MAX_ACCEPTABLE_MOTOR_POS = 600

# Set up logging
logger = logging.getLogger()
if not logger.hasHandlers():
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def init_hardware():
    logger.info("Initializing required hardware...")

    camera = AVTCamera()
    pm = PneumaticModule()
    motor = DRV8825Nema()
    motor.homeToLimitSwitches()
    led = LED_TPS5420TDDCT()
    led.turnOn()
    led.setDutyCycle(0)

    return camera, pm, motor, led


def sweep(
    camera,
    motor,
    led,
    sweep_range,
    cell_finder: CellFinder,
    progress_callback,
    image_callback,
    motor_label_callback,
    n_imgs_per_step: int = 2,
    save_path: Optional[Path] = None,
) -> None:
    """Sweeps and updates passed-in cell finder with images. The caller can then check cell_finder to see if it found cells.

    If a save_path is provided, images will be saved to that path with the motor position and image number in the filename.
    """

    logger.info("Starting sweep...")
    cell_finder.reset()
    led.turnOn()
    led.setDutyCycle(LED_BRIGHTNESS_PERC)
    total_steps = len(sweep_range)

    # Create save directory if provided
    if save_path:
        save_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created save directory: {save_path}")

    logger.info("Moving motor...")
    for step, motor_pos in enumerate(sweep_range, start=1):
        try:
            motor.move_abs(motor_pos)
            if save_path:
                logger.info(
                    f"Capturing {n_imgs_per_step} image(s) at motor position {motor_pos}..."
                )
                for i in range(n_imgs_per_step):
                    img, _ = next(camera.yieldImages())
                    save_loc = save_path / f"motor_pos_{motor_pos}_n{i:03d}.png"
                    cv2.imwrite(str(save_loc), img)
                    sleep(
                        0.1
                    )  # Small delay to ensure image is saved before next capture
            img, _ = next(camera.yieldImages())
            cell_finder.add_image(motor_pos, img)
            progress_callback(step, total_steps)
            image_callback(img)
            motor_label_callback(motor_pos)
        except Exception as e:
            logger.error(f"Unexpected error at motor position {motor_pos}: {e}")
            continue

    led.turnOff()
    logger.info("Sweep completed.")


def determine_sweep_range(motor):
    current_position = motor.pos
    max_position = motor.max_pos
    min_position = 0

    if current_position > max_position / 2:
        logger.info("Motor at top range. Sweeping from top to bottom.")
        return range(max_position, min_position - 1, -10)
    else:
        logger.info("Motor not at top range. Sweeping from bottom to top.")
        return range(min_position, max_position + 1, 10)


def pressure_check(pm: PneumaticModule) -> bool:
    """Ensure the lid is closed by checking the pressure."""
    initial_pressure, _ = pm.getPressure()
    pm.setDutyCycle(pm.getMinDutyCycle())
    sleep(0.5)
    post_pull_pressure, _ = pm.getPressureMaxReadAttempts(max_attempts=10)
    pm.setDutyCycle(pm.getMaxDutyCycle())

    pressure_diff = initial_pressure - post_pull_pressure
    logger.info(f"Measure pressure difference is: {pressure_diff}hPa.")
    return pressure_diff >= MIN_PRESSURE_DIFF


def main(n_steps: int = 15, imgs_per_step: int = 2):
    # Save location
    device_name = socket.gethostname()
    curr_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_path = Path(SSD_DIR) / SSD_NAME / f"zstack_{device_name}_{curr_time}"

    # Initialize hardware
    camera, pm, motor, led = init_hardware()
    cell_finder = CellFinder()

    # Retrieve camera dimensions
    img_width, img_height = (
        CAMERA_SELECTION.img_dims().width,
        CAMERA_SELECTION.img_dims().height,
    )

    # Set up GUI
    root = tk.Tk()
    root.title("Focus Stack Utility")
    root.geometry("800x600")
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Components
    status_label = tk.Label(root, text="", font=("Helvetica", 16))
    status_label.grid(row=0, column=0, pady=10, sticky="n")
    status_label.config(text="Please load a flow cell (with blood) and close the lid.")

    image_canvas = tk.Label(root, bg="black")
    image_canvas.grid(row=1, column=0, pady=10, sticky="n")

    progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
    progress.grid(row=2, column=0, pady=10, sticky="ew")

    motor_label = tk.Label(root, text="Motor Position: 0", font=("Helvetica", 14))
    motor_label.grid(row=3, column=0, pady=10, sticky="n")

    button_frame = tk.Frame(root)
    button_frame.grid(row=5, column=0, pady=20, sticky="se")

    slider_frame = tk.Frame(root)
    slider_frame.grid(row=4, column=0, pady=10, sticky="n")

    def update_progress(current, total):
        progress["maximum"] = total
        progress["value"] = current
        root.update_idletasks()

    def update_image(img):
        img = Image.fromarray(img)
        # Maintain aspect ratio while resizing to fit within the GUI window dimensions
        canvas_width = 800
        canvas_height = 600
        scale = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        img = img.resize((new_width, new_height), Image.ANTIALIAS)
        img_tk = ImageTk.PhotoImage(img)
        image_canvas.config(image=img_tk)
        image_canvas.image = img_tk

    def update_motor_label(position):
        motor_label.config(text=f"Motor Position: {position}")

    def start_sweep(
        n_steps: int = 15, imgs_per_step: int = 2, save_path: Optional[Path] = save_path
    ):
        status_label.config(text="Sweeping in progress...")
        status_label.config(text="Checking that a flow cell is loaded...")
        root.update()
        if not pressure_check(pm):
            messagebox.showinfo(
                "Error",
                "Please ensure the CAP module is on and a flow cell is loaded.",
            )
            status_label.config(
                text="Please load a flow cell (with blood) and close the lid."
            )
            root.update()
            return
        status_label.config(text="Pulling RBCs into the field of view...")
        root.update()
        pm.setDutyCycle(pm.getMinDutyCycle())
        sleep(PNEUMATIC_PULL_TIME_S)  # Allow cells to enter
        pm.setDutyCycle(pm.getMaxDutyCycle())

        progress["value"] = 0
        status_label.config(text="Finding cells...")
        root.update()
        sweep_range = determine_sweep_range(motor)
        sweep(
            camera,
            motor,
            led,
            sweep_range,
            cell_finder,
            update_progress,
            update_image,
            update_motor_label,
            n_imgs_per_step=imgs_per_step,
            save_path=None,
        )

        try:
            result = cell_finder.get_cells_found_position()
            status_label.config(text="Cells found!")
        except NoCellsFound:
            result = None

        if result is None:
            messagebox.showinfo(
                "No cells found.",
                "No cells found. Please try sweeping again.",
            )
            status_label.config(text="No cells found. Please try sweeping again.")
            return
        elif (result - n_steps) > 0 and (result + n_steps) < motor.max_pos:
            status_label.config(
                text=f"Cells found. Performing a sweep of +/- {n_steps}."
            )
            logger.info(f"Cells found at motor position: {result}")
            sweep_range = range(result - n_steps, result + n_steps + 1, 1)
            sweep(
                camera,
                motor,
                led,
                sweep_range,
                cell_finder,
                update_progress,
                update_image,
                update_motor_label,
                n_imgs_per_step=imgs_per_step,
                save_path=save_path,
            )

        status_label.config(text="Sweep completed.")

    def quit_application():
        camera.deactivateCamera()
        led.turnOff()
        root.destroy()

    # Buttons
    sweep_fn = partial(
        start_sweep, n_steps=n_steps, imgs_per_step=imgs_per_step, save_path=save_path
    )
    tk.Button(
        button_frame, text="Start Sweep", font=("Helvetica", 16), command=sweep_fn
    ).pack(side=tk.RIGHT, padx=10)
    tk.Button(
        button_frame, text="Quit", font=("Helvetica", 16), command=quit_application
    ).pack(side=tk.RIGHT, padx=10)

    # Run the application
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Coarse Focus Adjustment / Save Z-stack Utility"
    )
    parser.add_argument(
        "--sweep_range_about_center_steps",
        "-s",
        default=15,
        type=int,
        help="Number of steps (plus/minus) about the motor position where cells were found. I.e if this value is 15 and cells were found at motor position 450,"
        " the sweep will be from 435 to 465 with step increments of 1. Default: 15",
    )
    parser.add_argument(
        "--imgs_per_step",
        "-i",
        default=2,
        type=int,
        help="Number of images to capture at each motor position during the sweep. Default: 2",
    )
    args = parser.parse_args()

    main(
        n_steps=args.sweep_range_about_center_steps,
        imgs_per_step=args.imgs_per_step,
    )
