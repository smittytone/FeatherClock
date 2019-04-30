"""
Clock.py - a very simple four-digit timepiece

Version:   1.0.7
Author:    smittytone
Copyright: 2019, Tony Smith
Licence:   MIT
"""

"""
Imports
"""
import usocket as socket
import ustruct as struct
import ujson as json
import network
from micropython import const
from machine     import I2C, Pin, RTC
from utime       import localtime, sleep


"""
Constants
(see http://docs.micropython.org/en/latest/reference/speed_python.html#the-const-declaration)
"""
_HT16K33_BLINK_CMD = const(0x80)
_HT16K33_BLINK_DISPLAY_ON = const(0x01)
_HT16K33_CMD_BRIGHTNESS = const(0xE0)
_HT16K33_SYSTEM_ON = const(0x21)
_HT16K33_COLON_ROW = const(0x04)
_HT16K33_MINUS_CHAR = const(0x10)
_HT16K33_DEGREE_CHAR = const(0x11)


class HT16K33Segment:
    """
    A simple driver for the I2C-connected Holtek HT16K33 controller chip and a four-digit,
    seven-segment LED connected to it. For example: https://learn.adafruit.com/adafruit-7-segment-led-featherwings/overview
    """

    # The positions of the segments within the buffer
    pos = [0, 2, 6, 8]

    # Bytearray of the key alphanumeric characters we can show:
    # 0-9, A-F, minus, degree
    chars = b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x5F\x7C\x58\x5E\x7B\x71\x40\x63'


    def __init__(self, i2c, address=0x70):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(16)
        self._write_cmd(_HT16K33_SYSTEM_ON)
        self.set_blink_rate()
        self.set_brightness(15)

    def set_blink_rate(self, rate=0):
        """
        Set the display's flash rate.

        Only four values (in Hz) are permitted: 0, 2, 1, and 0,5.

        Args:
            rate (int): The chosen flash rate. Default: 0Hz.
        """
        rates = (0, 2, 1, 0.5)
        if rate not in rates: return
        rate = rate & 0x03
        self.blink_rate = rate
        self._write_cmd(_HT16K33_BLINK_CMD | _HT16K33_BLINK_DISPLAY_ON | rate << 1)

    def set_brightness(self, brightness=15):
        """
        Set the display's brightness (ie. duty cycle).

        Brightness values range from 0 (dim, but not off) to 15 (max. brightness).

        Args:
            brightness (int): The chosen flash rate. Default: 15 (100%).
        """
        if brightness < 0 or brightness > 15: brightness = 15
        brightness = brightness & 0x0F
        self.brightness = brightness
        self._write_cmd(_HT16K33_CMD_BRIGHTNESS | brightness)

    def set_glyph(self, glyph, digit=0, has_dot=False):
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
            has_dot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        if not 0 <= digit <= 3: return
        self.buffer[self.pos[digit]] = glyph
        if has_dot is True: self.buffer[self.pos[digit]] |= 0b10000000

    def set_number(self, number, digit=0, has_dot=False):
        """
        Present single decimal value (0-9) at the specified digit.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            number (int):  The number to show.
            digit (int):   The digit to show the number. Default: 0 (leftmost digit).
            has_dot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        self.set_char(str(number), digit, has_dot)

    def set_char(self, char, digit=0, has_dot=False):
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
            has_dot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.
        """
        if not 0 <= digit <= 3: return
        char = char.lower()
        if char in 'abcdef':
            char_val = ord(char) - 87
        elif char == '-':
            char_val = _HT16K33_MINUS_CHAR
        elif char in '0123456789':
            char_val = ord(char) - 48
        elif char == ' ':
            char_val = 0x00
        else:
            return

        self.buffer[self.pos[digit]] = self.chars[char_val]
        if has_dot is True: self.buffer[self.pos[digit]] |= 0b10000000

    def set_colon(self, is_set=True):
        """
        Set or unset the display's central colon symbol.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            isSet (bool): Whether the colon is lit (True) or not (False). Default: True.
        """
        self.buffer[_HT16K33_COLON_ROW] = 0x02 if is_set is True else 0x00

    def clear(self):
        """
        Clears the display.

        This method clears the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.
        """
        buff = self.buffer
        for index in range(16): buff[index] = 0x00

    def update(self):
        """
        Writes the current display buffer to the display itself.

        Call this method after clearing the buffer or writing characters to the buffer to update
        the LED.
        """
        self.i2c.writeto_mem(self.address, 0x00, self.buffer)

    def _write_cmd(self, byte):
        """
        Writes a single command to the HT16K33. A private method.

        Args:
            byte (int): The command value to send.
        """
        temp = bytearray(1)
        temp[0] = byte
        self.i2c.writeto(self.address, temp)


