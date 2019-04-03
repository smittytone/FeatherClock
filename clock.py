from micropython import const
from ntptime import settime
from machine import I2C, Pin
import utime
import network


HT16K33_BLINK_CMD        = const(0x80)
HT16K33_BLINK_DISPLAY_ON = const(0x01)
HT16K33_CMD_BRIGHTNESS   = const(0xE0)
HT16K33_SYSTEM_ON        = const(0x21)
HT16K33_COLON_ROW        = const(0x04)

NUMBERS = b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x77\x7C\x39\x5E\x79\x71\x40'


class HT16K33Segment:

    # Display positions in the buffer
    pos = [0, 2, 6, 8]

    def __init__(self, i2c, address=0x70):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(16)
        self.writeCmd(HT16K33_SYSTEM_ON)
        self.setBlinkRate()
        self.setBrightness(15)

    def setBlinkRate(self, rate=0):
        rates = (0, 2, 1, 0.5)
        if not rate in rates: return
        rate = rate & 0x03
        self.blinkrate = rate
        self.writeCmd(HT16K33_BLINK_CMD | HT16K33_BLINK_DISPLAY_ON | rate << 1)

    def setBrightness(self, brightness):
        if brightness < 0 or brightness > 15: brightness = 15
        self.brightness = brightness & 0x0F
        self._write_cmd(HT16K33_CMD_BRIGHTNESS | self.brightness)

    def setGlyph(self, glyph, index=0, hasDot=False):
        self.buffer[index] = glyph
        if hasDot is True: self.buffer[index] |= 0b10000000

    def setNumber(self, number, index=0, hasDot=False):
        self.setChar(str(number), index, hasDot)

    def setChar(self, char, index=0, hasDot=False):
        if not 0 <= index <= 3: return
        char = char.lower()
        if char in 'abcdef':
            c = ord(char) - 87
        elif char == '-':
            c = 16
        elif char in '0123456789':
            c = ord(char) - 48
        elif char == ' ':
            c = 0x00
        else:
            return

        self.buffer[self.pos[index]] = NUMBERS[c]
        if hasDot is True: self.buffer[self.pos[index]] |= 0b10000000

    def setColon(self, isSet=True):
        self.buffer[HT16K33_COLON_ROW] = 0x02 if isSet is True else 0x00

    def clear(self):
        for i in range(16): self.buffer[i] = 0x00

    def update(self):
        self.i2c.writeto_mem(self.address, 0x00, self.buffer)

    def writeCmd(self, byte):
        temp = bytearray(1)
        temp[0] = byte
        self.i2c.writeto(self.address, temp)


def isBST(n=None):
    return bstCheck(n)


def bstCheck(n=None):
    if n == None: n = utime.localtime()
    if n[1] > 3 and n[2] < 10: return True

    if n[1] == 3:
        # BST starts on the last Sunday of March
        for i in range(31, 24, -1):
            if dayOfWeek(i, 3, n[0]) == 0 and n[3] >= i: return True

    if n[1] == 10:
        # BST ends on the last Sunday of October
        for i in range(31, 24, -1):
            if dayOfWeek(i, 10, n[0]) == 0 and n[3] < i): return True

    return False


def dayOfWeek(d, m, y):
        # Use Zeller's Rule - http://mathforum.org/dr.math/faq/faq.calendar.html
        m -= 2
        if m < 1: m += 12
        e = int(str(y)[2:])
        s = int(str(y)[:2])
        t = e - 1 if m > 10 else e
        f = d + int((13 * m - 1) / 5) + t + int(t / 4) + int(s / 4) - (2 * s)
        f = f % 7
        if f < 0: f += 7
        return f
    }


def isLeapYear(y):
    if y % 4 == 0 and (y % 100 > 0 or y % 400 == 0): return True
    return False


def connect():
    state = True
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect('@SSID', '@PASS')
        while not wlan.isconnected():
            utime.sleep(0.5)
            matrix.setChar('c', 3, state)
            matrix.update()
            state = not state

    settime()
    matrix.clear()
    clock()


def clock():
    mode = False

    while True:
        now = utime.localtime()
        hour = now[3]
        min  = now[4]
        sec  = now[5]

        if isBST(now): hour += 1
        if hour > 23: hour =- 23

        pm = False
        if hour > 11: pm = True

        if min < 10:
            matrix.setNumber(0, 2, False)
            matrix.setNumber(min, 3, pm)
        else:
            a = int(min / 10)
            b = min - (a * 10)
            matrix.setNumber(a, 2, False)
            matrix.setNumber(b, 3, pm)

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

        matrix.setColon(sec % 2 == 0)
        matrix.update()


def syncText():
    matrix.clear()
    pos = [0, 2, 6, 8]
    sync = b'\x6D\x6E\x37\x39'
    for i in range(0, 4):
        matrix.setGlyph(pos[i], sync[i])
    matrix.update()


i2c = I2C(scl=Pin(5), sda=Pin(4))
matrix = HT16K33Segment(i2c)
matrix.setBrightness(10)

syncText()
connect()