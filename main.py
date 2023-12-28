from typing import Any
import dearpygui.dearpygui as dpg
# import dearpygui_ext.themes as dpg_themes
import threading
import subprocess
import os
import sys
from gnss_synchro_pb2 import GnssSynchro, Observables
from monitor_pvt_pb2 import MonitorPvt
from datetime import datetime
import trio

TERMINAL_APP_NAME = 'konsole'

working_dir = os.path.dirname(os.path.abspath(sys.argv[0])).replace('\\', '/')
spectrum_viewer_path = working_dir + '/dist/spectrum_viewer'

spectrum_viewer_subproc = None
gnss_sdr_subproc = None

active_conf_path = ''

gnss_synchro_data = []
pvt_data = []

buffer_size = 2048
update_interval = 1

gnss_synchro_address = '127.0.0.1'
gnss_synchro_port = 5050

pvt_address = '127.0.0.1'
pvt_port = 6060

gnss_synchro_thread = None
pvt_thread = None

gnss_synchro_monitor_running = False
pvt_monitor_running = False

series_autofit = True


class UDPThread(threading.Thread):
    def __init__(self, address, port, buffer_size, proto_type):
        super().__init__()
        self.address = address
        self.port = port
        self.running = False
        self.buffer_size = buffer_size
        self.sock = None
        self.proto_type = proto_type

    def run(self):
        trio.run(self.rx_data)

    async def rx_data(self):
        self.sock = trio.socket.socket(
            trio.socket.AF_INET, trio.socket.SOCK_DGRAM)

        await self.sock.bind((self.address, self.port))

        while self.running:

            packet, addr = await self.sock.recvfrom(self.buffer_size)
            if self.proto_type == 0:
                get_gnss_synchro_from_packet(packet)
            elif self.proto_type == 1:
                get_pvt_from_packet(packet)

    def start_thread(self):
        self.running = True
        super().start()

    def stop_thread(self):
        self.running = False
        if self.sock is not None:
            async def close_socket():
                self.sock.close()
            trio.run(close_socket)


def get_gnss_synchro_from_packet(packet):
    message = Observables()
    message.ParseFromString(packet)
    for gnss_synchro in message.observable:
        gnss_synchro: GnssSynchro() = gnss_synchro
        if gnss_synchro.fs != 0:
            add_data_to_gnss_synchro_list(
                [int(gnss_synchro.channel_id),
                 match_signal_name(str(gnss_synchro.signal)),
                 int(gnss_synchro.prn),

                 float(gnss_synchro.acq_delay_samples),
                 float(gnss_synchro.acq_doppler_hz),
                 int(gnss_synchro.acq_doppler_step),

                 bool(gnss_synchro.flag_valid_acquisition),
                 float(gnss_synchro.cn0_db_hz),

                 float(gnss_synchro.carrier_doppler_hz),
                 float(gnss_synchro.carrier_phase_rads),
                 float(gnss_synchro.code_phase_samples),

                 bool(gnss_synchro.flag_valid_word),
                 int(gnss_synchro.tow_at_current_symbol_ms),
                 float(gnss_synchro.interp_tow_ms),

                 bool(gnss_synchro.flag_valid_pseudorange),
                 float(gnss_synchro.pseudorange_m),
                 float(gnss_synchro.rx_time)])


def get_pvt_from_packet(packet):
    message = MonitorPvt()
    message.ParseFromString(packet)
    add_data_to_pvt_list(
        [int(message.tow_at_current_symbol_ms),
         float(message.latitude),
         float(message.longitude),
         float(message.height),
         float(message.gdop),
         float(message.pdop),
         float(message.hdop),
         float(message.vdop)])


def start_gnss_synchro_monitor_thread(sender, app_data):
    global gnss_synchro_thread, buffer_size, gnss_synchro_monitor_running

    if gnss_synchro_thread is None or (type(gnss_synchro_thread) is UDPThread and not gnss_synchro_thread.running):
        gnss_synchro_thread = UDPThread(
            gnss_synchro_address, gnss_synchro_port, buffer_size, 0)
        gnss_synchro_thread.start_thread()
        gnss_synchro_monitor_running = True
        dpg.set_value(item='gnss_synchro_monitor_running',
                      value=f'Running status: {gnss_synchro_monitor_running}')

    elif type(gnss_synchro_thread) is UDPThread and gnss_synchro_thread.running:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='GNSS Synchro monitor thread is already running.')


