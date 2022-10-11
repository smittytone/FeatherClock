'''
Clock RP2040 Oled

A very simple four-digit timepiece

Version:   1.3.0
Author:    smittytone
Copyright: 2022, Tony Smith
Licence:   MIT
'''

# ********** IMPORTS **********

import json
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from rtc import RTC
from time import localtime, sleep, mktime, struct_time

# ********** GLOBALS **********

prefs = None
yrdy = 0
display_present = False

# ********** CLASSES **********

class SSD1306OLED:
    """
    A simple driver for the I2C-connected Solomon SSD1306 controller chip and an OLED display.
    For example: https://www.adafruit.com/product/931
    This release is written for MicroPython and CircuitPython

    Version:   2.0.0
    Author:    smittytone
    Copyright: 2022, Tony Smith
    Licence:   MIT
    """

    # *********** CONSTANTS **********

    SSD1306_MEMORYMODE = 0x20
    SSD1306_COLUMNADDR = 0x21
    SSD1306_PAGEADDR = 0x22
    SSD1306_WRITETOBUFFER = 0x40
    SSD1306_SETSTARTLINE = 0x40
    SSD1306_SETCONTRAST = 0x81
    SSD1306_CHARGEPUMP = 0x8D
    SSD1306_SEGREMAP = 0xA1
    SSD1306_DISPLAYALLON_RESUME = 0xA4
    SSD1306_DISPLAYALLON = 0xA5
    SSD1306_NORMALDISPLAY = 0xA6
    SSD1306_INVERTDISPLAY = 0xA7
    SSD1306_SETMULTIPLEX = 0xA8
    SSD1306_DISPLAYOFF = 0xAE
    SSD1306_DISPLAYON = 0xAF
    SSD1306_COMSCANDEC = 0xC8
    SSD1306_SETDISPLAYOFFSET = 0xD3
    SSD1306_SETDISPLAYCLOCKDIV = 0xD5
    SSD1306_SETPRECHARGE = 0xD9
    SSD1306_SETCOMPINS = 0xDA
    SSD1306_SETVCOMDETECT = 0xDB

    CHARSET = [
        b"\x00\x00",                # space - Ascii 32
        b"\xfa",                    # !
        b"\xe0, 0xc0\x00\xe0\xc0",  # "
        b"\x24\x7e\x24\x7e\x24",    # #
        b"\x24\xd4\x56\x48",        # $
        b"\xc6\xc8\x10\x26\xc6",    # %
        b"\x6c\x92\x6a\x04\x0a",    # &
        b"\xc0",                    # '
        b"\x7c\x82",                # (
        b"\x82\x7c",                # )
        b"\x10\x7c\x38\x7c\x10",    # *
        b"\x10\x10\x7c\x10\x10",    # +
        b"\x06\x07",                # ,
        b"\x10\x10\x10\x10\x10",    # -
        b"\x06\x06",                # .
        b"\x04\x08\x10\x20\x40",    # /
        b"\x7c\x8a\x92\xa2\x7c",    # 0 - Ascii 48
        b"\x42\xfe\x02",            # 1
        b"\x46\x8a\x92\x92\x62",    # 2
        b"\x44\x92\x92\x92\x6c",    # 3
        b"\x18\x28\x48\xfe\x08",    # 4
        b"\xf4\x92\x92\x92\x8c",    # 5
        b"\x3c\x52\x92\x92\x8c",    # 6
        b"\x80\x8e\x90\xa0\xc0",    # 7
        b"\x6c\x92\x92\x92\x6c",    # 8
        b"\x60\x92\x92\x94\x78",    # 9
        b"\x36\x36",                # : - Ascii 58
        b"\x36\x37",                # ;
        b"\x10\x28\x44\x82",        # <
        b"\x24\x24\x24\x24\x24",    # =
        b"\x82\x44\x28\x10",        # >
        b"\x60\x80\x9a\x90\x60",    # ?
        b"\x7c\x82\xba\xaa\x78",    # @
        b"\x7e\x90\x90\x90\x7e",    # A - Ascii 65
        b"\xfe\x92\x92\x92\x6c",    # B
        b"\x7c\x82\x82\x82\x44",    # C
        b"\xfe\x82\x82\x82\x7c",    # D
        b"\xfe\x92\x92\x92\x82",    # E
        b"\xfe\x90\x90\x90\x80",    # F
        b"\x7c\x82\x92\x92\x5c",    # G
        b"\xfe\x10\x10\x10\xfe",    # H
        b"\x82\xfe\x82",            # I
        b"\x0c\x02\x02\x02\xfc",    # J
        b"\xfe\x10\x28\x44\x82",    # K
        b"\xfe\x02\x02\x02\x02",    # L
        b"\xfe\x40\x20\x40\xfe",    # M
        b"\xfe\x40\x20\x10\xfe",    # N
        b"\x7c\x82\x82\x82\x7c",    # O
        b"\xfe\x90\x90\x90\x60",    # P
        b"\x7c\x82\x92\x8c\x7a",    # Q
        b"\xfe\x90\x90\x98\x66",    # R
        b"\x64\x92\x92\x92\x4c",    # S
        b"\x80\x80\xfe\x80\x80",    # T
        b"\xfc\x02\x02\x02\xfc",    # U
        b"\xf8\x04\x02\x04\xf8",    # V
        b"\xfc\x02\x3c\x02\xfc",    # W
        b"\xc6\x28\x10\x28\xc6",    # X
        b"\xe0\x10\x0e\x10\xe0",    # Y
        b"\x86\x8a\x92\xa2\xc2",    # Z - Ascii 90
    ]

    NUMBERS = [
b"\x7F\xBF\xDF\xEF\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\xEF\xE7\xC3\x81\x00\x00\x00\x00\x00\x00\x00\x00\x81\xC3\xE7\xEF\xFE\xFD\xFB\xF7\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE",
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0F\x1F\x3F\x7F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x81\xC3\xE7\xEF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xF0\xF8\xFC\xFE",
b"\x00\x80\xC0\xE0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\x0F\x07\x03\x19\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x18\x00\x00\x00\xFE\xFD\xFB\xF7\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x07\x03\x01\x00",
b"\x00\x80\xC0\xE0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\x00\x00\x00\x18\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x99\xC3\xE7\xEF\x00\x01\x03\x07\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE",
b"\x7F\x3F\x1F\x0F\x00\x00\x00\x00\x00\x00\x00\x00\x0F\x1F\x3F\x7F\xE0\xE0\xC0\x98\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x99\xC3\xE7\xEF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xF0\xF8\xFC\xFE",
b"\x7F\xBF\xDF\xEF\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xE0\xC0\x80\x00\xE0\xE0\xC0\x98\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x19\x03\x07\x0F\x00\x01\x03\x07\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE",
b"\x7F\xBF\xDF\xEF\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xE0\xC0\x80\x00\xF7\xE7\xC3\x99\x3C\x3E\x7E\x7E\x7E\x7E\x3E\x3C\x19\x03\x07\x07\xFE\xFD\xFB\xF7\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE",
b"\x00\x80\xC0\xE0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x81\xC3\xE7\xEF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xF0\xF8\xFC\xFE",
b"\x7F\xBF\xDF\xEF\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\xEF\xE7\xC3\x99\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x99\xC3\xE7\xEF\xFE\xFD\xFB\xF7\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE",
b"\x7F\xBF\xDF\xEF\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xF0\xEF\xDF\xBF\x7F\xE0\xE0\xC0\x98\x3C\x7C\x7E\x7E\x7E\x7E\x7C\x3C\x99\xC3\xE7\xEF\x00\x01\x03\x07\x0F\x0F\x0F\x0F\x0F\x0F\x0F\x0F\xF7\xFB\xFD\xFE"
    ]

    COS_TABLE = [
        0.000,0.035,0.070,0.105,0.140,0.174,0.208,0.243,0.276,0.310,0.343,0.376,0.408,0.439,0.471,0.501,0.531,0.561,0.589,0.617,0.644,
        0.671,0.696,0.721,0.745,0.768,0.790,0.810,0.830,0.849,0.867,0.884,0.900,0.915,0.928,0.941,0.952,0.962,0.971,0.979,0.985,0.991,
        0.995,0.998,1.000,1.000,0.999,0.997,0.994,0.990,0.984,0.977,0.969,0.960,0.949,0.938,0.925,0.911,0.896,0.880,0.863,0.845,0.826,
        0.806,0.784,0.762,0.739,0.715,0.690,0.664,0.638,0.610,0.582,0.554,0.524,0.494,0.463,0.432,0.400,0.368,0.335,0.302,0.268,0.234,
        0.200,0.166,0.131,0.096,0.062,0.027,-0.008,-0.043,-0.078,-0.113,-0.148,-0.182,-0.217,-0.251,-0.284,-0.318,-0.351,-0.383,-0.415,
        -0.447,-0.478,-0.508,-0.538,-0.567,-0.596,-0.624,-0.651,-0.677,-0.702,-0.727,-0.750,-0.773,-0.795,-0.815,-0.835,-0.854,-0.872,
        -0.888,-0.904,-0.918,-0.931,-0.944,-0.955,-0.964,-0.973,-0.981,-0.987,-0.992,-0.996,-0.998,-1.000,-1.000,-0.999,-0.997,-0.993,
        -0.988,-0.982,-0.975,-0.967,-0.957,-0.947,-0.935,-0.922,-0.908,-0.893,-0.876,-0.859,-0.840,-0.821,-0.801,-0.779,-0.757,-0.733,
        -0.709,-0.684,-0.658,-0.631,-0.604,-0.575,-0.547,-0.517,-0.487,-0.456,-0.424,-0.392,-0.360,-0.327,-0.294,-0.260,-0.226,-0.192,
        -0.158,-0.123,-0.088,-0.053,-0.018]

    SIN_TABLE = [
        1.000,0.999,0.998,0.994,0.990,0.985,0.978,0.970,0.961,0.951,0.939,0.927,0.913,0.898,0.882,0.865,0.847,0.828,0.808,0.787,
        0.765,0.742,0.718,0.693,0.667,0.641,0.614,0.586,0.557,0.528,0.498,0.467,0.436,0.404,0.372,0.339,0.306,0.272,0.238,0.204,
        0.170,0.135,0.101,0.066,0.031,-0.004,-0.039,-0.074,-0.109,-0.144,-0.178,-0.213,-0.247,-0.280,-0.314,-0.347,-0.379,-0.412,
        -0.443,-0.474,-0.505,-0.535,-0.564,-0.593,-0.620,-0.647,-0.674,-0.699,-0.724,-0.747,-0.770,-0.792,-0.813,-0.833,-0.852,
        -0.870,-0.886,-0.902,-0.916,-0.930,-0.942,-0.953,-0.963,-0.972,-0.980,-0.986,-0.991,-0.995,-0.998,-1.000,-1.000,-0.999,
        -0.997,-0.994,-0.989,-0.983,-0.976,-0.968,-0.959,-0.948,-0.936,-0.924,-0.910,-0.895,-0.878,-0.861,-0.843,-0.823,-0.803,
        -0.782,-0.759,-0.736,-0.712,-0.687,-0.661,-0.635,-0.607,-0.579,-0.550,-0.520,-0.490,-0.459,-0.428,-0.396,-0.364,-0.331,
        -0.298,-0.264,-0.230,-0.196,-0.162,-0.127,-0.092,-0.057,-0.022,0.013,0.048,0.083,0.117,0.152,0.187,0.221,0.255,0.288,
        0.322,0.355,0.387,0.419,0.451,0.482,0.512,0.542,0.571,0.599,0.627,0.654,0.680,0.705,0.730,0.753,0.776,0.797,0.818,0.837,
        0.856,0.874,0.890,0.906,0.920,0.933,0.945,0.956,0.966,0.974,0.981,0.988,0.992,0.996,0.999,1.000]


    # *********** CONSTRUCTOR **********

    def __init__(self, i2c, address=0x3C, width=128, height=32):
        assert 0x00 <= address < 0x80, "ERROR - Invalid I2C address in HT16K33()"

        # Determine whether we're on MicroPython or CircuitPython
        try:
            import machine
            self.is_micropython = True
        except:
            self.is_micropython = False

        # Set up instance properties
        self.i2c = i2c
        self.address = address
        self.width = width
        self.height = height
        self.x = 0
        self.y = 0
        self.buffer = bytearray(width * int(height / 8))
        
        # Display wake-up time
        time.sleep(0.02)

        # Write the display settings
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_DISPLAYOFF]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETDISPLAYCLOCKDIV, 0x80]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETMULTIPLEX, self.height - 1]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETDISPLAYOFFSET, 0x00]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETSTARTLINE]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_CHARGEPUMP, 0x14]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_MEMORYMODE, 0x00]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SEGREMAP]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_COMSCANDEC]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETCOMPINS, 0x02 if self.height in (16, 32) else 0x12]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETCONTRAST, 0x8F]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETPRECHARGE, 0xF1]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_SETVCOMDETECT, 0x40]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_DISPLAYALLON_RESUME]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_NORMALDISPLAY]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_DISPLAYON]))

        pages = (self.height // 8) - 1 # 0x03 if self.height == 64 else 0x07
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_COLUMNADDR, 0x00, self.width - 1]))
        self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_PAGEADDR, 0x00, pages]))

        # Clear the display
        self.clear()
        self.draw()

    # *********** PUBLIC METHODS **********

    def set_inverse(self, is_inverse=True):
        """
        Set the entire display to black-on-white or white-on-black

        Args:
            is_inverse (bool): should the display be black-on-white (True) or white-on-black (False).
        """
        if is_inverse:
            self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_INVERTDISPLAY]))
        else:
            self.i2c.writeto(self.address, bytes([0x00, self.SSD1306_NORMALDISPLAY]))

    def home(self):
        """
        Set the cursor to the home position, (0, 0), at the top left of the screen

        Returns:
            The display object
        """
        return self.move(0, 0)

    def move(self, x, y):
        """
        Set the cursor to the specified position

        Args:
            x (int) The X co-ordinate in the range 0 - 127
            y (int) The Y co-ordinate in the range 0 - 32 or 64, depending on model

        Returns:
            The instance (self)
        """
        assert (0 <= x < self.width) and (0 <= y < self.height), "ERROR - Out-of-range co-ordinate(s) passed to move()"
        self.x = x
        self.y = y
        return self

    def plot(self, x, y, colour=1):
        """
        Plot a point (or clear) the pixel at the specified co-ordinates

        Args:
            x      (int) The X co-ordinate in the range 0 - 127
            y      (int) The Y co-ordinate in the range 0 - 32 or 64, depending on model
            colour (int) The colour of the pixel: 1 for set, 0 for clear. Default: 1

        Returns:
            The instance (self)
        """
        # Bail if any co-ordinates are off the screen
        if x < 0 or x > self.width - 1 or y < 0 or y > self.height - 1:
            return self
        if colour not in (0, 1): colour = 1
        byte = self._coords_to_index(x, y)
        bit = y - ((y >> 3) << 3)
        if colour == 1:
            # Set the pixel
            self.buffer[byte] |= (1 << bit)
        else:
            # Clear the pixel
            self.buffer[byte] &= ~(1 << bit)
        return self

    def line(self, x, y, tox, toy, thick=1, colour=1):
        """
        Draw a line between the specified co-ordinates

        Args:
            x      (int) The start X co-ordinate in the range 0 - 127
            y      (int) The start Y co-ordinate in the range 0 - 32 or 64, depending on model
            tox    (int) The end X co-ordinate in the range 0 - 127
            toy    (int) The end Y co-ordinate in the range 0 - 32 or 64, depending on model
            think  (int) The thickness of the line in pixels. Default: 1
            colour (int) The colour of the pixel: 1 for set, 0 for clear. Default: 1

        Returns:
            The instance (self)
        """
        # Make sure we have a thickness of at least one pixel
        thick = max(thick, 1)
        if colour not in (0, 1): colour = 1
        # Look for vertical and horizontal lines
        track_by_x = True
        if x == tox: track_by_x = False
        if (toy == y) and (track_by_x is False): return self
        #assert (y != toy) and (track_by_x is False), "ERROR - Bad co-ordinates passed to line()"

        # Swap start and end values for L-R raster
        if track_by_x:
            if x > tox:
                a = x
                x = tox
                tox = a
            start = x
            end = tox
            m = float(toy - y) / float(tox - x)
        else:
            if y > toy:
                a = y
                y = toy
                toy = a
            start = y
            end = toy
            m = float(tox - x) / float(toy - y)

        # Run for 'thick' times to generate thickness
        for j in range(thick):
            # Run from x to tox, calculating the y offset at each point
            for i in range(start, end):
                if track_by_x:
                    dy = y + int(m * (i - x)) + j
                    if (0 <= i < self.width) and (0 <= dy < self.height):
                        self.plot(i, dy, colour)
                else:
                    dx = x + int(m * (i - y)) + j
                    if (0 <= i < self.height) and (0 <= dx < self.width):
                        self.plot(dx, i, colour)
        return self

    def circle(self, x, y, radius, colour=1, fill=False):
        """
        Draw a circle at the specified co-ordinates

        Args:
            x (int)      The centre X co-ordinate in the range 0 - 127
            y (int)      The centre Y co-ordinate in the range 0 - 32 or 64, depending on model
            radius (int) The radius of the circle
            colour (int) The colour of the pixel: 1 for set, 0 for clear. Default: 1
            fill (bool)  Should the circle be solid (true) or outline (false). Default: false

        Returns:
            The instance (self)
        """
        for i in range(180):
            a = x - int(radius * self.SIN_TABLE[i])
            b = y - int(radius * self.COS_TABLE[i])
            # plot() handles off-screen plotting
            self.plot(a, b, colour)
            if fill:
                if a > x:
                    j = x
                    while j < a and j < self.width:
                        self.plot(j, b, colour)
                        j += 1
                else:
                    j = a + 1
                    while j <= x:
                        self.plot(j, b, colour)
                        j += 1
        return self

    def rect(self, x, y, width, height, colour=1, fill=False):
        """
        Draw a rectangle at the specified co-ordinates

        Args:
            x      (int)  The start X co-ordinate in the range 0 - 127
            y      (int)  The start Y co-ordinate in the range 0 - 32 or 64, depending on model
            width  (int)  The width of the rectangle
            height (int)  The height of the rectangle
            fill   (bool) Should the rectangle be solid (true) or outline (false). Default: false

        Returns:
            The instance (self)
        """
        # Make sure we only draw on the screen
        x = max(x, 0)
        y = max(y, 0)
        if x + width > self.width: width = self.width - x
        if y + height > self.height: height = self.height - y
        if colour not in (0, 1): colour = 1
        for i in range(y, y + height):
            for j in range(x, x + width):
                self.plot(j, i, colour)
                if fill is False and x < j < x + width - 1 and y < i < y + height - 1:
                    self.plot(j, i, 0)
        return self

    def text(self, print_string, do_wrap=True):
        """
        Write a line of text at the current cursor co-ordinates

        Args:
            print_string (string) The text to print

        Returns:
            The display object
        """
        assert len(print_string) > 0, "ERROR - Zero-length string passed to text()"
        return self._draw_text(print_string, do_wrap, False)


    def text_2x(self, print_string, do_wrap=True):
        """
        Write a line of double-size text at the current cursor co-ordinates

        Args:
            print_string (string) The text to print

        Returns:
            The display object
        """
        assert len(print_string) > 0, "ERROR - Zero-length string passed to text_2x()"
        return self._draw_text(print_string, do_wrap, True)

    def length_of_string(self, print_string):
        """
        Calculate the length in pixels of a proportionally spaced string

        Args:
            print_string (string) The text to print

        Returns:
            The string's length in pixels
        """
        length = 0
        if len(print_string) > 0:
            for i in range(0, len(print_string)):
                asc = ord(print_string[i]) - 32
                glyph = self.CHARSET[asc]
                length += (len(glyph) + 1)
        return length

    def clear(self):
        """
        Clears the display buffer by creating a new one

        Returns:
            The display object
        """
        for i in range(len(self.buffer)): self.buffer[i] = 0x00
        return self

    def draw(self):
        """
        Draw the current buffer contents on the screen
        """
        self._render()

    # ********** PRIVATE METHODS **********

    def _render(self):
        """
        Write the display buffer out to I2C
        """
        buffer = bytearray(len(self.buffer) + 1)
        buffer[1:] = self.buffer
        buffer[0] = self.SSD1306_WRITETOBUFFER
        self.i2c.writeto(self.address, bytes(buffer))

    def _coords_to_index(self, x, y):
        """
        Convert pixel co-ordinates to a bytearray index
        Calling function should check for valid co-ordinates first
        """
        return ((y >> 3) * self.width) + x

    def _index_to_coords(self, idx):
        """
        Convert bytearray index to pixel co-ordinates
        """
        y = idx >> 4
        x = idx - (y << 4)
        return (x, y)

    def _draw_text(self, the_string, do_wrap, do_double):
        """
        Generic text rendering routine
        """
        x = self.x
        y = self.y
        space_size = 4 if do_double else 1
        bit_max = 16 if do_double else 8

        for i in range(0, len(the_string)):
            glyph = self.CHARSET[ord(the_string[i]) - 32]
            col_0 = self._flip(glyph[0])

            if do_wrap:
                if x + len(glyph) * (2 if do_double else 1) >= self.width:
                    if y + bit_max < self.height:
                        x = 0
                        y += bit_max
                    else:
                        return self

            for j in range(1, len(glyph) + 1):
                if j == len(glyph):
                    if do_double: break
                    col_1 = self._flip(glyph[j - 1])
                else:
                    col_1 = self._flip(glyph[j])

                if do_double:
                    col_0_right = self._stretch(col_0)
                    col_0_left = col_0_right
                    col_1_right = self._stretch(col_1)
                    col_1_left = col_1_right

                    for a in range(6, -1, -1):
                        for b in range(1, 3):
                            if (col_0 >> a & 3 == 3 - b) and (col_1 >> a & 3 == b):
                                col_0_right |= (1 << ((a * 2) + b))
                                col_1_left |= (1 << ((a * 2) + 3 - b))

                z = (y - ((y >> 3) << 3)) - 1

                for k in range(0, bit_max):
                    if ((y + k) % 8) == 0 and k > 0:
                        z = 0
                    else:
                        z += 1

                    if do_double:
                        if x < self.width: self._char_plot(x, y, k, col_0_left, z)
                        if x + 1 < self.width: self._char_plot(x + 1, y, k, col_0_right, z)
                        if x + 2 < self.width: self._char_plot(x + 2, y, k, col_1_left, z)
                        if x + 3 < self.width: self._char_plot(x + 3, y, k, col_1_right, z)
                    else:
                        if x < self.width: self._char_plot(x, y, k, col_0, z)

                x += (2 if do_double else 1)
                if x >= self.width:
                    if not do_wrap: return self
                    if y + bit_max < self.height:
                        x = 0
                        y += bit_max
                    else:
                        break
                col_0 = col_1

            # Add spacer if we can
            if i < len(the_string) - 1:
                x += space_size
                if x >= self.width:
                    if not do_wrap: return self
                    if y + bit_max < self.height:
                        x = 0
                        y += bit_max
                    else:
                        break
        return self

    def _flip(self, value):
        """
        Rotates the character array from the saved state
        to that required by the screen orientation
        """
        flipped = 0
        for i in range (0, 8):
            if (value & (1 << i)) > 0:
                flipped += (1 << (7 - i))
        return flipped

    def _char_plot(self, x, y, k, c, a):
        """
        Write a pixel from a character glyph to the buffer
        """
        b = self._coords_to_index(x, y + k)
        if c & (1 << k) != 0: self.buffer[b] |= (1 << a)

    def _stretch(self, x):
        """
        Pixel-doubles an 8-bit value to 16 bits
        """
        x = (x & 0xF0) << 4 | (x & 0x0F)
        x = (x << 2 | x) & 0x3333
        x = (x << 1 | x) & 0x5555
        x = x | x << 1
        return x

    def draw_bitmap(self, x, y, width, colour, length, bitmap):
        # Paint the specific monochrome bitmap to the screen
        # with (x,y) the top-left co-ordinate. Zeros in the bit map are the
        # 'alpha channel', Ones are set or unset according to the value of
        # 'colour'. The value of 'length' is the number of bytes in the bitmap;
        # 'width' is the number of bytes per row in the image. Bytes are vertical,
        # with bit 0 at the top.

        # Save the left-hand co-ord
        x_start = x

        for i in range(0, length):
            # Get the column byte
            col = self._text_flip(bitmap[i])

            # Get the topmost bit (in range 0-7)
            z = (y - ((y >> 3) << 3)) - 1

            # Run through the bits in the column, setting the destination
            # bit accordingly
            for k in range(0, 8):
                if k > 0 and ((y + k) % 8) == 0:
                    z = 0
                else:
                    z += 1

                if x < self.width:
                    self.bitmap_plot(x, y, k, col, z, colour);

            # Move onto the next byte along, cycling back when we
            # get to the end of the width of the image
            x += 1
            if x >= x_start + width:
                x = x_start
                y += 8

    def bitmap_plot(self, x, y, char_bit, char_byte, byte_bit, colour):
        # Write a byte from bitmap to the screen buffer
        if x < 0 or x >= self.width: return
        if y + char_bit < 0 or y + char_bit >= self.height: return
        byte = self._coords_to_index(x, y + char_bit)

        if colour == 1:
            # Set the buffer pixel if it's set in the char byte
            if ((char_byte & (1 << char_bit)) != 0):
                self.buffer[byte] |= (1 << byte_bit)
        else:
            # Clear the buffer pixel if it's set in the char byte
            if ((char_byte & (1 << char_bit)) != 0):
                self.buffer[byte] &= ~(1 << byte_bit)

    def _text_flip(self, value):
        flipped = 0;
        for i in range(0, 8):
            if (value & (1 << i)) > 0:
                flipped += (1 << (7 - i))
        return flipped


