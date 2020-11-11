import argparse
import glob
import os

import cv2

# Program to convert gray to rgb jpg images


def convert_to_rgb_gray(image):
  return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-o', '--output', required=True,
                      help='File path of .tflite file.')
  parser.add_argument('-i', '--input', required=True,
                      help='File path of image to process.')
  parser.add_argument('-f', '--format', type=str, default=".png",
                      help='Format of image')
  args = parser.parse_args()
  path = os.path.abspath(args.output)
  if not os.path.exists(path):
        os.makedirs(path)
  else:
      print("Path {} already exists, might be overwriting data".format(path))
  for input_image in glob.glob(os.path.join(args.input, "*" + args.format)):
  	cv2.imwrite(
  	  os.path.join(path, os.path.basename(input_image)),
  	  convert_to_rgb_gray(cv2.imread(input_image)))

    
if __name__ == '__main__':
  main()
