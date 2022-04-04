import time
import datetime
import os
import cv2
import numpy as np
import typer
from tqdm import tqdm

EXTERNAL_DIR = "../experiments"


def main():
    typer.echo(
        "This utility converts files within a folder to a .mp4 video. You will be prompted to pick a top-level directory (TLD). All subfolders within that TLD which have `.npy` files will be converted to have an .mp4 file."
    )

    def get_time_stamp(filename):
        filename = filename[filename.rfind("/") + 1 :]
        time_str = filename[filename.rfind("-") + 1 : filename.find(".") - 5]
        time_str = time_str[:6]
        time_vals = datetime.datetime(*time.strptime(time_str, "%H%M%S")[:6])
        return time_vals

    dirs = [os.path.join(EXTERNAL_DIR, x) for x in sorted(os.listdir(EXTERNAL_DIR))]
    typer.echo("The following folders were found: ")
    for i, dir in enumerate(dirs):
        typer.echo(f"{i}.\t{dir}/")
    num = -1
    while num not in list(range(len(dirs))):
        try:
            num = int(
                typer.prompt(
                    "Pick which directory you would like to view (enter the index number)"
                )
            )
        except:
            pass
    dir = dirs[num]

    subfolders = sorted(
        os.path.join(EXTERNAL_DIR, dir, x)
        for x in os.listdir(dir)
        if os.path.isdir(os.path.join(dir, x))
    )
    typer.echo(f"\nThe following sub-folders were found\n{'='*10}")
    for i, dir in enumerate(subfolders):
        typer.echo(f"{i}.\t{dir}/")

    for folder in tqdm(subfolders):
        files = [
            os.path.join(folder, x) for x in sorted(os.listdir(folder)) if ".npy" in x
        ]
        start, end = get_time_stamp(files[0]), get_time_stamp(files[-1])
        runtime_s = (end - start).total_seconds()
        fps = int(len(files) / runtime_s)

        width, height = np.load(files[0]).shape
        filepath = os.path.join(folder, f"{folder}_video.mp4")
        writer = cv2.VideoWriter(
            f"{folder}_vid.mp4",
            fourcc=cv2.VideoWriter_fourcc(*"mp4v"),
            fps=fps,
            frameSize=(height, width),
            isColor=False,
        )

        for img in tqdm(files):
            img = np.load(img)
            writer.write(img)
        writer.release()


if __name__ == "__main__":
    typer.run(main)
