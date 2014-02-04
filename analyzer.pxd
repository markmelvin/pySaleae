# A common definition module (header file) for Cython importing
cimport numpy as np

cdef class Analyzer:
    cdef object deque
    cdef object analyzer
    cdef bint stop_request
    cdef object interface

    cdef add_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data_block)
    cdef add_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data_block)

    cpdef int analyze_u8_data_block(self, np.ndarray[np.npy_uint8, ndim=1] data) except -1
    cpdef int analyze_u16_data_block(self, np.ndarray[np.npy_uint16, ndim=1] data) except -1