def is_bst(now=None):
    """
    Convenience function for 'bstCheck()'.

    Args:
        n (tuple): An 8-tuple indicating the request date
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    """
    return bst_check(now)


def bst_check(now=None):
    """
    Determine whether the specified date lies within the British Summer Time period.

    Args:
        n (tuple): An 8-tuple indicating the request date
            (see http://docs.micropython.org/en/latest/library/utime.html?highlight=localtime#utime.localtime).

    Returns:
        bool: Whether the specified date is within the BST period (true), or not (false).
    """
    if now is None: now = localtime()

    if now[1] > 3 and now[1] < 10: return True

    if now[1] == 3:
        # BST starts on the last Sunday of March
        for index in range(31, 24, -1):
            if day_of_week(index, 3, now[0]) == 0 and now[3] >= index: return True

    if now[1] == 10:
        # BST ends on the last Sunday of October
        for index in range(31, 24, -1):
            if day_of_week(index, 10, now[0]) == 0 and now[3] < index: return True

    return False


def day_of_week(day, month, year):
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
    """
    Is the current year a leap year?

    Args:
        y (int): The year you wish to check.

    Returns:
        bool: Whether the year is a leap year (True) or not (False).
    """
    if year % 4 == 0 and (year % 100 > 0 or year % 400 == 0): return True
    return False