# ********** CALENDAR FUNCTIONS **********

def is_bst(now=None):
    '''
    Convenience function for 'bstCheck()'.

    Args:
        n (tuple): An 8-tuple indicating the request date
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    '''
    return bst_check(now)


def bst_check(now=None):
    '''
    Determine whether the specified date lies within the British Summer Time period.

    Args:
        n (tuple): An 8-tuple indicating the request date
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    '''
    if now is None: now = localtime()

    if now[1] > 3 and now[1] < 10: return True

    if now[1] == 3:
        # BST starts on the last Sunday of March
        for index in range(31, 24, -1):
            if day_of_week(index, 3, now[0]) == 0 and now[2] >= index: return True

    if now[1] == 10:
        # BST ends on the last Sunday of October
        for index in range(31, 24, -1):
            if day_of_week(index, 10, now[0]) == 0 and now[2] < index: return True

    return False


def day_of_week(day, month, year):
    '''
    Determine the day of the week for a given day, month and year, using
    Zeller's Rule (see http://mathforum.org/dr.math/faq/faq.calendar.html).

    Args:
        d (int): The specified day of the month (1-31).
        m (int): The specified month (1-12).
        y (int): The specified year (including the century, ie. '2019' not '19').

    Returns:
        int: The day of the week: 0 (Monday) to 6 (Sunday).
    '''
    month -= 2
    if month < 1: month += 12
    century = int(str(year)[:2])
    year = int(str(year)[2:])
    year = year - 1 if month > 10 else year
    dow = day + int((13 * month - 1) / 5) + year + int(year / 4) + int(century / 4) - (2 * century)
    dow = dow % 7
    if dow < 0: dow += 7
    return dow


