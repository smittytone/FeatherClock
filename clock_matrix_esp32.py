'''
Clock Matrix ESP32 - a very simple four-digit timepiece

Version:   1.4.0
Author:    smittytone
Copyright: 2025, Tony Smith
Licence:   MIT
'''

# ********** IMPORTS **********

import usocket as socket
import ustruct as struct
import urequests as requests
import ujson as json
import network
import sys
from micropython import const
from machine import I2C, Pin, RTC, soft_reset
from utime import gmtime, sleep, time

# ********** GLOBALS **********

prefs = None
wout = None
ow = None
mat_led = None
saved_temp = 0
LOG_PATH = "log.txt"

# ********** CLASSES **********

class HT16K33:
    """
    A simple, generic driver for the I2C-connected Holtek HT16K33 controller chip.
    This release supports MicroPython and CircuitPython

    Bus:        I2C
    Author:     Tony Smith (@smittytone)
    License:    MIT
    Copyright:  2025
    """

    # *********** CONSTANTS **********

    HT16K33_GENERIC_DISPLAY_ON = 0x81
    HT16K33_GENERIC_DISPLAY_OFF = 0x80
    HT16K33_GENERIC_SYSTEM_ON = 0x21
    HT16K33_GENERIC_SYSTEM_OFF = 0x20
    HT16K33_GENERIC_DISPLAY_ADDRESS = 0x00
    HT16K33_GENERIC_CMD_BRIGHTNESS = 0xE0
    HT16K33_GENERIC_CMD_BLINK = 0x81

    # *********** PRIVATE PROPERTIES **********

    i2c = None
    tx_buffer = None
    src_buffer = None
    address = 0
    brightness = 15
    flash_rate = 0
    blink_rate = 0
    # HT16K33 Row pin to LED column mapping. Default: 1:1
    map = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    # *********** CONSTRUCTOR **********

    def __init__(self, i2c, i2c_address, map=None):
        assert 0x00 <= i2c_address < 0x80, "ERROR - Invalid I2C address in HT16K33()"
        self.i2c = i2c
        self.address = i2c_address
        self.tx_buffer = bytearray(33)
        self.src_buffer = bytearray(32)
        if map is not None:
            assert len(map) == 16, "ERROR - Invalid map size (should be 16) in HT16K33()"
            self.map = map
        self.power_on()

    # *********** PUBLIC METHODS **********

    def set_blink_rate(self, rate=0):
        """
        Set the display's flash rate.

        Only four values (in Hz) are permitted: 0, 2, 1, and 0.5.

        Args:
            rate (int): The chosen flash rate. Default: 0Hz (no flash).
        """
        allowed_rates = (0, 2, 1, 0.5)
        assert rate in allowed_rates, "ERROR - Invalid blink rate set in set_blink_rate()"
        self.blink_rate = allowed_rates.index(rate) & 0x03
        self._write_cmd(self.HT16K33_GENERIC_CMD_BLINK | self.blink_rate << 1)

    def set_brightness(self, brightness=15):
        """
        Set the display's brightness (ie. duty cycle).

        Brightness values range from 0 (dim, but not off) to 15 (max. brightness).

        Args:
            brightness (int): The chosen flash rate. Default: 15 (100%).
        """
        if brightness < 0 or brightness > 15: brightness = 15
        self.brightness = brightness
        self._write_cmd(self.HT16K33_GENERIC_CMD_BRIGHTNESS | brightness)

    def draw(self):
        """
        Writes the current display buffer to the display itself.

        Call this method after updating the buffer to update
        the LED itself.
        """
        self._render()

    def update(self):
        """
        Alternative for draw() for backwards compatibility
        """
        self._render()

    def clear(self):
        """
        Clear the buffer.

        Returns:
            The instance (self)
        """
        for i in range(0, len(self.buffer)): self.buffer[i] = 0x00
        return self

    def power_on(self):
        """
        Power on the controller and display.
        """
        self._write_cmd(self.HT16K33_GENERIC_SYSTEM_ON)
        self._write_cmd(self.HT16K33_GENERIC_DISPLAY_ON)

    def power_off(self):
        """
        Power on the controller and display.
        """
        self._write_cmd(self.HT16K33_GENERIC_DISPLAY_OFF)
        self._write_cmd(self.HT16K33_GENERIC_SYSTEM_OFF)

    # ********** PRIVATE METHODS **********

    def _render(self):
        """
        Write the display buffer out to I2C
        """
        if len(self.buffer) == 8:
            for i in range(0,8):
                self.src_buffer[i * 2] = self.buffer[i]
        else:
            for i in range(0,len(self.buffer)):
                self.src_buffer[i] = self.buffer[i]
        # Apply mapping
        for i in range(1,32,2):
            k = self._map_word((self.src_buffer[i] << 8) | self.src_buffer[i - 1])
            self.tx_buffer[i] = k & 0xFF
            self.tx_buffer[i + 1] = (k >> 8) & 0xFF
        self.i2c.writeto(self.address, bytes(self.tx_buffer))

    def _write_cmd(self, byte):
        """
        Writes a single command to the HT16K33. A private method.
        """
        self.i2c.writeto(self.address, bytes([byte]))

    def _map_word(self, bb):
        k = 0
        for i in range(0,16):
            bit = (bb & (1 << i)) >> i
            value = (bit << self.map[i])
            k |= value
        return k

