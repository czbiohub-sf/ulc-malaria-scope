#!/usr/bin/env python3
# /// script
# requires-python = ">3.10"
# dependencies = [
#     "matplotlib>=3.7",
#     "numpy>=1.24",
#     "tqdm",
# ]
# ///

import argparse
from pathlib import Path
import re
import sys
from typing import List, Tuple, Union

import matplotlib
from matplotlib.image import imread
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from tqdm import tqdm

if sys.platform not in ["win32", "darwin"]:
    matplotlib.use("TkAgg")


def parse_fn(fn: Path) -> Tuple[int, int]:
    """Parse the filename for the motor position and repeat index.

    We assume the convention that the first XXX digits and the motor_position
    and the subsequent digits YYY are the 0-padded i'th images taken at that
    position
    """

    digits = re.compile(r"\d+").findall(fn.name)

    if len(digits) < 2:
        raise ValueError(
            f"Invalid filename: {fn}, expected it to follow (motor_pos, index) format"
        )

    return (int(digits[0]), int(digits[1]))


def _per_frame_energy(img: npt.NDArray, tile: int) -> npt.NDArray[np.float32]:
    """Compute tile-pooled squared-gradient energy for a single image."""
    gx = img[1:-1, 2:] - img[1:-1, :-2]
    energy = gx * gx
    del gx
    gy = img[2:, 1:-1] - img[:-2, 1:-1]
    energy += gy * gy
    del gy
    H, W = energy.shape
    Hb, Wb = H // tile, W // tile
    energy = energy[: Hb * tile, : Wb * tile]
    return (
        energy.reshape(Hb, tile, Wb, tile)
        .sum(axis=(1, 3))
        .astype(np.float32, copy=False)
    )


def stream_sharpness(
    dir: Path, tile: int
) -> Tuple[npt.NDArray[np.int64], npt.NDArray[np.float32], npt.NDArray]:
    """Stream PNGs from `dir` and accumulate the tile-pooled gradient energy cube without holding the full image stack in memory.

    Returns
    -------
    positions: (Z,) sorted unique motor positions
    energy:    (Energy, repeats, Hb, Wb) tile-pooled gradient energy, float32
    paths:     (Z, R) object array of Path entries for lazy image reload
    """
    files: List[Path] = sorted(dir.rglob("*.png"))
    if not files:
        raise ValueError(f"Found no pngs in {dir}")

    keys: List[Tuple[int, int]] = [parse_fn(f) for f in files]
    pos: List[int] = sorted({k[0] for k in keys})
    pos_to_idx = {p: i for (i, p) in enumerate(pos)}
    max_rep = max(k[1] for k in keys) + 1

    img_h, img_w = imread(files[0]).shape
    Hb, Wb = img_h // tile, img_w // tile

    energy: npt.NDArray[np.float32] = np.zeros(
        (len(pos), max_rep, Hb, Wb), dtype=np.float32
    )
    paths: npt.NDArray = np.empty((len(pos), max_rep), dtype=object)

    for path, (p, n) in tqdm(
        zip(files, keys), desc="Calculating energy gradient", total=len(files)
    ):
        zi = pos_to_idx[p]
        energy[zi, n] = _per_frame_energy(imread(path), tile)
        paths[zi, n] = path

    return np.asarray(pos), energy, paths


def view_sharpness_map(
    energy: npt.NDArray[np.float32],
    paths: npt.NDArray,
    positions: npt.NDArray[np.int64],
) -> None:
    """Convenience matplotlib plot with scrollwheel to view energy gradient v. motor pos.

    Images are lazy-loaded from disk on scroll.
    """
    mean_energy = np.mean(energy, axis=1)

    fig, (ax_img, ax_energy) = plt.subplots(1, 2)
    fig.set_facecolor("#FFFFF7")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02, wspace=0.05)
    im = ax_img.imshow(imread(paths[0, 0]), cmap="gray")
    im_energy = ax_energy.imshow(mean_energy[0], cmap="gray")
    ax_img.set_title(f"Image — motor pos {positions[0]}")
    ax_energy.set_title("Image gradient energy map")
    ax_img.axis("off")
    ax_energy.axis("off")

    im._idx = 0

    def scroll(event):
        i = im._idx + (1 if event.button == "up" else -1)
        im._idx = np.clip(i, 0, len(mean_energy) - 1)
        idx = im._idx
        im.set_data(imread(paths[idx, 0]))
        im_energy.set_data(mean_energy[idx])
        ax_img.set_title(f"Image — pos {positions[idx]}")
        fig.canvas.draw_idle()

    def step(delta: int) -> None:
        im._idx = int(np.clip(im._idx + delta, 0, len(mean_energy) - 1))
        idx = im._idx
        im.set_data(imread(paths[idx, 0]))
        im_energy.set_data(mean_energy[idx])
        ax_img.set_title(f"Image — pos {positions[idx]}")
        fig.canvas.draw_idle()

    def on_scroll(event):
        step(1 if event.button == "up" else -1)

    def on_key(event):
        if event.key in ("up", "right"):
            step(1)
        elif event.key in ("down", "left"):
            step(-1)

    fig.canvas.mpl_connect("scroll_event", on_scroll)
    fig.canvas.mpl_connect("key_press_event", on_key)

    fig.canvas.mpl_connect("scroll_event", scroll)
    plt.tight_layout()
    plt.show()


