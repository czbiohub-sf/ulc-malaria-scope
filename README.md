# Ultra-Low Cost (ULC) malaria scope

Welcome to the ULC Malaria Scope! We are developing a barebones optical microscope with embedded computing hardware capable of dianosing malaria in fresh, whole blood with no fixation, staining, or preparation steps. No highly trained technicians will be required to perform time-consuming sample preparation or manual scoring of parasites under the microscope. The target BOM cost is $250.

## Introduction

## Optics

## Realtime malaria detection

## Hardware

## Flow cell

### Flexure-based autofocus

## GUI Operation

### Dependencies
In the root folder, run <code>pip install -e .</code> to install all dependencies.

### Starting the GUI
Navigate to ulc_mm_package/QtQUI and run <code>python3 UI.py</code>. Use optional flags to enable operation modes:
* <code>-s</code> or <code>--sim</code>: Simulation mode (dummy functions replace hardware objects)
* <code>-d</code> or <code>--dev</code>: Developer mode (manual control of hardware objects)

Note: The original GUI was activated by liveviewer.py, which is now obsolete. Use UI.py instead.
