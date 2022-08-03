import subprocess
import enum

class PWM_CHANNEL(enum.Enum):
    PWM1 = 0
    PWM2 = 1

class dtoverlay_PWM:
    def __init__(self, channel: PWM_CHANNEL):
        self.channel = channel.value
        self._start()

    def _start(self):
        cmd = '''
            echo 0 > export;
            echo 1 > export;
            echo 1 > pwm0/enable;
            echo 1 > pwm1/enable;
        '''
        subprocess.run(cmd, capture_output= True, shell=True, cwd=f"/sys/class/pwm/pwmchip0")

    def setFreq(self, freq: int):
        period_ns = int((1 / freq)*1e9)
        cmd = f"echo {period_ns} > pwm{self.channel}/period;"
        subprocess.run(cmd, capture_output= True, shell=True, cwd=f"/sys/class/pwm/pwmchip0")

    def setDutyCycle(self, duty_cycle_perc: float):
        """duty_cycle_perc between 0 - 1.0"""
        duty_cycle_val = int(duty_cycle_perc * 1e5)
        cmd = f"echo {duty_cycle_val} > pwm{self.channel}/duty_cycle;"
        subprocess.run(cmd, capture_output= True, shell=True, cwd=f"/sys/class/pwm/pwmchip0")

    def exit(self):
        cmd = '''
        echo 0 > pwm0/enable;
        echo 0 > pwm1/enable;
        '''
        subprocess.run(cmd, capture_output= True, shell=True, cwd=f"/sys/class/pwm/pwmchip0")
        
if __name__ == "__main__":
    from time import sleep

    pwm = dtoverlay_PWM(PWM_CHANNEL.PWM2)
    pwm.setFreq(50000)
    pwm.setDutyCycle(0.5)

    sleep(3)

    pwm.exit()