def stop_gnss_synchro_monitor_thread(sender, app_data):
    global gnss_synchro_thread, gnss_synchro_monitor_running

    if gnss_synchro_thread is not None and gnss_synchro_thread.running:
        gnss_synchro_thread.stop_thread()
        gnss_synchro_monitor_running = False
        dpg.set_value(item='gnss_synchro_monitor_running',
                      value=f'Running status: {gnss_synchro_monitor_running}')

    else:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='GNSS Synchro monitor thread is not running.')


def start_pvt_monitor_thread(sender, app_data):
    global pvt_thread, buffer_size, pvt_monitor_running

    if pvt_thread is None or (type(pvt_thread) is UDPThread and not pvt_thread.running):
        pvt_thread = UDPThread(pvt_address, pvt_port, buffer_size, 1)
        pvt_thread.start_thread()
        pvt_monitor_running = True
        dpg.set_value(item='pvt_monitor_running',
                      value=f'Running status: {pvt_monitor_running}')

    elif type(pvt_thread) is UDPThread and pvt_thread.running:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='PVT monitor thread is already running.')


def stop_pvt_monitor_thread(sender, app_data):
    global pvt_thread, pvt_monitor_running

    if pvt_thread is not None and pvt_thread.running:
        pvt_thread.stop_thread()
        pvt_monitor_running = False
        dpg.set_value(item='pvt_monitor_running',
                      value=f'Running status: {pvt_monitor_running}')

    else:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='PVT monitor thread is not running.')


def run_spectrum_viewer_subproc():
    '''
    spectrum viewer subprocess in separate thread
    '''
    global spectrum_viewer_subproc
    spectrum_viewer_subproc = subprocess.Popen(
        [spectrum_viewer_path], stdout=subprocess.PIPE)


def start_spectrum_viewer_thread():
    '''
    spectrum viewer menu item callback
    '''
    global spectrum_viewer_subproc

    if spectrum_viewer_subproc is not None and spectrum_viewer_subproc.poll() is None:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='Spectrum viewer is already running.')

    elif gnss_sdr_subproc is not None and gnss_sdr_subproc.poll() is None:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(
            item='error_message',
            value='GNSS-SDR is running. Stop subprocess and launch spectrum viewer again.')

    else:
        threading.Thread(target=run_spectrum_viewer_subproc).start()


def run_gnss_sdr_subproc():
    '''
    gnss-sdr subprocess in separate thread
    '''
    global gnss_sdr_subproc, active_conf_path
    [TERMINAL_APP_NAME, "-e", "bash -c 'gnss-sdr -c=./cfg/gl.conf; exec bash'"]
    gnss_sdr_subproc = subprocess.Popen(
        args=[TERMINAL_APP_NAME, "-e",
              f"bash -c 'gnss-sdr -c={active_conf_path}; exec bash'"])

    # gnss_sdr_subproc = subprocess.Popen(
    #     ['xterm', '-hold', '-e', f'gnss-sdr -c={active_conf_path}'])
    # use xterm if gnome doesnt work


def start_gnss_sdr_thread():
    '''
    gnss-sdr menu item callback
    '''
    global gnss_sdr_subproc

    if gnss_sdr_subproc is not None and gnss_sdr_subproc.poll() is None:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(item='error_message',
                      value='GNSS-SDR is already running.')

    elif spectrum_viewer_subproc is not None and spectrum_viewer_subproc.poll() is None:
        dpg.show_item(item='subproc_error_window')
        dpg.set_value(
            item='error_message',
            value='Spectrum viewer is running. Stop subprocess and launch GNSS-SDR again.')

    else:
        threading.Thread(target=run_gnss_sdr_subproc).start()


'''
gui callbacks
'''


def set_conf_file_path(sender, app_data, user_data):
    global active_conf_path
    active_conf_path = app_data['file_path_name']
    dpg.set_value(item='conf_file_path_input_text', value=active_conf_path)


def set_gnss_synchro_address(sender, app_data, user_data):
    global gnss_synchro_address
    gnss_synchro_address = app_data


