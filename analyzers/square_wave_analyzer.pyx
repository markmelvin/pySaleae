##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
A simple frequency, period and duty cycle analyzer.
"""
# Cython imports
cimport numpy as np
from analyzer cimport Analyzer

# Python imports
import numpy as np
import SaleaeDevice
import cython

# ----------------------------------------------------------------------------
cdef class SquareWaveAnalyzer(Analyzer):
    """A simple analyzer that calculates the frequency and duty cycle of a
       square wave on an input."""
    cdef unsigned short channel
    cdef unsigned short last_sample
    cdef unsigned long long counts_since_last_leading_edge
    cdef unsigned long long counts_since_last_trailing_edge
    cdef unsigned long long avg_high_pulsewidth
    cdef unsigned long long avg_low_pulsewidth

    def __init__(self, channel_num):
        Analyzer.__init__(self)
        self.channel = 2**channel_num
        self.counts_since_last_leading_edge = 0
        self.counts_since_last_trailing_edge = 0
        self.avg_high_pulsewidth = 0
        self.avg_low_pulsewidth = 0
        self.last_sample = 0

    def get_name(self,):
        return "Square Wave Analyzer"

    @cython.boundscheck(False)
    cdef int analyze_edges(self, unsigned short edges, unsigned short current_data) except -1:
        cdef bint edge = (edges & self.channel) != 0
        cdef bint level = (current_data & self.channel) != 0
        cdef bint leading_edge = (edge and level)
        cdef bint trailing_edge = (edge and not level)

        if leading_edge:
            self.counts_since_last_leading_edge += 1
            self.avg_low_pulsewidth = \
                (self.avg_low_pulsewidth + self.counts_since_last_trailing_edge) / 2
            self.counts_since_last_trailing_edge = 0
        elif self.counts_since_last_leading_edge > 0:
            # We're counting high pulses
            self.counts_since_last_leading_edge += 1

        if trailing_edge:
            self.counts_since_last_trailing_edge += 1
            self.avg_high_pulsewidth = \
                (self.avg_high_pulsewidth + self.counts_since_last_leading_edge) / 2
            self.counts_since_last_leading_edge = 0
        elif self.counts_since_last_trailing_edge > 0:
            # We're counting low pulses
            self.counts_since_last_trailing_edge += 1

    @cython.boundscheck(False)
    cpdef int analyze_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data) except -1:
        cdef int length = data.shape[0]
        cdef unsigned short value
        for i in range(length):
            value = data[i]
            self.analyze_edges(self.last_sample ^ value, value)
            self.last_sample = value
        return 0

    @cython.boundscheck(False)
    cpdef int analyze_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data) except -1:
        cdef int length = data.shape[0]
        cdef unsigned short value
        for i in range(length):
            value = data[i]
            self.analyze_edges(self.last_sample ^ value, value)
            self.last_sample = value
        return 0

    def get_frequency(self,):
        """Returns the calculated average frequency of the square wave in hertz."""
        try:
            return 1.0 / self.get_period()
        except:
            return 0

    def get_period(self,):
        """Returns the calculated average period of the square wave in seconds."""
        if self.interface is not None:
            return (self.avg_high_pulsewidth + self.avg_low_pulsewidth) * \
                    (1.0 / self.interface.get_sampling_rate_hz())
        return -1

    def get_duty_cycle(self,):
        """Returns the calculated average duty cycle (time_on/period)*100 of the
           square wave in percent."""
        try:
            return self.avg_high_pulsewidth * 100 / (self.avg_high_pulsewidth + self.avg_low_pulsewidth)
        except:
            return 0
