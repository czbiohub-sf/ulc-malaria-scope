import time
import datetime
import os
import cv2
import numpy as np
import typer
from tqdm import tqdm

EXTERNAL_DIR = "../experiments"


def loader(img_name):
    if ".tiff" in img_name:
        return cv2.imread(img_name, 0)
    elif ".npy" in img_name:
        return np.load(img_name)

def main():
    typer.echo(f"{'='*20}")
    typer.echo(
        "This utility converts files within a folder to a .mp4 video. You will be prompted to pick a top-level directory (TLD). All subfolders within that TLD which have `.npy` or '.tiff' files will be converted to have an .mp4 file."
    )
    typer.echo(f"{'='*20}\n")

    def get_time_stamp(filename):
        filename = filename[filename.rfind("/") + 1 :]
        time_str = filename[filename.rfind("-") + 1 : filename.find(".") - 5]
        time_str = time_str[:6]
        time_vals = datetime.datetime(*time.strptime(time_str, "%H%M%S")[:6])
        return time_vals

    dirs = [os.path.join(EXTERNAL_DIR, x) for x in sorted(os.listdir(EXTERNAL_DIR)) if os.path.isdir(os.path.join(EXTERNAL_DIR, x))]
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
        try:
            end_val = dir.rfind('/', dir.rfind('/'))
            cleaned = dir[end_val:]
        except:
            cleaned = dir
        
        typer.echo(f"{i}.\t{cleaned}/")

    for folder in tqdm(subfolders):
        files = [
            os.path.join(folder, x) for x in sorted(os.listdir(folder)) if ".npy" in x or '.tiff' in x
        ]
        try:
            start, end = get_time_stamp(files[0]), get_time_stamp(files[-1])
            runtime_s = (end - start).total_seconds()
            fps = int(len(files) / runtime_s)
        except:
            fps = 10

        width, height = loader(files[0]).shape
        writer = cv2.VideoWriter(
            f"{folder}_vid.mp4",
            fourcc=cv2.VideoWriter_fourcc(*"mp4v"),
            fps=fps,
            frameSize=(height, width),
            isColor=False,
        )

        for img in tqdm(files):
            img = loader(img)
            writer.write(img)
        writer.release()


if __name__ == "__main__":
    typer.run(main)