class HT16K33MatrixFeatherWing(HT16K33):
    """
    Micro/Circuit Python class for the Adafruit 0.8-in 16x8 LED matrix FeatherWing.

    Bus:        I2C
    Author:     Tony Smith (@smittytone)
    License:    MIT
    Copyright:  2025
    """

    # *********** CONSTANTS **********

    CHARSET = [
        b"\x7C\x82\x7C",    # 0
        b"\x42\xFE\x02",    # 1
        b"\x4E\x92\x62",    # 2
        b"\x44\x92\x6C",    # 3
        b"\xF0\x08\x3E",    # 4
        b"\x62\x92\x8E",    # 5
        b"\x7C\x92\x0C",    # 6
        b"\x8E\x90\xE0",    # 7
        b"\x6C\x92\x6C",    # 8
        b"\x60\x92\x7C",    # 9
        b"\x00\x00\x00"     # space
    ]

    # ********** PRIVATE PROPERTIES **********

    width = 16
    height = 8
    def_chars = None
    is_inverse = False

    # *********** CONSTRUCTOR **********

    def __init__(self, i2c, i2c_address=0x70):
        self.buffer = bytearray(self.width * 2)
        self.def_chars = []
        for i in range(32): self.def_chars.append(b"\x00")
        super(HT16K33MatrixFeatherWing, self).__init__(i2c, i2c_address)

    # *********** PUBLIC METHODS **********

    def set_inverse(self):
        """
        Inverts the ink colour of the display

        Returns:
            The instance (self)
        """
        self.is_inverse = not self.is_inverse
        for i in range(self.width * 2):
            self.buffer[i] = (~ self.buffer[i]) & 0xFF
        return self

    def set_icon(self, glyph, column=0):
        """
        Present a user-defined character glyph at the specified digit.

        Glyph values are byte arrays of eight 8-bit values.
        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'draw()' to render the buffer on the display.

        Args:
            glyph (bytearray) The glyph pattern.
            column (int)      The column at which to write the icon. Default: 0

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert 0 < len(glyph) <= self.width * 2, "ERROR - Invalid glyph set in set_icon()"
        assert 0 <= column < self.width, "ERROR - Invalid column number set in set_icon()"

        for i in range(len(glyph)):
            buf_column = self._get_row(column + i)
            if buf_column is False: break
            self.buffer[buf_column] = glyph[i] if self.is_inverse is False else ((~ glyph[i]) & 0xFF)
        return self

    def set_character(self, ascii_value=32, column=0):
        """
        Display a single character specified by its Ascii value on the matrix.

        Args:
            ascii_value (int) Character Ascii code. Default: 32 (space)
            column (int)      Whether the icon should be displayed centred on the screen. Default: False

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert 0 <= ascii_value < 128, "ERROR - Invalid ascii code set in set_character()"
        assert 0 <= column < self.width, "ERROR - Invalid column number set in set_icon()"

        glyph = None
        if ascii_value < 32:
            # A user-definable character has been chosen
            glyph = self.def_chars[ascii_value]
        else:
            # A standard character has been chosen
            ascii_value -= 32
            if ascii_value < 0 or ascii_value >= len(self.CHARSET): ascii_value = 0
            glyph = self.CHARSET[ascii_value]
        return self.set_icon(glyph, column)

    def scroll_text(self, the_line, speed=0.1):
        """
        Scroll the specified line of text leftwards across the display.

        Args:
            the_line (string) The string to display
            speed (float)     The delay between frames
        """
        # Import the time library as we use time.sleep() here
        import time

        # Bail on zero string length
        assert len(the_line) > 0, "ERROR - Invalid string set in scroll_text()"

        # Calculate the source buffer size
        length = 0
        for i in range(len(the_line)):
            asc_val = ord(the_line[i])
            if asc_val < 32:
                glyph = self.def_chars[asc_val]
            else:
                glyph = self.CHARSET[asc_val - 32]
            length += len(glyph)
            if asc_val > 32: length += 1
        src_buffer = bytearray(length)

        # Draw the string to the source buffer
        row = 0
        for i in range(len(the_line)):
            asc_val = ord(the_line[i])
            if asc_val < 32:
                glyph = self.def_chars[asc_val]
            else:
                glyph = self.CHARSET[asc_val - 32]
            for j in range(len(glyph)):
                src_buffer[row] = glyph[j] if self.is_inverse is False else ((~ glyph[j]) & 0xFF)
                row += 1
            if asc_val > 32: row += 1
        assert row == length, "ERROR - Mismatched lengths in scroll_text()"

        # Finally, a the line
        cursor = 0
        while True:
            a = cursor
            for i in range(self.width):
                self.buffer[self._get_row(i)] = src_buffer[a]
                a += 1
            self.draw()
            cursor += 1
            if cursor > length - self.width: break
            time.sleep(speed)

    def define_character(self, glyph, char_code=0):
        """
        Set a user-definable character.

        Args:
            glyph (bytearray) The glyph pattern.
            char_code (int)   The character’s ID code (0-31). Default: 0

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert 0 < len(glyph) < self.width * 2, "ERROR - Invalid glyph set in define_character()"
        assert 0 <= char_code < 32, "ERROR - Invalid character code set in define_character()"

        self.def_chars[char_code] = glyph
        return self

    def plot(self, x, y, ink=1, xor=False):
        """
        Plot a point on the matrix. (0,0) is bottom left as viewed.

        Args:
            x (integer)   X co-ordinate left to right
            y (integer)   Y co-ordinate bottom to top
            ink (integer) Pixel color: 1 = 'white', 0 = black. NOTE inverse video mode reverses this. Default: 1
            xor (bool)    Whether an underlying pixel already of color ink should be inverted. Default: False

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert (0 <= x < self.width) and (0 <= y < self.height), "ERROR - Invalid coordinate set in plot()"

        if ink not in (0, 1): ink = 1
        x2 = self._get_row(x)
        if ink == 1:
            if self.is_set(x ,y) and xor:
                self.buffer[x2] ^= (1 << y)
            else:
                if self.buffer[x2] & (1 << y) == 0: self.buffer[x2] |= (1 << y)
        else:
            if not self.is_set(x ,y) and xor:
                self.buffer[x2] ^= (1 << y)
            else:
                if self.buffer[x2] & (1 << y) != 0: self.buffer[x2] &= ~(1 << y)
        return self

    def is_set(self, x, y):
        """
        Indicate whether a pixel is set.

        Args:
            x (int) X co-ordinate left to right
            y (int) Y co-ordinate bottom to top

        Returns:
            Whether the
        """
        # Bail on incorrect row numbers or character values
        assert (0 <= x < self.width) and (0 <= y < self.height), "ERROR - Invalid coordinate set in is_set()"

        x = self._get_row(x)
        bit = (self.buffer[x] >> y) & 1
        return True if bit > 0 else False

    # ********** PRIVATE METHODS **********

    def _get_row(self, x):
        """
        Convert a column co-ordinate to its memory location
        in the FeatherWing, and return the location.
        An out-of-range value returns False
        """
        a = 1 + (x << 1)
        if x < 8: a += 15
        if a >= self.width * 2: return False
        return a

