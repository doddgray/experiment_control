#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
YSL Supercontinuum Source Filter controller
Required Instruments:
1. Ocean Optics HR4000 spectrometer
2. Klinger Scientific CC1.1 Motor controller
3. Power meter (ILX Lightwave OMM-6810B)
4. Source meter (HP 4156C)
"""

# import socket
# import struct

import sys
from pyqtgraph.Qt import QtGui, QtCore
from os import path
import csv

import numpy as np
from instrumental import Q_

import pyqtgraph as pg
import pyqtgraph.exporters
from pyqtgraph.ptime import time

from time import sleep
from datetime import datetime
import time

Npts = 500
wait_sec = 2
sample_time_sec = 0.45 # estimate of time taken by server to return value
rescale = True

# ### set up TCP communication ################
# HOST, PORT = "localhost", 9997
# data = " ".join(sys.argv[1:])
#
# width_pix = 1280
# height_pix = 960
# ##############################################



# # Functions from client script
# def get_val():
#     val = get_sp()
#     return val

# GUI
class Window(QtGui.QMainWindow):
    # Initialize class variables
    timer_factor = 1.2e-3

    def __init__(self):

        # Initialize instance variables
        self.spectra_data = np.array([])
        self.power_data = []
        self.power_data_timestamps = []
        self.power_data_timezero = time.time()
        self.current_wl = Q_(0.0, 'nm')
        self.data_dir = path.normpath('./')
        self.feedback_state = 0
        self.Kp =100.0
        self.Ki = 0.0 # 10.0
        self.Kd = 0.0 #10.0
        self.feedback_timeout = 20.0

        self.target_wl = Q_(550.0, 'nm')
        self.hr4000_params={'IntegrationTime_micros':100000}
        self.smu_channel = 1
        self.smu_bias = Q_(0.0, 'V')
        self.motor_steps = 0

        self.initialize_instruments()

        self.initialize_gui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_live_spectra)
        self.timer.start(Window.timer_factor*self.hr4000_params['IntegrationTime_micros']) # in msec

    def initialize_gui(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowTitle("POE Super Continuum Source Filter Control!")
        # self.setWindowIcon(QtGui.QIcon('pythonlogo.png'))

        # Menu definition
        mainMenu = self.menuBar()

        ## File menu
        fileMenu = mainMenu.addMenu('&File')

        extractAction = QtGui.QAction("&Quit Application", self)
        extractAction.setShortcut("Ctrl+Q")
        extractAction.setStatusTip('Leave The App')
        extractAction.triggered.connect(self.close_application)
        fileMenu.addAction(extractAction)

        ## Experiments menu, experiment availability aware
        if self.spec is not None:
            experimentMenu = mainMenu.addMenu('&Experiments')

            if self.pm is not None:
                measIllumAction = QtGui.QAction("Measure &Illumination", self)
                measIllumAction.setShortcut("Ctrl+I")
                measIllumAction.setStatusTip('Place over power meter to measure illumination')
                measIllumAction.triggered.connect(self.exp_illum)
                experimentMenu.addAction(measIllumAction)

            if self.smu is not None:
                measPhotocurrentAction = QtGui.QAction("Measure &Photocurrent", self)
                measPhotocurrentAction.setShortcut("Ctrl+P")
                measPhotocurrentAction.setStatusTip('Place over device to measure Photocurrent')
                measPhotocurrentAction.triggered.connect(self.exp_photocurrent)
                experimentMenu.addAction(measPhotocurrentAction)

        # Generate status bar
        self.statusBar()

        # Set Window as central widget
        self.w = QtGui.QWidget()
        self.setCentralWidget(self.w)

        ## Create a grid layout to manage the widgets size and position
        self.layout = QtGui.QGridLayout()
        self.w.setLayout(self.layout)

        ## Add widgets to the layout in their proper positions
        self.layout.addWidget(QtGui.QLabel('Device Name'), 0, 0, 1,1)

        self.edit_deviceName = QtGui.QLineEdit('TC0')
        self.layout.addWidget(self.edit_deviceName, 0, 1, 1,1)

        self.btn_save = QtGui.QPushButton('Save Spectra')
        self.btn_save.clicked.connect(self.save_spectra)
        self.layout.addWidget(self.btn_save, 0, 2, 1,1) # save spectra button

        self.btn_setdirec = QtGui.QPushButton('Set Data Directory')
        self.btn_setdirec.clicked.connect(self.set_directory)
        self.layout.addWidget(self.btn_setdirec, 1, 2, 1,1) # Set directory button


        row = 2
        if self.spec is not None:
            self.layout.addWidget(QtGui.QLabel('Integration Time [usec]'), row,0, 1,1)

            self.edit_intTime = QtGui.QLineEdit('{:d}'.format(self.hr4000_params['IntegrationTime_micros']))
            self.edit_intTime.editingFinished.connect(self.set_spec_params)
            self.layout.addWidget(self.edit_intTime, row, 1,  1,1)

            self.btn_setparam = QtGui.QPushButton('Set Spectrometer Params')
            self.btn_setparam.clicked.connect(self.set_spec_params)
            self.layout.addWidget(self.btn_setparam, row, 2,  1,1) # Set parameters button

            row = row+1

        self.layout.addWidget(QtGui.QLabel('Target Wavelength [nm]'), row,0, 1,1)

        self.edit_wavelength = QtGui.QLineEdit('{0.magnitude}'.format(self.target_wl))
        # self.edit_wavelength.editingFinished.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))
        self.layout.addWidget(self.edit_wavelength, row, 1,  1,1)

        self.btn_wavelength = QtGui.QPushButton('Set Wavelength')
        self.btn_wavelength.clicked.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))
        self.layout.addWidget(self.btn_wavelength, row, 2,  1,1) # Set wavelength button

        row = row+1

        # Motor UI elements
        if self.mc is not None:
            self.layout.addWidget(QtGui.QLabel('   Kp []'), row,0,  1,1)
            self.edit_kp = QtGui.QLineEdit('{}'.format(self.Kp))
            self.layout.addWidget(self.edit_kp, row, 1, 1,1)

            row = row+1

            self.layout.addWidget(QtGui.QLabel('   Ki []'), row,0,  1,1)
            self.edit_ki = QtGui.QLineEdit('{}'.format(self.Ki))
            self.layout.addWidget(self.edit_ki, row, 1, 1,1)

            row = row+1

            self.layout.addWidget(QtGui.QLabel('   Kd []'), row,0,  1,1)
            self.edit_kd = QtGui.QLineEdit('{}'.format(self.Kd))
            self.layout.addWidget(self.edit_kd, row, 1, 1,1)

            row = row+1

            self.btn_feedback = QtGui.QPushButton('Set Feedback Gains')
            self.btn_feedback.clicked.connect(self.set_feedback_params)
            self.layout.addWidget(self.btn_feedback, row, 0, 1,1)

            self.check_feedback = QtGui.QCheckBox('Feedback')
            self.check_feedback.stateChanged.connect(self.toggle_feedback)
            self.layout.addWidget(self.check_feedback, row, 1, 1,1)

            row = row+1

            self.layout.addWidget(QtGui.QLabel('Motor steps [-60,000~60,000]'), row,0,  1,1)

            self.edit_motor = QtGui.QLineEdit('0')
            # self.edit_motor.editingFinished.connect(lambda: self.mc.go_steps(N=int(self.edit_motor.text())))
            self.layout.addWidget(self.edit_motor, row, 1, 1,1)

            self.btn_motor = QtGui.QPushButton('Move motor')
            self.btn_motor.clicked.connect(lambda: self.mc.go_steps(N=int(self.edit_motor.text())))
            self.layout.addWidget(self.btn_motor, row, 2, 1,1)

            row = row+1

        self.label_wavelength = QtGui.QLabel('Peak Wavelength:')
        self.label_wavelength.setStyleSheet("font: bold 12pt Arial")
        self.layout.addWidget(self.label_wavelength, row, 0,  1,4)

        row = row+1

        # Power meter related UI elements
        if self.pm is not None:
            self.label_illumpower = QtGui.QLabel('Illumination Power: ')
            self.label_illumpower.setStyleSheet("font: bold 12pt Arial; color: gray")
            self.layout.addWidget(self.label_illumpower, row, 0, 1, 2)

            self.check_pm = QtGui.QCheckBox('Read Power Meter')
            self.check_pm.stateChanged.connect(self.toggle_pm_output)
            self.check_pm.setCheckState(0) # off
            self.layout.addWidget(self.check_pm, row, 2, 1, 1)

            self.btn_save = QtGui.QPushButton('Save Power trace')
            self.btn_save.clicked.connect(self.save_power_trace)
            self.layout.addWidget(self.btn_save, row, 3, 1,1) # save spectra button

            row = row+1


        # SMU UI elements
        if self.smu is not None:
            self.layout.addWidget(QtGui.QLabel('SMU channel [1~4]'), row,0,  1,1)

            self.edit_channel = QtGui.QLineEdit('{}'.format(self.smu_channel))
            self.edit_channel.editingFinished.connect(self.set_smu_params)
            self.layout.addWidget(self.edit_channel, row, 1,  1,1)

            self.layout.addWidget(QtGui.QLabel('SMU voltage [V]'), row,2,  1,1)

            self.edit_bias = QtGui.QLineEdit('{:.4g}'.format(self.smu_bias.magnitude))
            self.edit_bias.editingFinished.connect(self.set_smu_params)
            self.layout.addWidget(self.edit_bias, row, 3,  1,1)

            row = row+1

            self.label_photocurrent = QtGui.QLabel('Photocurrent:')
            self.label_photocurrent.setStyleSheet("font: bold 12pt Arial; color: gray")
            self.layout.addWidget(self.label_photocurrent, row, 0, 1, 3)

            self.check_smu = QtGui.QCheckBox('Read Source Meter')
            self.check_smu.stateChanged.connect(self.toggle_smu_output)
            self.check_smu.setCheckState(0) # off
            self.layout.addWidget(self.check_smu, row, 3, 1, 1)

            row = row+1

        self.wavelength_start = Q_(550.0, 'nm')
        self.layout.addWidget(QtGui.QLabel('   Start [nm]:'), row,0,  1,1)
        self.edit_wavelength_start = QtGui.QLineEdit('{}'.format(self.wavelength_start.magnitude))
        self.edit_wavelength_start.editingFinished.connect(self.set_sweep_params)
        self.layout.addWidget(self.edit_wavelength_start, row,1,  1,1)

        row = row+1

        self.wavelength_stop = Q_(560.0, 'nm')
        self.layout.addWidget(QtGui.QLabel('   End [nm]:'), row,0,  1,1)
        self.edit_wavelength_stop = QtGui.QLineEdit('{}'.format(self.wavelength_stop.magnitude))
        self.edit_wavelength_stop.editingFinished.connect(self.set_sweep_params)
        self.layout.addWidget(self.edit_wavelength_stop, row,1,  1,1)

        row = row+1

        self.wavelength_step = Q_(10.0, 'nm')
        self.layout.addWidget(QtGui.QLabel('   Step [nm]:'), row,0,  1,1)
        self.edit_wavelength_step = QtGui.QLineEdit('{}'.format(self.wavelength_step.magnitude))
        self.edit_wavelength_step.editingFinished.connect(self.set_sweep_params)
        self.layout.addWidget(self.edit_wavelength_step, row,1,  1,1)

        row = row + 1

        self.exp_N = 5
        self.layout.addWidget(QtGui.QLabel('   # of Samples'), row,0,  1,1)
        self.edit_exp_N = QtGui.QLineEdit('{}'.format(self.exp_N))
        self.edit_exp_N.editingFinished.connect(self.set_sweep_params)
        self.layout.addWidget(self.edit_exp_N, row,1,  1,1)

        row = row + 1

        # Plot of spectra
        self.p_spec = pg.PlotWidget()
        self.xlabel = self.p_spec.setLabel('bottom',text='Wavelength',units='nm')
        self.ylabel = self.p_spec.setLabel('left',text='Counts',units='Arb. Unit')
        self.layout.addWidget(self.p_spec, 0, 4, int(row/2)+2, int(row/2)+2)

        # Plot of power fluctuations
        self.p_power = pg.PlotWidget()
        self.p_power.setLabel('bottom',text='Time',units='sec')
        self.p_power.setLabel('left',text='Power',units='W')
        self.layout.addWidget(self.p_power, int(row/2)+2, 4, int(row/2), int(row/2)+2)


        # Equalizes column stretch factor
        for i in range(self.layout.columnCount()):
            self.layout.setColumnStretch(i, 1)
        # self.layout.setColumnStretch(4, 10)

        self.show()

    def initialize_instruments(self):
        # Initialize HR4000 Spectrometer
        try:
            import seabreeze.spectrometers as sb

            self.hr4000_params={'IntegrationTime_micros':200000}

            devices = sb.list_devices()
            self.spec = sb.Spectrometer(devices[0])
        except:
            print('HR4000 Spectrometer not connected')
            self.spec = None
        else:
            self.spec.integration_time_micros(self.hr4000_params['IntegrationTime_micros'])

        # Initialize Motor controller
        try:
            from instrumental.drivers.motion.klinger import KlingerMotorController

            self.mc = KlingerMotorController(visa_address='GPIB0::8::INSTR')
        except:
            print('Klinger Motor controller not connected')
            self.mc = None
        else:
            # Set motor at high speed
            # self.mc.set_steprate(R=245, S=1, F=20)
            self.mc.set_steprate(R=250, S=1, F=20) #stalls

        # Initialize Power meter
        try:
            from instrumental.drivers.powermeters.ilx_lightwave import OMM_6810B

            self.pm = OMM_6810B(visa_address='GPIB0::2::INSTR')
        except:
            print('OMM-6810B Power meter not connected')
            self.pm = None
        else:
            self.pm.wavelength = self.target_wl
            self.pm.set_no_filter()

        # Initialize Source meter
        try:
            from instrumental.drivers.sourcemeasureunit.hp import HP_4156C

            self.smu = HP_4156C(visa_address='GPIB0::17::INSTR')
        except:
            print('HP 4156C Parameter Analyzer not connected')
            self.smu = None
        else:
            self.smu.set_integration_time('short')


    # UI Event handlers
    def save_spectra(self):
        self.timer.stop()
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

        # Save csv
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.csv'
        fpath = path.normpath(path.join(self.data_dir,fname))

        with open(fpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Wavelength nm', 'Count', 'Integration time', str(self.hr4000_params['IntegrationTime_micros'])])

            for i in range(self.spectra_data.shape[0]):
                csvwriter.writerow([str(self.spectra_data[i,0]), str(self.spectra_data[i,1])])

        # Save png
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.png'
        fpath = path.normpath(path.join(self.data_dir,fname))

        # QtGui.QApplication.processEvents()
        # create an exporter instance, as an argument give it
        # the item you wish to export
        exporter = pg.exporters.ImageExporter(self.p_spec.scene())
        exporter.export(fpath)

        self.statusBar().showMessage('Saved spectra to {}'.format(fpath), 5000)
        # restart timer
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def save_power_trace(self):
        self.timer.stop()
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

        saveDirectory, measDescription, fullpath = self.get_filename()
        self.save_to_csv(saveDirectory, measDescription, ['Time', 'Power [W]'], self.power_data_timestamps, self.power_data)

        # Save png
        fpath = fullpath+'.png'

        exporter = pg.exporters.ImageExporter(self.p_power.scene())
        exporter.export(fpath)

        self.statusBar().showMessage('Saved power trace to {}'.format(fpath), 5000)
        # restart timer
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def set_spec_params(self):
        self.timer.stop()

        self.hr4000_params['IntegrationTime_micros'] = float(self.edit_intTime.text())
        # spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set spectrometer parameters', 5000)

    def set_smu_params(self):
        try:
            self.smu_channel = int(self.edit_channel.text())
        except:
            self.statusBar().showMessage('Invalid input for SMU channel', 3000)
            self.smu_channel = 1
            self.edit_channel.setText('1')

        try:
            self.smu_bias = Q_(float(self.edit_bias.text()), 'V')
        except:
            self.statusBar().showMessage('Invalid input for SMU voltage', 3000)
            self.smu_bias = Q_(0.0, 'V')
            self.edit_channel.setText('0.0')

        if self.smu is not None:
            self.smu.set_channel(channel=self.smu_channel)
            self.smu.set_voltage(voltage=self.smu_bias)
            self.statusBar().showMessage('Setting SMU channel {} to {:.4g~}'.format(self.smu_channel, self.smu_bias), 3000)

    def set_directory(self):
        self.timer.stop()
        self.data_dir = QtGui.QFileDialog.getExistingDirectory()

        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set data directory to {}'.format(self.data_dir), 5000)

    def set_wavelength(self, wavelength):
        if self.pm is not None:
            self.pm.wavelength = wavelength

        self.target_wl = wavelength

        self.statusBar().showMessage('Setting wavelength to {:.4g~}'.format(wavelength.to_compact()), 5000)

        # self.goto_wavelength(wavelength = self.target_wl)

    def set_sweep_params(self):
        self.wavelength_start = Q_(float(self.edit_wavelength_start.text()), 'nm')
        self.wavelength_stop = Q_(float(self.edit_wavelength_stop.text()), 'nm')
        self.wavelength_step = Q_(float(self.edit_wavelength_step.text()), 'nm')

        self.exp_N = int(self.edit_exp_N.text())

        self.statusBar().showMessage('Setting wavelength sweep', 1000)

    def toggle_feedback(self, state):
        self.feedback_state = int(state)
        if state >0:
            # disable parameter Setting
            self.btn_setparam.setEnabled(False)
            self.btn_wavelength.setEnabled(False)
            self.btn_feedback.setEnabled(False)

            self.statusBar().showMessage('Feedback On', 1000)
            # Initialize PID parameters
            self.errDot = 0.0
            self.errAccum = 0.0
            self.dt = self.timer.interval()*1e-3 # seconds
        else:
            self.statusBar().showMessage('Feedback Off', 1000)
            self.btn_setparam.setEnabled(True)
            self.btn_wavelength.setEnabled(True)
            self.btn_feedback.setEnabled(True)

    def toggle_pm_output(self):
        if self.check_pm.checkState() == 0:
            self.label_illumpower.setStyleSheet("font: bold 12pt Arial; color: gray")
        else:
            self.label_illumpower.setStyleSheet("font: bold 12pt Arial")
            self.power_data = []
            self.power_data_timestamps = []
            self.power_data_timezero = time.time()

    def toggle_smu_output(self):
        if self.check_smu.checkState() == 0:
            self.label_photocurrent.setStyleSheet("font: bold 12pt Arial; color: gray")
        else:
            self.label_photocurrent.setStyleSheet("font: bold 12pt Arial")

    def set_feedback_params(self):
        self.Kp=float(self.edit_kp.text())
        self.Ki=float(self.edit_ki.text())
        self.Kd=float(self.edit_kd.text())

        self.statusBar().showMessage('Set feedback gains', 1000)

    # Timer event handler
    def refresh_live_spectra(self):
        if self.spec is not None:
            # print('Refreshing plot')
            self.spectra_data = np.transpose( self.spec.spectrum() )
            self.p_spec.plot(self.spectra_data, clear=True)

            # refresh peak wavelength
            # print(self.spectra_data.shape)
            self.current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
            self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))
            # self.label_wavelength.setText("Peak wavelength {}".format(self.current_wl.to_compact()))


        if self.pm is not None and self.check_pm.checkState() > 0:
            meas_power = self.pm.power()
            self.label_illumpower.setText('Illumination Power: {:0<4.4g~}'.format(meas_power.to_compact()))

            self.power_data_timestamps.append(time.time()-self.power_data_timezero)
            self.power_data.append(meas_power)
            self.p_power.plot(self.power_data_timestamps, [data.magnitude for data in self.power_data], clear=True)

        if self.smu is not None and self.check_smu.checkState() > 0:
            self.label_photocurrent.setText('Photocurrent: {:9<4.4g~}'.format(self.smu.measure_current().to_compact()))

        if self.mc is not None:
            if self.feedback_state > 0:
                error = self.target_wl-self.current_wl
                errP = -self.Kp*error.magnitude
                drive = np.clip(int(errP), -5000, 5000)

                print("adusting feedback drive steps: {}".format(drive))
                if drive != 0:
                    self.mc.go_steps(N=drive)
                    sleep(abs(drive)/500)

    # Menu handlers
    def exp_illum(self):
        from instrumental.drivers.util import visa_timeout_context

        with visa_timeout_context(self.pm._rsrc, 1000):
            print('Measuring Illumination')
            saveDirectory, measDescription, fullpath = self.get_filename()
            # print([saveDirectory, measDescription])

            # prepare power meter
            self.pm.set_slow_filter()

            #  Load measurement parameters
            wl = self.wavelength_start

            data_x = []
            data_y = []
            while wl <= self.wavelength_stop:
                print('Measuring {}'.format(wl.to_compact()))

                meas_wl = self.goto_wavelength(wl)
                # meas_wl = wl

                self.pm.wavelength = meas_wl
                data_x.append(meas_wl.magnitude)

                data_row = []
                for n in range(self.exp_N):
                    data_row.append(self.pm.power())
                    print('   Sample {}: {} at {}'.format(n, data_row[-1], meas_wl))
                # Append average and stdev
                data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_row.extend([Q_(data_mean, 'W'), Q_(data_std, 'W')])

                # Bring average and stdev to the front
                data_row = [data_row[i-2] for i in range(len(data_row))]
                data_y.append(data_row)
                wl = wl + self.wavelength_step

            fields = ['Wavelength [nm]'] + ['Avg. Power [W]', 'Std Dev [W]'] + ['Power {} [W]'.format(n) for n in range(self.exp_N)]

            self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

            # return power meter to fast sampling
            self.pm.set_no_filter()

    def exp_photocurrent(self):
        from instrumental.drivers.util import visa_timeout_context

        with visa_timeout_context(self.smu._rsrc, 5000):
            print('Measuring photocurrent')
            saveDirectory, measDescription, fullpath = self.get_filename()
            # print([saveDirectory, measDescription])

            # prepare source meter
            self.set_smu_params()
            self.smu.set_integration_time('long')

            #  Load measurement parameters
            wl = self.wavelength_start

            data_x = []
            data_y = []
            while wl <= self.wavelength_stop:
                print('Measuring {}'.format(wl.to_compact()))

                meas_wl = self.goto_wavelength(wl)
                # meas_wl = wl

                # self.pm.wavelength = meas_wl
                data_x.append(meas_wl.magnitude)

                data_row = []
                for n in range(self.exp_N):
                    data_row.append(self.smu.measure_current())
                    print('   Sample {}: {} at {}'.format(n, data_row[-1], meas_wl))
                # Append average and stdev
                data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_row.extend([Q_(data_mean, 'A'), Q_(data_std, 'A')])

                data_row = [data_row[i-2] for i in range(len(data_row))]

                data_y.append(data_row)
                wl = wl + self.wavelength_step

            fields = ['Wavelength [nm]'] + ['Avg. Power [A]', 'Std Dev [A]'] + ['Photocurrent {} [A]'.format(n) for n in range(self.exp_N)]
            self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

            # return source meter to fast sampling
            self.smu.set_integration_time('short')

    def close_application(self):
        sys.exit()

    # Helper Functions
    def get_filename(self):
        fpath = QtGui.QFileDialog.getSaveFileName(self, 'Save Data to')

        saveDirectory = path.dirname(fpath[0])
        measDescription = path.basename(fpath[0])

        return saveDirectory, measDescription, fpath[0]

    def save_to_csv(self, saveDirectory, measDescription, fields, data_x, data_y):

        # fields = ['Wavelength', 'count']
        fname = measDescription+'.csv'
        fpath = path.normpath(path.join(saveDirectory,fname))
        # print(fpath)

        with open(fpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, dialect='excel')
            
            csvwriter.writerow(fields)

            for row in range(len(data_x)):
                try :
                    # print('print ok')
                    csvwriter.writerow([data_x[row]]+[format(data_y[row][col].magnitude) for col in range(len(data_y[row]))])
                except:
                    # print('exception occurred')
                    csvwriter.writerow([data_x[row], format(data_y[row].magnitude)])


    def goto_wavelength(self, wavelength):
        # Check necessary instruments
        if self.spec is not None and self.mc is not None:
            print('going to {}'.format(wavelength))

            timeout = self.feedback_timeout # s
            tick = 0.0
            tock = 0.0

            # Get current wavelength
            self.spectra_data = np.transpose( self.spec.spectrum() )
            self.p_spec.plot(self.spectra_data, clear=True)

            current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
            self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))

            prevError = Q_(0.0, 'nm')
            errorAccum = Q_(0.0, 'nm')
            errorDot = Q_(0.0, 'nm')
            error = wavelength-current_wl

            while tick < timeout and np.abs(error)>Q_(0.3, 'nm'):
                errP = self.Kp*error.magnitude
                errI = self.Ki*(errorAccum).magnitude
                errD = self.Kd*(errorDot).magnitude
                drive = -np.clip(int(errP+errI+errD), -5000, 5000)

                print("moving motor {} steps".format(drive))
                if drive != 0:
                    self.mc.go_steps(N=drive)

                    tock = np.abs(drive)/1000
                else:
                    tock = 0.2

                tick = tick + tock
                print('tick {}'.format(tick))
                sleep(tock)

                # Get new wavelength and estimate error
                self.spectra_data = np.transpose( self.spec.spectrum() )
                self.p_spec.plot(self.spectra_data, clear=True)

                current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
                self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))

                prevError = error
                error = wavelength-current_wl

                errorAccum = errorAccum + (error + prevError)/2.0*tock
                errorDot = (error-prevError)/tock
                print('error {}'.format(error))

            return current_wl

def run():
    app = QtGui.QApplication(sys.argv)
    GUI = Window()
    sys.exit(app.exec_())

# run application
run()
