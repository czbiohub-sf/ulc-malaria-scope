# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating camera.
         See camera module under hardware/real/ for info on actual functionality.
         
"""

import cv2

from time import time, perf_counter, sleep

from ulc_mm_package.hardware.hardware_constants import DEFAULT_EXPOSURE_MS, VIDEO_PATH
from ulc_mm_package.hardware.camera import CameraError, CameraDims


class SimCamera:
    def __init__(self):
        self._isActivated = True

        try:
            self.binning = 2
            self.setBinning(self.binning)
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
        if bin_factor == 1:
            w, h = CameraDims.get_dims()
            CameraDims.set_resolution(w * 2, h * 2)
        elif bin_factor == 2:
            w, h = CameraDims.get_dims()
            CameraDims.set_resolution(w // 2, h // 2)

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
    CameraDims.set_resolution(1200, 1600)


class AVTCamera(SimCamera):
    CameraDims.set_resolution(1544, 2064)
