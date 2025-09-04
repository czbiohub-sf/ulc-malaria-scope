import argparse
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError


def init_argparse() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
  # usage="%(prog)s [pwm([0-1])]",
  description="Set the LED power manually using a [0,1] input value",
  )
  parser.add_argument("-pwm", nargs=1, default=0, type=float)

  return parser

def _init_led():
# Create the LED
  try:
    led = LED_TPS5420TDDCT()
    led.turnOn()
    led.setDutyCycle(0)
  except LEDError as e:
    print(f"LED initialization failed: {e}")

  return led


def main():
  parser = init_argparse()
  args = parser.parse_args()
  pwm = args.pwm[0]
  
  if (pwm < 0) or (pwm > 1):
    print("pwm value has to be between [0, 1]!")
    return

  led = _init_led()
  led.setDutyCycle(pwm)
  led.turnOn()
  print("CTRL-C to exit...")

  try: 
    while(1):
      pass

  except KeyboardInterrupt:
    pass

  finally:
    led.setDutyCycle(0)
    led.turnOff()

if __name__ == "__main__":
  main()