class OpenMeteo:
    '''
    This class allows you to make one of two possible calls to Open Meteo's
    API. For more information, see https://open-meteo.com/en/docs

    NOTE this class does not parse the incoming data, which is highly complex.
        It is up to your application to extract the data you require.

    Version:        0.1.0
    Author:         Tony Smith (@smittytone)
    License:        MIT
    Copyright:      2025
    '''

    # *********** CONSTANTS **********

    VERSION = "0.1.0"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    # *********Private Properties **********

    requests = None
    debug = False

    # *********** CONSTRUCTOR **********

    def __init__(self, requests_object=None, do_debug=False):
        '''
        Instantiate the class.

        Args:
            requests_object [requests] An instance of the Requests class.
            do_debug [bool             Output debug information. Default: False.
        '''
        assert requests_object is not None, \
            "[ERROR] OpenMeteo() requires a valid requests instance"
        assert do_debug is True or do_debug is False, \
            "[ERROR] OpenMeteo() requires a boolean for debug selection"

        # Set private properties
        self.debug = do_debug
        self.requests = requests_object

    # *********** PUBLIC METHODS **********

    def request_forecast(self, latitude=999.0, longitude=999.0):
        '''
        Make a request for future weather data.

        Args:
            longitude [float]   Longitude of location for which a forecast is required.
            latitude [float]    Latitude of location for which a forecast is required.

        Returns:
            The weather data.
        '''
        # Check the supplied co-ordinates
        if not self._check_coords(latitude, longitude, "request_forecast"):
            return {"error": "Co-ordinate error"}

        # Co-ordinates good, so get a forecast
        url = self.FORECAST_URL
        url += f"?latitude={latitude:.6f}&longitude={longitude:.6f}&current=temperature_2m"
        self._print_debug("Request URL: " + url)
        return self._send_request(url)

    # ********* PRIVATE FUNCTIONS - DO NOT CALL **********

    def _send_request(self, request_uri):
        '''
        Send a request to OpenMeteo.

        Args:
            request_uri [string]    The URL-encoded request to send.

        Returns:
            Dictionary containing `data` or `err` keys.
        '''
        return self._process_response(self.requests.get(request_uri))

    def _process_response(self, response):
        '''
        Process a response received from OpenMeteo.

        Args:
            response [response] The HTTPS response.

        Returns
            Dictionary containing `data` or `err` keys.
        '''
        err = ""
        data = ""

        if response.status_code != 200:
            err = "Unable to retrieve forecast data (code: " + str(response.status_code) + ")"
        else:
            try:
                # Have we valid JSON?
                data = response.json()
                data["statuscode"] = response.status_code
            except self.requests.exceptions.JSONDecodeError as exp:
                err = "Unable to decode data received from Open Weather: " + str(exp)

        response.close()

        if err:
            return {"err": err}

        return {"data": data}

    def _check_coords(self, latitude=999.0, longitude=999.0, caller="function"):
        '''
        Check that valid co-ordinates have been supplied.

        Args:
            longitude [float]   Longitude of location for which a forecast is required.
            latitude [float]    Latitude of location for which a forecast is required.
            caller [string]     The name of the calling function, for error reporting.

        Returns:
            Whether the supplied co-ordinates are valid (True) or not (False).
        '''
        err = "OpenMeteo." + caller + "() "
        try:
            longitude = float(longitude)
        except (ValueError, OverflowError):
            self._print_error(err + "can't process supplied longitude value")
            return False

        try:
            latitude = float(latitude)
        except (ValueError, OverflowError):
            self._print_error(err + "can't process supplied latitude value")
            return False

        if longitude == 999.0 or latitude == 999.0:
            self._print_error(err + "requires valid latitude/longitude co-ordinates")
            return False

        if latitude > 90.0 or latitude < -90.0:
            self._print_error(err + "latitude co-ordinate out of range")
            return False

        if longitude > 180.0 or longitude < -180.0:
            self._print_error(err + "latitude co-ordinate out of range")
            return False
        return True

    def _print_error(self, *msgs):
        '''
        Print an error message.

        Args:
            msg [string]    The error message.
        '''
        msg = "[ERROR] "
        for item in msgs: msg += item
        log(msg)

    def _print_debug(self, *msgs):
        '''
        Print a debug message.

        Args:
            msg [tuple]    One or more string components
        '''
        if self.debug:
            msg = "[DEBUG] "
            for item in msgs: msg += item
            log(msg)

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
    if now is None: now = gmtime()

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

