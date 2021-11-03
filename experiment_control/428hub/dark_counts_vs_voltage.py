import pyvisa
import numpy as np
import time
import csv
import matplotlib.pyplot as plt

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

Vbd = 24.2 # [V]
max_overbias = 10 # [%]
step_overbias = 1 # [%] Each step 1% more overbias


# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
threshold = -0.003 # [V] (absolute)

def open_SourceMeter():
    SOURCEMETER = rm.open_resource(USB_adress_SOURCEMETER)
    SOURCEMETER.write('*RST') # Reset to default settings
    SOURCEMETER.write(':SOUR1:FUNC:MODE VOLT')
    SOURCEMETER.write(':SENS1:CURR:PROT 100E-06') # Set compliance at 100 uA

    return SOURCEMETER

# Open Frequency Counter and set it to count measurement
def open_FreqCounter():
	COUNTER = rm.open_resource(USB_adress_COUNTER)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:TOT:TIM 1') # Collect the number of events in 1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.write('INP1:LEV {}'.format(threshold)) # Set threshold
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER


# Set bias at Vbias and collect counts during 1 sec
def take_measure(COUNTER, SOURCEMETER, Vbias):
    # Set voltage to Vbias
    SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vbias))
    SOURCEMETER.write(':OUTP ON')
    time.sleep(0.5)

    # Initiate couting
    COUNTER.write('INIT') # Initiate couting
    COUNTER.write('*WAI')
    num_counts = COUNTER.query_ascii_values('FETC?')
    return num_counts[0]


# Bring the SPAD from 0V to Vbias at Vbias V/step
def bring_to_breakdown(SOURCEMETER, Vbd):
    Vinit = 0
    Vstep = 0.25

    while (Vinit < Vbd):
        SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        SOURCEMETER.write(':OUTP ON')
        Vinit = Vinit + Vstep
        time.sleep(0.5)




rm = pyvisa.ResourceManager()
COUNTER = open_FreqCounter()
SOURCEMETER = open_SourceMeter()
bring_to_breakdown(SOURCEMETER, Vbd)


num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
vec_overbias = np.linspace(0, max_overbias, num = num_measures)
voltage_counts = [vec_overbias , np.empty(num_measures), np.empty(num_measures)]

for i in range (0, num_measures):
    voltage_counts[1][i] = Vbd + Vbd*vec_overbias[i]/100 # New overbias
    voltage_counts[2][i] = take_measure(COUNTER, SOURCEMETER, voltage_counts[1][i]) # Collect counts

plt.figure()
plt.plot(voltage_counts[1], voltage_counts[2], 'ro')
plt.title('Dark counts')
plt.xlabel('Reverse Bias Voltage [V]')
plt.ylabel('Dark counts [1/s]')
plt.grid(True)
plt.savefig("dark_counts_vs_overbias_Vbd_{}_{}max_{}step.png".format(Vbd, max_overbias, step_overbias))

with open("dark_counts_vs_overbias_Vbd_{}_{}max_{}step.csv".format(Vbd, max_overbias, step_overbias), "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(map(lambda x: [x], voltage_counts[2]))

COUNTER.close()
SOURCEMETER.close()
