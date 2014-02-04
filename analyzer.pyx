##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
An 'analyzer' class which queues up blocks of data from the Saleae logic analyzer
for processing. Typically, any subclass will also need to be implemented in Cython
for speed reasons.
"""
# Cython imports
cimport numpy as np
cimport analyzer

# Python imports
import numpy as np
import SaleaeDevice
import collections
import threading
import time
import cython
import traceback

# ----------------------------------------------------------------------------
cdef class Analyzer:
    """A generic Analyzer class intended to be subclassed."""

    def __init__(self,):
        self.deque = collections.deque()
        self.analyzer = self.create_analyzer_thread()
        self.stop_request = 0
        self.interface = None

    def create_analyzer_thread(self,):
        """Creates a separate analyzer thread."""
        return threading.Thread(group=None, target=self.analyze_data, name=self.get_name())

    def get_name(self,):
        """Returns the name of this analyzer."""
        return "Raw Data Analyzer"

    def set_interface(self, interface):
        """Set a reference to the Logic interface (Logic or Logic16)."""
        self.interface = interface

    def get_interface(self,):
        """Returns a reference to the Logic interface or device (Logic or Logic16)."""
        return self.interface

    cdef add_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data_block):
        """Adds a block of 8-bit data to the internal queue."""
        # Fully typing the data_block argument gives us maximum Cython speed
        self.deque.append(data_block)
        if not self.analyzer.is_alive() and not self.stop_request:
            self.analyzer.start()

    cdef add_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data_block):
        """Adds a block of 16-bit data to the internal queue."""
        # Fully typing the data_block argument gives us maximum Cython speed
        self.deque.append(data_block)
        if not self.analyzer.is_alive() and not self.stop_request:
            self.analyzer.start()

    def get_minimum_acquisition_rate(self,):
        """Returns the minimum acquisition rate for this analyzer (usually based on
           the number of channels, etc)."""
        return 16000000

    def cleanup(self,):
        """Do any cleanup required for this analyzer. Called after stop()."""
        pass

    def stop(self,):
        """Stops the analyzer thread, then calls cleanup()."""
        self.stop_request = 1
        if self.analyzer.is_alive():
            if threading.current_thread() != self.analyzer:
                self.analyzer.join()
        self.cleanup()

    @cython.boundscheck(False)
    cpdef int analyze_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data) except -1:
        """Analyze a block of 8-bit data (from a Logic). Can be called from either
           Cython or Python (but chances are, you'll need to call it from Cython for
           speed reasons)."""
        return 0

    @cython.boundscheck(False)
    cpdef int analyze_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data) except -1:
        """Analyze a block of 16-bit data (from a Logic16). Can be called from either
           Cython or Python (but chances are, you'll need to call it from Cython for
           speed reasons)."""
        return 0

    def analyze_data(self,):
        """Called by the underlying Logic/Logic16 device when a block of data arrives
           that needs to be analyzed."""
        is_16_bit = False
        if isinstance(self.interface, SaleaeDevice.PyLogic16Interface):
            is_16_bit = True
        while True:
            try:
                if len(self.deque) and not self.stop_request:
                    data = self.deque.popleft()
                    if is_16_bit:
                        self.analyze_u16_data_block(data)
                    else:
                        self.analyze_u8_data_block(data)
                if self.stop_request:
                    break
                time.sleep(0.0005)
            except Exception, e:
                SaleaeDevice.PyDevicesManager.on_error(self.interface.get_id(), str(e))

    def new_decoded_data(self, data):
        """Inform any listeners that a chunk of data was analyzed."""
        SaleaeDevice.PyDevicesManager.on_analyzer_data(self.interface.get_id(), data)