def is_leap_year(year):
    '''
    Is the current year a leap year?

    Args:
        y (int): The year you wish to check.

    Returns:
        bool: Whether the year is a leap year (True) or not (False).
    '''
    if year % 4 == 0 and (year % 100 > 0 or year % 400 == 0): return True
    return False

# ********** RTC FUNCTIONS **********

def set_rtc(epoch_val):
    global yrdy

    time_data = localtime(epoch_val)
    yrdy = time_data[7]
    # Tuple format: (year, month, mday, hour, minute, second, weekday, yearday)

    #time_data = time_data[0:3] + (0,) + time_data[3:6] + (0,)
    # Tuple format: (year, month, day, weekday, hours, minutes, seconds)
    RTC().datetime = struct_time(time_data)
    log("RTC set")

# ********** PREFS MANAGEMENT FUNCTIONS **********

def load_prefs():
    file_data = None
    try:
        with open("prefs.json", "r") as file:
            file_data = file.read()
    except:
        log_error("No prefs file")
        return

    if file_data != None:
        try:
            data = json.loads(file_data)
            set_prefs(data)
            set_rtc(prefs["epoch"])
        except ValueError:
            log_error("Prefs JSON decode error")


def set_prefs(prefs_data):
    '''
    Set the clock's preferences to reflect the specified object's contents.
    '''
    global prefs
    if "mode" in prefs_data: prefs["mode"] = prefs_data["mode"]
    if "colon" in prefs_data: prefs["colon"] = prefs_data["colon"]
    if "flash" in prefs_data: prefs["flash"] = prefs_data["flash"]
    if "bright" in prefs_data: prefs["bright"] = prefs_data["bright"]
    if "on" in prefs_data: prefs["on"] = prefs_data["on"]
    if "epoch" in prefs_data: prefs["epoch"] = prefs_data["epoch"]