def view_traces(energy: npt.NDArray[np.float32], pos: npt.NDArray[np.int64]) -> None:
    """Plot the per-tile traces across the stack"""
    mean_energy = np.mean(energy, axis=1)
    traces = mean_energy.reshape(mean_energy.shape[0], -1)
    fig, ax = plt.subplots(figsize=(6, 5), facecolor="#FFFFF7")

    ax.set_title("Per-tile mean gradient energy trace")
    ax.plot(pos, traces, color="k", alpha=0.3)
    plt.tight_layout()
    plt.show()


def get_peak_from_parabolic_fit(
    energy: npt.NDArray[np.float32], window: int = 3
) -> npt.NDArray[np.float32]:
    """Fit a parabola to the energy gradient stack for each tile's trace and return the peak; more robust than picking the argmax.

    Algorithm is:
    1. Take the argmax
    2. Take the points from (argmax - window) to (argmax + window)
    3. Do a least-squares fit to that range
    """
    energy_mean = np.mean(energy, axis=1)
    Z = energy_mean.shape[0]
    naive_peaks = np.argmax(energy_mean, axis=0)
    bounded_range = np.clip(naive_peaks, window, Z - window - 1)

    offsets = np.arange(-window, window + 1)
    z_idx = bounded_range[..., None] + offsets

    # ax^2 + bx + c
    A = np.stack([offsets**2, offsets, np.ones_like(offsets)], axis=1).astype(
        np.float64
    )
    reorient_em = energy_mean.transpose(
        1, 2, 0
    )  # z_idx which has the +/- N has shape (Hb, Wb, Z) so we match that
    window_z_vals = np.take_along_axis(reorient_em, z_idx, axis=-1)

    # least squares fit
    coeffs = window_z_vals @ np.linalg.pinv(A).T
    alpha, beta = coeffs[..., 0], coeffs[..., 1]

    tol = 1e-9
    delta = np.where(np.abs(alpha) > tol, -0.5 * beta / alpha, 0.0)
    delta = np.clip(delta, -window, window)

    fit_peaks = bounded_range + delta

    return fit_peaks


def view_focus_gradient(
    energy: npt.NDArray[np.float32], positions: npt.NDArray[np.int64]
):
    peak_idx = get_peak_from_parabolic_fit(energy)

    fig, ax = plt.subplots(figsize=(6, 5), facecolor="#FFFFF7")
    ax.imshow(peak_idx, cmap="coolwarm", interpolation="bicubic")
    for r in range(peak_idx.shape[0]):
        for c in range(peak_idx.shape[1]):
            ax.text(
                c,
                r,
                f"{peak_idx[r, c]:.1f}",
                ha="center",
                va="center",
                fontsize=8,
                color="k",
            )
    ax.set_title("Peak focus pos per tile block (parabolic fit)")
    ax.axis("off")
    plt.tight_layout()
    plt.show()


def view_peak_maps(maps: npt.NDArray[np.float32], names: List[str]) -> None:
    """Scrollable viewer over per-stack peak position maps; color scale autoscales per map."""
    fig, ax = plt.subplots(figsize=(6, 5), facecolor="#FFFFF7")
    fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05)
    im = ax.imshow(maps[0], cmap="coolwarm", interpolation="bicubic")
    ax.set_title(f"{names[0]}  (1/{len(names)})")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="peak Z idx")

    im._idx = 0

    def step(delta: int) -> None:
        im._idx = int(np.clip(im._idx + delta, 0, len(maps) - 1))
        im.set_data(maps[im._idx])
        im.set_clim(float(maps[im._idx].min()), float(maps[im._idx].max()))
        ax.set_title(f"{names[im._idx]}  ({im._idx + 1}/{len(names)})")
        fig.canvas.draw_idle()

    def on_scroll(event):
        step(1 if event.button == "up" else -1)

    def on_key(event):
        if event.key in ("up", "right"):
            step(1)
        elif event.key in ("down", "left"):
            step(-1)

    fig.canvas.mpl_connect("scroll_event", on_scroll)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.tight_layout()
    plt.show()


def view_mean_peak_map(maps: npt.NDArray[np.float32]) -> None:
    """Display the per-tile peak Z idx averaged across all stacks."""
    mean_map = maps.mean(axis=0)

    fig, ax = plt.subplots(figsize=(6, 5), facecolor="#FFFFF7")
    ax.imshow(mean_map, cmap="coolwarm", interpolation="bicubic")
    for r in range(mean_map.shape[0]):
        for c in range(mean_map.shape[1]):
            ax.text(
                c,
                r,
                f"{mean_map[r, c]:.1f}",
                ha="center",
                va="center",
                fontsize=8,
                color="k",
            )
    ax.set_title(f"Mean peak Z idx per tile  (N={maps.shape[0]} stacks)")
    ax.axis("off")
    plt.tight_layout()
    plt.show()


