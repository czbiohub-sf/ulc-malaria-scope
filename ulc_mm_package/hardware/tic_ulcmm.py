""" A simple wrapper on top of PyMotors' TicStage

The Pololu Tic Stepper is being used temporarily while the PCB is finished (which uses the DRV8825 motor driver).
This file sets up a TicStepper using default parameters. 

-- Important Links --
PyMotors:
    https://github.com/czbiohub/pyMotors
Datasheet:
    https://www.pololu.com/docs/0J71
"""

from pymotors import TicStage

class TicStageULCMM():
    def __init__(self):
        _TIC_COM_MODE = 'serial'
        _TIC_COM = '/dev/tty.usbserial-AD0JIXRE'
        _TIC_BAUDRATE = 9600
        _TIC_DEVICE_NUMBER = 14
        self.tic_stage = TicStage(_TIC_COM_MODE, [_TIC_COM, _TIC_BAUDRATE], _TIC_DEVICE_NUMBER, 500, 200, micro_step_factor=1, default_step_tol=1)
        self.tic_stage.enable = True
        self.tic_stage.discoverMotionRange()