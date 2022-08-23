#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Oct 1, 2021

@author: i-jey
"""

from setuptools import setup, find_packages

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='ulc_mm_package',
      version ='0.0.1',
      description = 'Instrument control software for the malaria microscope project',
      long_description = readme(),
      url = 'https://github.com/czbiohub/ulc-malaria-scope',
      author = 'Ilakkiyan Jeyakumar',
      author_email = 'ilakkiyan.jeyakumar@czbiohub.org',
      license = 'MIT',
      packages = find_packages(),
      install_requires = ['Pillow',
                          'matplotlib==3.4.3',
                          'numpy==1.20.3',
                          'opencv-python',
                          'scipy==1.8.1',
                          'PyQt5==5.15.4',
                          'pypylon==1.7.2',
                          'zarr==2.10.1',
                          'pigpio==1.78',
                          'adafruit-circuitpython-pcf8523==1.5.5',
                          'adafruit-circuitpython-mprls==1.2.7',
                          'adafruit-circuitpython-sht31d',
                          'argparse',
                          'pimoroni-ioexpander',
                          'qimage2ndarray==1.9.0',
                          'py_cameras @ git+https://github.com/czbiohub/pyCameras@master',
                          'pymotors @ git+https://github.com/czbiohub/PyMotors@master',
                          'typer==0.4.1',
                          'tqdm==4.63.0',
                          ],
      classifiers = ["CZ Biohub :: Bioengineering"],
)