def analyze_stack(dir: Path, tile: int) -> npt.NDArray[np.float32]:
    """Return the peak idx position per-tile for the given stack"""
    _pos, energy, _paths = stream_sharpness(dir, tile)
    return get_peak_from_parabolic_fit(energy)


def analyze_multiple_stacks(
    dir: Union[Path, List[Path]], tile: int
) -> Tuple[List[str], npt.NDArray[np.float32]]:
    """Given a directory, find all the stacks within and calculate the peak position within each tile block.
    If explicitly given a list of Paths, run the same analysis on those stacks.
    Returns the stack names alongside an (N, Hb, Wb) array of per-tile peak positions.
    """

    if isinstance(dir, List):
        stack_dirs = List(dir)
    else:
        stack_dirs = sorted(
            d
            for d in dir.iterdir()
            if d.is_dir() and next(d.glob("*.png"), None) is not None
        )

    if not stack_dirs:
        raise ValueError(f"Found no stack subdirectories in {dir}")

    names = [d.name for d in stack_dirs]
    maps = np.stack(
        [analyze_stack(d, tile) for d in tqdm(stack_dirs, desc="Analyzing stacks")]
    )
    return names, maps


def fit_plane(peak_idx_map: npt.NDArray) -> Tuple[npt.NDArray, npt.NDArray[np.float32]]:
    Hb, Wb = peak_idx_map.shape[-2:]
    yy, xx = np.meshgrid(
        np.arange(Hb), np.arange(Wb), indexing="ij"
    )  # matrix convention
    A = np.stack([xx.ravel(), yy.ravel(), np.ones(Hb * Wb)], axis=1).astype(np.float64)

    # Account for single stack and multi-stack case
    if peak_idx_map.ndim == 2:
        B = peak_idx_map.ravel().astype(np.float64)  # Single stack (m,)
    else:
        B = peak_idx_map.reshape(peak_idx_map.shape[0], -1).T.astype(
            np.float64
        )  # Multi-stack, convert to each col is each stack's peak-z

    coef, *_ = np.linalg.lstsq(A, B, rcond=None)
    plane = (A @ coef).T.reshape(peak_idx_map.shape).astype(np.float32)

    return coef, plane


def print_plane_diag(maps: npt.NDArray) -> None:
    """Convenience function to print plane stats"""
    coeffs, plane = fit_plane(maps)
    Hb, Wb = maps.shape[-2:]

    if coeffs.ndim == 2:
        slope_mean = coeffs[:2].mean(axis=1)
        slope_std = coeffs[:2].std(axis=1, ddof=1)
    else:
        slope_mean = coeffs[:2]
        slope_std = [0, 0]

    extents = np.array([Wb - 1, Hb - 1], dtype=np.float64)
    total_dz = slope_mean * extents
    total_dz_SD = slope_std * extents

    print(f"Grid size (h, w): ({Hb},{Wb})")
    print(
        f"slope per tile:   ({slope_mean[0]:+.3f}, {slope_mean[1]:+.3f})   Motor steps / tile"
    )
    print(f"slope std:        (±{slope_std[0]:.3f}, ±{slope_std[1]:.3f})")
    print(
        f"total dZ (x, y):  ({total_dz[0]:+.2f}, {total_dz[1]:+.2f})   Motor steps between outermost tile centers"
    )
    print(f"total dZ SD:      (±{total_dz_SD[0]:.2f}, ±{total_dz_SD[1]:.2f})")


def run_flatness_check(stack_dir: Path, tile: int = 128) -> None:
    """Compute and display flatness diagnostics for a single z-stack directory.

    Prints plane-fit summary to stdout, then opens (in sequence) the sharpness
    map viewer and the per-tile focus gradient plot.
    """
    pos, energy, paths = stream_sharpness(stack_dir, tile)
    peak_idx = get_peak_from_parabolic_fit(energy)
    print_plane_diag(peak_idx)
    view_focus_gradient(energy, pos)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage flatness measurement utility - point it to a z-stack folder (or a folder containing multiple z-stacks)"
    )
    p.add_argument("dir", type=Path, help="Path to z-stack directory")
    p.add_argument(
        "--tile", type=int, default=128, help="tile size in pixels (default: 128)"
    )
    return p.parse_args()


def main():
    args = parse_args()

    # check whether user passed in a single stack or a directory of stacks
    if next(args.dir.glob("*.png"), None) is not None:
        pos, energy, paths = stream_sharpness(args.dir, args.tile)
        peak_idx = get_peak_from_parabolic_fit(energy)

        print_plane_diag(peak_idx)
        view_traces(energy, pos)

        # This graph with the interactive energy map isn't particularly useful on-scope, but it is
        # a fun widget toy to play with on your laptop
        if sys.platform in ["win32", "darwin"]:
            view_sharpness_map(energy, paths, pos)

        view_focus_gradient(energy, pos)
    else:
        names, maps = analyze_multiple_stacks(args.dir, args.tile)
        print_plane_diag(maps)

        view_peak_maps(maps, names)
        view_mean_peak_map(maps)

if __name__ == "__main__":
    main()
