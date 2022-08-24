from datetime import datetime
import os
import cv2
import zarr
import numpy as np
import typer
from tqdm import tqdm
import pandas as pd

from ulc_mm_package.image_processing.background_subtraction import MedianBGSubtraction

EXTERNAL_DIR = "experiments/"

def loader(img_name):
    if img_name[-5:] == ".tiff":
        return cv2.imread(img_name, 0)
    elif img_name[-4:] == ".npy":
        return np.load(img_name)
    return None

def get_timestamp(timestamp_str):
        return datetime.strptime(timestamp_str, "%Y-%m-%d-%H%M%S_%f")

def get_zarr_image_size(zarr_store):
    return zarr_store[0].shape

def open_zarr(folder):
    """Returns the .zip file (i.e the Zarr file) in the given folder"""
    file = [os.path.join(folder, x) for x in sorted(os.listdir(folder)) if ".zip" in x[-4:]][0]
    return zarr.open(file)

def get_csv_file(folder):
    """Returns the .csv file in the given folder"""
    file = [os.path.join(folder, x) for x in sorted(os.listdir(folder)) if ".csv" in x[-4:]][0]
    return file

def get_fps_from_csv_timestamps(csv_file):
    """Reads a csv file and determines what the average framerate was based on timestamps"""
    df = pd.read_csv(csv_file)
    start = get_timestamp(df['timestamp'][0])
    end = get_timestamp(df['timestamp'][len(df['timestamp'])-1])
    tdiff = (end - start).total_seconds()

    return len(df['timestamp'])/tdiff

def get_zarr_metadata(zarr_store):
    all_metadata = {}
    for key in zarr_store[0].attrs.keys():
        all_metadata[key] = [0]*len(zarr_store)
    for i in tqdm(range(len(zarr_store))):
        for key in zarr_store[0].attrs.keys():
            all_metadata[key][i] = zarr_store[i].attrs[key]
    return all_metadata

def zarr_image_generator(zarr_store):
    for i in range(len(zarr_store)):
        yield zarr_store[i][:]

def main(path: str=typer.Option("", help="Path of the top-evel folder containing subfolders of experiments. Each subfolder should have .npy files."), bg_sub: bool=typer.Option(False, "--bg-sub", help="Whether to perform background subtraction on the images")):
    if path == "":
        typer.echo(f"{'='*20}")
        typer.echo(
            "This utility converts files within a folder to a .mp4 video. You will be prompted to pick a top-level directory (TLD). All subfolders within that TLD which have `.npy` or '.tiff' files will be converted to have an .mp4 file."
        )
        typer.echo(f"{'='*20}\n")

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
        path = dir
        subfolders = sorted(
            os.path.join(dir, x)
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
    else:
        try:
            if os.path.isdir(path):
                subfolders = [os.path.join(path, folder) for folder in sorted(os.listdir(path)) if os.path.isdir(os.path.join(path, folder))]
            else:
                raise
        except:
            typer.echo(f"\n{'='*20}")
            typer.echo("Bad path passed. Exiting...")
            typer.echo(f"{'='*20}\n")
            quit()

    try:
        output_dir = os.path.join(path, "Output")
        video_dir = os.path.join(output_dir, "Videos")
        for dir in [output_dir, video_dir]:
            os.mkdir(dir)
    except:
        pass

    for folder in tqdm(subfolders):
        try:
            print("Opening the Zarr file...")
            zstore = open_zarr(folder)
        except:
            typer.echo(f"\n{'='*20}")
            typer.echo(f"Error finding/opening the Zarr zipstore in folder {folder}. Skipping and continuing...")
            typer.echo(f"{'='*20}\n")
            continue
        try:
            csv_path = get_csv_file(folder)
            fps = int(get_fps_from_csv_timestamps(csv_path))
            print(f"Video at average framerate of: {fps}")
        except Exception as e:
            print("Error parsing timestamps and setting fps. Defaulting to fps=30\n")
            print(e)
            fps = 30

        width, height = get_zarr_image_size(zstore)
        file_root = folder[folder.rfind("/")+1:]
        filename = file_root+"_vid.mp4"
        if bg_sub:
            filename = file_root + "_bgsubbed_vid.mp4"
        output_path = os.path.join(video_dir, filename)

        typer.echo("Generating video...")
        writer = cv2.VideoWriter(
            f"{output_path}",
            fourcc=cv2.VideoWriter_fourcc(*"mp4v"),
            fps=fps,
            frameSize=(height, width),
            isColor=False,
        )

        # Initialize BG subtraction
        bg_sub_set = False
        if bg_sub:
            if len(zstore) > 200:
                h, w = zstore[0][:].shape
                mbg = MedianBGSubtraction(h, w, 200)
                for i in range(200):
                    mbg.addImage(zstore[i][:])
                bg = mbg.getMedian()
                max_val = 215
                bg_sub_set = True
            else:
                print("Can't BG-sub, fewer than 200 images in the dataset (and the MedianBGSubtraction uses a 200-frame window by default)")

        img_gen = zarr_image_generator(zstore)
        for i, img in enumerate(tqdm(range(len(zstore)))):
            img = next(img_gen)
            if bg_sub and bg_sub_set:
                img = np.asarray(np.clip(img + (max_val-bg), 0, 255), dtype=np.uint8)
            if img is not None:
                writer.write(img)
        writer.release()

if __name__ == "__main__":
    typer.run(main)
