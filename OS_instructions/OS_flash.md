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

### Setting up ngrok

[Ngrok](https://ngrok.com/) is a service used to create `ssh` tunnels for accessing our scopes when they are behind private networks. At the time of writing (2022-11-28), `ngrok` free-tier accounts allow you to have one persistent `ssh` connection per account.

Each scope needs to sign up for its own ngrok account (using a unique email) to be able to open and maintain a persistent ssh connection when the program starts. To create an `ngrok` account, "Google Distribution email accounts" (i.e a forwarding received emails-only email account) are sufficient. (According to IT at the time of writing, having an inbound/outbox default @czbiohub.org mailbox costs $7/mo.)

1. Ask IT to make a new account for the scope (and ask them to set your email as the forwarding one), e.g `lfm_newscope@czbiohub.org`
2. Sign up for `ngrok`, and note down the unique token.
3. Add this token to the scope's persistent environment variables by doing the following:
  - Open the bashrc file: `nano /home/pi/.bashrc`
  - Add `export NGROK_AUTH_TOKEN=<TOKEN_HERE>` to the bottom of the file.
4. TODO - set up the emailing functionality (`lfm_central@czbiohub.org`) (instead of each scope having a regular mailbox, which costs $7/mo for a @czbiohub.org address, we have a single @czbiohub.org address that all the scopes use to send emails.) **Fill this in with details once we have this implemented.
