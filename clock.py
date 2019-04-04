"""
Imports
"""
from micropython import const
from ntptime     import settime
from machine     import I2C, Pin
from utime       import localtime, sleep
import network

"""
Constants
(see http://docs.micropython.org/en/latest/reference/speed_python.html#the-const-declaration)
"""
HT16K33_BLINK_CMD        = const(0x80)
HT16K33_BLINK_DISPLAY_ON = const(0x01)
HT16K33_CMD_BRIGHTNESS   = const(0xE0)
HT16K33_SYSTEM_ON        = const(0x21)
HT16K33_COLON_ROW        = const(0x04)
HT16K33_MINUS_CHAR       = const(0x10)
HT16K33_DEGREE_CHAR      = const(0x11)

"""
Bytearray of the key alphanumeric characters we can show:
    0-9, A-F, minus, degree
"""
HT16K33_CHARS = b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x5F\x7C\x58\x5E\x7B\x71\x40\x63'


class HT16K33Segment:
    """
    A simple driver for the I2C-connected Holtek HT16K33 controller chip and a four-digit, 
    seven-segment LED connected to it. For example: https://learn.adafruit.com/adafruit-7-segment-led-featherwings/overview
    """

    # The positions of the segments within the buffer
    pos = [0, 2, 6, 8]

    def __init__(self, i2c, address=0x70):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(16)
        self._writeCmd(HT16K33_SYSTEM_ON)
        self.setBlinkRate()
        self.setBrightness(15)

    def setBlinkRate(self, rate=0):
        """
        Set the display's flash rate.

        Only four values (in Hz) are permitted: 0, 2, 1, and 0,5.

        Args:
            rate (int): The chosen flash rate. Default: 0Hz.
        """
        rates = (0, 2, 1, 0.5)
        if not rate in rates: return
        rate = rate & 0x03
        self.blinkrate = rate
        self._writeCmd(HT16K33_BLINK_CMD | HT16K33_BLINK_DISPLAY_ON | rate << 1)

    def setBrightness(self, brightness=15):
        """
        Set the display's brightness (ie. duty cycle).

        Brightness values range from 0 (dim, but not off) to 15 (max. brightness).

        Args:
            brightness (int): The chosen flash rate. Default: 15 (100%).
        """
        if brightness < 0 or brightness > 15: brightness = 15
        brightness = brightness & 0x0F
        self.brightness = brightness
        self._writeCmd(HT16K33_CMD_BRIGHTNESS | brightness)

    def setGlyph(self, glyph, digit=0, hasDot=False):
        """
        Present a user-defined character glyph at the specified digit.

        Glyph values are 8-bit integers representing a pattern of set LED segments.
        The value is calculated by setting the bit(s) representing the segment(s) you want illuminated.
        Bit-to-segment mapping runs clockwise from the top around the outside of the matrix; the inner segment is bit 6:
    
                0
                _
            5 |   | 1
              |   |
                - <----- 6
            4 |   | 2
              | _ |
                3

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            glyph (int):   The glyph pattern.
            digit (int):   The digit to show the glyph. Default: 0 (leftmost digit).
            hasDot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        if not 0 <= digit <= 3: return
        self.buffer[self.pos[digit]] = glyph
        if hasDot is True: self.buffer[self.pos[digit]] |= 0b10000000

    def setNumber(self, number, digit=0, hasDot=False):
        """
        Present single decimal value (0-9) at the specified digit.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            number (int):  The number to show.
            digit (int):   The digit to show the number. Default: 0 (leftmost digit).
            hasDot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        self.setChar(str(number), digit, hasDot)

    def setChar(self, char, digit=0, hasDot=False):
        """
        Present single alphanumeric character at the specified digit.

        Only characters from the class' character set are available:
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, a, b, c, d ,e, f, -, degree symbol.
        Other characters can be defined and presented using 'setGlyp()'.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            char (string): The character to show.
            digit (int):   The digit to show the number. Default: 0 (leftmost digit).
            hasDot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        if not 0 <= digit <= 3: return
        char = char.lower()
        if char in 'abcdef':
            c = ord(char) - 87
        elif char == '-':
            c = HT16K33_MINUS_CHAR
        elif char in '0123456789':
            c = ord(char) - 48
        elif char == ' ':
            c = 0x00
        else:
            return

        self.buffer[self.pos[digit]] = HT16K33_CHARS[c]
        if hasDot is True: self.buffer[self.pos[digit]] |= 0b10000000

    def setColon(self, isSet=True):
        """
        Set or unset the display's central colon symbol.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.
        
        Args:
            isSet (bool): Whether the colon is lit (True) or not (False). Default: True.
        """
        self.buffer[HT16K33_COLON_ROW] = 0x02 if isSet is True else 0x00

    def clear(self):
        """
        Clears the display.

        This method clears the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.
        """
        buff = self.buffer
        for i in range(16): buff[i] = 0x00

    def update(self):
        """
        Writes the current display buffer to the display itself.

        Call this method after clearing the buffer or writing characters to the buffer to update
        the LED.
        """
        self.i2c.writeto_mem(self.address, 0x00, self.buffer)

    def _writeCmd(self, byte):
        """
        Writes a single command to the HT16K33. A private method.

        Args:
            byte (int): The command value to send.
        """
        temp = bytearray(1)
        temp[0] = byte
        self.i2c.writeto(self.address, temp)


def isBST(n=None):
    """
    Convenience function for 'bstCheck()'.

    Args:
        n (tuple): An 8-tuple indicating the request date 
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    """
    return bstCheck(n)


def bstCheck(n=None):
    """
    Determine whether the specified date lies within the British Summer Time period.

    Args:
        n (tuple): An 8-tuple indicating the request date 
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    """
    if n == None: n = localtime()
    if n[1] > 3 and n[2] < 10: return True

    if n[1] == 3:
        # BST starts on the last Sunday of March
        for i in range(31, 24, -1):
            if dayOfWeek(i, 3, n[0]) == 0 and n[3] >= i: return True

    if n[1] == 10:
        # BST ends on the last Sunday of October
        for i in range(31, 24, -1):
            if dayOfWeek(i, 10, n[0]) == 0 and n[3] < i: return True

    return False


def dayOfWeek(d, m, y):
    """
    Determine the day of the week for a given day, month and year, using
    Zeller's Rule (see http://mathforum.org/dr.math/faq/faq.calendar.html).

    Args:
        d (int): The specified day of the month (1-31).
        m (int): The specified month (1-12).
        y (int): The specified year (including the century, ie. '2019' not '19').

    Returns:
        int: The day of the week: 0 (Monday) to 6 (Sunday).
    """
    m -= 2
    if m < 1: m += 12
    e = int(str(y)[2:])
    s = int(str(y)[:2])
    t = e - 1 if m > 10 else e
    f = d + int((13 * m - 1) / 5) + t + int(t / 4) + int(s / 4) - (2 * s)
    f = f % 7
    if f < 0: f += 7
    return f


def isLeapYear(y):
    """
    Is the current year a leap year?

    Args:
        y (int): The year you wish to check.

    Returns:
        bool: Whether the year is a leap year (True) or not (False).
    """
    if y % 4 == 0 and (y % 100 > 0 or y % 400 == 0): return True
    return False


def connect():
    """
    Attempt to connect to the Internet as a station, and flash the decimal
    point at the right-side of the display while the connection is in
    progress. Upon connection, set the RTC then start the clock.
    NOTE Replace '@SSID' and '@PASS' with your own WiFi credentials.
    """
    state = True
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect('@SSID', '@PASS')
        while not wlan.isconnected():
            sleep(0.5)
            matrix.setGlyph(0x39, 3, state)
            matrix.update()
            state = not state

    # Connection succeeded, so set the RTC
    settime()

    # Clear the display and start the clock loop
    matrix.clear()
    clock()


def clock():
    """
    The primary clock routine: in infinite loop that displays the time
    from the UTC every pass and flips the display's central colon every
    second. 
    NOTE #1 Change 'mode' to True for 24-hour clock, or False for a 12-hour clock.
            TODO Make this an externally accessible setting.
    NOTE #2 The code calls 'isBST()' to determine if we are in British Summer Time.
            You will need to alter that call if you use some other form of daylight
            savings calculation.
    """
    mode = False

    while True:
        now = localtime()
        hour = now[3]
        min  = now[4]
        sec  = now[5]

        if isBST(now): hour += 1
        if hour > 23: hour =- 23

        pm = False
        if hour > 11: pm = True
        
        # Calculate and set the minutes digits
        if min < 10:
            matrix.setNumber(0, 2, False)
            matrix.setNumber(min, 3, pm)
        else:
            a = int(min / 10)
            b = min - (a * 10)
            matrix.setNumber(a, 2, False)
            matrix.setNumber(b, 3, pm)

        # Calculate and set the hours digits
        h = hour
        if mode is False:
            if pm is True: h = h - 12
            if h == 0: h = 12

        if h < 10:
            matrix.setNumber(h, 1, False)
            matrix.setChar((' ' if mode is False else '0'), 0, False)
        else:
            a = int(h / 10)
            b = h - (a * 10)
            matrix.setNumber(b, 1, False)
            matrix.setNumber(a, 0, (pm if mode is False else False))

        # Set the colon and present the display
        matrix.setColon(sec % 2 == 0)
        matrix.update()


def syncText():
    """
    This function displays the text 'SYNC' on the display while the 
    newly booted clock is connecting to the Internet and getting the
    current time.
    """
    matrix.clear()
    sync = b'\x6D\x6E\x37\x39'
    for i in range(0, 4): matrix.setGlyph(sync[i], i)
    matrix.update()


"""
This is the simple runtime start point.
Set up the display on I2C
"""
i2c = I2C(scl=Pin(5), sda=Pin(4))
matrix = HT16K33Segment(i2c)
matrix.setBrightness(10)

# Display 'sync' on the display while connecting,
# and attempt to connect
syncText()
connect()