cimport numpy as np
from analyzer cimport Analyzer

import numpy as np
import threading
import collections
import time
import exceptions
import cython
import wave
import os
import datetime

from analyzer import Analyzer
import SaleaeDevice

cdef public FFT_LENGTH = 2048

cdef public enum GEdge:
    LEADING_EDGE = 0
    FALLING_EDGE = 1

cdef public enum GFrameAlign:
    FRAME_ALIGN_LAST_BIT = 0
    FRAME_ALIGN_FIRST_BIT = 1

cdef enum GFrameState:
    LOOKING_FOR_FIRST_FRAME_EDGE = 0
    LOOKING_FOR_FRAME_EDGE = 1
    LOOKING_FOR_CLOCK_EDGE = 2

cdef public enum GOnDecodeError:
    HALT = 0
    CONTINUE = 1

# ----------------------------------------------------------------------------
class InvalidStateError(exceptions.Exception):
    """Exception for invalid states."""
    def __init__(self, message, parameters=None):
        exceptions.Exception.__init__(self, message)
        self.parameters = parameters
# ----------------------------------------------------------------------------
class DataFormatError(exceptions.Exception):
    """Exception for data format errors."""
    def __init__(self, message, parameters=None):
        exceptions.Exception.__init__(self, message)
        self.parameters = parameters