def get_time(timeout=10):
    '''
    Modify the standard code to extend the timeout, and catch OSErrors triggered when the socket operation times out
    See https://github.com/micropython/micropython/blob/master/ports/esp8266/modules/ntptime.py
    '''
    log("Getting time")
    ntp_query = bytearray(48)
    ntp_query[0] = 0x1b
    err = 1
    return_value = None
    sock = None
    try:
        log("Getting NTP address ")
        address = socket.getaddrinfo("pool.ntp.org", 123)[0][-1]

        # Create DGRAM UDP socket
        err = 2
        log("Getting NTP socket ")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        err = 3
        log("Getting NTP data ")
        _ = sock.sendto(ntp_query, address)

        err = 4
        msg = sock.recv(48)

        err = 5
        log("Got NTP data ")
        val = struct.unpack("!I", msg[40:44])[0]
        return_value = val - 3155673600
    except BaseException:
        log_error("Could not set NTP", err)
    if sock: sock.close()
    return return_value

def set_rtc(timeout=10):
    '''
    Apply received NTP data to set the RTC
    '''
    now_time = get_time(timeout)
    if now_time:
        time_data = gmtime(now_time)
        time_data = time_data[0:3] + (0,) + time_data[3:6] + (0,)
        RTC().datetime(time_data)
        log("RTC set")
        return True
    log_error("RTC not set")
    return False

