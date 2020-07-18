To get the RPi HQ cam running in openCV on the RPi 4, I followed Adrian's tutorials closely, with one exception outlined below.

1. Follow this tutorial to install OpenCV on the RPi: https://www.pyimagesearch.com/2019/09/16/install-opencv-4-on-raspberry-pi-4-and-raspbian-buster/

NOTE: In step 3, I encountered an issue after updating ~/.bashrc
The virtual env could not be created, with the following error: 
ERROR: Environment ‘/home/pi/.virtualenvs/cv’ does not contain an activate script.

I followed the solution here by user Simon TheChain:  
https://stackoverflow.com/questions/60252119/error-environment-users-myuser-virtualenvs-iron-does-not-contain-activation-s/60292344#60292344

Pasted here for convenience:
===============================================================================================================================================================
"
I'm running on a raspbian buster with Python 3.7.3. I ran into the same issue, "ERROR...no activation script". I tried @Lombax answer but it didn't work.

However, I noticed that the version of virtualenvwrapper I had installed was 5.0.0. I checked on PyPi and it's still at version 4.8.4. So I uninstalled virtualenv and virtualenvwrapper: sudo pip3 uninstall virtualenv virtualenvwrapper.

Then I reinstalled both and specified the version: sudo pip3 install virtualenv virtualenvwrapper=='4.8.4' I sourced my .bashrc, in which I had appended the settings:

VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv
export PATH=/usr/local/bin:$PATH
export WORKON_HOME=~/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh
And now mkvirtualenv test works. Not sure what's the bug with version 5.x of virtualenvwrapper, in the meantime, this got around the problem for me, hope this helps.
"
===============================================================================================================================================================

Now finish Adrian's tutorial.


2. Install picamera and test the camera by following this tutorial: https://www.pyimagesearch.com/2015/03/30/accessing-the-raspberry-pi-camera-with-opencv-and-python/

3. Run test_image.py
4. Run test_video.py
