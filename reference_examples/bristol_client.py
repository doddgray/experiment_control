#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot of peak wavelength measured by Bristol 721 (LSA) or 621 (wavemeter).
"""

import socket
import sys
import struct
import numpy as np
from time import sleep
from instrumental import u

default_wait = 0.1*u.second

### set up TCP communication ################
HOST, PORT = "localhost", 9998
data = " ".join(sys.argv[1:])
##############################################

def get_lm(wait=default_wait):
    lm = -1*u.nm
    n_tries = 0
    while lm.m<0 and n_tries<10:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request AI0 data from server
            sock.sendall(bytes('LM', "utf-8"))
            sleep(wait.to(u.second).m)
            # Receive float wavelength in nm from the server
            lm = struct.unpack('f',sock.recv(1024))[0]*u.nm # Bristol LSA peak wavelength in nm in this case

        finally:
            # close server
            sock.close()
        n_tries +=1
    return lm