def save_prefs():
    '''
    Write the current prefs to Flash.
    '''
    global prefs

    if display_present:
        try:
            json_prefs = json.dumps(prefs)
            with open("prefs.json", "w") as file:
                file.write(json_prefs)
        except:
            log_error("Prefs JSON save error")


def default_prefs():
    '''
    Set the clock's default preferences.
    '''
    global prefs
    prefs = {}
    prefs["mode"] = True
    prefs["colon"] = True
    prefs["flash"] = True
    prefs["bright"] = 10
    prefs["bst"] = True
    prefs["on"] = True
    prefs["epoch"] = 0

# ********** CLOCK MANAGEMENT FUNCTIONS **********

def clock(timecheck=False):
    '''
    The primary clock routine: in infinite loop that displays the time
    from the UTC every pass and flips the display's central colon every
    second.
    NOTE The code calls 'isBST()' to determine if we are in British Summer Time.
         You will need to alter that call if you use some other form of daylight
         savings calculation.
    '''
    global prefs

    mode = prefs["mode"]

    while True:
        now = localtime()
        now_hour = now[3]
        now_min = now[4]
        now_sec = now[5]

        if prefs["bst"] is True and is_bst() is True:
            now_hour += 1
        if now_hour > 23: now_hour -= 23

        is_pm = False
        if now_hour > 11: is_pm = True

        # Calculate and set the hours digits
        hour = now_hour
        if mode is False:
            if is_pm is True: hour -= 12
            if hour == 0: hour = 12

        # Display the hour
        # The decimal point by the first digit is used to indicate connection status
        # (lit if the clock is disconnected)
        decimal = bcd(hour)
        n = 0
        if display_present:
            if mode is False and hour < 10:
                n = SSD1306OLED.NUMBERS[0]
            else:
                n = SSD1306OLED.NUMBERS[decimal >> 4]
        
            matrix.draw_bitmap(8, 7, 16, 1, len(n), n)
            n = SSD1306OLED.NUMBERS[decimal & 0x0F]
            matrix.draw_bitmap(32, 7, 16, 1, len(n), n)

            # Display the minute
            # The decimal point by the last digit is used to indicate AM/PM,
            # but only for the 12-hour clock mode (mode == False)
            decimal = bcd(now_min)
            n = SSD1306OLED.NUMBERS[decimal >> 4]
            matrix.draw_bitmap(79, 7, 16, 1, len(n), n)
            n = SSD1306OLED.NUMBERS[decimal & 0x0F]
            matrix.draw_bitmap(103, 7, 16, 1, len(n), n)

            if mode is False:
                if is_pm:
                    matrix.move(122, 24).text("P")
                else:
                    matrix.move(122, 24).text("A")

            # Set the colon and present the display
            if prefs["colon"]:
                matrix.rect(60, 7, 8, 8, 1, True)
                matrix.rect(60, 23, 8, 8, 1, True)

            # Display the time if the BOOT button is pressed
            if show_time_button.value == False:
                matrix.draw()
            else:
                matrix.clear().draw()

        # Every hour dump the RTC in case of resets
        if (1 < now_min < 10) and timecheck is False:
            rtc_time = localtime()
            prefs["epoch"] = int(mktime(rtc_time))
            save_prefs()
            timecheck = True

        # Reset the 'do check' flag every other hour
        if now_min > 10: timecheck = False

        sleep(0.001)