def set_gnss_synchro_port(sender, app_data, user_data):
    global gnss_synchro_port
    gnss_synchro_port = int(app_data) if app_data != '' else 0


def set_pvt_address(sender, app_data, user_data):
    global pvt_address
    pvt_address = app_data


def set_pvt_port(sender, app_data, user_data):
    global pvt_port
    pvt_port = int(app_data) if app_data != '' else 0


def set_buffer_size(sender, app_data, user_data):
    global buffer_size
    buffer_size = int(app_data) if app_data != '' else 1


def set_update_interval(sender, app_data, user_data):
    global update_interval
    update_interval = int(app_data) if app_data != '' else 1


def open_monitor_windows():
    dpg.show_item(item='gnss_synchro_monitor_window')
    dpg.show_item(item='pvt_monitor_window')


def set_series_autofit(sender, app_data, user_data):
    global series_autofit
    series_autofit = dpg.get_value(item=sender)


'''
gui description
'''
dpg.create_context()
# dpg.bind_theme(dpg_themes.create_theme_imgui_light())

'''
primary window
'''
with dpg.window(tag='primary_window'):
    with dpg.menu_bar():
        with dpg.menu(label='Run'):
            dpg.add_menu_item(label='Spectrum viewer',
                              callback=start_spectrum_viewer_thread)
            dpg.add_menu_item(label='GNSS-SDR',
                              callback=start_gnss_sdr_thread)
            dpg.add_menu_item(label='Monitor',
                              callback=open_monitor_windows)
        dpg.add_button(label='Options',
                       callback=lambda: dpg.show_item('options_window'))


'''
conf file choose dialog window
'''
with dpg.file_dialog(label='Choose gnss-sdr configuration file',
                     width=700,
                     height=500,
                     show=False,
                     modal=True,
                     directory_selector=False,
                     callback=lambda s, a, u: set_conf_file_path(s, a, u), tag='conf_file_dialog'):
    dpg.add_file_extension(".conf", color=(0, 255, 0, 255))


'''
options window
'''
with dpg.window(label='Options',
                tag='options_window',
                width=int(dpg.get_item_width('primary_window')),
                height=int(dpg.get_item_height('primary_window')),
                pos=(400, 400),
                no_collapse=True,
                autosize=True,
                show=False):
    dpg.add_text(default_value='GNSS-SDR')
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_text(default_value='Conf file path:')
        dpg.add_input_text(tag='conf_file_path_input_text', width=400)
        dpg.add_button(label="Choose...",
                       user_data=dpg.get_item_user_data('conf_file_dialog'),
                       callback=lambda s, a, u: dpg.show_item('conf_file_dialog'))

    dpg.add_spacer(height=20)
    dpg.add_text(default_value='Monitor')
    dpg.add_separator()

    with dpg.group(horizontal=True):
        dpg.add_text(default_value='GNSS_Synchro address:  ')
        dpg.add_input_text(default_value=gnss_synchro_address,
                           tag='gnss_synchro_address',
                           width=130,
                           callback=set_gnss_synchro_address)

        dpg.add_text(default_value='  PVT address:')
        dpg.add_input_text(default_value=pvt_address,
                           tag='pvt_address',
                           width=130,
                           callback=set_pvt_address)

    with dpg.group(horizontal=True):
        dpg.add_text(default_value='GNSS_Synchro port:     ')
        dpg.add_input_text(default_value=str(gnss_synchro_port),
                           decimal=True,
                           tag='gnss_synchro_port',
                           width=130,
                           callback=set_gnss_synchro_port)

        dpg.add_text(default_value='  PVT port:   ')
        dpg.add_input_text(default_value=str(pvt_port),
                           tag='pvt_port',
                           width=130,
                           callback=set_pvt_port)

    with dpg.group(horizontal=True):
        dpg.add_text(default_value='Buffer size [bytes]:   ')
        dpg.add_input_int(default_value=buffer_size,
                          tag='buffer_size',
                          width=130,
                          min_value=1024,
                          max_value=4096,
                          min_clamped=True,
                          max_clamped=True,
                          callback=set_buffer_size)

    with dpg.group(horizontal=True):
        dpg.add_text(default_value='Update interval [sec.]:')
        dpg.add_input_int(default_value=update_interval,
                          tag='update_interval',
                          width=130,
                          min_value=0,
                          max_value=3,
                          min_clamped=True,
                          max_clamped=True,
                          callback=set_update_interval)