# ********** PREFERENCES FUNCTIONS **********

def load_prefs():
    '''
    Read the prefs file from disk
    '''
    file_data = None
    try:
        with open("prefs.json", "r", encoding="utf-8") as file:
            file_data = file.read()
    except FileNotFoundError:
        log_error("No prefs file")
        return
    except IOError:
        log_error("Prefs file could not be read")
        return

    if file_data is not None:
        try:
            data = json.loads(file_data)
            set_prefs(data)
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
    if "do_log" in prefs_data: prefs["do_log"] = prefs_data["do_log"]
    # FROM 1.4.0
    if "show_temp" in prefs_data:
        prefs["show_temp"] = prefs_data["show_temp"]
        if "lat" in prefs_data:
            prefs["lat"] = prefs_data["lat"]
        else:
            prefs_data["show_temp"] = False
        if "lng" in prefs_data:
            prefs["lng"] = prefs_data["lng"]
        else:
            prefs["show_temp"] = False
    if "show_date" in prefs_data:
        prefs["show_date"] = prefs_data["show_date"]

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
    prefs["url"] = "@AGENT"
    prefs["do_log"] = True
    # FROM 1.4.0
    prefs["show_date"] = True
    prefs["show_temp"] = False
    prefs["lat"] = 0.0
    prefs["lng"] = 0.0

# ********** NETWORK FUNCTIONS **********

def connect():
    '''
    Attempt to connect to the Internet as a station, and flash the decimal
    point at the right-side of the display while the connection is in
    progress. Upon connection, set the RTC then start the clock.
    NOTE Replace '@SSID' and '@PASS' with your own WiFi credentials.
         The 'install-app.sh' script does this for you
    '''
    global wout

    con_count = 0
    state = True
    if wout is None: wout = network.WLAN(network.STA_IF)
    if not wout.active(): wout.active(True)
    mat_led.plot(15, 0, 1).draw()
    log("Connecting")
    if not wout.isconnected():
        # Attempt to connect
        wout.connect("@SSID", "@PASS")
        while not wout.isconnected():
            # Flash corner decimal point during connection
            sleep(0.5)
            ink = 0 if state is True else 1
            mat_led.plot(15, 0, ink).draw()
            state = not state
            con_count += 1
            if con_count > 120:
                mat_led.plot(15, 0, False).draw()
                log("Unable to connect in 60s")
                return
    log("Connected")

