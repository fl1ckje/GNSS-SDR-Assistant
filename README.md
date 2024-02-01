# GNSS-SDR-Assistant
![Maintenance](https://img.shields.io/badge/maintenance-stable-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
[![Discord](https://img.shields.io/badge/chat-on_discord-%237289DA.svg)](https://discordapp.com/users/346979343995633664)

GNSS-SDR-Assistant is a python application with graphical user interface (GUI) for monitoring the internal status of the software receiver defined by GNSS-SDR in real time.

GUI is implemented with [DearPyGUI]. Spectrum analyzer is implemented with [GNU Radio].

At the current time, this application can:
* run spectrum analyzer as subprocess with [HackRF One] SDR;
* run GNSS-SDR as subprocess with provided conf file;
* provide information from GNSS_Synchro and PVT_Monitor protobuf serialized objects, which are generated and transmitted from GNSS-SDR to IP-network using UDP protocol.

## Supported operating systems
Application runs on Linux:
* Linux:
  - Ubuntu 22.04 :white_check_mark:
  - Arch Linux :white_check_mark:

If you have got a desktop pc/laptop with Mac OS, I would appreciate your feedback about compatibility.

## Build, install and run quick-guide
### 1. Build and install GNSS-SDR
You can follow the steps below for Debian/Ubuntu. In other cases just follow official build and installation steps from [GNSS-SDR readme].

1. Install dependencies using software packages:
```sh
$ sudo apt-get install build-essential cmake git pkg-config libboost-dev libboost-date-time-dev \
    libboost-system-dev libboost-filesystem-dev libboost-thread-dev libboost-chrono-dev \
    libboost-serialization-dev liblog4cpp5-dev libuhd-dev gnuradio-dev gr-osmosdr \
    libblas-dev liblapack-dev libarmadillo-dev libgflags-dev libgoogle-glog-dev \
    libgnutls-openssl-dev libpcap-dev libmatio-dev libpugixml-dev libgtest-dev \
    libprotobuf-dev protobuf-compiler python3-mako python3-pip
```
2. Clone, build and install GNSS-SDR:
```sh
$ git clone https://github.com/gnss-sdr/gnss-sdr
$ cd gnss-sdr/build
```
```sh
$ cmake -DENABLE_OSMOSDR=ON -DENABLE_UHD=OFF -DENABLE_PACKAGING=ON \
    -DENABLE_UNIT_TESTING=OFF -DENABLE_EXTERNAL_MATHJAX=OFF ..
```
```sh
$ make && sudo make install
```
Important note: you can modify some [building configuration options] to match your SDR device. I've chosen [OsmoSDR] (HackRF One/RTL-SDR/BladeRF/LimeSDR implementation).

3. In order to take advantage of the SIMD instruction sets present in your processor, you will need to run the profiler tools of the VOLK and VOLK_GNSSSDR libraries (these operations only need to be done once, and can take a while):
```sh
$ cd $HOME
$ volk_profile && volk_gnsssdr_profile
```
### 2. Build and run GNSS-SDR-Assistant
1. Clone GNSS-SDR-Assistant:
```sh
$ git clone https://github.com/fl1ckje/GNSS-SDR-Assistant
$ cd GNSS-SDR-Assistant
```
2. Install Python dependencies:
```sh
$ pip3 install -r requirements.txt
```
3. Build spectrum viewer and make it executable:
```sh
$ cd gnu_radio
$ pyinstaller spectrum_viewer.py --clean --onefile --strip
$ chmod +x ./dist/spectrum_viewer
```
4. Generate protobuf code bindings:
```sh
$ cd ..
$ protoc -I=./protobuf --python_out=. ./protobuf/gnss_synchro.proto
$ protoc -I=./protobuf --python_out=. ./protobuf/monitor_pvt.proto
```
5. Run GNSS-SDR-Assistant:
```sh
$ python3 main.py
```
## Screenshots
Main window

![ScreenshotMain](https://github.com/fl1ckje/GNSS-SDR-Assistant/blob/master/Docs/Media/GNSS-SDR-Assistant-main-window.png)

Spectrum viewer

![ScreenshotSpectrum](https://github.com/fl1ckje/GNSS-SDR-Assistant/blob/master/Docs/Media/Spectrum-viewer.png)

[DearPyGUI]: https://github.com/hoffstadt/DearPyGui/
[GNU Radio]: https://github.com/gnuradio/gnuradio/
[HackRF One]: https://greatscottgadgets.com/hackrf/one/
[GNSS-SDR readme]: https://github.com/gnss-sdr/gnss-sdr/blob/main/README.md/
[building configuration options]: https://gnss-sdr.org/docs/tutorials/configuration-options-building-time/
[OsmoSDR]: https://github.com/osmocom/gr-osmosdr/
