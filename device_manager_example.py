##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
An example showing how to use the device manager to register for events.
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
                         EVENT_ID_ONDISCONNECT, EVENT_ID_ONERROR, EVENT_ID_ONREADDATA,  \
                         EVENT_ID_ONANALYZERDATA

class SaleaeEventListener(object):
    def __init__(self,):
        self.analyzer = None

    def on_event(self, event, device_id):
        """Called when an event is broadcast from the Saleae API wrapper."""
        print("Device: %d, Event ID: %d, Event Name: %s, Data: %s" % (device_id, event.id, event.name, event.data))

# --------------------------------------------------------------------------
if __name__ == "__main__":
    listener = SaleaeEventListener()
    PyDevicesManager.register_listener(listener, EVENT_ID_ALL_EVENTS)
    
    # Alternatively we could register to listen for specific events as shown below
    # PyDevicesManager.register_listener(listener, EVENT_ID_ONCONNECT)
    # PyDevicesManager.register_listener(listener, EVENT_ID_ONDISCONNECT)
    # PyDevicesManager.register_listener(listener, EVENT_ID_ONERROR)
    # PyDevicesManager.register_listener(listener, EVENT_ID_ONREADDATA)
    # PyDevicesManager.register_listener(listener, EVENT_ID_ONANALYZERDATA)

    # Start looking for events
    PyDevicesManager.begin_connect()

    print("Listening for events. Press spacebar to exit.")
    while not msvcrt.kbhit() and msvcrt.getch() != b' ':
        time.sleep(0.01)