# ----------------------------------------------------------------------------
cdef class PCMAnalyzer(Analyzer):
    cdef object fft_lock
    cdef object fftdataqueue
    cdef object outputfiles
    cdef object outputfilenames
    cdef object logfile
    cdef unsigned short last_sample, frame_channel, clock_channel, data_channel, frame_state
    cdef unsigned short framesize, channels_per_frame, bits_per_channel
    cdef unsigned int audio_sampling_rate
    cdef bint is_first_sample, on_decode_error, frame_align, clock_edge, sampling, frame_transition, one_complete_frame_received
    cdef bint calculate_ffts
    cdef int current_decoded_value
    cdef np.ndarray decoded_data
    cdef int last_decoded_data_array_size
    # Used for tracking the average clock pulse width (in samples)
    cdef unsigned long long counts_since_last_clock_edge
    cdef unsigned long long avg_clock_pulse_width
    # The current channel being read (bit by bit)
    cdef int current_channel
    # The current channel bit being read
    cdef int current_channel_bit
    # Used to keep track of a maximum buffer size
    cdef int max_buffer_size

    def __init__(self, output_folder=None,
                 clock_channel=0, frame_channel=1, data_channel=2,
                 audio_channels_per_frame=2, audio_sampling_rate_hz=16000, bits_per_channel=16,
                 frame_align=FRAME_ALIGN_LAST_BIT, frame_transition=LEADING_EDGE,
                 clock_edge=FALLING_EDGE, on_decode_error=HALT, calculate_ffts=False,
                 logging=False):
        cdef unsigned int i
        Analyzer.__init__(self)
        self.clock_channel = 2**clock_channel
        self.frame_channel = 2**frame_channel
        self.data_channel = 2**data_channel
        self.frame_align = frame_align
        self.clock_edge = clock_edge
        self.frame_transition = frame_transition
        self.on_decode_error = on_decode_error
        self.fft_lock = threading.Lock()
        self.fftdataqueue = collections.deque()
        self.calculate_ffts = calculate_ffts

        # Audio data characteristics
        self.channels_per_frame = audio_channels_per_frame
        self.audio_sampling_rate = audio_sampling_rate_hz
        self.bits_per_channel = bits_per_channel

        self.avg_clock_pulse_width = 0
        self.counts_since_last_clock_edge = 0
        self.current_channel = 0
        self.current_channel_bit = 0
        self.outputfiles = []
        self.outputfilenames = []
        if output_folder is not None:
            # Initialize output files
            _now = datetime.datetime.now()
            filename_prefix = "%02d%02d%04d_%02d%02d%02d" % (_now.month, _now.day, _now.year, _now.hour, _now.minute, _now.second)
            if logging:
                self.logfile = open(os.path.join(output_folder, filename_prefix + '_log.txt'), 'w')
            else:
                self.logfile = None
            for i in range(self.channels_per_frame):
                fname = os.path.join(output_folder, filename_prefix + '_channel_%d.wav' % (i,))
                f = wave.open(fname, 'w')
                f.setparams((1, self.bits_per_channel // 8, self.audio_sampling_rate, 0, 'NONE', 'not compressed'))
                self.outputfiles.append(f)
                self.outputfilenames.append(fname)

        self.frame_state = LOOKING_FOR_FIRST_FRAME_EDGE
        self.current_decoded_value = 0
        self.last_sample = 0
        self.is_first_sample = 1
        self.framesize = 0
        self.one_complete_frame_received = 0
        self.last_decoded_data_array_size = 0
        self.max_buffer_size = 0

        # Initial arrays are allocated at 5000 elements, but it is expected that the maximum
        # buffer size is smaller than this
        if self.bits_per_channel <= 16:
            self.decoded_data = np.zeros((self.channels_per_frame, 5000), dtype=np.int16)
        else:
            self.decoded_data = np.zeros((self.channels_per_frame, 5000), dtype=np.int32)

    def get_minimum_acquisition_rate(self,):
        clock_freq = self.channels_per_frame * self.audio_sampling_rate * self.bits_per_channel
        if clock_freq < 2000000:
            return 16000000
        return 32000000

    def get_name(self,):
        return "PCM Data Analyzer"

    def get_output_files(self,):
        return self.outputfilenames

    def get_fft_length(self,):
        return FFT_LENGTH

    def get_latest_fft_data(self, purge=False):
        data = None
        self.fft_lock.acquire()
        try:
            if len(self.fftdataqueue):
                data = self.fftdataqueue.popleft()
                if purge:
                    self.fftdataqueue.clear()
        finally:
            self.fft_lock.release()
        return data

    @cython.boundscheck(False)
    cdef int fft_analyzed_data_blocks(self, np.ndarray data) except -1:
        cdef float norm_div
        cdef np.ndarray norm_data, mag_data
        cdef np.ndarray fftdata = np.zeros((data.shape[0], (FFT_LENGTH/2)), dtype=np.float64)
        norm_div = <float> 2**(self.bits_per_channel - 1)
        for i in range(data.shape[0]):
            norm_data = ( data[i] * np.hanning(len(data[i])) ) / norm_div
            mag_data = np.fft.rfft(norm_data, n=FFT_LENGTH)[:FFT_LENGTH/2] / FFT_LENGTH
            fftdata[i] = 20 * np.log10(1e-20 + np.absolute(mag_data))
        self.fft_lock.acquire()
        try:
            self.fftdataqueue.append(fftdata)
        finally:
            self.fft_lock.release()
        return 0

    @cython.boundscheck(False)
    cdef int analyze_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data) except -1:
        cdef int i, j
        cdef int length = data.shape[0]
        cdef unsigned short value
        cdef np.ndarray temp_data

        if self.one_complete_frame_received:
            if self.last_decoded_data_array_size != 0:
                temp_data = np.zeros(self.channels_per_frame)
                # If we didn't get a complete frame of data, we need to copy the last samples from the 
                # previous partial frame into the first slots of the new array
                # Back them up
                if self.current_channel > 0:
                    for j in range(self.channels_per_frame):
                        temp_data[j] = self.decoded_data[j][self.last_decoded_data_array_size]

                # Trim off excess array data
                self.decoded_data = np.array([w[:self.last_decoded_data_array_size] for w in self.decoded_data[:]])
                # If told to do so, calculate FFTs
                if self.calculate_ffts:
                    self.fft_analyzed_data_blocks(self.decoded_data)
                # Broadcast the new data
                self.new_decoded_data(self.decoded_data)

                # Write the last decoded buffer to disk
                if len(self.outputfiles) > 0:
                    for j in range(self.channels_per_frame):
                        self.outputfiles[j].writeframes(self.decoded_data[j].tostring())

                # Track the maximum buffer size
                self.max_buffer_size = max(self.max_buffer_size, 2 * self.last_decoded_data_array_size)

                # Create a new chunk of decoded data
                if self.bits_per_channel <= 16:
                    self.decoded_data = np.zeros((self.channels_per_frame, self.max_buffer_size), dtype=np.int16)
                else:
                    self.decoded_data = np.zeros((self.channels_per_frame, self.max_buffer_size), dtype=np.int32)
                self.last_decoded_data_array_size = 0

                # Copy the temp array into the first samples of the new one
                for j in range(self.channels_per_frame):
                    self.decoded_data[j][0] = temp_data[j]

        for i in range(length):
            value = data[i]
            if not self.is_first_sample:
                if self.one_complete_frame_received:
                    self.counts_since_last_clock_edge += 1
                try:
                    self.analyze_edges(self.last_sample ^ value, value)
                except InvalidStateError, e:
                    if self.on_decode_error == CONTINUE:
                        self.reset_analyzer()
                        SaleaeDevice.PyDevicesManager.on_error(self.interface.get_id(), str(e))
                    else:
                        raise
            else:
                self.is_first_sample = 0
            self.last_sample = value
        return 0

    @cython.boundscheck(False)
    cdef int analyze_edges(self, unsigned short edges, unsigned short current_data) except -1:
        cdef unsigned int frame_level, clock_level, last_expected_channel, last_expected_bit
        cdef bint frame_edge = 0
        cdef bint clock_edge = 0
        cdef bint data_level = (current_data & self.data_channel) != 0
        cdef unsigned short frame = edges & self.frame_channel
        cdef unsigned short clock = edges & self.clock_channel

        if self.logfile is not None and False:
            self.logfile.write(np.binary_repr(current_data, width=3) + "\n")

        if frame:
            frame_level = self.frame_channel & current_data
            if (self.frame_transition == LEADING_EDGE and frame_level) or \
               (self.frame_transition == FALLING_EDGE and not frame_level):
                frame_edge = 1
        if clock:
            clock_level = self.clock_channel & current_data
            if (self.clock_edge == LEADING_EDGE and clock_level) or \
               (self.clock_edge == FALLING_EDGE and not clock_level):
                clock_edge = 1

        if self.frame_state == LOOKING_FOR_FIRST_FRAME_EDGE and not frame_edge:
            # Nothing to see here
            return 2

        if self.frame_state == LOOKING_FOR_FIRST_FRAME_EDGE and frame_edge:
            # We got our inital frame edge - initialize the channel info, and look
            # for clock edges
            self.current_channel = 0
            self.current_channel_bit = 0
            if self.frame_align == FRAME_ALIGN_LAST_BIT:
                self.current_channel = self.channels_per_frame - 1
                self.current_channel_bit = self.bits_per_channel - 1
            self.frame_state = LOOKING_FOR_CLOCK_EDGE
            return 1
            
        ## Todo - perhaps we don't need this check
        if clock_edge and frame_edge:
            # Should never get both
            if self.logfile is not None:
                self.logfile.write("Can't have a clock edge and frame edge at the same time!\n")
            raise InvalidStateError("Can't have a clock edge and frame edge at the same time!")

        if self.frame_state != LOOKING_FOR_FRAME_EDGE and frame_edge:
            # Got a frame edge when we shouldn't have
            if self.logfile is not None:
                self.logfile.write("Invalid frame state change detected!\n")
            raise InvalidStateError("Invalid frame state change detected!")

        # We've now decoded the current sample into clock and frame edges, and determined the
        # level of the data line.
        if self.frame_state == LOOKING_FOR_FRAME_EDGE and frame_edge:
            if self.one_complete_frame_received == 0 and \
                    self.framesize >= (self.bits_per_channel * self.channels_per_frame):
                self.one_complete_frame_received = 1
                # Validate frame size
                if self.one_complete_frame_received:
                    # Validate frame width
                    if self.framesize != (self.bits_per_channel * self.channels_per_frame):
                        if self.logfile is not None:
                            self.logfile.write("Detected frame size (%d bits) is invalid!\n" % (self.framesize,))
                        raise DataFormatError, "Detected frame size (%d bits) is invalid!" % (self.framesize,)

            self.frame_state = LOOKING_FOR_CLOCK_EDGE
            return 0

        # Now everything keys off the clock edge
        if clock_edge:
            if self.frame_state != LOOKING_FOR_CLOCK_EDGE:
                # Got a clock edge when we shouldn't have
                if self.logfile is not None:
                    self.logfile.write("Unexpected clock edge detected!\n")
                raise InvalidStateError("Unexpected clock edge detected!")

            # If we got here, we got a clock edge, and we are expecting one

            # Clock period measurement stuff
            self.avg_clock_pulse_width = \
                (self.avg_clock_pulse_width + self.counts_since_last_clock_edge) / 2
            self.counts_since_last_clock_edge = 0

            # Now determine if it is time to start looking for a frame
            # edge
            last_expected_channel = self.channels_per_frame - 1
            # Default case for FRAME_ALIGN_FIRST_BIT
            last_expected_bit = self.bits_per_channel - 1
            if self.frame_align == FRAME_ALIGN_LAST_BIT:
                last_expected_bit = self.bits_per_channel - 2

            if self.current_channel == last_expected_channel and \
                    self.current_channel_bit == last_expected_bit:
                # We got a clock edge, and it is the last expected one before
                # the frame transitions, so change state
                self.frame_state = LOOKING_FOR_FRAME_EDGE

            # Shift the data in
            self.shift_data(data_level)

        return 0

    cdef int shift_data(self, bint level) except -1:
        # Keep track of the number of bits in the first frame for sanity
        # checks later
        if self.one_complete_frame_received == 0:
            self.framesize = self.framesize + 1

        # if self.logfile is not None:
            # self.logfile.write("Channel: %d, Bit: %d\n" % (self.current_channel, self.current_channel_bit))
        # if self.logfile is not None:
            # self.logfile.write("Framesize: %d, State: %d, Current Value: %d\n" % (self.framesize, self.frame_state, self.current_decoded_value))
        self.current_decoded_value = (self.current_decoded_value | (level & 0x1)) << 1
        self.current_channel_bit = self.current_channel_bit + 1
        if self.current_channel_bit >= self.bits_per_channel:
            self.current_channel_bit = 0
            self.complete_current_data_word()
            self.current_channel = self.current_channel + 1

        if self.current_channel >= self.channels_per_frame:
            self.current_channel = 0
            self.last_decoded_data_array_size += 1
        return 0

    cdef int complete_current_data_word(self,) except -1:
        self.decoded_data[self.current_channel, self.last_decoded_data_array_size] = self.current_decoded_value
        self.current_decoded_value = 0
        return 0

    def first_valid_frame_received(self,):
        return self.one_complete_frame_received

    def get_average_clock_period_in_samples(self,):
        return self.avg_clock_pulse_width

    def cleanup(self,):
        if self.logfile is not None:
            try:
                self.logfile.close()
            except:
                pass
        if self.outputfiles is not None:
            if len(self.outputfiles) > 0:
                for f in self.outputfiles:
                    try:
                        f.close()
                    except:
                        pass

    def reset_analyzer(self,):
        self.frame_state = LOOKING_FOR_FIRST_FRAME_EDGE
        self.current_decoded_value = 0
        self.last_sample = 0
        self.is_first_sample = 1
        self.framesize = 0
        self.one_complete_frame_received = 0

        self.avg_clock_pulse_width = 0
        self.counts_since_last_clock_edge = 0
        self.current_channel = 0
        self.current_channel_bit = 0

        # self.frame_state = LOOKING_FOR_FIRST_FRAME_EDGE
        # self.current_decoded_value = 0
        # self.current_channel = 0
        # self.current_channel_bit = 0
        #self.last_decoded_data_array_size = 0
        self.counts_since_last_clock_edge = 0

        # if not self.one_complete_frame_received:
            # self.framesize = 0