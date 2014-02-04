##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
A Qt-based UI for the Saleae I2S/PCM recording utility.
"""


import threading
import sys
import os
import time
import pyaudio
import numpy
import wave
from Queue import Queue

os.environ['QT_API'] = 'pyside'
import matplotlib
matplotlib.use('Qt4Agg')
matplotlib.rcParams['backend.qt4']='PySide'
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.animation as animation

global RUN_PATH
if hasattr(sys, "frozen"):
    RUN_PATH = os.path.abspath(os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding())))
else:
    RUN_PATH = os.path.abspath(os.path.dirname(unicode(__file__, sys.getfilesystemencoding())))
sys.path.append(RUN_PATH)

from SaleaeDevice import PyDevicesManager, EVENT_ID_ONCONNECT, EVENT_ID_ONDISCONNECT, \
                         EVENT_ID_ONERROR, EVENT_ID_ONREADDATA, EVENT_ID_ONANALYZERDATA
from pcm_analyzer import PCMAnalyzer, FRAME_ALIGN_FIRST_BIT, FRAME_ALIGN_LAST_BIT, \
                         LEADING_EDGE, FALLING_EDGE, HALT, CONTINUE

from PySide.QtGui import QMainWindow, QApplication, QFileDialog, QLabel, QWidget
from PySide import QtCore
from pcm2wav_ui import Ui_MainWindow

# List indices match enum values from SaleaeDevice module
FRAME_ALIGNMENTS        = ["Last Bit", "First Bit"]
EDGES                   = ["Leading Edge", "Falling Edge"]
ON_DECODE_ERROR_OPTS    = ["Halt", "Continue"]

STATE_IDLE              = 0
STATE_WAITING_FOR_FRAME = 1
STATE_RECORDING         = 2

COMMAND_ID_NONE         = -1
COMMAND_ID_START        = 0
COMMAND_ID_STOP         = 1
COMMAND_ID_KILL         = 2
COMMAND_ID_READDATA     = 3

MODE_WRITE_TO_FILE      = 0
MODE_LISTEN             = 1

class SoundOutputRenderer(QtCore.QThread):
    def __init__(self, _pyaudio, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.pyaudio = _pyaudio
        self.stream = None
        self.device = None
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.channel_to_play = 0

    def configure(self, device, format = pyaudio.paInt16,
                  channels = 1, rate = 16000, channel_to_play = 0):
        """This must be called before the thread is started."""
        self.device = device
        self.format = format
        self.channels = channels
        self.rate = rate
        self.channel_to_play = channel_to_play

    def on_data_received(self, data):
        if self.stream is not None:
            self.stream.write(data[self.channel_to_play].tostring())

    def run(self,):
        if self.pyaudio is not None:
            self.stream = self.pyaudio.open(
                                output_device_index = self.device,
                                format = self.format,
                                channels = self.channels,
                                rate = self.rate,
                                output = True)
        # This blocks until the thread is stopped
        self.exec_()
        if self.stream is not None and not self.stream.is_stopped():
            self.stream.stop_stream()
            while not self.stream.is_stopped():
                time.sleep(0.05)
            self.stream.close()
            self.stream = None

class SaleaeEventListener(QtCore.QThread):
    saleae_event_received = QtCore.Signal(object, object)

    def __init__(self, parent = None):
        QtCore.QThread.__init__(self, parent)

    def on_event(self, event, device):
        """Called when an event is broadcast from the Saleae API wrapper.
           This can be called from any thread and must communicate with the
           main GUI thread through signals/slots.
        """
        # Emit the event to any listeners (which will respond in the GUI thread)
        self.saleae_event_received.emit(event, device)

    def run(self,):
        # Just run the signals/slots event loop
        self.exec_()

class MainWindow(QMainWindow):
    analyzed_data_received_event = QtCore.Signal(object)

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self.device = None
        self.analyzer = None
        self.in_error = False
        self.current_expected_pcm_clock_rate = None
        self.error_ticks = 0
        self.error_counts = 0

        self.audio = pyaudio.PyAudio()
        self.event_listener = SaleaeEventListener()
        self.event_listener.saleae_event_received.connect(self.on_saleae_event)
        self.play_sound_thread = SoundOutputRenderer(self.audio)
        self.analyzed_data_received_event.connect(self.play_sound_thread.on_data_received)
        PyDevicesManager.register_listener(self.event_listener, EVENT_ID_ONCONNECT)
        PyDevicesManager.register_listener(self.event_listener, EVENT_ID_ONDISCONNECT)
        PyDevicesManager.register_listener(self.event_listener, EVENT_ID_ONERROR)
        PyDevicesManager.register_listener(self.event_listener, EVENT_ID_ONREADDATA)
        PyDevicesManager.register_listener(self.event_listener, EVENT_ID_ONANALYZERDATA)

        self.audio_output_devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                self.audio_output_devices.append(info)
        self.initialize_ui_items()

        self.recording_state = STATE_IDLE
        self.last_record_start = time.clock()
        self.realtime_timer = QtCore.QTimer()
        self.realtime_timer.timeout.connect(self.realtime_timer_timeout)
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.plot_timer_timeout)

        self.figure = Figure(dpi=100)
        self.plotCanvas = FigureCanvas(self.figure)
        self.plotCanvas.setParent(self._ui.plotWidget)
        # Hook this up so we can resize the plot canvas dynamically
        self._ui.plotWidget.installEventFilter(self)
        self.fft_axis = self.figure.add_subplot(111)
        self.fft_line = None
        ytick_values = range(-140, -6, 6)
        self.fft_axis.set_yticks(ytick_values)
        self.fft_axis.set_yticklabels(["%d" % w for w in ytick_values], size='xx-small')
        self.fft_axis.set_xlabel("Frequency (kHz)", size='small')
        self.fft_axis.set_ylabel("dBFS", size='small')
        self.fft_axis.grid(True)
        self.fft_axis.autoscale(enable=False, axis='both')
        self.plot_background = None

        self.update_controls()

        self.show_message("Waiting for a Logic device to connect...")
        self.event_listener.start()
        PyDevicesManager.begin_connect()

    def initialize_ui_items(self,):
        self._ui.onDecodeErrorComboBox.addItems(ON_DECODE_ERROR_OPTS)
        self._ui.onDecodeErrorComboBox.setCurrentIndex(HALT)
        self._ui.frameAlignmentComboBox.addItems(FRAME_ALIGNMENTS)
        self._ui.frameAlignmentComboBox.setCurrentIndex(FRAME_ALIGN_LAST_BIT)
        self._ui.clockEdgeComboBox.addItems(EDGES)
        self._ui.clockEdgeComboBox.setCurrentIndex(FALLING_EDGE)
        self._ui.outputLocationLineEdit.setText(RUN_PATH)

        for item in self.audio_output_devices:
            self._ui.comboOutputDeviceSelection.addItem(item['name'], item)
        # Select the default audio output
        default = self.audio.get_default_output_device_info()
        index = self._ui.comboOutputDeviceSelection.findData(default)
        if index < 0:
            index = 0
        self._ui.comboOutputDeviceSelection.setCurrentIndex(index)

        num_channels = self._ui.channelsPerFrameSpinBox.value()
        self._ui.comboPCMChannelToListenTo.addItems(['%d' % w for w in range(1, num_channels + 1)])
        self._ui.comboPCMChannelToListenTo.setCurrentIndex(0)

    def show_message(self, msg):
        self._ui.messagesLabel.setText(msg)

    def start_recording(self, mode):
        # Create an analyzer
        channels_per_frame = self._ui.channelsPerFrameSpinBox.value()
        sampling_rate = int(self._ui.samplingRateLineEdit.text())
        bits_per_channel = self._ui.bitsPerChannelSpinBox.value()
        clock_channel = self._ui.clockChannelSpinBox.value()
        frame_channel = self._ui.frameChannelSpinBox.value()
        data_channel = self._ui.dataChannelSpinBox.value()
        clock_edge = self._ui.clockEdgeComboBox.currentIndex()
        frame_edge = LEADING_EDGE
        self.current_expected_pcm_clock_rate = \
                    channels_per_frame * sampling_rate * bits_per_channel

        if clock_edge == LEADING_EDGE:
            frame_edge = FALLING_EDGE
        decode_error = self._ui.onDecodeErrorComboBox.currentIndex()
        frame_transition = self._ui.frameAlignmentComboBox.currentIndex()
        output_dir = None
        if mode == MODE_WRITE_TO_FILE:
            output_dir = self._ui.outputLocationLineEdit.text()
        plot_spectrum = self._ui.checkboxShowSpectrum.isChecked()
        self.analyzer = PCMAnalyzer(
                               output_folder = output_dir,
                               audio_channels_per_frame = channels_per_frame,
                               audio_sampling_rate_hz = sampling_rate,
                               bits_per_channel = bits_per_channel,
                               clock_channel = clock_channel,
                               frame_channel = frame_channel,
                               data_channel = data_channel,
                               frame_align = frame_edge,
                               frame_transition = frame_transition,
                               clock_edge = clock_edge,
                               on_decode_error = decode_error,
                               calculate_ffts = plot_spectrum,
                               logging = False)     # Do not enable this unless you have a HUUUGE hard drive!
        self.device.set_analyzer(self.analyzer)
        self.device.set_active_channels(list(range(4)))
        rate = self.device.get_analyzer().get_minimum_acquisition_rate()
        self.device.set_sampling_rate_hz(rate)
        self.device.set_use_5_volts(False)
        self.recording_state = STATE_WAITING_FOR_FRAME

        self.last_record_start = time.clock()
        self.realtime_timer.start(100)
        if plot_spectrum:
            self.plot_timer.start(150)

        if mode == MODE_LISTEN:
            # Configure the audio player
            data = self._ui.comboOutputDeviceSelection.itemData(
                        self._ui.comboOutputDeviceSelection.currentIndex())
            format = pyaudio.paInt16
            if bits_per_channel > 16:
                format = pyaudio.paInt32
            self.play_sound_thread.configure(data['index'], format=format,
                    channels=1, rate = sampling_rate,
                    channel_to_play=self._ui.comboPCMChannelToListenTo.currentIndex())
            self.play_sound_thread.start()

        self.show_message("Waiting for valid frame...")
        self.device.read_start()
        self.update_controls()

    def stop_recording(self,):
        self.reset()
        self.recording_state = STATE_IDLE
        self.show_message("Recording stopped.")
        self.update_controls()
        self.validate()

    def eventFilter(self, object, event):
        if event.type() == QtCore.QEvent.Resize:
            if object == self._ui.plotWidget:
                self.update_plot_canvas()
        return QWidget.eventFilter(self, object, event)

    @QtCore.Slot()
    def on_recordButton_clicked(self,):
        if self._ui.recordButton.text() == 'Record':
            self.start_recording(MODE_WRITE_TO_FILE)
        elif self._ui.recordButton.text() == 'Listen':
            self.start_recording(MODE_LISTEN)
        else:
            self.stop_recording()

    def realtime_timer_timeout(self,):
        elapsed = time.clock() - self.last_record_start
        time_text = "%d:%02.1f" % (elapsed / 60, elapsed % 60)
        self._ui.recordTimeLabel.setText(time_text)
        if self.in_error:
            if self.error_ticks > 15:
                self._ui.messagesLabel.setStyleSheet("background-color: none;")
                self.show_message("Continuing recording (last error: %s)..." % time_text)
                self.error_ticks = 0
                self.error_counts = 0
                self.in_error = False
            else:
                self._ui.messagesLabel.setStyleSheet("background-color: red;")
                self.error_ticks += 1

    def plot_timer_timeout(self, d=None):
        if self.device is not None and self.device.get_analyzer() is not None:
            analyzer = self.device.get_analyzer()
            data = analyzer.get_latest_fft_data(purge=True)
            if data is not None:
                self.update_plot(data)

    @QtCore.Slot()
    def on_outputLocationBrowseButton_clicked(self,):
        # Prompt for file name
        dirname = QFileDialog.getExistingDirectory(self, "Select Output Folder",
                            self._ui.outputLocationLineEdit.text(),
                            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        # Returns a tuple of (filename, filetype)
        if dirname is not None and len(dirname) > 0:
            self._ui.outputLocationLineEdit.setText(dirname)

    @QtCore.Slot(int)
    def on_channelsPerFrameSpinBox_valueChanged(self, i):
        self._ui.comboPCMChannelToListenTo.clear()
        num_channels = self._ui.channelsPerFrameSpinBox.value()
        self._ui.comboPCMChannelToListenTo.addItems(['%d' % w for w in range(1, num_channels + 1)])
        self._ui.comboPCMChannelToListenTo.setCurrentIndex(0)
        self.validate()

    @QtCore.Slot(int)
    def on_clockChannelSpinBox_valueChanged(self, i):
        self.validate()

    @QtCore.Slot(int)
    def on_frameChannelSpinBox_valueChanged(self, i):
        self.validate()

    @QtCore.Slot(int)
    def on_dataChannelSpinBox_valueChanged(self, i):
        self.validate()

    @QtCore.Slot(int)
    def on_comboPCMChannelToListenTo_currentIndexChanged(self, i):
        if self.play_sound_thread is not None:
            self.play_sound_thread.channel_to_play = self._ui.comboPCMChannelToListenTo.currentIndex()

    @QtCore.Slot(int)
    def on_comboOutputDeviceSelection_currentIndexChanged(self, i):
        pass

    @QtCore.Slot()
    def on_tabOutputRenderer_currentChanged(self,):
        if self.recording_state != STATE_IDLE:
            self.stop_recording()
        self.update_controls()

    def update_controls(self,):
        is_recording = (self.recording_state != STATE_IDLE)
        if not is_recording:
            current_tab = self._ui.tabOutputRenderer.currentWidget()
            if current_tab == self._ui.recordToFile:
                self._ui.recordButton.setText("Record")
            elif current_tab == self._ui.outputToSoundCard:
                self._ui.recordButton.setText("Listen")
        else:
            self._ui.recordButton.setText("Stop")

        self._ui.comboOutputDeviceSelection.setEnabled(not is_recording)
        self._ui.outputLocationBrowseButton.setEnabled(not is_recording)
        self._ui.logicGroupBox.setEnabled(not is_recording)
        self._ui.pcmGroupBox.setEnabled(not is_recording)
        self._ui.outputGroupBox.setEnabled(not is_recording)
        self._ui.checkboxShowSpectrum.setEnabled(not is_recording)
        self.update_plot_canvas()

    def update_plot_canvas(self,):
        self.fft_axis.set_xlim(0, int(self._ui.samplingRateLineEdit.text()) / 2)
        freq_values = range(0, int(self._ui.samplingRateLineEdit.text()) / 2, 1000) + \
                            [int(self._ui.samplingRateLineEdit.text()) / 2]
        self.fft_axis.set_xticks(freq_values)
        self.fft_axis.set_xticklabels(["%d" % (w / 1000) for w in freq_values], size='xx-small')
        self.plotCanvas.resize(self._ui.plotWidget.size().width(),
                               self._ui.plotWidget.size().height())
        self.plotCanvas.draw()
        self.plot_background = None

    def validate(self,):
        valid = False
        if self.device is not None:
            if (self._ui.clockChannelSpinBox.value() != self._ui.frameChannelSpinBox.value()) and \
               (self._ui.frameChannelSpinBox.value() != self._ui.dataChannelSpinBox.value()) and \
               (self._ui.clockChannelSpinBox.value() != self._ui.dataChannelSpinBox.value()):
                dirname = self._ui.outputLocationLineEdit.text()
                if dirname is not None and len(dirname) > 0:
                    valid = True
        self.set_valid(valid)

    def set_valid(self, is_valid):
        self._ui.recordButton.setEnabled(is_valid)

    def on_saleae_event(self, event, device):
        analyzer = None
        if device is not None and device == self.device and \
                self.device.get_analyzer() is not None:
            analyzer = self.device.get_analyzer()
        if event.id == EVENT_ID_ONCONNECT:
            self.show_message("Device connected with id %d" % device.get_id())
            self.device = device
            self.update_controls()
            self.validate()
        elif event.id == EVENT_ID_ONERROR:
            if self._ui.onDecodeErrorComboBox.currentIndex() == HALT:
                self.stop_recording()
                self.show_message("ERROR: %s" % event.data)
            else:
                if not self.in_error:
                    self.in_error = True
                    self.show_message("ERROR: %s" % event.data)
                else:
                    self.error_counts += 1
                    if self.error_counts > 5:
                        self.stop_recording()
                        self.show_message("Too many errors! %s" % event.data)
        elif event.id == EVENT_ID_ONDISCONNECT:
            self.recording_state = STATE_IDLE
            self.show_message("Device id %d disconnected." % device.get_id())
            self.shutdown()
        elif event.id == EVENT_ID_ONREADDATA:
            if analyzer is not None:
                if self.recording_state == STATE_WAITING_FOR_FRAME:
                    if self.device.get_analyzer().first_valid_frame_received():
                        self.show_message("Recording. Press 'Stop' to stop recording.")
                        self.recording_state = STATE_RECORDING
        elif event.id == EVENT_ID_ONANALYZERDATA:
            if self.recording_state == STATE_RECORDING and \
                    self.current_expected_pcm_clock_rate is not None:
                # Sanity check the sampling rate with the detected clock frequency
                if analyzer is not None:
                    clock_period_samples = self.device.get_analyzer().get_average_clock_period_in_samples()
                    meas_clock_freq = self.device.get_sampling_rate_hz() / clock_period_samples
                    if (1.2 * self.current_expected_pcm_clock_rate) <  meas_clock_freq or \
                        (0.8 * self.current_expected_pcm_clock_rate) > meas_clock_freq:
                        # The user's setup is probably wrong, so bail immediately
                        self.stop_recording()
                        self.show_message("Detected a PCM clock of ~%d Hz. Check your settings!" % meas_clock_freq)

            self.analyzed_data_received_event.emit(event.data)

    def update_plot(self, data):
        if self.plot_background is None:
            self.plot_background = self.plotCanvas.copy_from_bbox(self.fft_axis.bbox)

        channel = self._ui.comboPCMChannelToListenTo.currentIndex()
        channel_data = data[channel]
        numpoints = len(channel_data)
        if self.fft_line is None:
            self.fft_line, = self.fft_axis.plot(numpy.zeros(numpoints), animated=True)

        sampling_rate = int(self._ui.samplingRateLineEdit.text())
        freqs = numpy.fft.fftfreq(numpoints * 2, d=1.0 / float(sampling_rate))

        # Restore the clean slate background (this is the 'blit' method, which
        # is much faster to render)
        self.plotCanvas.restore_region(self.plot_background, bbox=self.fft_axis.bbox)

        self.fft_line.set_ydata(channel_data)
        self.fft_line.set_xdata(freqs[:numpoints])
        # Draw the line
        self.fft_axis.draw_artist(self.fft_line)
        # Blit the canvas
        self.plotCanvas.blit(self.fft_axis.bbox)

    def reset(self,):
        self.current_expected_pcm_clock_rate = None
        if self.device is not None:
            self.device.stop()
            self.analyzer = None
        self.realtime_timer.stop()
        self.plot_timer.stop()
        if self.play_sound_thread.isRunning():
            self.play_sound_thread.quit()
            self.play_sound_thread.wait()
            
        self._ui.messagesLabel.setStyleSheet("background-color: none;")
        self.error_ticks = 0
        self.error_counts = 0
        self.in_error = False

    def shutdown(self,):
        self.recording_state = STATE_IDLE
        self.reset()
        self.device = None
        try:
            self.figure.close()
        except:
            pass
    
    def closeEvent(self, event):
        """Intercepts the close event of the MainWindow."""
        self.show_message("Closing device...")
        try:
            self.shutdown()
            self.event_listener.quit()
            self.event_listener.wait()
            self.audio.terminate()
        finally:
            super(MainWindow, self).closeEvent(event)

# --------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    app.exec_()
