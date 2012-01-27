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
        return threading.Thread(group=None, target=self.analyze_data, name=self.get_name())

    def get_name(self,):
        return "Raw Data Analyzer"

    def set_interface(self, interface):
        self.interface = interface

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
        return 16000000

    def cleanup(self,):
        pass

    def stop(self,):
        self.stop_request = 1
        if self.analyzer.is_alive():
            if threading.current_thread() != self.analyzer:
                self.analyzer.join()
        self.cleanup()

    @cython.boundscheck(False)
    cdef int analyze_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data) except -1:
        return 0

    @cython.boundscheck(False)
    cdef int analyze_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data) except -1:
        return 0

    def analyze_data(self,):
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
        SaleaeDevice.PyDevicesManager.on_analyzer_data(self.interface.get_id(), data)
