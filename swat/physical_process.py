"""
SWaT sub1 physical process

RawWaterTank has an inflow pipe and outflow pipe, both are modeled according
to the equation of continuity from the domain of hydraulics
(pressurized liquids) and a drain orefice modeled using the Bernoulli's
principle (for the trajectories).
"""


from minicps.devices import Tank

from utils import PUMP_FLOWRATE_IN, PUMP_FLOWRATE_OUT
from utils import TANK_HEIGHT, TANK_SECTION, TANK_DIAMETER
from utils import LIT_101_M, RWT_INIT_LEVEL, LIT_301_M
from utils import STATE, PP_PERIOD_SEC, PP_PERIOD_HOURS, PP_SAMPLES
import pandas as pd

import sys
import time


# SPHINX_SWAT_TUTORIAL TAGS(
MV101 = ('MV101', 1)
P101 = ('P101', 1)
LIT101 = ('LIT101', 1)
LIT301 = ('LIT301', 3)
FIT101 = ('FIT101', 1)
FIT201 = ('FIT201', 2)
# SPHINX_SWAT_TUTORIAL TAGS)


# TODO: implement orefice drain with Bernoulli/Torricelli formula
class RawWaterTank(Tank):

    def pre_loop(self):

        # SPHINX_SWAT_TUTORIAL STATE INIT(
        self.set(MV101, 1)
        self.set(P101, 0)
        self.level = self.set(LIT101, 0.800)
        # SPHINX_SWAT_TUTORIAL STATE INIT)

        # test underflow
        # self.set(MV101, 0)
        # self.set(P101, 1)
        # self.level = self.set(LIT101, 0.500)

    def main_loop(self):

        count = 0
        columns = ['Time', 'MV101', 'P101', 'LIT101', 'LIT301', 'FIT101', 'FIT201']
        df = pd.DataFrame(columns=columns)
        timestamp=0
        while(count <= PP_SAMPLES):

            new_level = self.level

            # Get valve and pump statuses
            mv101 = int(self.get(MV101))
            p101 = int(self.get(P101))

            # Compute water volume
            water_volume = self.section * new_level

            # Inflows
            if mv101 == 1:
                inflow = PUMP_FLOWRATE_IN * PP_PERIOD_HOURS
                water_volume += inflow
                self.set(FIT101, PUMP_FLOWRATE_IN)
            else:
                self.set(FIT101, 0.00)

            # Outflows
            if p101 == 1:
                outflow = PUMP_FLOWRATE_OUT * PP_PERIOD_HOURS
                water_volume -= outflow
                self.set(FIT201, PUMP_FLOWRATE_OUT)
            else:
                self.set(FIT201, 0.00)

            # Compute new water level
            new_level = water_volume / self.section

            # Ensure level is within bounds
            new_level = max(0.0, min(new_level, TANK_HEIGHT))

            # Update internal and state water level
            print(f"DEBUG new_level: {new_level:.5f} \t delta: {new_level - self.level:.5f}")
            self.level = self.set(LIT101, new_level)

            # Simulate the effect on the next tank (LIT301)
            lit301 = float(self.get(LIT301))
            if p101 == 1:
                lit301 += (PUMP_FLOWRATE_OUT * PP_PERIOD_HOURS) / self.section
            lit301 = max(0.0, min(lit301, TANK_HEIGHT))
            self.set(LIT301, lit301)

            # Print current state for debugging
            print(f"DEBUG: MV101={mv101}, P101={p101}, LIT101={new_level}, LIT301={lit301}, FIT101={self.get(FIT101)}, FIT201={self.get(FIT201)}")

            # Check for level thresholds
            if new_level >= LIT_101_M['HH']:
                print(f'DEBUG RawWaterTank above HH count: {count}')
            elif new_level <= LIT_101_M['LL']:
                print(f'DEBUG RawWaterTank below LL count: {count}')

            if lit301 > LIT_301_M['L']:
                decrease_rate = PUMP_FLOWRATE_OUT * PP_PERIOD_HOURS * 0.5 / self.section  # Adjust this factor as needed
                lit301 -= decrease_rate
                lit301 = max(0.0, min(lit301, TANK_HEIGHT))
                self.set(LIT301, lit301)

            new_data = pd.DataFrame(data = [[timestamp, self.get(MV101), self.get(P101), self.get(LIT101), self.get(LIT301), self.get(FIT101), self.get(FIT201)]], columns=columns)
            df = pd.concat([df,new_data])
            df.to_csv('logs/data.csv', index=False)
            count += 1
            time.sleep(PP_PERIOD_SEC)
            timestamp+=int(PP_PERIOD_SEC)


if __name__ == '__main__':

    rwt = RawWaterTank(
        name='rwt',
        state=STATE,
        protocol=None,
        section=TANK_SECTION,
        level=RWT_INIT_LEVEL
    )
