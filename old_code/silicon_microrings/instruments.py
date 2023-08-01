
__all__ = ["SCOPE"]

import visa
import struct
import numpy

#_RM = visa.ResourceManager('@py')
_RM = visa.ResourceManager() # I changed this because I don't have @py 

class Instrument(object):
    def _write(self, cmd):
        self._instr.write(cmd)
    def _query(self, cmd):
        return self._instr.query(cmd+"?")[:-1]
    def _read_raw(self):
        return self._instr.read_raw()
    def close(self):
        self._instr.close()

class InfiniiumScope(Instrument):
    def __init__(self, ip):
        self._instr = _RM.open_resource("TCPIP::"+ip+"::INSTR")
        self._write(":SYSTEM:HEADER OFF")
        self._write(":WAVEFORM:FORMAT WORD")
        self._write(":WAVEFORM:BYTEORDER LSBFIRST")
    @staticmethod
    def _decode_raw(data, preamble):
        P = preamble.split(",")
        data = numpy.array(struct.unpack("h"*int(P[2]),
            data[int(chr(data[1]))+2:-1])) * float(P[7]) + float(P[8])
        return {"Y":data, "dT":float(P[4]), "T0":float(P[5]), "N":len(data),
            "type" : "raw" if P[1]=='1' else "avg:"+P[3]+":"+P[19],
            "model" : P[17][1:-1],
            "timestamp" : P[15][1:-1].replace(" ",":")+":"+P[16][1:-1]}
    @staticmethod
    def write_traces(hdf5_group, traces):
        if type(traces) is not list: traces = [traces]
        for tr in traces:
            dataset = hdf5_group.create_dataset(tr["timestamp"], data=tr["Y"])
            for k in tr.keys():
                if k is not "Y":
                    dataset.attrs[k] = tr[k]
    def grab_traces(self, ch):
        if type(ch) is not list: ch = [ch]
        traces = []
        for c in ch:
            self._write(":WAVEFORM:SOURCE CHANNEL"+str(c))
            preamble = self._query(":WAVEFORM:PREAMBLE")
            self._write(":WAVEFORM:DATA?")
            data = self._read_raw()
            traces.append(self._decode_raw(data, preamble))
        return traces
    def take_traces(self, ch=None):
        if ch is not None:
            if type(ch) is not list: ch = [ch]
            for c in ch: self._write(":CHANNEL"+str(c)+":DISPLAY ON")
        self._write(":DIGITIZE")

SCOPE = InfiniiumScope("171.64.85.53")
