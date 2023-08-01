# This file should probably be located within a 'cryostat' directory within the drivers directory
from __future__ import print_function, unicode_literals, division # true_divide
import socket
from codecs import encode, decode
from instrumental import u, Q_
# from . import Cryostat
# from .. import _ParamDict
# from ... import u, Q_, __path__
#
#
# def _instrument(params):
#     # Should add a check of instrument type here. Not sure how to do this now,
#     # since querying '*IDN?' doesn't work.
#
#     return MontanaCryostat()

class MontanaCryostat():
    def __init__(self):
        host = 'localhost'
        port = 7773
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.leftover = None
        # Parameter dicitonary for saving
        #self._param_dict = _ParamDict({})
        #self._param_dict['module'] = 'cryostats.montana'


    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _send(self, message):
        self.sock.sendall(bytes('{:02d}{}'.format(len(message), message), "utf-8"))
        # self.sock.sendall(bytes('{:02d}{}'.format(len(message), encode(message)), "utf-8"))
        #self.sock.sendall('{:02d}{}'.format(len(message), encode(message)))

    def _recv(self):
        if self.leftover:
            bytes_recd = len(self.leftover)
            chunks = [self.leftover]
        else:
            bytes_recd = 0
            chunks = []

        while bytes_recd < 2:
            try:
                chunk = self.sock.recv(2)
            except socket.timeout:
                raise Exception("Timed out while waiting for message data")
            except Exception as e:
                raise Exception("Socket error while waiting for message data: {}".format(str(e)))

            chunks.append(chunk)
            bytes_recd += len(chunk)
            if not chunk:
                if bytes_recd == 0:
                    return None
                raise RuntimeError("Socket connection ended unexpectedly")

        length = int(b''.join(chunks))
        while bytes_recd < length+2:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                raise Exception("Timed out while waiting for message data")
            except Exception as e:
                raise Exception("Socket error while waiting for message data: {}".format(str(e)))

            chunks.append(chunk)
            bytes_recd += len(chunk)
            if not chunk:
                raise RuntimeError("Socket connection ended unexpectedly")
        full_msg = b''.join(chunks)
        chunks = [full_msg[2+length:]]  # Save excess chunks for later (shouldn't normally happen)
        return decode(full_msg[2:])

    def _query(self, message):
        self._send(message)
        return self._recv()

    # The following query/control methods are defined according to Montana
    # Instruments' "Cryostation Communication Specification" Ver. 1.12

    def get_platform_temperature(self):
        temp = float(self._query('GPT'))
        return None if temp < 0 else temp * u.degK

    def get_alarm_state(self):
        alarm_state = bool(self._query('GAS'))
        return alarm_state

    def get_chamber_pressure(self):
        pressure = float(self._query('GCP'))
        return None if pressure < 0 else pressure * u.mTorr

    def get_high_temp_set_point(self):
        response = self._query('GHTSP')
        try:
            temp = float(response)
            return temp * u.degK
        except:
            print("Message from Montana: ",response)
            return None

    def get_magnet_state(self):
        response = self._query('GHTSP')
        if response[0:5]=="MAGNET":
            return response
        else:
            print("Message from Montana: ",response)
            return None

    def get_magnet_target_field(self):
        field = float(self._query('GMTF'))
        return None if field==-9.999999 else field * u.Tesla

    def get_platform_heater_power(self):
        power = float(self._query('GPHP'))
        return None if power < 0 else power * u.watt

    def get_platform_stability(self):
        stability = float(self._query('GPS'))
        return None if stability < 0 else stability * u.degK

    def get_stage1_heater_power(self):
        power = float(self._query('GS1HP'))
        return None if power < 0 else power * u.watt

    def get_stage1_temperature(self):
        temp = float(self._query('GS1T'))
        return None if temp < 0 else temp * u.degK

    def get_stage2_temperature(self):
        temp = float(self._query('GS2T'))
        return None if temp < 0 else temp * u.degK

    def get_sample_stability(self):
        stability = float(self._query('GSS'))
        return None if stability < 0 else stability * u.degK

    def get_sample_temperature(self):
        temp = float(self._query('GST'))
        return None if temp < 0 else temp * u.degK

    def get_temperature_set_point(self):
        temp = float(self._query('GTSP'))
        return None if temp < 0 else temp * u.degK

    def get_user_stability(self):
        stability = float(self._query('GUS'))
        return None if stability < 0 else stability * u.degK

    def get_user_temperature(self):
        temp = float(self._query('GUT'))
        return None if temp < 0 else temp * u.degK

    def start_cool_down(self):
        response = self._query('SCD')
        print("Message from Montana: ",response)
        if response=='OK': return True
        else: return False

    def set_high_temperature_set_point(self,set_temp):
        set_temp_K = set_temp.to(u.degK).magnitude
        set_temp_str = "{:0.2}".format(float(set_temp_K))
        response = self._query('SHTSP'+set_temp_str)
        print("Message from Montana: ",response)
        if response[0:2]=='OK': return True
        else: return False

    def set_magnet_disabled(self):
        response = self._query('SMD')
        print("Message from Montana: ",response)
        if response[0:2]=='OK': return True
        else: return False

    def set_magnet_enabled(self):
        response = self._query('SME')
        print("Message from Montana: ",response)
        if response[0:2]=='OK': return True
        else: return False

    def set_magnet_target_field(self,set_field):
        set_field_T = set_field.to(u.Tesla).magnitude
        set_field_str = "{:0.6}".format(float(set_field_T))
        response = self._query('SMTF'+set_field_str)
        print("Message from Montana: ",response)
        if response[0:2]=='OK': return True
        else: return False

    def start_standby(self):
        response = self._query('SSB')
        print("Message from Montana: ",response)
        if response=='OK': return True
        else: return False

    def stop(self):
        response = self._query('STP')
        print("Message from Montana: ",response)
        if response=='OK': return True
        else: return False

    def set_temperature_set_point(self,set_temp):
        set_temp_K = set_temp.to(u.degK).magnitude
        set_temp_str = "{:0.3}".format(float(set_temp_K))
        response = self._query('STSP'+set_temp_str)
        print("Message from Montana: ",response)
        if response[0:2]=='OK': return True
        else: return False

    def start_warm_up(self):
        response = self._query('SWU')
        print("Message from Montana: ",response)
        if response=='OK': return True
        else: return False
