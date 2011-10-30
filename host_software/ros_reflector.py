import serial

#import roslib; roslib.load_manifest('std_msgs')
import roslib; roslib.load_manifest('rospy')
import rospy
from std_msgs.msg import Int64

class Reflector:
    def __init__(self,port = '/dev/ttyUSB0',baudrate = 2000000):
        self.ser = serial.Serial(port,baudrate)
        self.pub = rospy.Publisher('light_measurement', Int64)
        rospy.init_node('light_measurement',anonymous=True,disable_signals=True)

    def run(self):
        print 'now run:'
        print '  rxplot /light_measurement/data'
        while 1:
            line = self.ser.readline()
            if line=='':
                print 'no data line!'
                continue
            line = line.split()
            if len(line) != 2:
                print 'short data line!'
                continue
            cnt,val = map(int,line)
            self.pub.publish(Int64(val))

if __name__=='__main__':
    r = Reflector()
    r.run()
