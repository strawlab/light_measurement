import serial
import time


port = '/dev/ttyUSB0'
baudrate = 2000000


ser = serial.Serial(port,baudrate)

while 1:

    line = ser.readline()
    line = line.split()
    print line

