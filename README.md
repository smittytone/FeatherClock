# FeatherClock 1.0.8 #

This repo contains code written for the [Adafruit Feather HUZZAH ESP8266](https://learn.adafruit.com/adafruit-feather-huzzah-esp8266) running [MicroPython](http://docs.micropython.org/en/latest/index.html).

It is an initial attempt to replicate my [Electric Imp clock project](https://github.com/smittytone/Clock). Based on the Feather HUZZAH ESP8266 and the [Adafruit FeatherWing](https://learn.adafruit.com/adafruit-7-segment-led-featherwings/overview) four-digit, seven-segment LED add-on.

Currently, the clock has no remote control, which the Electric Imp Platform makes very easy to implement, but is rather less so here. Adding a web UI, served locally or remotely, is the next phase of the project.

### Installation ###

1. Connect your assembled Feather Clock (Feather plus LED add-on).
2. Run `./install.sh`
3. Press `Enter` to continue or `Q` to quit.
4. Enter your WiFi SSID.
5. Enter your WiFi password.
6. After the code has copied, power-cycle your Feather Clock or press the RESET button.

### To Do ###

- Web UI for clock settings control.

### Release History ###

- 1.0.8 &mdash; *6 September 2019*
    - Add installation script
- 1.0.7 &mdash; *25 April 2019*
    - Add optional on-device JSON prefs (.prefs.json) loading
- 1.0.6 &mdash; *13 April 2019*
    - Add app preferences structure
- 1.0.5 &mdash; *10 April 2019*
    - Correct the months used for BST checking
- 1.0.4 &mdash; *9 April 2019*
    - Various linting-suggested code improvements
- 1.0.3 &mdash; *8 April 2019*
    - Improve RTC updates by making NTP checks
- 1.0.2 &mdash; *5 April 2019*
    - Add regular RTC updates
- 1.0.1 &mdash; *4 April 2019*
    - Add disconnection indicator to display
    - Correct constant usage
- 1.0.0 &mdash; *3 April 2019*
    - Initial release

### Licence ###

FeatherClock is copyright 2019, Tony Smith. It is released under the MIT licence.