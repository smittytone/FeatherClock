'''
Clock RP2040 OLED/Segment

A very simple four-digit timepiece

Version:   1.3.0
Author:    smittytone
Copyright: 2022, Tony Smith
Licence:   MIT
'''
import board
import busio
import storage

display_present = False

# Instantiate I2C and check whether a display is
# connected. If it is, set the Trinkey Flash to be accessible
# to code; otherwise make it accessible as a USB drive.
# NOTE This process assumes the standard 128x32 I2C address
#      of `0x3C`. The 128x64 display address is `0x3D`.
i2c = busio.I2C(board.SCL, board.SDA)
while not i2c.try_lock():
    pass
devices = i2c.scan()
if len(devices) > 0:
    for device in devices:
        # Allow for both OLED and Segment displays
        if int(device) in (0x3C, 0x70):
            display_present = True
            break

# For the second parameter of `storage.remount()`:
# Pass True to make the `CIRCUITPY` drive writable by your computer. 
# Pass False to make the `CIRCUITPY` drive writable by CircuitPython.
# This is the opposite of `display_present`, ie. when the display is 
# not connected, you can update the code
storage.remount("/", (False if display_present is True else True))
print("CIRCUITPY","LOCKED" if display_present is True else "UNLOCKED")