def match_signal_name(name):
    if name == '1C':
        name = 'GPS L1 C/A'
    elif name == '1B':
        name = 'Galileo E1b/c'
    elif name == '1G':
        name = 'GLONASS L1 C/A'
    elif name == 'B1':
        name = 'Beidou B1I'
    elif name == '2S':
        name = 'GPS L2 L2C(M)'
    elif name == '2G':
        name = 'GLONASS L2 C/A'
    elif name == 'B3':
        name = 'Beidou B3I'
    elif name == 'L5':
        name = 'GPS L5'
    elif name == '5X':
        name = 'Galileo E5a'
    elif name == 'E6':
        name = 'Galileo E6B'
    elif name == '7X':
        name = 'Galileo E5b'

    return name


def add_data_to_gnss_synchro_list(data: list[Any]):
    global gnss_synchro_data

    for row in gnss_synchro_data:
        if int(data[0]) == int(row[0]):
            row = data
            return

    gnss_synchro_data.append(data)


def sort_table(sender, sort_specs):
    if sort_specs is None:
        return
    rows = dpg.get_item_children(sender, 1)
    sortable_list = []

    for row in rows:
        first_cell = dpg.get_item_children(row, 1)[0]
        sortable_list.append([row, dpg.get_value(first_cell)])

    def _sorter(e):
        return int(e[1])

    sortable_list.sort(key=_sorter, reverse=sort_specs[0][1] < 0)
    new_order = []

    for pair in sortable_list:
        new_order.append(pair[0])

    dpg.reorder_items(sender, 1, new_order)


def process_item(item):
    if type(item) is float:
        item = round(item, 3)
    return item


def add_gnss_synchro_to_table(data):
    '''
    adds data to gnss_synchro table
    '''
    for row in data:
        with dpg.table_row(parent='gnss_synchro_table'):
            for item in row:
                dpg.add_text(f'{process_item(item)}')


def clear_gnss_synchro_table():
    '''
    selects all rows in table and cleans them
    '''
    rows = dpg.get_item_children(item='gnss_synchro_table', slot=1)
    for row in rows:
        dpg.delete_item(item=row)


def add_data_to_pvt_list(data: list[Any]):
    global pvt_data

    pvt_data.append(data)


def set_pvt_table(data):
    '''
    sets data in pvt table
    '''
    if len(data) == 0:
        return

    row = dpg.get_item_children(item='pvt_table', slot=1)[0]
    data = data[-1]

    for i, cell in enumerate(dpg.get_item_children(item=row, slot=1)):
        dpg.set_value(item=cell, value=process_item(data[i]))


def clear_pvt_table():
    row = dpg.get_item_children(item='pvt_table', slot=1)[0]
    for cell in dpg.get_item_children(item=row, slot=1):
        dpg.set_value(item=cell, value='')


def update_pvt_series():
    global pvt_data, series_autofit

    gdop_data = []
    pdop_data = []
    hdop_data = []
    vdop_data = []
    tow_ms = []
    lat = []
    long = []
    height = []

    for item in pvt_data:
        tow_ms.append(item[0])
        lat.append(item[1])
        long.append(item[2])
        height.append(item[3])
        gdop_data.append(item[4])
        pdop_data.append(item[5])
        hdop_data.append(item[6])
        vdop_data.append(item[7])

    dpg.set_value(item='long_lat_series', value=[long, lat])
    dpg.set_value(item='h_series', value=[tow_ms, height])
    dpg.set_value(item='gdop_series', value=[tow_ms, gdop_data])
    dpg.set_value(item='pdop_series', value=[tow_ms, pdop_data])
    dpg.set_value(item='hdop_series', value=[tow_ms, hdop_data])
    dpg.set_value(item='vdop_series', value=[tow_ms, vdop_data])

    if series_autofit:
        dpg.fit_axis_data(axis='dop_axis')
        dpg.fit_axis_data(axis='tow_axis')
        dpg.fit_axis_data(axis='lat_axis')
        dpg.fit_axis_data(axis='long_axis')
        dpg.fit_axis_data(axis='h_axis')
        dpg.fit_axis_data(axis='tow_axis_2')


