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


### Setting up email functionality for sending back the ngrok address automatically
We use a non Biohub free gmail account to do basic email sending. The email, `lfmscope@gmail.com` sends an email to itself which is then forwarded to all the people on its forwarding list.
Gmail allows you to generate a unique password for each new device that you want to run on. Instructions to generate application-specific-passwords are [here](https://support.google.com/accounts/answer/185833?hl=en). Every microscope needs to have its own unique application-specific-password.
1. Create an application specific password using the `lfmscope@gmail.com` account
2. Place the password in the microscope's persistent environment variables (similar to what we did above for `ngrok`):
  - Open the bashrc file: `nano /home/pi/.bashrc`
  - Add `export GMAIL_TOKEN=<TOKEN_HERE>` to the bottom of the file.
3. Run both `oracle.py` and `dev_run.py` to ensure you're receiving emails and that there are no errors (for example, if you forget to set the email token, that will raise a custom `EmailError: no token set` error. Similarly if an ngrok token isn't set, a custom `NgrokError: no token set` error will be raised.)

### Setting up bash aliases
1. To avoid users having to enter in an arduous path into the terminal to run a program (which is also likely to be error-prone), we have a few bash aliases instead. These aliases are stored under `ulc-malaria-scope/ulc_mm_package/utilities/.bash_aliases`. `cd` into that directory and `cp` that file to `/home/pi`, i.e:
```
cd Documents/ulc-malaria-scope/ulc_mm_package/utilities
cp .bash_aliases /home/pi
```

The commands in the file can now be run from the terminal. At the time of writing (2022-12-09), the following commands are available:
- `lfm_run` - runs `oracle.py`
- `lfm_dev` - runs `dev_run.py`
- `send_address` - runs `email_utils.py` (attempts to send the ngrok address to `lfmscope@gmail.com`)