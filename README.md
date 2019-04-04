# Feather #

This repo contains code written for the [Adafruit Feather HUZZAH ESP8266](https://learn.adafruit.com/adafruit-feather-huzzah-esp8266) running [MicroPython](http://docs.micropython.org/en/latest/index.html).

## clock.py ##

An initial attempt to replicate my [Electric Imp clock project](https://github.com/smittytone/Clock). Based on the Feather HUZZAH ESP8266 and the [Adafruit FeatherWing](https://learn.adafruit.com/adafruit-7-segment-led-featherwings/overview) four-digit, seven-segment LED add-on.

Currently, the clock has no remote control, which the Electric Imp Platform makes very easy to implement, but is rather less so here. Adding a web UI, served locally or remotely, is the next phase of the project.

### To Do ###

- Better disconnection handling.
- Better handling of connection timeouts and *settime()* timeouts.
- Web UI for clock settings control.