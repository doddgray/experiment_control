
import time
import numpy as np
import matplotlib.pyplot as plt
import h5py

from instruments import SCOPE

times = np.empty(2000)
control = np.empty_like(times)
spread = np.empty_like(times)

for j in range(len(times)):
    times[j] = time.clock()
    SCOPE.take_traces()
    data = SCOPE.grab_traces(1)
    control[j] = np.mean(data[0]['Y'])
    spread[j] = np.var(data[0]['Y'])
    print("Taken {0:d}/{1:d} points".format(j+1, len(times)))
    time.sleep(0.9)

with h5py.File("fceo_drift.hdf5", "a") as hdf5_file:
    hdf5_group = hdf5_file["2018Feb08"]
    hdf5_group.attrs["ceo_freq"] = 378e6
    hdf5_group.attrs["preamp_gain"] = 50
    hdf5_group.attrs["preamp_lowpass"] = 300e3
    hdf5_group.attrs["pi_gain"] = 3.0
    hdf5_group.attrs["pi_corner"] = 30e3
    hdf5_group.attrs["scope_timediv"] = 5e-3
    hdf5_group = hdf5_group.create_group(time.ctime())
    hdf5_group.create_dataset("times", data=times)
    hdf5_group.create_dataset("control", data=control)
    hdf5_group.create_dataset("spread", data=spread)

plt.errorbar(times, control, spread)
plt.show()
