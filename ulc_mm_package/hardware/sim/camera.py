# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating camera.
         See camera module under hardware/real/ for info on actual functionality.

"""

import cv2

from time import time, perf_counter, sleep

from ulc_mm_package.scope_constants import VIDEO_REC
from ulc_mm_package.hardware.hardware_constants import DEFAULT_EXPOSURE_MS
from ulc_mm_package.hardware.camera import CameraError


class SimCamera:
    def __init__(self):

        _viable_videos = (
            "../QtGUI/sim_media/avt-sample.mp4",
            "../QtGUI/sim_media/sample.avi",
            "../QtGUI/sim_media/sample.mp4",
        )
        VIDEO_PATH = next((vid for vid in _viable_videos if os.path.exists(vid)), None)
        if VIDEO_PATH == None:
            raise RuntimeError(
                "Sample video for simulation mode could not be found. "
                f"Download a video from {VIDEO_REC} and save as {_viable_videos[0]} or {_viable_videos[1]}"
            )

        self._isActivated = True

        try:
            self.binning = 1
            self.exposureTime_ms = DEFAULT_EXPOSURE_MS

            # Setup simulated video stream
            self.video = cv2.VideoCapture(VIDEO_PATH)
            self.frame_count = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video.get(cv2.CAP_PROP_FPS)

            success = True

        except Exception as e:
            print(e)
            raise CameraError("Camera could not be instantiated.")

    def setBinning(self, bin_factor=1, mode="Average"):
        self.binning = bin_factor

    def getBinning(self):
        return self.binning

    def yieldImages(self):
        while True:
            success, frame = self.video.read()
            # Reload video
            if not success:
                self.video = cv2.VideoCapture(VIDEO_PATH)
                success, frame = self.video.read()
            yield cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), perf_counter()
            sleep(1 / self.fps)

    def snapImage(self):
        return self.frames[self.index]

    def preview(self):
        try:
            while True:
                frame = self.yieldImages()
                cv2.imshow("preview", frame)
                cv2.waitKey(1)
        except KeyboardInterrupt:
            pass

    def print(self):
        print("This is a simulated camera")

    def stopAcquisition(self):
        pass

    def activateCamera(self):
        pass

    def deactivateCamera(self):
        pass


class BaslerCamera(SimCamera):
    pass


class AVTCamera(SimCamera):
    pass
