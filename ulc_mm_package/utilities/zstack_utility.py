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
from typing import Callable, Optional

from ulc_mm_package.hardware.camera import AVTCamera
from ulc_mm_package.hardware.hardware_constants import MIN_PRESSURE_DIFF
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT
from ulc_mm_package.hardware.scope_routines import CellFinder, NoCellsFound
from ulc_mm_package.image_processing.autobrightness import (
    Autobrightness,
    BrightnessTargetNotAchieved,
    BrightnessCriticallyLow,
)
from ulc_mm_package.image_processing.flow_control import FlowController
import ulc_mm_package.image_processing.processing_constants as processing_constants
from ulc_mm_package.scope_constants import CAMERA_SELECTION, DOWNSAMPLE_FACTOR
from ulc_mm_package.image_processing.focus_metrics import downsample_image
from ulc_mm_package.scope_constants import SSD_DIR, SSD_NAME
from ulc_mm_package.utilities.stage_grad import run_flatness_check

PNEUMATIC_PULL_TIME_S = 7
LED_BRIGHTNESS_PERC = 0.15
MIN_ACCEPTABLE_MOTOR_POS = 200
MAX_ACCEPTABLE_MOTOR_POS = 600
FLATNESS_TILE = 128

_BG = "#ffffff"
_BG_MID = "#f5f5f5"
_BG_LIGHT = "#e8e8e8"
_FG = "#1a1a1a"
_FG_DIM = "#888888"
_BORDER = "#d0d0d0"

logger = logging.getLogger("focus_stack")
if not logger.hasHandlers():
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Keep third-party loggers quiet
logging.getLogger().setLevel(logging.WARNING)
for _lib in (
    "PIL",
    "PIL.PngImagePlugin",
    "PIL.Image",
    "matplotlib",
    "matplotlib.font_manager",
):
    logging.getLogger(_lib).setLevel(logging.WARNING)


def init_hardware():
    logger.info("Initializing hardware...")
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
    autobrightness: Optional[Autobrightness] = None,
    autobrightness_fn: Optional[Callable] = None,
    save_path: Optional[Path] = None,
    collect_images: bool = False,
    run_brightness: bool = False,
    status_label: Optional[tk.Label] = None,
) -> Optional[list]:
    """Sweep motor range, feed images to cell_finder. Optionally save/collect."""
    cell_finder.reset()
    led.turnOn()
    led.setDutyCycle(LED_BRIGHTNESS_PERC)
    total_steps = len(sweep_range)
    collected: Optional[list] = [] if collect_images else None

    if save_path:
        save_path.mkdir(parents=True, exist_ok=True)

    for step, pos in enumerate(sweep_range, start=1):
        try:
            motor.move_abs(pos)
            if step == 1 and run_brightness:
                autobrightness_fn(autobrightness)  # type:ignore
                if status_label:
                    status_label.config(text="Sweep in progress...")
            if save_path:
                for i in range(n_imgs_per_step):
                    img, _ = next(camera.yieldImages())
                    cv2.imwrite(str(save_path / f"motor_pos_{pos}_n{i:03d}.png"), img)
                    sleep(0.1)
            img, _ = next(camera.yieldImages())
            cell_finder.add_image(pos, img)
            if collect_images:
                collected.append((pos, img))  # type:ignore
            progress_callback(step, total_steps)
            image_callback(img)
            motor_label_callback(pos)
            sleep(0.05)
        except Exception as e:
            logger.error(f"Error at motor position {pos}: {e}")
            continue

    led.turnOff()
    return collected if collect_images else None


