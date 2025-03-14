# Remoscope: a label-free imaging cytometer for malaria diagnostics

![An artistic rendition of the Remoscope](icon.png)

## Introduction
This repository hosts instrument control software for the Remoscope, an automated and low-cost malaria diagnostic system, requiring minimal user training. The Remoscope was developed by the Bioengineering team at the Chan Zuckerberg Biohub San Francisco (CZBSF). The Remoscope images unstained fresh whole blood in liquid form and can screen up to two million red blood cells for _Plasmodium falciparum_ parasites. 

Please see our preprint here:

![image](https://github.com/user-attachments/assets/0a6896c8-2bae-41b2-a18e-0afa75b93250)

The Remoscope runs off a Raspberry Pi 4 Model B 8GB and an Intel Neural Compute Stick 2 (no longer available) to accelerate on-device neural network inferencing. The instrument control software is written in Python 3.7.3.

## Repository structure

```
├── ulc_mm_package
│   ├── utilities
│   ├── summary_report
│   ├── neural_nets
│   ├── image_processing
│   ├── hardware
│   ├── configs
│   ├── QtGUI
│   ├── scope_constants.py
├── OS_instructions
│   ├── OS_setup.md
│   └── OS_flash.md
├── architecture_description
├── setup.py
└── README.md
```

For a more detailed description of each folder and its scripts, see the `architecture_description/` folder.

## Installation and use

NOTE: If you are using a version downstream of commit `283a823` on `develop` (2024-03-06), you will need to install the `stats_utils` module. To do so, in the root directory run
```
python3 -m pip install -e .
```

### Option 1: Clone the image

1. Flash a pre-existing image to an SD card (must be at least 32GB), see `OS_flash.md`

### Option 2: Manual install

1. Follow the instructions under `OS_instructions`.

## Operation

To start the software, navigate to ulc_mm_package/QtGUI and run `python3 oracle.py`.

To use developer mode, navigate to ulc_mm_package/QtGUI and run `python3 dev_run.py`. This opens a GUI with manual hardware control for debugging purposes.

#### Related repositories
1. Object detection - YOGO: https://github.com/czbiohub-sf/yogo
2. Autofocus - SSAF: https://github.com/czbiohub-sf/ulc-malaria-autofocus
3. Data processing utilities / model evaluations: https://github.com/czbiohub-sf/lfm-data-utilities/
4. Statistics utilities: https://github.com/czbiohub-sf/remo-stats-utils
