from time import sleep, perf_counter
import cv2
import camera

cam = camera.LiveCamera()
start = perf_counter()
frames = 0
try:
    for img in cam.yieldImages():
        frames += 1
        # print(img)
        cv2.imshow('temp', img)
        cv2.waitKey(1)
except KeyboardInterrupt:
    end = perf_counter()
    runtime = end - start
    framerate = frames / runtime
    print({f"{frames}, {runtime}, {framerate}"})
