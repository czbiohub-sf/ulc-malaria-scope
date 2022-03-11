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
                          'h5py', 
                          'matplotlib',
                          'numpy',
                          'opencv-python',
                          'PyQt5',
                          'pypylon',
                          'zarr',
                          'pigpio',
                          'adafruit-circuitpython-pcf8523',
                          'adafruit-circuitpython-mprls',
                          'pimoroni-ioexpander',
                          'qimage2ndarray',
                          'py_cameras @ git+https://github.com/czbiohub/pyCameras@master',
                          'pymotors @ git+https://github.com/czbiohub/PyMotors@master',
                          'typer',
                          ],
      classifiers = ["CZ Biohub :: Bioengineering"],
)
