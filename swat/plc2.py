
"""
swat-s1 plc2
"""

from minicps.devices import PLC

import time

IP = {
    'plc1': '192.168.1.10',
    'plc2': '192.168.1.20',
    'plc3': '192.168.1.30',
    'plc4': '192.168.1.60',
    'plc5': '192.168.1.80',
    'plc6': '192.168.1.90',
    'attacker': '192.168.1.70',
}

PLC_SAMPLES = 1000
PLC_PERIOD_SEC = 0.40  # plc update rate in seconds

PLC2_ADDR = IP['plc2']
PLC2_TAGS = (
    ('FIT201', 2, 'REAL'),
    ('MV201', 2, 'INT'),
    # no interlocks
)
PLC2_SERVER = {
    'address': PLC2_ADDR,
    'tags': PLC2_TAGS
}
PLC2_PROTOCOL = {
    'name': 'enip',
    'mode': 1,
    'server': PLC2_SERVER
}

PLC2_DATA = {
    'TODO': 'TODO',
}

PATH = '/home/robbiemcgugan/Documents/refined/swat/swat_s1_db.sqlite'
NAME = 'swat_s1'

STATE = {
    'name': NAME,
    'path': PATH
}

###############################################################################

PLC1_ADDR = IP['plc1']
PLC2_ADDR = IP['plc2']
PLC3_ADDR = IP['plc3']

FIT201_2 = ('FIT201', 2)


class SwatPLC2(PLC):

    def pre_loop(self, sleep=0.1):
        print('DEBUG: swat-s1 plc2 enters pre_loop')

        time.sleep(sleep)

    def main_loop(self):
        """plc2 main loop.

            - read flow level sensors #2
            - update interal enip server
        """

        print('DEBUG: swat-s1 plc2 enters main_loop.')

        count = 0
        while(count <= PLC_SAMPLES):

            fit201 = float(self.get(FIT201_2))
            print("DEBUG PLC2 - get fit201: %f" % fit201)

            self.send(FIT201_2, fit201, PLC2_ADDR)
            # fit201 = self.receive(FIT201_2, PLC2_ADDR)
            # print("DEBUG PLC2 - receive fit201: ", fit201)

            time.sleep(PLC_PERIOD_SEC)
            count += 1

        print('DEBUG swat plc2 shutdown')


if __name__ == "__main__":

    # notice that memory init is different form disk init
    plc2 = SwatPLC2(
        name='plc2',
        state=STATE,
        protocol=PLC2_PROTOCOL,
        memory=PLC2_DATA,
        disk=PLC2_DATA)
