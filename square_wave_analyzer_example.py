##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
A Python module that demonstrates the use of the square_wave_analyzer.
"""
import time
import msvcrt
import os
import sys

# Add the folder with the SaleaeDevice.dll to the system path
# before importing anything
DLL_FOLDER = 'dependencies'
os.environ['PATH'] = os.path.join(os.getcwd(), DLL_FOLDER) + ';' + os.environ['PATH']

from SaleaeDevice import PyDevicesManager, EVENT_ID_ALL_EVENTS, EVENT_ID_ONCONNECT,     \
                         EVENT_ID_ONDISCONNECT, EVENT_ID_ONERROR
from square_wave_analyzer import SquareWaveAnalyzer

# The channel number to look for a square wave on
CHANNEL_NUMBER = 0

# --------------------------------------------------------------------------
class SaleaeEventListener(object):
    def __init__(self,):
        self.analyzer = SquareWaveAnalyzer(CHANNEL_NUMBER)
        self.analyzing = False

    def on_event(self, event, device_id):
        """Called when an event is broadcast from the Saleae API wrapper."""
        if event.id == EVENT_ID_ONCONNECT:
            device = PyDevicesManager.get_device(device_id)
            if device is not None:
                print("Device connected with id %d" % device_id)
                device.set_analyzer(self.analyzer)
                # There is a long-standing issue with the Logic16 device API where the number of channels
                # seems to matter, and also needs to be a power of two. Using 3 channels causes major
                # fluctuations in data, but using 4 channels seems much more stable.
                device.set_active_channels(list(range(4)))
                # Arbitrarily pick 40MHz as the sampling rate
                device.set_sampling_rate_hz(40000000)
                device.set_use_5_volts(False)
                print("Analyzing channel %d with %s" % (CHANNEL_NUMBER, self.analyzer.get_name()))
                device.read_start()
                self.analyzing = True
        elif event.id == EVENT_ID_ONDISCONNECT:
            self.stop()
        elif event.id == EVENT_ID_ONERROR:
            print("\nDevice: %d, Event ID: %d, Event Name: %s, Message: %s" % (device_id, event.id, event.name, event.data))

    def stop(self,):
        self.analyzing = False
        if self.analyzer is not None:
            print("\nShutting down %s" % self.analyzer.get_name())
            iface = self.analyzer.get_interface()
            if iface is not None:
                iface.stop()
                # The above line also stops the analyzer
# --------------------------------------------------------------------------
if __name__ == "__main__":
    listener = SaleaeEventListener()
    PyDevicesManager.register_listener(listener, EVENT_ID_ALL_EVENTS)
    # Start looking for events
    PyDevicesManager.begin_connect()

    print("Waiting for a device to connect. Press spacebar at any time to exit.")
    while not msvcrt.kbhit() or msvcrt.getch() != b' ':
        if listener.analyzing:
            f = listener.analyzer.get_frequency()
            p = listener.analyzer.get_period()
            dc = listener.analyzer.get_duty_cycle()
            sys.stdout.write("\rFrequency: %9d Hz\tPeriod: %e s\tDuty Cycle: %3d%%" % (f, p, dc))
        time.sleep(0.01)
    print("")
    listener.stop()