# ********** LOGGING FUNCTIONS **********

def log_error(msg, error_code=0):
    '''
    Log an error message
    '''
    if error_code > 0:
        msg = "[ERROR] {} ({})".format(msg, error_code)
    else:
        msg = "[ERROR] {}".format(msg)
    log(msg)


def log_debug(msg):
    log("[DEBUG] {}".format(msg))


def log(msg):
    if display_present:
        now = localtime()
        with open("log.txt", "a") as file:
            file.write("{}-{}-{} {}:{}:{} {}\n".format(now[0], now[1], now[2], now[3], now[4], now[5], msg))

# ********** MISC FUNCTIONS **********

def bcd(bin_value):
    for i in range(0, 8):
        bin_value = bin_value << 1
        if i == 7: break
        if (bin_value & 0xF00) > 0x4FF: bin_value += 0x300
        if (bin_value & 0xF000) > 0x4FFF: bin_value += 0x3000
    return (bin_value >> 8) & 0xFF

# ********** RUNTIME START **********

if __name__ == '__main__':
    # Set default prefs
    default_prefs()

    # Load non-default prefs, if any
    load_prefs()

    # We're not using a matrix, but use the term for code consistency
    # Set up I2C
    i2c = busio.I2C(board.SCL, board.SDA)
    while not i2c.try_lock():
        pass
    
    devices = i2c.scan()
    display_present = False
    if len(devices) > 0:
        for device in devices:
            if int(device) == 0x3C:
                display_present = True
                break
    
    if display_present:
        matrix = SSD1306OLED(i2c)
        matrix.clear().draw()

    # Config the button -- this will be pressed to show the time
    show_time_button = DigitalInOut(board.BUTTON)
    show_time_button.direction = Direction.INPUT
    show_time_button.pull = Pull.UP

    # Start the clock loop
    clock(False)
