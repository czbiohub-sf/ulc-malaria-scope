# Flashing Instructions

99% of the time, you will be flashing one of these images. They are pre-made and ready specifically for the ULC Malaria Scope.

First, go get the Raspberry Pi Imager, if you don't have it already:

https://www.raspberrypi.com/software/

Second, go to the drive link:

https://drive.google.com/drive/u/0/folders/1lGbjsn2M_-sXlK0GY4xKjBfApmT6D6bf

Download the most recent image (currently in folder `2022-11-28 Base OS`) - it should be a `.img` or `.img.xz` file.

Now you simply flash the image. Open the program, plug in your SD card, and follow these options:

- For "Operating System", choose the `.img` or `.img.xz` file that you downloaded. This will be under "Custom" images
- For "Storage", choose the SD card

Next, press "shift-control-x" and update some settings such as the hostname and wifi.

Now, simply click "Write" and let the program finish.

## Post Flash

The first step here will be to insert the SD card into a Raspberry Pi and access it. Either `ssh` into it (make sure you have the hostname!), or plug a keyboard and monitor into it. Then, open a terminal, and run the following commands:

```console
cd ~/Documents/ulc-malaria-scope
git pull  # enter your ghp keys here, if necessary
```
