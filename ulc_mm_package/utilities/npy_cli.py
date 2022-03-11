"""
A basic terminal UI for picking a folder of .npy (numpy array) files,
picking a viewing framerate, and displaying them as a video.
"""

import os
from time import perf_counter
import typer
import numpy as np
import cv2

import typer_utils

EXTERNAL_DIR = "/media/pi/T7/"

def time_file_open(img_path):
    start = perf_counter()
    np.load(img_path)
    return perf_counter() - start

def main():
    files = typer_utils.choose_dir_get_files(EXTERNAL_DIR)
    time_to_open = time_file_open(files[0])

    fps_choices = [15, 30, 60]
    fps = -1
    typer.echo(f"Pick a viewing framerate ({fps_choices}): ")
    for val in fps_choices:
        typer.echo(f"@{val}fps video will run for {len(files) / val + len(files)*time_to_open:.2f}s")
    while fps < 0:
        try:
            fps = int(typer.prompt(f"Type in a desired viewing fps (e.g {fps_choices})"))
        except:
            pass
    
    with typer.progressbar(range(len(files))) as progress:
        for i in progress:
            file = files[i]
            if file[-4:] == ".npy":
                img = np.load(file).astype(np.uint8)
                cv2.imshow('Images', img)
                cv2.waitKey(int(1 / fps * 1000))
    

if __name__ == "__main__":
    typer.run(main)