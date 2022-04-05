# Instructions
SSHing large folders/files from the RPi to your local machine is slow. You can copy folders of `.npy` files here from the SSD over USB3.0. 

The `utilities/make_video.py` CLI will look in this folder for sub-folders to make videos. The CLI will prompt you to pick a top-level folder for which it will videos. All sub-folders within the top-level-folder you pick will have a video made for it.

## Steps
1. Drag-and-drop files from the SSD (over USB 3.0) into this folder here.
2. Run `python3 utilities/make_video.py`
3. Select the desired folder with the CLI. All the subfolders within that folder which have `.npy` files will have `.mp4` made for them.