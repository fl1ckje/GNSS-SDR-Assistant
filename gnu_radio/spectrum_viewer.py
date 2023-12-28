#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Spectrum viewer
# GNU Radio version: 3.10.1.1

from packaging.version import Version as StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from PyQt5.QtCore import QObject, pyqtSlot
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import blocks
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio.qtgui import Range, RangeWidget
from PyQt5 import QtCore
import osmosdr
import time



from gnuradio import qtgui

class spectrum_viewer(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Spectrum viewer", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Spectrum viewer")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "spectrum_viewer")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.vga = vga = 0
        self.samp_rate = samp_rate = 8000000
        self.lna = lna = 40
        self.carrier_freq = carrier_freq = 1602000000
        self.baseband_filter_bandwidth = baseband_filter_bandwidth = 10000000
        self.amp = amp = 0

        ##################################################
        # Blocks
        ##################################################
        self._vga_range = Range(0, 62, 2, 0, 200)
        self._vga_win = RangeWidget(self._vga_range, self.set_vga, "VGA gain, dB", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._vga_win, 10, 3, 1, 1)
        for r in range(10, 11):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._samp_rate_range = Range(8000000, 20000000, 1000000, 8000000, 200)
        self._samp_rate_win = RangeWidget(self._samp_rate_range, self.set_samp_rate, "Sample rate, Hz", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._samp_rate_win, 9, 0, 1, 3)
        for r in range(9, 10):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._lna_range = Range(0, 40, 8, 40, 200)
        self._lna_win = RangeWidget(self._lna_range, self.set_lna, "LNA gain, dB", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._lna_win, 9, 3, 1, 1)
        for r in range(9, 10):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        # Create the options list
        self._carrier_freq_options = [1602000000, 1575420000, 1561098000, 1278750000, 1268520000, 1246000000, 1227000000, 1207140000, 1176450000]
        # Create the labels list
        self._carrier_freq_labels = ['GLONASS L1 C/A - 1602.000 MHz', 'GPS L1 C/A and Galileo E1b/c - 1575.420 MHz', 'BeiDou B1I - 1561.098 MHz', 'Galileo E6B - 1278.750 MHz', 'BeiDou B3I - 1268.520 MHz', 'GLONASS L2 C/A - 1246.000 MHz', 'GPS L2C - 1227.600 MHz', 'Galileo E5b - 1207.140 MHz', 'GPS L5 and Galileo E5a - 1176.450 MHz']
        # Create the combo box
        # Create the radio buttons
        self._carrier_freq_group_box = Qt.QGroupBox("Center frequency" + ": ")
        self._carrier_freq_box = Qt.QVBoxLayout()
        class variable_chooser_button_group(Qt.QButtonGroup):
            def __init__(self, parent=None):
                Qt.QButtonGroup.__init__(self, parent)
            @pyqtSlot(int)
            def updateButtonChecked(self, button_id):
                self.button(button_id).setChecked(True)
        self._carrier_freq_button_group = variable_chooser_button_group()
        self._carrier_freq_group_box.setLayout(self._carrier_freq_box)
        for i, _label in enumerate(self._carrier_freq_labels):
            radio_button = Qt.QRadioButton(_label)
            self._carrier_freq_box.addWidget(radio_button)
            self._carrier_freq_button_group.addButton(radio_button, i)
        self._carrier_freq_callback = lambda i: Qt.QMetaObject.invokeMethod(self._carrier_freq_button_group, "updateButtonChecked", Qt.Q_ARG("int", self._carrier_freq_options.index(i)))
        self._carrier_freq_callback(self.carrier_freq)
        self._carrier_freq_button_group.buttonClicked[int].connect(
            lambda i: self.set_carrier_freq(self._carrier_freq_options[i]))
        self.top_grid_layout.addWidget(self._carrier_freq_group_box, 9, 4, 4, 1)
        for r in range(9, 13):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(4, 5):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._baseband_filter_bandwidth_range = Range(1750000, 20000000, 250000, 10000000, 200)
        self._baseband_filter_bandwidth_win = RangeWidget(self._baseband_filter_bandwidth_range, self.set_baseband_filter_bandwidth, "Baseband filter bandwidth, Hz", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._baseband_filter_bandwidth_win, 10, 0, 1, 3)
        for r in range(10, 11):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        # Create the options list
        self._amp_options = [0, 14]
        # Create the labels list
        self._amp_labels = ['Off', 'On']
        # Create the combo box
        self._amp_tool_bar = Qt.QToolBar(self)
        self._amp_tool_bar.addWidget(Qt.QLabel("AMP" + ": "))
        self._amp_combo_box = Qt.QComboBox()
        self._amp_tool_bar.addWidget(self._amp_combo_box)
        for _label in self._amp_labels: self._amp_combo_box.addItem(_label)
        self._amp_callback = lambda i: Qt.QMetaObject.invokeMethod(self._amp_combo_box, "setCurrentIndex", Qt.Q_ARG("int", self._amp_options.index(i)))
        self._amp_callback(self.amp)
        self._amp_combo_box.currentIndexChanged.connect(
            lambda i: self.set_amp(self._amp_options[i]))
        # Create the radio buttons
        self.top_grid_layout.addWidget(self._amp_tool_bar, 11, 3, 1, 1)
        for r in range(11, 12):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            8192, #size
            window.WIN_HAMMING, #wintype
            carrier_freq, #fc
            samp_rate, #bw
            "", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis(-140, 10)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(True)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(True)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)

        self.qtgui_freq_sink_x_0.disable_legend()


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win, 0, 0, 9, 6)
        for r in range(0, 9):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.osmosdr_source_0 = osmosdr.source(
            args="numchan=" + str(1) + " " + 'hackrf=0,bias=1'
        )
        self.osmosdr_source_0.set_clock_source('internal', 0)
        self.osmosdr_source_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.osmosdr_source_0.set_sample_rate(samp_rate)
        self.osmosdr_source_0.set_center_freq(carrier_freq, 0)
        self.osmosdr_source_0.set_freq_corr(0, 0)
        self.osmosdr_source_0.set_dc_offset_mode(0, 0)
        self.osmosdr_source_0.set_iq_balance_mode(0, 0)
        self.osmosdr_source_0.set_gain_mode(True, 0)
        self.osmosdr_source_0.set_gain(amp, 0)
        self.osmosdr_source_0.set_if_gain(lna, 0)
        self.osmosdr_source_0.set_bb_gain(vga, 0)
        self.osmosdr_source_0.set_antenna('', 0)
        self.osmosdr_source_0.set_bandwidth(baseband_filter_bandwidth, 0)
        self.blocks_correctiq_0 = blocks.correctiq()


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_correctiq_0, 0), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.osmosdr_source_0, 0), (self.blocks_correctiq_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "spectrum_viewer")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_vga(self):
        return self.vga

    def set_vga(self, vga):
        self.vga = vga
        self.osmosdr_source_0.set_bb_gain(self.vga, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.osmosdr_source_0.set_sample_rate(self.samp_rate)
        self.qtgui_freq_sink_x_0.set_frequency_range(self.carrier_freq, self.samp_rate)

    def get_lna(self):
        return self.lna

    def set_lna(self, lna):
        self.lna = lna
        self.osmosdr_source_0.set_if_gain(self.lna, 0)

    def get_carrier_freq(self):
        return self.carrier_freq

    def set_carrier_freq(self, carrier_freq):
        self.carrier_freq = carrier_freq
        self._carrier_freq_callback(self.carrier_freq)
        self.osmosdr_source_0.set_center_freq(self.carrier_freq, 0)
        self.qtgui_freq_sink_x_0.set_frequency_range(self.carrier_freq, self.samp_rate)

    def get_baseband_filter_bandwidth(self):
        return self.baseband_filter_bandwidth

    def set_baseband_filter_bandwidth(self, baseband_filter_bandwidth):
        self.baseband_filter_bandwidth = baseband_filter_bandwidth
        self.osmosdr_source_0.set_bandwidth(self.baseband_filter_bandwidth, 0)

    def get_amp(self):
        return self.amp

    def set_amp(self, amp):
        self.amp = amp
        self._amp_callback(self.amp)
        self.osmosdr_source_0.set_gain(self.amp, 0)




def main(top_block_cls=spectrum_viewer, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
