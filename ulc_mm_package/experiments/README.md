# Instructions
Since SSHing large folders/files from the RPi to your local machine is slow, you can place folders of `.npy` files here. 

The `utilities/make_video.py` CLI will look in this folder for sub-folders to make videos. 

## Steps
1. Drag-and-drop files from the SSD (over USB 3.0) into this folder here.
2. Run `python3 utilities/make_video.py`
3. Select the desired folder with the CLI. All the subfolders within that folder which have `.npy` files will have `.mp4` made for them.