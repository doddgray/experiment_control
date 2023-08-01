
import numpy as np
import matplotlib.pyplot as plt

from instruments import SCOPE

def ftdiff(N, dx):
    return 1/(N*dx)

def ftaxis(N, dx, ssb=False):
    f = (np.arange(0,N) - N//2) * ftdiff(N, dx)
    if ssb:
        f = f[N//2:]
    return f

def ft(y, dt):
    return np.fft.fftshift(np.fft.fft(np.fft.ifftshift(y*dt)))

def psd(y, dt, ssb=True):
    N = y.size
    psd = np.abs(ft(y,dt))**2 * ftdiff(N-1,dt)
    if ssb:
        dc = N//2
        psd[dc+1:] *= 2
        psd = psd[dc:]
    return psd

Navg = 10
CHerr = 4

fig, ax = plt.subplots(1,1,figsize=(11,8))
plt.ion()
ln = None

ax.set_xlim([1e1,1e5])
ax.set_ylim([1e-12,1e-7])
ax.set_xlabel("Frequency (Hz)", fontsize=14)
ax.set_ylabel("PSD (rad²/Hz)", fontsize=14)
ax.xaxis.set_tick_params(labelsize=14)
ax.yaxis.set_tick_params(labelsize=14)
ax.grid(which="both")

while True:
    f = None
    Savg = None
    for n in range(Navg):
        SCOPE.take_traces()
        data = SCOPE.grab_traces(CHerr)[0]
        #S = psd(data['Y'], data['dT']) / (25*0.044)**2
        S = psd(data['Y'], data['dT']) / (10*0.044)**2
        if Savg is None:
            f = ftaxis(data['N'], data['dT'], ssb=True)
            Savg = S
        else:
            Savg += S
    Savg /= Navg
    if ln is None:
        ln, = ax.loglog(f, Savg)
    else:
        ln.set_data(f, Savg)
    plt.pause(0.1)
