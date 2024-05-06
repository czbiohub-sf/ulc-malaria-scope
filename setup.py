#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Oct 1, 2021
"""

from setuptools import setup, find_packages


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="ulc_mm_package",
    version="0.0.1",
    description="Instrument control software for the malaria microscope project",
    long_description=readme(),
    url="https://github.com/czbiohub/ulc-malaria-scope",
    author="Bioengineering | CZ Biohub SF",
    author_email="paul.lebel@czbiohub.org",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "Pillow",
        "matplotlib==3.4.3",
        "numpy==1.21.0",
        "opencv-python",
        "PyQt5>=5.15.2",
        "pypylon==1.7.2",
        "zarr==2.10.1",
        "pigpio==1.78",
        "adafruit-circuitpython-pcf8523==1.5.5",
        "adafruit-circuitpython-mprls==1.2.7",
        "adafruit-circuitpython-sht31d",
        "argparse",
        "pimoroni-ioexpander",
        "qimage2ndarray==1.9.0",
        "py_cameras @ git+https://github.com/czbiohub/pyCameras@master",
        "pymotors @ git+https://github.com/czbiohub/PyMotors@master",
        "stats_utils @ git+https://github.com/czbiohub-sf/remo-stats-utils@v0.0.9",
        "typer==0.4.1",
        "tqdm==4.63.0",
        "transitions==0.8.11",
        "pyngrok==7.0.3",
        "numba==0.56.0",
        "Jinja2==3.1.4",
        "xhtml2pdf==0.2.11",
    ],
    extras_require={
        "dev": [
            "AllanTools",
            "black==23.1.0",
            "mypy==1.0.1",
            "mypy-extensions==1.0.0",
            "PyQt5-stubs",
            "ruff==0.0.253",
        ]
    },
    classifiers=["CZ Biohub :: Bioengineering"],
)
