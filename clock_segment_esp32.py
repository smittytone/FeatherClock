'''
Clock Segment ESP32 - a very simple four-digit timepiece

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
seg_led = None
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
        self.tx_buffer = bytearray(17)
        self.src_buffer = bytearray(16)
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
            for i in range(0,16):
                self.src_buffer[i] = self.buffer[i]
        # Apply mapping
        for i in range(1,16,2):
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

class HT16K33Segment(HT16K33):
    """
    Micro/Circuit Python class for the Adafruit 0.56-in 4-digit,
    7-segment LED matrix backpack and equivalent Featherwing.

    Bus:        I2C
    Author:     Tony Smith (@smittytone)
    License:    MIT
    Copyright:  2025
    """

    # *********** CONSTANTS **********

    HT16K33_SEGMENT_COLON_ROW = 0x04
    HT16K33_SEGMENT_MINUS_CHAR = 0x10
    HT16K33_SEGMENT_DEGREE_CHAR = 0x11
    HT16K33_SEGMENT_SPACE_CHAR = 0x12

    # The positions of the segments within the buffer
    POS = (0, 2, 6, 8)

    # Bytearray of the key alphanumeric characters we can show:
    # 0-9, A-F, minus, degree, space
    CHARSET = b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x5F\x7C\x58\x5E\x7B\x71\x40\x63\x00'
    # FROM 4.1.0
    CHARSET_UC = b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x77\x7C\x39\x5E\x79\x71\x40\x63\x00'

    # *********** CONSTRUCTOR **********

    def __init__(self, i2c, i2c_address=0x70):
        self.buffer = bytearray(16)
        self.is_rotated = False

        # FROM 4.1.0
        self.use_uppercase = False
        self.charset = self.CHARSET

        super(HT16K33Segment, self).__init__(i2c, i2c_address)

    # *********** PUBLIC METHODS **********

    def rotate(self):
        """
        Rotate/flip the segment display.

        Returns:
            The instance (self)
        """
        self.is_rotated = not self.is_rotated
        return self

    def set_colon(self, is_set=True):
        """
        Set or unset the display's central colon symbol.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            isSet (bool): Whether the colon is lit (True) or not (False). Default: True.

        Returns:
            The instance (self)
        """
        self.buffer[self.HT16K33_SEGMENT_COLON_ROW] = 0x02 if is_set is True else 0x00
        return self

    def set_uppercase(self):
        """
        Set the character set used to display upper case alpha characters.

        FROM 4.1.0

        Returns:
            The instance (self)
        """
        return self._set_case(True)

    def set_lowercase(self):
        """
        Set the character set used to display lower case alpha characters.

        FROM 4.1.0

        Returns:
            The instance (self)
        """
        return self._set_case(False)

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

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert 0 <= digit < 4, "ERROR - Invalid digit (0-3) set in set_glyph()"
        assert 0 <= glyph < 0x80, "ERROR - Invalid glyph (0x00-0x80) set in set_glyph()"

        self.buffer[self.POS[digit]] = glyph
        if has_dot is True: self.buffer[self.POS[digit]] |= 0x80
        return self

    def set_number(self, number, digit=0, has_dot=False):
        """
        Present single decimal value (0-9) at the specified digit.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            number (int):  The number to show.
            digit (int):   The digit to show the number. Default: 0 (leftmost digit).
            has_dot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers or character values
        assert 0 <= digit < 4, "ERROR - Invalid digit (0-3) set in set_number()"
        assert 0 <= number < 10, "ERROR - Invalid value (0-9) set in set_number()"

        return self.set_character(str(number), digit, has_dot)

    def set_character(self, char, digit=0, has_dot=False):
        """
        Present single alphanumeric character at the specified digit.

        Only characters from the class' character set are available:
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, a, b, c, d ,e, f, -.
        Other characters can be defined and presented using 'set_glyph()'.

        This method updates the display buffer, but does not send the buffer to the display itself.
        Call 'update()' to render the buffer on the display.

        Args:
            char (string):  The character to show.
            digit (int):    The digit to show the number. Default: 0 (leftmost digit).
            has_dot (bool): Whether the decimal point to the right of the digit should be lit. Default: False.

        Returns:
            The instance (self)
        """
        # Bail on incorrect row numbers
        assert 0 <= digit < 4, "ERROR - Invalid digit set in set_character()"

        char = char.lower()
        char_val = 0xFF
        if char == "deg":
            char_val = self.HT16K33_SEGMENT_DEGREE_CHAR
        elif char == '-':
            char_val = self.HT16K33_SEGMENT_MINUS_CHAR
        elif char == ' ':
            char_val = self.HT16K33_SEGMENT_SPACE_CHAR
        elif char in 'abcdef':
            char_val = ord(char) - 87
        elif char in '0123456789':
            char_val = ord(char) - 48

        # Bail on incorrect character values
        assert char_val != 0xFF, "ERROR - Invalid char string set in set_character()"

        self.buffer[self.POS[digit]] = self.charset[char_val]
        if has_dot is True: self.buffer[self.POS[digit]] |= 0x80
        return self

    def draw(self):
        """
        Writes the current display buffer to the display itself.

        Call this method after updating the buffer to update
        the LED itself. Rotation handled here.
        """
        if self.is_rotated:
            # Swap digits 0,3 and 1,2
            a = self.buffer[self.POS[0]]
            self.buffer[self.POS[0]] = self.buffer[self.POS[3]]
            self.buffer[self.POS[3]] = a

            a = self.buffer[self.POS[1]]
            self.buffer[self.POS[1]] = self.buffer[self.POS[2]]
            self.buffer[self.POS[2]] = a

            # Rotate each digit
            for i in range(0, 4):
                a = self.buffer[self.POS[i]]
                b = (a & 0x07) << 3
                c = (a & 0x38) >> 3
                a &= 0xC0
                self.buffer[self.POS[i]] = a | b | c
        self._render()

    # *********** PRIVATE METHODS **********

    def _set_case(self, is_upper):
        """
        Set the character set used to display alpha characters.

        FROM 4.1.0

        Args:
            is_upper (Bool): `True` for upper case characters; `False` for lower case.

        Returns:
            The instance (self)
        """
        if self.use_uppercase is not is_upper:
            self.charset = self.CHARSET_UC if is_upper else self.CHARSET
            self.use_uppercase = is_upper
        return self

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
        with open("prefs.json", "r", encoding="utf-8") as in_file:
            file_data = in_file.read()
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
    glyph = 0x39
    if wout is None: wout = network.WLAN(network.STA_IF)
    if not wout.active(): wout.active(True)
    log("Connecting")
    if not wout.isconnected():
        # Attempt to connect
        wout.connect("@SSID", "@PASS")
        while not wout.isconnected():
            # Flash char 4's decimal point during connection
            sleep(0.5)
            seg_led.set_glyph(glyph, 3, state).draw()
            state = not state
            con_count += 1
            if con_count > 120:
                seg_led.set_glyph(glyph, 3, False).draw()
                log("Unable to connect in 60s")
                return
    seg_led.set_glyph(glyph, 3, False).draw()
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
    seg_led.clear()
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

# ********** DISPLAY FUNCTIONS **********

def display_clock(t):
    '''
    Display the current time.
    '''
    now_hour = t[3]
    now_min = t[4]
    now_sec = t[5]
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
    # The decimal point by the first digit is used to indicate connection status
    # (lit if the clock is disconnected)
    decimal = bcd(hour)
    if mode is False and hour < 10:
        seg_led.set_glyph(0, 0, not wout.isconnected())
    else:
        seg_led.set_number(decimal >> 4, 0, not wout.isconnected())
    seg_led.set_number(decimal & 0x0F, 1, False)

    # Display the minute
    # The decimal point by the last digit is used to indicate AM/PM,
    # but only for the 12-hour clock mode (mode == False)
    decimal = bcd(now_min)
    seg_led.set_number(decimal >> 4, 2, False)
    seg_led.set_number(decimal & 0x0F, 3, is_pm if mode is False else False)

    # Set the colon and present the display
    seg_led.set_colon(prefs["colon"])
    if prefs["colon"] is True and prefs["flash"] is True:
        seg_led.set_colon(now_sec % 2 == 0)
    seg_led.draw()

def display_date(t):
    '''
    Display the current date.
    '''
    now_month = t[1]
    now_day = t[2]

    # Display the day
    # The decimal point by the first digit is used to indicate connection status
    # (lit if the clock is disconnected)
    decimal = bcd(now_day)
    if now_day < 10:
        seg_led.set_glyph(0, 0, not wout.isconnected())
    else:
        seg_led.set_number(decimal >> 4, 0, not wout.isconnected())
    seg_led.set_number(decimal & 0x0F, 1, False)

    # Display the month
    decimal = bcd(now_month)
    if now_month < 10:
        seg_led.set_glyph(0, 2, False)
    else:
        seg_led.set_number(decimal >> 4, 2, False)
    seg_led.set_number(decimal & 0x0F, 3, False)

    # Set the colon and present the display
    seg_led.set_colon(False)
    seg_led.draw()

def display_temperature(_):
    '''
    Display the current temperature.
    '''
    seg_led.set_glyph(0, 0)
    seg_led.set_glyph(0x63, 3)
    seg_led.set_colon(False)

    temp = saved_temp
    if saved_temp < 0:
        seg_led.set_character("-", 0)
        temp = saved_temp * -1

    decimal = bcd(temp)
    seg_led.set_number(decimal & 0x0F, 2)
    if saved_temp < 10:
        seg_led.set_number(0, 1)
    else:
        seg_led.set_number(decimal >> 4, 1)
    seg_led.draw()

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
    seg_led.clear()
    sync = b'\x6D\x6E\x37\x39'
    for i in range(0, 4): seg_led.set_glyph(sync[i], i)
    seg_led.draw()

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

# ********** RUNTIME START **********

def featherclock():
    global seg_led, ow

    # Set default prefs
    default_prefs()

    # Load non-default prefs, if any
    load_prefs()

    # Set up the segment LED display
    i2c = I2C(scl=Pin(22), sda=Pin(23))
    seg_led = HT16K33Segment(i2c)
    seg_led.set_brightness(prefs["bright"])

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
            #template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            #message = template.format(type(err).__name__, err.args)
            #print(message)
            sys.print_exception(err, crash_log)
        # Reboot?
        #soft_reset()