def initial_connect():
    '''
    Connect at the start and get the time straight away
    '''
    connect()
    timecheck = False
    if wout.isconnected():
        timecheck = set_rtc(59)
        if prefs["show_temp"]:
            forecast = ow.request_forecast(prefs["lat"], prefs["lng"])
            process_forecast(forecast)

    # Clear the display and start the clock loop
    mat_led.clear()
    clock(timecheck)

def process_forecast(forecast):
    '''
    Extract the data we want from an incoming OpenMeteo forecast
    '''
    global saved_temp

    if "data" in forecast:
        # Get second item in array: this is the weather one hour from now
        item = forecast["data"]["current"]
        # Send the icon name to the device
        saved_temp = int(item["temperature_2m"])
    else:
        log_error(forecast["err"])

# ********** CLOCK FUNCTIONS **********

def clock(timecheck=False):
    '''
    The primary clock routine: in infinite loop that displays the time
    from the UTC every pass and flips the display's central colon every
    second.
    NOTE The code calls 'isBST()' to determine if we are in British Summer Time.
         You will need to alter that call if you use some other form of daylight
         savings calculation.
    '''

    flipped = False
    received = False
    index = 0
    flip_time = 3

    # Build an array of face display functions to call in sequence
    faces = [display_clock]
    if prefs["show_date"]: faces.append(display_date)
    if prefs["show_temp"]: faces.append(display_temperature)

    # Now begin the display cycle
    while True:
        now = gmtime()
        now_hour = now[3]
        now_min = now[4]
        now_sec = now[5]

        # FROM 1.4.0
        # Every `flip_time` seconds, flip the clock face.
        # The flag `flipped` makes sure we don't re-flip during the period
        # the temporal condition is true
        if now_sec % flip_time == 0:
            if not flipped:
                index = (index + 1) % len(faces)
                flipped = True
        else:
            flipped = False

        # Call the current clock face display function
        faces[index](now)

        # Set the disconnected marker
        ink = 0 if wout.isconnected() else 1
        mat_led.plot(15, 7, ink)

        # Every six hours re-sync the RTC
        if now_hour % 6 == 0 and (1 < now_min < 8) and timecheck is False:
            if not wout.isconnected(): connect()
            if wout.isconnected(): timecheck = set_rtc(59)

        # Reset the RTC sync flag every other hour from the above
        if now_hour % 6 > 0: timecheck = False

        # FROM 1.4.0
        # Get the outside temperature every hour
        if prefs["show_temp"] and ow is not None and now_min == 7 and not received:
            forecast = ow.request_forecast(prefs["lat"], prefs["lng"])
            process_forecast(forecast)
            received = True

        # Reset the temperature check flag every other minute from the above
        if now_min != 7: received = False

        sleep(0.05)

# ********** WEATHER FUNCTIONS **********

def display_clock(t):
    '''
    Display the current time.
    '''
    set_digit(10, 13)
    now_hour = t[3]
    now_min = t[4]
    mode = prefs["mode"]

    if prefs["bst"] is True and is_bst() is True:
        now_hour += 1
    if now_hour > 23: now_hour -= 24

    is_pm = False
    if now_hour > 11: is_pm = True

    # Calculate and set the hours digits
    hour = now_hour
    if mode is False:
        if is_pm is True: hour -= 12
        if hour == 0: hour = 12

    # Display the hour
    decimal = bcd(hour)
    first_digit = decimal >> 4
    if mode is False and hour < 10: first_digit = 10
    set_digit(first_digit, 0)
    set_digit(decimal & 0x0F, 4)

    # Display the minute
    decimal = bcd(now_min)
    set_digit(decimal >> 4, 8)
    set_digit(decimal & 0x0F, 12)

    # Set am/pm as needed
    if mode is False: mat_led.plot(15, 0, is_pm)

    # Present the display
    mat_led.draw()

def display_date(t):
    '''
    Display the current date.
    '''
    set_digit(10, 13)
    now_month = t[1]
    now_day = t[2]

    # Display the day
    # The decimal point by the first digit is used to indicate connection status
    # (lit if the clock is disconnected)
    decimal = bcd(now_day)
    if now_day < 10:
        set_digit(10, 0)
    else:
        set_digit(decimal >> 4, 0)
    set_digit(decimal & 0x0F, 4)

    # Display the month
    decimal = bcd(now_month)
    if now_month < 10:
        set_digit(10, 8)
    else:
        set_digit(decimal >> 4, 8)
    set_digit(decimal & 0x0F, 12)

    # Present the display
    mat_led.draw()

