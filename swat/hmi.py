"""
swat-s1 hmi.py
"""

from minicps.devices import HMI
from utils import PLC1_DATA, STATE, ATTACKER_PROTOCOL
import sqlite3
import time

DB_PATH = 'swat_s1_db.sqlite'
TABLE_NAME = 'swat_s1'

class SwatHMI(HMI):

    def pre_loop(self, sleep=0.1):
        print('DEBUG: swat-s1 hmi enters pre_loop')
        time.sleep(sleep)

    def main_loop(self):
        """hmi main loop.

            - reads sensor values from the database
        """

        print('DEBUG: swat-s1 hmi enters main_loop.')

        count = 0
        while True:
            self.read_db()
            time.sleep(1)
            count += 1

        print('DEBUG swat hmi shutdown')

    def read_db(self):
        """Read the name and value from the database and print them."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(f"SELECT name, value FROM {TABLE_NAME}")
            rows = cursor.fetchall()
            for row in rows:
                name, value = row
                print(f'READING {name}: {value}')
            conn.close()
        except sqlite3.Error as e:
            print(f'Error reading from database: {e}')

if __name__ == "__main__":
    hmi = SwatHMI(
        name='hmi',
        state=STATE,
        protocol=ATTACKER_PROTOCOL,
        memory={},
        disk={}
    )
    hmi.main_loop()