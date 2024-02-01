# Remoscope: an automated, low-cost, and fast malaria diagnostic system
![An artistic rendition of the Remoscope](icon.png)

[TODO] - Add figure showing workflow once finalized

## Introduction
TODO [Add reference to paper once uploaded]

This repository houses the machine learning models and instrument control software for the Remoscope, an automated and low-cost malaria diagnostic system, requiring minimal user training. The Remoscope was developed by the Bioengineering team at the Chan Zuckerberg Biohub San Francisco (CZBSF). The Remoscope images unstained fresh whole blood in liquid form and can screen up to two million red blood cells for _Plasmodium falciparum_ parasites.

The Remoscope runs off a Raspberry Pi 4 Model B 8GB and an Intel Neural Compute Stick 2 (no longer available) to accelerate on-device neural network inferencing. The instrument control software is written in Python 3.7.3.

## User guide
[TODO] - Verify that the user guide is publicly accessible (https://docs.google.com/document/d/11vunMRfG9IbehD3opIatyN18aQXaa78SdT_b89pUGIs/edit#)

## Mechanical model
[TODO] - Add Onshape link, rotating gif of onshape model here

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
### Option 1: Clone the image
1. Flash a pre-existing image to an SD card (must be at least 32GB), see `OS_flash.md`

### Option 2: Manual install
1. Follow the instructions under `OS_instructions`.

## Operation

To start the software, navigate to ulc_mm_package/QtGUI and run `python3 oracle.py`.

To use developer mode, navigate to ulc_mm_package/QtGUI and run `python3 dev_run.py`. This opens a GUI with manual hardware control for debugging purposes.

#### Related malaria scope repositories reference
1. Main: https://github.com/czbiohub/ulc-malaria-scope
2. Object detection - YOGO: https://github.com/czbiohub-sf/yogo
3. Autofocus - SSAF: https://github.com/czbiohub-sf/ulc-malaria-autofocus
4. Data processing utilities / model evaluations: https://github.com/czbiohub-sf/lfm-data-utilities/
5. Dataset definitions (sets of files defining which datasets to use for training/testing, etc.): https://github.com/czbiohub-sf/lfm-dataset-definitions/tree/main
6. Thumbnail labels (stored on flexo, backed up to this repository): https://github.com/czbiohub-sf/lfm-human-labels
7. Statistics utilities: https://github.com/czbiohub-sf/remo-stats-utils