def compress_saved_images(
    save_path: Path, remove_original: bool = True
) -> Optional[Path]:
    """Compress saved images with pigz, fallback gzip."""
    if not save_path.exists():
        return None

    archive_path = save_path.parent / f"{save_path.name}.tar.gz"
    try:
        try:
            subprocess.run(
                [
                    "tar",
                    "-I",
                    "pigz -9",
                    "-cf",
                    str(archive_path),
                    "-C",
                    str(save_path.parent),
                    save_path.name,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            subprocess.run(
                [
                    "tar",
                    "-czf",
                    str(archive_path),
                    "-C",
                    str(save_path.parent),
                    save_path.name,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

        if not archive_path.exists():
            logger.error("Archive not found after compression")
            return None
        if remove_original:
            try:
                shutil.rmtree(save_path)
            except Exception as e:
                logger.warning(f"Failed to remove original folder: {e}")
        return archive_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Compression failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return None


def determine_sweep_range(motor):
    if motor.pos > motor.max_pos / 2:
        return range(motor.max_pos, -1, -10)
    return range(0, motor.max_pos + 1, 10)


def pressure_check(pm: PneumaticModule) -> bool:
    initial, _ = pm.getPressure()
    pm.setDutyCycle(pm.getMinDutyCycle())
    sleep(0.5)
    post, _ = pm.getPressureMaxReadAttempts(max_attempts=10)
    pm.setDutyCycle(pm.getMaxDutyCycle())
    diff = initial - post
    logger.info(f"Pressure diff: {diff:.2f} mBar")
    return diff >= MIN_PRESSURE_DIFF


def manual_review(images_with_positions, on_select):
    """Slider-based review for manual cell position selection."""
    if not images_with_positions:
        messagebox.showinfo("No Images", "No images available.")
        return

    win = tk.Toplevel()
    win.title("Manual Cell Selection")
    win.configure(bg=_BG)
    win.geometry("800x480")
    win.grid_rowconfigure(1, weight=1)
    win.grid_columnconfigure(0, weight=1)

    tk.Label(
        win,
        text="No cells found. Select a position with cells.",
        font=("Helvetica", 11),
        wraplength=780,
        bg=_BG,
        fg=_FG,
    ).grid(row=0, column=0, pady=4, sticky="n")

    img_label = tk.Label(win, bg="black")
    img_label.grid(row=1, column=0, sticky="nsew")

    pos_label = tk.Label(win, text="Motor: 0", font=("Helvetica", 10), bg=_BG, fg=_FG)
    pos_label.grid(row=2, column=0, padx=8, pady=2, sticky="w")

    sf = tk.Frame(win, bg=_BG)
    sf.grid(row=3, column=0, pady=2, sticky="ew")
    sf.grid_columnconfigure(0, weight=1)

    idx = tk.IntVar(value=0)
    last = len(images_with_positions) - 1

    def refresh():
        i = idx.get()
        if not (0 <= i <= last):
            return
        mpos, img = images_with_positions[i]
        pos_label.config(text=f"Motor: {mpos}")
        pil = Image.fromarray(img)
        w, h = pil.size
        cw = max(img_label.winfo_width(), 100)
        ch = max(img_label.winfo_height(), 100)
        s = min(cw / w, ch / h)
        nw, nh = max(int(w * s), 1), max(int(h * s), 1)
        pil = pil.resize((nw, nh), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(pil)
        img_label.config(image=tk_img)
        img_label.image = tk_img

    ttk.Scale(
        sf,
        from_=0,
        to=last,
        orient="horizontal",
        variable=idx,
        command=lambda _: refresh(),
    ).grid(row=0, column=0, sticky="ew", padx=8)

    bf = tk.Frame(win, bg=_BG)
    bf.grid(row=4, column=0, pady=6, sticky="s")

    def sweep_here():
        mpos, _ = images_with_positions[idx.get()]
        win.destroy()
        on_select(mpos)

    tk.Button(
        bf,
        text="Sweep Here",
        font=("Helvetica", 11),
        relief="solid",
        bd=1,
        command=sweep_here,
        bg=_FG,
        fg=_BG,
        padx=10,
        pady=6,
    ).pack(side=tk.LEFT, padx=8)
    tk.Button(
        bf,
        text="Cancel",
        font=("Helvetica", 11),
        relief="solid",
        bd=1,
        command=win.destroy,
        bg=_BG,
        fg=_FG,
        padx=10,
        pady=6,
    ).pack(side=tk.LEFT, padx=8)

    def on_key(event):
        i = idx.get()
        if event.keysym == "Left" and i > 0:
            idx.set(i - 1)
            refresh()
        elif event.keysym == "Right" and i < last:
            idx.set(i + 1)
            refresh()
        elif event.keysym == "Return":
            sweep_here()
        elif event.keysym == "Escape":
            win.destroy()

    win.bind("<Key>", on_key)
    win.focus_set()
    refresh()
    win.transient()
    win.grab_set()
    win.wait_window()


def main():
    args = parse_args()
    n_steps = args.sweep_range_about_center_steps
    imgs_per_step = args.imgs_per_step
    target_flowrate = args.flowrate
    device_name = socket.gethostname()

    logger.info(
        f"n_steps={n_steps}  imgs_per_step={imgs_per_step}  "
        f"flowrate={target_flowrate}  device={device_name}"
    )

    camera, pm, motor, led = init_hardware()
    cell_finder = CellFinder()
    ab = Autobrightness(led)
    flow_control = FlowController(pm)
    img_w, img_h = CAMERA_SELECTION.img_dims().width, CAMERA_SELECTION.img_dims().height

    # Window: top bar (row 0), image (row 1, expands), bottom bar (row 2)
    root = tk.Tk()
    root.title("Focus Stack Utility")
    root.configure(bg=_BG)
    root.geometry("800x480")
    root.minsize(640, 400)
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Top bar — two rows to fit 800px width
    top = tk.Frame(root, bg=_BG_MID, padx=6, pady=3)
    top.grid(row=0, column=0, sticky="ew")
    top.grid_columnconfigure(0, weight=1)

    # Row 0: status + buttons
    top_r0 = tk.Frame(top, bg=_BG_MID)
    top_r0.grid(row=0, column=0, sticky="ew")
    top_r0.grid_columnconfigure(0, weight=1)

    status_label = tk.Label(
        top_r0,
        text="Load a flow cell (with blood) and close the lid.",
        font=("Helvetica", 11, "bold"),
        bg=_BG_MID,
        fg=_FG,
        anchor="w",
    )
    status_label.grid(row=0, column=0, sticky="ew")

    btn_box = tk.Frame(top_r0, bg=_BG_MID)
    btn_box.grid(row=0, column=1, sticky="e")

    # Row 1: params
    tk.Label(
        top,
        text=f"+/-{n_steps} steps | {imgs_per_step} img/step | {target_flowrate} uL/min | {device_name}",
        font=("Helvetica", 8),
        bg=_BG_MID,
        fg=_FG_DIM,
        anchor="w",
    ).grid(row=1, column=0, sticky="w")

    # Image
    image_canvas = tk.Label(root, bg="black")
    image_canvas.grid(row=1, column=0, sticky="nsew")

    # Bottom bar
    bot = tk.Frame(root, bg=_BG_MID, padx=6, pady=3)
    bot.grid(row=2, column=0, sticky="ew")
    bot.grid_columnconfigure(1, weight=1)

    motor_label = tk.Label(
        bot,
        text="Motor: ---",
        font=("Courier", 9),
        bg=_BG_MID,
        fg=_FG,
        width=14,
        anchor="w",
    )
    motor_label.grid(row=0, column=0, sticky="w", padx=(0, 4))

    progress = ttk.Progressbar(bot, orient="horizontal", mode="determinate")
    progress.grid(row=0, column=1, sticky="ew", padx=2)

    flatness_label = tk.Label(
        bot,
        text="",
        font=("Courier", 9),
        bg=_BG_MID,
        fg=_FG_DIM,
        anchor="e",
    )
    flatness_label.grid(row=0, column=2, sticky="e", padx=(4, 0))

    sweep_count_label = tk.Label(
        bot,
        text="",
        font=("Helvetica", 9),
        bg=_BG_MID,
        fg=_FG_DIM,
        anchor="e",
    )
    sweep_count_label.grid(row=0, column=3, sticky="e", padx=(12, 0))

    # Callbacks
    def update_progress(cur, total):
        progress["maximum"] = total
        progress["value"] = cur
        root.update_idletasks()

    def update_image(img):
        pil = Image.fromarray(img)
        cw = max(image_canvas.winfo_width(), 100)
        ch = max(image_canvas.winfo_height(), 100)
        s = min(cw / img_w, ch / img_h)
        nw, nh = max(int(img_w * s), 1), max(int(img_h * s), 1)
        pil = pil.resize((nw, nh), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(pil)
        image_canvas.config(image=tk_img)
        image_canvas.image = tk_img

    def update_motor_label(pos):
        motor_label.config(text=f"Motor: {pos:>5d}")

    def set_flow(fc: FlowController, target: float):
        status_label.config(text="Setting flow rate...")
        root.update()
        fc.set_target_flowrate(target)
        fc.set_alpha(processing_constants.FLOW_CONTROL_EWMA_ALPHA * 2)
        fc.pneumatic_module.min_step_size *= 2  # type:ignore
        can_move: Optional[bool] = None
        prev = True
        while True:
            img, ts = next(camera.yieldImages())
            img = downsample_image(img, DOWNSAMPLE_FACTOR)
            prev = can_move if can_move is not None else prev
            _, err, can_move = fc.control_flow(img, ts)
            if prev and not can_move:
                fc.pneumatic_module.min_step_size = (
                    fc.pneumatic_module.default_min_step_size
                )  # type:ignore
                logger.warning("Syringe at end of travel.")
                return
            if err is not None and err == 0:
                return

    def set_brightness(autobrightness: Autobrightness):
        status_label.config(text="Adjusting brightness...")
        root.update()
        done = False
        while not done:
            img, _ = next(camera.yieldImages())
            try:
                done = autobrightness.runAutobrightness(img)
            except BrightnessTargetNotAchieved:
                autobrightness.reset()
                return
            except BrightnessCriticallyLow:
                autobrightness.reset()
                return

    state = {"last_stack": None, "sweep_count": 0}

    def check_flatness():
        stack = state["last_stack"]
        if stack is None or not stack.exists():
            messagebox.showinfo("No stack", "Acquire a stack first.")
            return
        status_label.config(text="Computing flatness...")
        root.update()
        try:
            result = run_flatness_check(stack, FLATNESS_TILE)
            flatness_label.config(text=f"Flatness: {result}", fg=_FG)
            status_label.config(text="Flatness check complete.")
        except Exception as e:
            logger.error(f"Flatness check failed: {e}")
            flatness_label.config(text="Flatness: ERROR", fg=_FG)
            status_label.config(text="Flatness check failed.")

    def start_sweep(n_steps: int = 20, imgs_per_step: int = 2):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_path = Path(SSD_DIR) / SSD_NAME / f"zstack_{device_name}_{now}"

        status_label.config(text="Checking flow cell...")
        root.update()

        if target_flowrate > 0:
            if not pressure_check(pm):
                messagebox.showinfo(
                    "Error", "Ensure CAP module is on and flow cell is loaded."
                )
                status_label.config(
                    text="Load a flow cell (with blood) and close the lid."
                )
                return
            status_label.config(text="Pulling RBCs into field of view...")
            root.update()
            pm.setDutyCycle(pm.getMinDutyCycle())
            sleep(PNEUMATIC_PULL_TIME_S)
            pm.setDutyCycle(pm.getMaxDutyCycle())

        set_brightness(ab)
        progress["value"] = 0

        # Coarse sweep
        status_label.config(text="Finding cells...")
        root.update()
        sr = determine_sweep_range(motor)
        collected = sweep(
            camera,
            motor,
            led,
            sr,
            cell_finder,
            update_progress,
            update_image,
            update_motor_label,
            n_imgs_per_step=imgs_per_step,
            collect_images=True,
        )

        try:
            result = cell_finder.get_cells_found_position()
            status_label.config(text="Cells found!")
            if target_flowrate > 0:
                set_flow(flow_control, target_flowrate)
        except NoCellsFound:
            result = None

        # Re-sweep post-flow
        status_label.config(text="CellFinder post-flow...")
        root.update()
        collected = sweep(
            camera,
            motor,
            led,
            sr,
            cell_finder,
            update_progress,
            update_image,
            update_motor_label,
            n_imgs_per_step=imgs_per_step,
            collect_images=True,
        )

        try:
            result = cell_finder.get_cells_found_position()
            status_label.config(text="Cells found!")
        except NoCellsFound:
            result = None

        def _fine_sweep(center: int):
            if target_flowrate > 0:
                set_flow(flow_control, target_flowrate)
            status_label.config(text=f"Fine sweep around {center}...")
            root.update()
            sweep(
                camera,
                motor,
                led,
                range(center - n_steps, center + n_steps + 1, 1),
                cell_finder,
                update_progress,
                update_image,
                update_motor_label,
                n_imgs_per_step=imgs_per_step,
                save_path=save_path,
                run_brightness=True,
                autobrightness=ab,
                autobrightness_fn=set_brightness,
                status_label=status_label,
            )

        if result is None:
            manual_review(collected, _fine_sweep)
        elif (result - n_steps) > 0 and (result + n_steps) < motor.max_pos:
            _fine_sweep(result)

        pm.setDutyCycle(pm.getMaxDutyCycle())
        state["sweep_count"] += 1
        sweep_count_label.config(text=f"Stacks: {state['sweep_count']}")

        if save_path.exists():
            state["last_stack"] = save_path
            flatness_btn.config(state="normal")
            status_label.config(text="Done. Check Flatness or sweep again.")
        else:
            status_label.config(text="Ready. Start Sweep (Space).")

    def quit_app():
        pm.setDutyCycle(pm.getMaxDutyCycle())
        led.turnOff()
        camera.deactivateCamera()
        led.turnOff()
        root.destroy()

    # Buttons
    _bkw = dict(
        font=("Helvetica", 11),
        padx=10,
        pady=6,
        bd=1,
        cursor="hand2",
        highlightthickness=0,
        relief="solid",
    )
    sweep_fn = partial(start_sweep, n_steps=n_steps, imgs_per_step=imgs_per_step)

    tk.Button(
        btn_box,
        text="Start Sweep",
        command=sweep_fn,
        bg=_FG,
        fg=_BG,
        activebackground="#444444",
        activeforeground=_BG,
        **_bkw,
    ).pack(side=tk.LEFT, padx=4)

    flatness_btn = tk.Button(
        btn_box,
        text="Check Flatness",
        command=check_flatness,
        state="disabled",
        bg=_BG,
        fg=_FG,
        activebackground=_BG_LIGHT,
        disabledforeground=_BORDER,
        **_bkw,
    )
    flatness_btn.pack(side=tk.LEFT, padx=4)

    tk.Button(
        btn_box,
        text="Quit",
        command=quit_app,
        bg=_BG,
        fg=_FG,
        activebackground=_BG_LIGHT,
        **_bkw,
    ).pack(side=tk.LEFT, padx=4)

    root.mainloop()


def parse_args():
    parser = argparse.ArgumentParser(description="Focus Stack / Z-stack Utility")
    parser.add_argument(
        "--sweep_range_about_center_steps",
        "-s",
        default=30,
        type=int,
        help="Steps +/- about cell position (default: 15)",
    )
    parser.add_argument(
        "--imgs_per_step",
        "-i",
        default=3,
        type=int,
        help="Images per motor position (default: 5)",
    )
    flowrate_options = [f.value for f in processing_constants.FLOWRATE] + [0.0]
    parser.add_argument(
        "--flowrate",
        "-f",
        default=processing_constants.FLOWRATE.MEDIUM.value,
        type=float,
        choices=flowrate_options,
        help="Target flowrate uL/min",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
