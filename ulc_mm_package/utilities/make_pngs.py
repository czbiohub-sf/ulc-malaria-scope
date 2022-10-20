import os
import zarr
import cv2
import typer
from tqdm import tqdm

def main(path: str=typer.Option("", help="Path to the zarr .zip file."), num_imgs: int=typer.Option(-1, help="Number of images to save (default: all)")):
    try:
        zf = zarr.open(path)
    except:
        typer.echo(f"Unable to open the zarr file at: {path}")
    
    typer.echo("Successfully opened file, starting tiff generation.")
    top_dir = os.path.dirname(path)
    typer.echo(top_dir)    
    output_dir = os.path.join(top_dir, "pngs")
    try:
        os.mkdir(output_dir)
    except:
        pass

    num_imgs = num_imgs if num_imgs != -1 else len(zf)
    for i in tqdm(range(num_imgs)):
        img = zf[i][:]
        cv2.imwrite(f"{output_dir}/{i}.png", img)

if __name__ == "__main__":
    typer.run(main)