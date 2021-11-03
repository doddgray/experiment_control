'''
Created 04/18/2020 @ 11:40

Not tried yet.

Instruments:
	Frequency counter Keysight 53220A
    SMU Keysight B2902A

Description
	Collects dark counts and laser counts for different bias voltages.

	1) Collect dark counts sweeping threshold from -2.5mV up to peak's height.
	2) Collect laser counts sweeping threshold from -2.5mV up to the height of a
	dark peak (different for each bias)
	3) Calculate a figure of merit
	4) Save data

'''


import sys
import pyvisa
import numpy as np
import time
import csv
#import matplotlib.pyplot as plt
from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
from pint import Quantity as Q_
from utils import *

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
#USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

if len(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''




Vbd = 35 # [V]
max_overbias = 10 # [%]
step_overbias = 0.5 # [%] Each step 1% more overbias


# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV





# Open Frequency Counter and set it to count measurement
def open_FreqCounter():
	COUNTER = rm.open_resource(USB_adress_COUNTER)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:TOT:TIM 1') # Collect the number of events in 1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER






# Set bias at Vbias and collect counts during 1 sec
def take_measure(COUNTER, SOURCEMETER, Vbias, Vthres):
    # Set voltage to Vbias
    SOURCEMETER.set_voltage(Q_(Vbias, 'V'))
    time.sleep(0.5)

    COUNTER.write('INP1:LEV {}'.format(Vthres)) # Set threshold
    res = 0
    reps = 1
    for i in range(0, reps):
        COUNTER.write('INIT') # Initiate couting
        COUNTER.write('*WAI')
        num_counts = COUNTER.query_ascii_values('FETC?')
        res = res + num_counts[0]

    return res/reps


# Collect dark counts at different trigger levels until no count is registered
def sweep_threshold(COUNTER, SOURCEMETER, Vbias):
	Vthresh = -0.025 # Start with -2.5 mV threshold
	counts = [take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh)]

	Vthresh = -0.050
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
	return [Vthresh, counts]

	Vthresh = -0.075
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
	return [Vthresh, counts]
'''
	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	while (counts[-1] != 0):
		Vthresh = Vthresh + 0.05
		counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
'''

def bring_to_breakdown(SOURCEMETER, Vbd):
    Vbd = Q_(Vbd, 'V')
    Vinit = Q_(0, 'V')
    Vstep = Q_(5.0, 'V')

    while (Vinit < Vbd):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit + Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Vbd)
    time.sleep(1.0)
    print('Sourcemeter at breakdown voltage {}'.format(Vbd))

# Bring the SPAD from breakdown to 0V at Vstep V/step
def bring_down_from_breakdown(SOURCEMETER, Vbd):
    Vbd = Q_(Vbd, 'V')
    Vstep = Q_(5.0, 'V')
    Vinit = Vbd-Vstep

    while (Vinit > Q_(0, 'V')):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit - Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Q_(0, 'V'))
    print('Sourcemeter at 0V')


#---------------------------------------------------------------------------------------


# Open the instruments
rm = pyvisa.ResourceManager()
COUNTER = open_FreqCounter()
SOURCEMETER = Keithley_2400(visa_address='GPIB0::15::INSTR')
SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
bring_to_breakdown(SOURCEMETER, Vbd)


# Start with dark measurements
num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
dark_counts = []
max_threshold = np.empty(num_measures) # Max threshold to measure counts (peak's height)

print('Performing Dark counts measurement...')

for i in range (0, num_measures):
    result = sweep_threshold(COUNTER, SOURCEMETER, vec_overbias[i])
    max_threshold[i] = result[0]
    dark_counts.append(result[1])

print('Dark counts measurement finished...')

# Save results
with open("od10_last_new2_W12-26_PD4A_16_CE_Vbd_{}_{}max_{}step_NB2.csv".format(Vbd, max_overbias, step_overbias), "w", newline="\n") as file:
    #writer = csv.writer(file)

    file.write('Light counts'  + "\n")
    for i in range (0, num_measures):
        file.write(str(vec_overbias[i]) + ',  ' + ','.join(map(str, dark_counts[i])) + "\n")
'''
    writer.writerows('Laser counts' + "\n")
    for i in range (0, num_measures):
        writer.writerows(str(vec_overbias[i]) + ',  ' + ','.join(map(str, laser_counts[i])) + "\n")

    writer.writerows('Figure of merit' + "\n")
    for i in range (0, num_measures):
        writer.writerows(str(vec_overbias[i]) + ',  ' + ','.join(map(str, fm[i])) + "\n")
'''
bring_down_from_breakdown(SOURCEMETER, Vbd)
COUNTER.close()
#SOURCEMETER.close()
