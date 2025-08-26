# RTC

The RTC ensures the Pi has accurate datetime regardless of Internet connection and power loss. To stay up to date, the RTC also needs to be updated whenever the Pi has correct time via network time protocol (NTP) syncing.

The instructions below configure the OS for the following behavior:
- If Pi is disconnected from internet at startup: Update system time from RTC
- If Pi successfully syncs to NTP via internet: Update RTC from system (NTP) time

## Setup instructions

The following files need to live in the Pi's `/etc/` directory:
- `rc.local` sets behavior on boot
- `dhcpcd.exit-hook` sets behavior on Internet connection

Ensure both files have executable permission:
```
sudo chmod +x rc.local
sudo chmod +x dhcpcd.exit-hook
```

## Tests

Reboot after adding the above files to start the RTC before testing.

### RTC in use

Verify system vs RTC time using `timedatectl` in terminal. You will see a printout like this:
```
               Local time: Mon 2025-08-25 15:42:07 PDT
           Universal time: Mon 2025-08-25 22:42:07 UTC
                 RTC time: Mon 2025-08-25 22:42:08
                Time zone: America/Los_Angeles (PDT, -0700)
System clock synchronized: yes
              NTP service: active
          RTC in local TZ: no
```

If the RTC did not successfully start, RTC time will be listed as `n/a`.

### System updated by RTC

Test the use case where there's no Internet connection:

First, turn off NTP sync, otherwise the time will automatically be corrected when `timedatectl` is run.
```
timedatectl ntp-sync false
```

Then, manually write an incorrect date/time to the RTC.
```
sudo hwclock --set --date "01/01/2001 00:00:00"
```

Run `timedatectl` to verify the RTC's datetime.


Turn wifi off and reboot. The system time should now be the incorrect RTC time. Be patient as it can take up to 1 min for the system time to update after reconnection.

_NOTE: If you ever want to overwrite system time using the RTC on the spot, run `sudo hwclock -s`._

### RTC updated bt system (NTP) time

Test the use case where the Pi reconnects to Internet:

Turn on wifi when it was previously off or reboot Pi. Both the system time and RTC time should be correct and can be verified by running `timedatectl`

_NOTE: If you want to overwrite the RTC using the NTP time on the spot, run `sudo hwclock -w`._


## Supplementary info
- [hwclock](https://linux.die.net/man/8/hwclock) tool
- [timedatectl](https://www.freedesktop.org/software/systemd/man/latest/timedatectl.html) tool