def display_temperature(_):
    '''
    Display the current temperature.
    '''
    mat_led.clear()
    mat_led.set_icon(b'\x40\x1C\x22\x14', 12)

    temp = saved_temp
    if saved_temp < 0:
        mat_led.set_icon(b'\x63\x63\x63', 0)
        temp = saved_temp * -1

    decimal = bcd(temp)
    set_digit(decimal & 0x0F, 8)
    if saved_temp < 10:
        set_digit(0, 4)
    else:
        set_digit(decimal >> 4, 4)
    mat_led.draw()

# ********** LOGGING FUNCTIONS **********

def log_error(msg, error_code=0):
    '''
    Log an error message
    '''
    if error_code > 0:
        msg = f"[ERROR] {msg} ({error_code})"
    else:
        msg = f"[ERROR] {msg}"
    log(msg, True)

def log_debug(msg):
    '''
    Log a debug message
    '''
    log(f"[DEBUG] {msg}")

def log(msg, is_err=False):
    '''
    Log a generic message
    '''
    if prefs["do_log"] or is_err:
        now = gmtime()
        with open(LOG_PATH, "a", encoding="utf-8") as append_file:
            append_file.write(f"{now[0]}-{now[1]}-{now[2]} {now[3]}:{now[4]}:{now[5]} {msg}\n")

# ********** MISC FUNCTIONS **********

def sync_text():
    '''
    This function displays the text 'SYNC' on the display while the
    newly booted clock is connecting to the Internet and getting the
    current time.
    '''
    mat_led.clear()
    sync = b'\x62\x92\x8C\x00\x30\x0E\x30\x00\x1E\x20\x1E\x00\x1C\x22\x14'
    mat_led.set_icon(sync, 0)
    mat_led.draw()

def bcd(bin_value):
    '''
    Convert an integer from 0-99 to Binary Coded Decimal
    '''
    for i in range(0, 8):
        bin_value = bin_value << 1
        if i == 7: break
        if (bin_value & 0xF00) > 0x4FF: bin_value += 0x300
        if (bin_value & 0xF000) > 0x4FFF: bin_value += 0x3000
    return (bin_value >> 8) & 0xFF

def set_digit(value, posn):
    '''
    Convenience function for applying digits to the matrix
    '''
    glyph = mat_led.CHARSET[value]
    mat_led.set_icon(glyph, posn)
    return posn + len(glyph) + 1

# ********** RUNTIME START **********

def featherclock():
    global mat_led, ow

    # Set default prefs
    default_prefs()

    # Load non-default prefs, if any
    load_prefs()

    # Set up the matrix LED display
    i2c = I2C(scl=Pin(22), sda=Pin(23))
    mat_led = HT16K33MatrixFeatherWing(i2c)
    mat_led.set_brightness(prefs["bright"])

    # Add logging
    if prefs["do_log"]:
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as file:
                pass
        except FileNotFoundError:
            with open(LOG_PATH, "w", encoding="utf-8") as file:
                file.write("FeatherCLock Log\n")
        except IOError:
            log_error("Prefs file could not be read")

    # FROM 1.4.0
    # Instantiate OpenMeteo
    if prefs["show_temp"]:
        ow = OpenMeteo(requests, True)

    # Display 'sync' on the display while connecting,
    # and attempt to connect
    sync_text()
    initial_connect()

if __name__ == '__main__':
    try:
        featherclock()
    except Exception as err:
        #err_line = sys.exc_info()[-1].tb_lineno
        #alt=sys.print_exception(err,)
        #crash=[f"Error on line {err_line}","\n",err]
        err_time=str(time())
        with open("CRASH-"+err_time+".txt", "w", encoding="utf-8") as crash_log:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(err).__name__, err.args)
            print(message)
            sys.print_exception(err, crash_log)
        # Reboot?
        #soft_reset()
