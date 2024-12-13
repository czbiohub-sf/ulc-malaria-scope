import logging
from time import sleep

import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Tuple

from ulc_mm_package.hardware.camera import AVTCamera
from ulc_mm_package.hardware.hardware_constants import MIN_PRESSURE_DIFF
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT
from ulc_mm_package.hardware.scope_routines import CellFinder, NoCellsFound
from ulc_mm_package.scope_constants import CAMERA_SELECTION

PNEUMATIC_PULL_TIME_S = 7
LED_BRIGHTNESS_PERC = 0.15
MIN_ACCEPTABLE_MOTOR_POS = 100
MAX_ACCEPTABLE_MOTOR_POS = 800

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


def perform_sweep(
    camera,
    motor,
    led,
    sweep_range,
    cell_finder: CellFinder,
    progress_callback,
    image_callback,
    motor_label_callback,
) -> Tuple[List[np.ndarray], List[int]]:
    logger.info("Starting sweep...")
    cell_finder.reset()
    led.turnOn()
    led.setDutyCycle(LED_BRIGHTNESS_PERC)
    total_steps = len(sweep_range)
    images = []

    logger.info(f"Moving motor...")
    for step, motor_pos in enumerate(sweep_range, start=1):
        motor.move_abs(motor_pos)
        img, timestamp = next(camera.yieldImages())
        images.append(img)
        cell_finder.add_image(motor_pos, img)
        progress_callback(step, total_steps)
        image_callback(img)
        motor_label_callback(motor_pos)

    led.turnOff()

    return images, list(sweep_range)


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


def main():
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
    root.title("Coarse Focus Adjustment Utility")
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

    slider = None  # Global reference to the slider
    first_sweep_done = False  # Track if the first sweep has been completed

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

    def display_images(images: List[np.ndarray], motor_positions: List[int]):
        nonlocal slider  # Reference the global slider
        if slider:
            slider.destroy()  # Destroy the existing slider if present

        def on_slider_move(value):
            index = int(float(value))
            update_image(images[index])
            motor_label.config(text=f"Motor Position: {motor_positions[index]}")

        slider = tk.Scale(
            slider_frame,
            from_=0,
            to=len(images) - 1,
            orient="horizontal",
            command=on_slider_move,
            length=500,
        )
        slider.pack()
        for motor_pos in motor_positions:
            slider.set(motor_pos)  # Set the tick marks to motor positions
        update_image(images[0])  # Display the first image initially
        motor_label.config(text=f"Motor Position: {motor_positions[0]}")

    def start_sweep():
        nonlocal first_sweep_done
        status_label.config(text="Sweeping in progress...")
        root.update()

        if not first_sweep_done:
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
            first_sweep_done = True

        progress["value"] = 0
        status_label.config(text="Sweeping in progress...")
        root.update()
        sweep_range = determine_sweep_range(motor)
        images, motor_positions = perform_sweep(
            camera,
            motor,
            led,
            sweep_range,
            cell_finder,
            update_progress,
            update_image,
            update_motor_label,
        )

        try:
            result = cell_finder.get_cells_found_position()
        except NoCellsFound:
            result = None

        if result is None:
            messagebox.showinfo(
                "Manual Adjustment Required",
                "No cells found. Use the slider to manually review images.",
            )
            display_images(images, motor_positions)
        elif result >= MAX_ACCEPTABLE_MOTOR_POS:
            messagebox.showinfo(
                "Adjustment Required",
                "Cells found too high. Please pull up on the stage.",
            )
        elif result <= MIN_ACCEPTABLE_MOTOR_POS:
            messagebox.showinfo(
                "Adjustment Required",
                "Cells found too low. Please push down on the stage.",
            )
        elif MIN_ACCEPTABLE_MOTOR_POS < result < MAX_ACCEPTABLE_MOTOR_POS:
            res = result
            output_string = (
                f"Stage adjustment successful!\nCells found at motor position {res}."
            )
            messagebox.showinfo(f"Success", output_string)
        else:
            messagebox.showerror("Error", "An unexpected error occurred.")

        status_label.config(text="Sweep completed.")

    def quit_application():
        camera.deactivateCamera()
        led.turnOff()
        root.destroy()

    # Buttons
    tk.Button(
        button_frame, text="Start Sweep", font=("Helvetica", 16), command=start_sweep
    ).pack(side=tk.RIGHT, padx=10)
    tk.Button(
        button_frame, text="Quit", font=("Helvetica", 16), command=quit_application
    ).pack(side=tk.RIGHT, padx=10)

    # Run the application
    root.mainloop()


if __name__ == "__main__":
    main()