def get_time(timeout):
    # https://github.com/micropython/micropython/blob/master/ports/esp8266/modules/ntptime.py
    # Modify the standard code to extend the timeout, and catch OSErrors triggered when the
    # socket operation times out
    ntp_query = bytearray(48)
    ntp_query[0] = 0x1b
    address = socket.getaddrinfo("pool.ntp.org", 123)[0][-1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        _ = sock.sendto(ntp_query, address)
        msg = sock.recv(48)
        sock.close()
        val = struct.unpack("!I", msg[40:44])[0]
        return val - 3155673600
    except OSError:
        sock.close()
        return None


def set_rtc(timeout=10):
    now_time = get_time(timeout)
    if now_time is not None:
        time_data = localtime(now_time)
        time_data = time_data[0:3] + (0,) + time_data[3:6] + (0,)
        RTC().datetime(time_data)
        return True
    return False


def load_prefs():
    file_data = None
    try:
        with open(".prefs.json", "r") as file: file_data = file.read()
    except:
        print("Whoops: no prefs file")
        return

    if file_data != None:
        try:
            data = json.loads(file_data)
        except ValueError:
            print("Whoops: JSON decode error")
            return
        set_prefs(data)


def set_prefs(prefs_data):
    """
    Set the clock's preferences to reflect the specified object's contents.
    """
    global prefs
    prefs["mode"] = prefs_data["mode"]
    prefs["colon"] = prefs_data["colon"]
    prefs["flash"] = prefs_data["flash"]
    prefs["bright"] = prefs_data["bright"]
    prefs["on"] = prefs_data["on"]


def get_prefs():




def default_prefs():
    """
    Set the clock's default preferences.
    """
    global prefs
    prefs = {}
    prefs["mode"] = False
    prefs["colon"] = True
    prefs["flash"] = True
    prefs["bright"] = 10
    prefs["bst"] = True
    prefs["on"] = True
    prefs["url"] = "@AGENT"


def connect():
    """
    Attempt to connect to the Internet as a station, and flash the decimal
    point at the right-side of the display while the connection is in
    progress. Upon connection, set the RTC then start the clock.
    NOTE Replace '@SSID' and '@PASS' with your own WiFi credentials.
    """
    global wout

    state = True
    wout = network.WLAN(network.STA_IF)
    wout.active(True)
    if not wout.isconnected():
        wout.connect("@SSID", "@PASS")
        while not wout.isconnected():
            sleep(0.5)
            matrix.set_glyph(0x39, 3, state)
            matrix.update()
            state = not state

    # Connection succeeded, so set the RTC
    matrix.set_glyph(0x39, 3, True)
    timecheck = set_rtc(30)
    #get_prefs(30)

    # Clear the display and start the clock loop
    matrix.clear()
    clock(timecheck)


def clock(timecheck):
    """
    The primary clock routine: in infinite loop that displays the time
    from the UTC every pass and flips the display's central colon every
    second.
    NOTE The code calls 'isBST()' to determine if we are in British Summer Time.
         You will need to alter that call if you use some other form of daylight
         savings calculation.
    """

    mode = prefs["mode"]

    while True:
        now = localtime()
        now_hour = now[3]
        now_min = now[4]
        now_sec = now[5]

        if prefs["bst"] is True:
            if is_bst(): now_hour += 1
        if now_hour > 23: now_hour -= 23

        is_pm = False
        if now_hour > 11: is_pm = True

        # Calculate and set the minutes digits
        # NOTE digit three's decimal point is use to indicate AM/PM
        if now_min < 10:
            matrix.set_number(0, 2, False)
            matrix.set_number(now_min, 3, is_pm)
        else:
            digit_a = int(now_min / 10)
            digit_b = now_min - (digit_a * 10)
            matrix.set_number(digit_a, 2, False)
            matrix.set_number(digit_b, 3, is_pm)

        # Calculate and set the hours digits
        hour = now_hour
        if mode is False:
            if is_pm is True: hour -= 12
            if hour == 0: hour = 12

        # NOTE digit zero's decimal point is use to indicate disconnection
        if hour < 10:
            matrix.set_number(hour, 1, False)
            if mode is False:
                matrix.set_glyph(0, 0, not wout.isconnected())
            else:
                matrix.set_char('0', 0, not wout.isconnected())
        else:
            digit_a = int(hour / 10)
            digit_b = hour - (digit_a * 10)
            matrix.set_number(digit_a, 0, not wout.isconnected())
            matrix.set_number(digit_b, 1, False)

        # Set the colon and present the display
        if prefs["colon"] is True:
            if prefs["flash"] is True:
                matrix.set_colon(now_sec % 2 == 0)
            else:
                matrix.set_colon(True)
        else:
            matrix.set_colon(True)
        matrix.update()

        # Every two hours re-sync the RTC
        # (which is poor, see http://docs.micropython.org/en/latest/esp8266/general.html#real-time-clock)
        if now_hour % 2 == 0 and wout.isconnected() and timecheck is False:
            timecheck = set_rtc()
        # Reset the 'do check' flag every other hour
        if now_hour % 2 > 0: timecheck = False


def sync_text():
    """
    This function displays the text 'SYNC' on the display while the
    newly booted clock is connecting to the Internet and getting the
    current time.
    """
    matrix.clear()
    sync = b'\x6D\x6E\x37\x39'
    for i in range(0, 4): matrix.set_glyph(sync[i], i)
    matrix.update()


"""
This is the simple runtime start point.
Set up the display on I2C
"""
prefs = None
wout = None

# Set default prefs
default_prefs()

# Load non-default prefs, if any
load_prefs()

# Initialize hardware
i2c = I2C(scl=Pin(5), sda=Pin(4))
matrix = HT16K33Segment(i2c)
matrix.set_brightness(prefs["bright"])

# Display 'sync' on the display while connecting,
# and attempt to connect
sync_text()
connect()