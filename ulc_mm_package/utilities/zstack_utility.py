import argparse
from datetime import datetime
import logging
from functools import partial
import shutil
import socket
import subprocess
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
    collect_images: bool = False,
) -> Optional[list]:
    """Sweeps and updates the given CellFinder object with images. The caller can then check cell_finder to see if it found cells.

    If a save_path is provided, images will be saved to that path with the motor position and image number in the filename.
    If collect_images is True, returns a list of (motor_pos, img) tuples for manual review.
    """

    logger.info("Starting sweep...")
    cell_finder.reset()
    led.turnOn()
    led.setDutyCycle(LED_BRIGHTNESS_PERC)
    total_steps = len(sweep_range)

    # Initialize collection list if needed
    collected_images: Optional[list] = [] if collect_images else None

    # Create save directory if provided
    if save_path:
        save_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created save directory: {save_path}")

    logger.info("Moving motor...")
    for step, motor_pos in enumerate(sweep_range, start=1):
        try:
            motor.move_abs(motor_pos)
            if save_path:
                for i in range(n_imgs_per_step):
                    img, _ = next(camera.yieldImages())
                    save_loc = save_path / f"motor_pos_{motor_pos}_n{i:03d}.png"
                    cv2.imwrite(str(save_loc), img)
                    sleep(
                        0.1
                    )  # Small delay to ensure image is saved before next capture
            img, _ = next(camera.yieldImages())
            cell_finder.add_image(motor_pos, img)

            # Collect image for manual review if requested
            if collect_images:
                collected_images.append((motor_pos, img))  # type:ignore

            progress_callback(step, total_steps)
            image_callback(img)
            motor_label_callback(motor_pos)
            sleep(0.05)  # Allow motor to settle
        except Exception as e:
            logger.error(f"Unexpected error at motor position {motor_pos}: {e}")
            continue

    led.turnOff()
    logger.info("Sweep completed.")

    if collect_images:
        return collected_images
    else:
        return None