def clear_pvt_data():
    global pvt_data

    pvt_data.clear()
    clear_pvt_table()

    dpg.set_value(item='long_lat_series', value=[[], []])
    dpg.set_value(item='h_series', value=[[], []])
    dpg.set_value(item='gdop_series', value=[[], []])
    dpg.set_value(item='pdop_series', value=[[], []])
    dpg.set_value(item='hdop_series', value=[[], []])
    dpg.set_value(item='vdop_series', value=[[], []])


'''
gnss_synchro monitor window
'''
with dpg.window(label='GNSS Synchro Monitor',
                tag='gnss_synchro_monitor_window',
                pos=(40, 40),
                no_collapse=True,
                autosize=True,
                show=False):
    with dpg.group(horizontal=True):
        dpg.add_button(label="Start",
                       width=50,
                       callback=start_gnss_synchro_monitor_thread)
        dpg.add_button(label="Stop",
                       width=50,
                       callback=stop_gnss_synchro_monitor_thread)
    dpg.add_text(
        default_value=f'Running status: {gnss_synchro_monitor_running}', tag='gnss_synchro_monitor_running')

    with dpg.table(tag='gnss_synchro_table',
                   row_background=True,
                   borders_innerH=True,
                   borders_outerH=True,
                   borders_innerV=True,
                   borders_outerV=True,
                   sortable=True,
                   callback=sort_table):
        dpg.add_table_column(label='CID',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Channel ID')

        dpg.add_table_column(label='Signal',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('GNSS signal')

        dpg.add_table_column(label='PRN',
                             no_sort=True, width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Pseudorandom noise number')

        dpg.add_table_column(label='ACQ CCDE [samples]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Coarse code delay estimation')

        dpg.add_table_column(label='ACQ Doppler [Hz]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Coarse Doppler estimation in each channel')

        dpg.add_table_column(label='ACQ FBS [Hz]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Step of the frequency bin in the search grid')

        dpg.add_table_column(label='ACQ Valid',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Acquisition status')

        dpg.add_table_column(label='C/N0 [dB-Hz]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Carrier-to-Noise density ratio')

        dpg.add_table_column(label='C. Doppler [Hz]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Carrier Doppler estimation')

        dpg.add_table_column(label='C. Phase [rad]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Carrier phase estimation')

        dpg.add_table_column(label='Code Phase [samples]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Code phase in samples')

        dpg.add_table_column(label='Valid word',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(
                'Indicates the validity of the decoded navigation message word')

        dpg.add_table_column(label='TOW [ms]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Time of week of the current symbol')

        dpg.add_table_column(label='Interp. TOW [ms]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Interpolated time of week')

        dpg.add_table_column(label='PCS',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Pseudorange computation status')

        dpg.add_table_column(label='Pseudorange [m]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Pseudorange computation')

        dpg.add_table_column(label='RX Time [s]',
                             no_sort=True,
                             width_fixed=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Receiving time after the start of the week')

with dpg.window(label='PVT Monitor',
                tag='pvt_monitor_window',
                pos=(40, 400),
                width=450,
                height=500,
                no_scrollbar=True,
                no_collapse=True,
                no_scroll_with_mouse=True,
                min_size=(1200, 500),
                show=False):
    with dpg.group(horizontal=True):
        dpg.add_button(label="Start",
                       width=50,
                       callback=start_pvt_monitor_thread)
        dpg.add_button(label="Stop",
                       width=50,
                       callback=stop_pvt_monitor_thread)
        dpg.add_button(label='Clear PVT data',
                       width=120,
                       callback=clear_pvt_data)

    dpg.add_text(default_value=f'Running status: {pvt_monitor_running}',
                 tag='pvt_monitor_running')
    with dpg.table(tag='pvt_table',
                   row_background=True,
                   borders_innerH=True,
                   borders_outerH=True,
                   borders_innerV=True,
                   borders_outerV=True,
                   sortable=False,
                   resizable=True,
                   width=800):
        dpg.add_table_column(label='TOW [ms]',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Time of week of the current symbol')

        dpg.add_table_column(label='Lat [deg]',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Latitude')

        dpg.add_table_column(label='Long [deg]',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Longitude')

        dpg.add_table_column(label='H [m]',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Height')

        dpg.add_table_column(label='GDOP',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Geometric Dilution of Precision')

        dpg.add_table_column(label='PDOP',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Position (3D) Dilution of Precision')

        dpg.add_table_column(label='HDOP',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Horizontal Dilution of Precision')

        dpg.add_table_column(label='VDOP',
                             width=80)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text('Vertical Dilution of Precision')

        with dpg.table_row():
            for i in range(8):
                dpg.add_text()

    dpg.add_checkbox(label='Auto fit axis data',
                     default_value=series_autofit,
                     callback=set_series_autofit)

    with dpg.table(header_row=False,
                   resizable=True,
                   scrollX=False,
                   scrollY=False,
                   sortable=False):
        dpg.add_table_column()
        dpg.add_table_column()
        dpg.add_table_column()

        with dpg.table_row():
            with dpg.theme(tag='plot_theme'):
                with dpg.theme_component(dpg.mvScatterSeries):
                    dpg.add_theme_style(
                        dpg.mvPlotStyleVar_MarkerSize, 2, category=dpg.mvThemeCat_Plots)

            with dpg.plot(label='DOP vs Time', height=-1, width=-1):
                dpg.add_plot_legend(outside=True, horizontal=True, location=1)
                dpg.add_plot_axis(
                    dpg.mvXAxis, label='TOW [ms]', tag='tow_axis')
                dpg.add_plot_axis(dpg.mvYAxis, label='DOP', tag='dop_axis')
                dpg.add_line_series(x=[], y=[], label='GDOP',
                                    parent='dop_axis', tag='gdop_series')
                dpg.add_line_series(x=[], y=[], label='PDOP',
                                    parent='dop_axis', tag='pdop_series')
                dpg.add_line_series(x=[], y=[], label='HDOP',
                                    parent='dop_axis', tag='hdop_series')
                dpg.add_line_series(x=[], y=[], label='VDOP',
                                    parent='dop_axis', tag='vdop_series')

            with dpg.plot(label='Lat vs Long', height=-1, width=-1):
                dpg.add_plot_axis(dpg.mvXAxis, label='Long', tag='long_axis')
                dpg.add_plot_axis(dpg.mvYAxis, label='Lat', tag='lat_axis')
                dpg.add_scatter_series(x=[], y=[], parent='lat_axis',
                                       tag='long_lat_series')
            dpg.bind_item_theme(item='long_lat_series', theme='plot_theme')

            with dpg.plot(label='Height vs Time', height=-1, width=-1):
                dpg.add_plot_axis(
                    dpg.mvXAxis, label='TOW [ms]', tag='tow_axis_2')
                dpg.add_plot_axis(
                    dpg.mvYAxis, label='Height [m]', tag='h_axis')
                dpg.add_line_series(x=[], y=[],
                                    parent='h_axis', tag='h_series')

'''
error window
'''
with dpg.window(label='Error',
                tag='subproc_error_window',
                modal=True,
                autosize=True,
                show=False):
    dpg.add_text(default_value='',
                 tag='error_message')

'''
viewport setup and dearpygui rendering loop setup
'''
dpg.create_viewport(title='GNSS-SDR assistant')
dpg.set_viewport_vsync = True
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window('primary_window', True)
dpg.maximize_viewport()

start = datetime.now()
elapsed = 0

while dpg.is_dearpygui_running():
    end = datetime.now()

    if (end - start).total_seconds() >= update_interval:

        if gnss_synchro_thread is not None:
            if gnss_synchro_thread.running:
                clear_gnss_synchro_table()
                add_gnss_synchro_to_table(gnss_synchro_data)
                gnss_synchro_data.clear()
                sort_table('gnss_synchro_table', [[65, 1]])

        if pvt_thread is not None:
            if pvt_thread.running:
                update_pvt_series()
                set_pvt_table(pvt_data)

        start = datetime.now()
        elapsed += 1

    dpg.render_dearpygui_frame()

dpg.destroy_context()
