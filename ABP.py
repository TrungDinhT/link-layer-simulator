from __future__ import division
from baseclasses import *

class Sender(EndPoint):

    def __init__(self, H, l, C, maxSN, eventScheduler, statsManager):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.statsManager = statsManager
        self.currentTime = 0
        self.SN = 0
        self.nextExpectedPacket = 1
        self.packetSize = H + l
        self.dataSize = l


    def get_timeout(self):
        return self.timeout

    
    def reset(self, timeout):
        self.timeout = timeout
        self.currentTime = 0
        self.SN = 0
        self.nextExpectedPacket = 1


    def get_current_time(self):
        return self.currentTime


    def update_current_time(self, time):
        self.currentTime = time


    def send_packet(self):
        # Update currentTime as if the packet is successfully transmitted to channel
        self.currentTime = self.currentTime + self.packetSize / self.C

        # Purge any timeout in the event and add new one
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(EventType.TIMEOUT, self.currentTime + self.timeout))
        
        # Return 3 variables: time, SN, L as input for function SEND()
        return self.currentTime, self.SN, self.packetSize


    def read_event(self):
        # Dequeue event and update currentTime
        currentEvent = self.eventScheduler.dequeue()
        self.currentTime = currentEvent.time

        # Read event's type to decide what kind of action to do next
        # At the end, we return a status for each event which was read. 
        # The simulator than can handle from that.
        # In case we get a successful ack, we have to update the statistics
        if currentEvent.type == EventType.TIMEOUT:
            return EventStatus.TIMEOUT
        elif currentEvent.type == EventType.ACK:
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN != self.nextExpectedPacket:
                return EventStatus.ACK_ERROR 
            else:
                self.SN = (self.SN + 1) % self.maxSN
                self.nextExpectedPacket = (self.SN + 1) % self.maxSN
                self.statsManager.update_stats(self.dataSize, self.currentTime)
                return EventStatus.ACK



class SimulatorABP(Simulator):
    
    def set_params(self, timeout, tau, BER):
        super(SimulatorABP, self).set_params(tau, BER)
        self.sender.reset(timeout)


    def run(self):
        duration = self.duration

        while(duration > 0):
            # This is the return from sender.read_event()
            status = self.transmission_process()
            
            # If it's a timeout, we move on for retransmission
            if status == EventStatus.TIMEOUT: 
                continue

            # If it's a corrupted ACK, we dequeue ES until we get TIMEOUT
            elif status == EventStatus.ACK_ERROR:
                currentEvent = self.eventScheduler.dequeue()
                while(currentEvent and currentEvent.type != EventType.TIMEOUT):
                    currentEvent = self.eventScheduler.dequeue()
                # This should not happen, so it's just a mechanism for sanity check
                if currentEvent is None:
                    print 'Error: there is no timeout in event'
                    exit(1) 
                # This event is a TIMEOUT, so we update current time and move on for retransmission
                else:
                    self.sender.update_current_time(currentEvent.time)
            
            # This is a successful ACK, so we count 1 more packet successfully transmitted
            elif status == EventStatus.ACK:
                duration -= 1



class SimulatorABP_NAK(SimulatorABP):

    def run(self):
        duration = self.duration
        while(duration > 0):
            # This is the return from sender.read_event()
            status = self.transmission_process()

             # Timeout or ack received corrupted, we process in the same way.
             # We move on immediately for retransmission
            if status == EventStatus.TIMEOUT or status == EventStatus.ACK_ERROR:
                continue

            # This is a successful ACK, so we count 1 more packet successfully transmitted
            elif status == EventStatus.ACK:
                duration -= 1

