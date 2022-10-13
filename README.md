# Ultra-Low Cost (ULC) malaria scope

Welcome to the ULC Malaria Scope! We are developing a barebones optical microscope with embedded computing hardware capable of dianosing malaria in fresh, whole blood with no fixation, staining, or preparation steps. No highly trained technicians will be required to perform time-consuming sample preparation or manual scoring of parasites under the microscope. The target BOM cost is $250.

## Introduction

## Optics

## Realtime malaria detection

## Hardware

## Flow cell

### Flexure-based autofocus

## Software operation

### Installing dependencies
In the root folder, run <code>pip install -e .</code> to install all pip dependencies. There are also some modules that need to be manually installed:

Allied Vision's Vimba library:
1. Check that Python 3.7 is installed and verify with <code>python --version</code>
2. Check that pip is up to date and verify with <code>python -m pip --version</code>
3. [Download the SDK](https://www.alliedvision.com/en/products/vimba-sdk/#c1497).
4. Navigate to the "VimbaPython" installation directory in a terminal and run <code>python -m pip install .</code>

### Running the GUI

Navigate to ulc_mm_package/QtQUI and run <code>python3 oracle.py</code>.

Note: The original GUI lived in <code>liveviewer.py</code>, which is now obsolete. Use the above command instead.

### Debugging using developer mode

Navigate to ulc_mm_package/QtQUI and run <code>python3 dev_run.py</code>. This opens a GUI with manual hardware control for debugging purposes.

### Using simulation mode

To run any of these scripts using simulated hardware (eg. to test code without a scope), add an empty <code>simulation.py</code> file to your working directory. 

For example, to run <code>oracle.py</code> in simulation mode, your file structure should include a <code>simulation.py</code> file as shown below:
'''
|--ulc_mm_package
   |--QtGUI
      |--simulation.py
      |--oracle.py
        
'''