def compress_saved_images(
    save_path: Path, remove_original: bool = True
) -> Optional[Path]:
    """Compress the saved images folder using tar with pigz compression.

    Args:
        save_path: Path to the folder containing saved images
        remove_original: If True, remove the original folder after successful compression

    Returns:
        Path to the compressed archive, or None if compression failed
    """
    if not save_path.exists():
        logger.warning(f"Save path does not exist: {save_path}")
        return None

    # Create archive name in the same directory as save_path
    archive_path = save_path.parent / f"{save_path.name}.tar.gz"

    try:
        logger.info(f"Compressing {save_path} to {archive_path}...")

        # First try with pigz (parallel gzip)
        try:
            cmd = [
                "tar",
                "-I",
                "pigz -9",
                "-cf",
                str(archive_path),
                "-C",
                str(save_path.parent),
                save_path.name,
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Used pigz for compression")

        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to regular gzip if pigz is not available
            logger.info("pigz not available, falling back to gzip")
            cmd = [
                "tar",
                "-czf",
                str(archive_path),
                "-C",
                str(save_path.parent),
                save_path.name,
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Used gzip for compression")

        if archive_path.exists():
            archive_size = archive_path.stat().st_size / (1024 * 1024)  # Size in MB

            # Calculate original folder size in MB
            def get_folder_size(path):
                total = 0
                for p in path.rglob("*"):
                    if p.is_file():
                        total += p.stat().st_size
                return total / (1024 * 1024)  # Size in MB

            original_size = get_folder_size(save_path)
            logger.info(
                f"Compression completed successfully. Archive size: {archive_size:.2f} MB, Original folder size: {original_size:.2f} MB"
            )

            # Remove original folder if requested
            if remove_original:
                try:
                    shutil.rmtree(save_path)
                    logger.info(f"Removed original folder: {save_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove original folder: {e}")

            return archive_path
        else:
            logger.error("Compression completed but archive file not found")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"Compression failed with error: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during compression: {e}")
        return None


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


def manual_review(images_with_positions, on_select):
    """Manual review interface for when CellFinder fails to find cells.

    Args:
        images_with_positions: List of (motor_pos, img) tuples
        on_select: Callback function that takes a motor position and performs the local sweep
    """
    if not images_with_positions:
        messagebox.showinfo("No Images", "No images available for manual review.")
        return

    # Create review window
    review_win = tk.Toplevel()
    review_win.title("Manual Cell Selection")
    review_win.geometry("900x700")
    review_win.grid_rowconfigure(1, weight=1)
    review_win.grid_columnconfigure(0, weight=1)

    # Header
    header_label = tk.Label(
        review_win,
        text="No cells found automatically. Please manually select a position with cells.",
        font=("Helvetica", 14),
        wraplength=800,
    )
    header_label.grid(row=0, column=0, pady=10, sticky="n")

    # Image display
    image_canvas = tk.Label(review_win, bg="black")
    image_canvas.grid(row=1, column=0, rowspan=4, pady=0, sticky="nsew")

    # Position info
    position_label = tk.Label(
        review_win, text="Motor Position: 0", font=("Helvetica", 12)
    )
    position_label.grid(row=4, column=0, pady=5, sticky="n")

    # Slider frame
    slider_frame = tk.Frame(review_win)
    slider_frame.grid(row=5, column=0, pady=10, sticky="ew")
    slider_frame.grid_columnconfigure(0, weight=1)

    # Slider
    current_index = tk.IntVar(value=0)
    slider = ttk.Scale(
        slider_frame,
        from_=0,
        to=len(images_with_positions) - 1,
        orient="horizontal",
        variable=current_index,
        command=lambda x: update_display(),
    )
    slider.grid(row=0, column=0, sticky="ew", padx=10)

    # Slider labels
    tk.Label(slider_frame, text="0").grid(row=1, column=0, sticky="w", padx=10)
    tk.Label(slider_frame, text=str(len(images_with_positions) - 1)).grid(
        row=1, column=0, sticky="e", padx=10
    )

    # Button frame
    button_frame = tk.Frame(review_win)
    button_frame.grid(row=6, column=0, pady=20, sticky="s")

    def update_display():
        """Update the displayed image and position information."""
        idx = current_index.get()
        if 0 <= idx < len(images_with_positions):
            motor_pos, img = images_with_positions[idx]

            # Update position label
            position_label.config(text=f"Motor Position: {motor_pos}")

            # Convert and display image
            img_pil = Image.fromarray(img)

            # Resize image to fit in the window while maintaining aspect ratio
            canvas_width = 800
            canvas_height = 400
            img_width, img_height = img_pil.size
            scale = min(canvas_width / img_width, canvas_height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            img_pil = img_pil.resize((new_width, new_height), Image.ANTIALIAS)

            img_tk = ImageTk.PhotoImage(img_pil)
            image_canvas.config(image=img_tk)
            image_canvas.image = img_tk  # Keep a reference

    def sweep_here():
        """Trigger the local sweep at the currently selected position."""
        idx = current_index.get()
        if 0 <= idx < len(images_with_positions):
            motor_pos, _ = images_with_positions[idx]
            review_win.destroy()
            on_select(motor_pos)

    def cancel():
        """Cancel the manual review."""
        review_win.destroy()

    # Buttons
    tk.Button(
        button_frame,
        text="Sweep Here",
        font=("Helvetica", 14),
        command=sweep_here,
        bg="green",
        fg="white",
    ).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Cancel", font=("Helvetica", 14), command=cancel).pack(
        side=tk.LEFT, padx=10
    )

    # Keyboard shortcuts
    def on_key(event):
        if event.keysym == "Left":
            if current_index.get() > 0:
                current_index.set(current_index.get() - 1)
                update_display()
        elif event.keysym == "Right":
            if current_index.get() < len(images_with_positions) - 1:
                current_index.set(current_index.get() + 1)
                update_display()
        elif event.keysym == "Return":
            sweep_here()
        elif event.keysym == "Escape":
            cancel()

    review_win.bind("<Key>", on_key)
    review_win.focus_set()

    # Initialize display
    update_display()

    # Make window modal
    review_win.transient()
    review_win.grab_set()
    review_win.wait_window()


def main():
    args = parse_args()
    n_steps = args.sweep_range_about_center_steps
    imgs_per_step = args.imgs_per_step

    logger.info(
        f"Starting Z-stack utility with n_steps={n_steps} and imgs_per_step={imgs_per_step}"
    )

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
    image_canvas.grid(row=1, column=0, pady=10, rowspan=4, sticky="nsew")

    progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
    progress.grid(row=4, column=0, pady=10, sticky="ew")

    motor_label = tk.Label(root, text="Motor Position: 0", font=("Helvetica", 14))
    motor_label.grid(row=5, column=0, pady=10, sticky="n")

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
        n_steps: int = 20, imgs_per_step: int = 2, save_path: Optional[Path] = save_path
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
        collected_images = sweep(
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
            collect_images=True,
        )

        try:
            result = cell_finder.get_cells_found_position()
            status_label.config(text="Cells found!")
        except NoCellsFound:
            result = None

        if result is None:
            # No cells found automatically - launch manual review
            def do_local_sweep(center_pos):
                """Perform local sweep around user-selected position."""
                status_label.config(
                    text=f"Performing local sweep around position {center_pos}..."
                )
                root.update()
                logger.info(f"User selected motor position: {center_pos}")
                sweep_range = range(center_pos - n_steps, center_pos + n_steps + 1, 1)
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
                    collect_images=False,
                )
                status_label.config(text="Sweep completed.")

            manual_review(collected_images, do_local_sweep)
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
                collect_images=False,
            )

        status_label.config(text="Sweep completed.")
        if save_path:
            logger.info("Compressing images...")
            compressed_path = compress_saved_images(save_path)
            if compressed_path:
                status_label.config(text="Images saved and compressed.")

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


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Coarse Focus Adjustment / Save Z-stack Utility"
    )
    parser.add_argument(
        "--sweep_range_about_center_steps",
        "-s",
        default=20,
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

    return args


if __name__ == "__main__":
    main()
