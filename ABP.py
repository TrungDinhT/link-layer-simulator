from __future__ import division
from baseclasses import *

# For ABP protocol, we only have packet 0 and 1
maxSN = 2

class Sender(EndPoint):

    def __init__(self, timeout, H, l, C, maxSN, eventScheduler):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.currentTime = 0
        self.SN = 0
        self.nextExpectedPacket = 1
        self.timeout = timeout
        self.packetSize = H + l
        self.dataSize = l

    def get_timeout(self):
        return self.timeout
    
    def update_current_time(self, time):
        self.currentTime = time

    def send_packet(self):
        self.currentTime = self.currentTime + self.packetSize / self.C
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(EventType.TIMEOUT, time + self.timeout))
        return self.currentTime, self.SN, self.packetSize

    def read_event(self):
        currentEvent = self.eventScheduler.dequeue()
        self.currentTime = currentEvent.time
        if currentEvent.type == EventType.TIMEOUT:
            return EventStatus.TIMEOUT # return timeout to prepare for a retransmission of packet
        elif currentEvent.type == EventType.ACK:
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN != self.nextExpectedPacket:
                return EventStatus.ACK_ERROR # ignore because current protocol is ABP 
            else:
                self.SN = (self.SN + 1) % maxSN
                self.nextExpectedPacket = (self.SN + 1) % maxSN
                return EventStatus.ACK # return ACK informs Simulator a successfully delivered packet
        else:
            print 'Unknown type of event'
            exit(1)



class SimulatorABP(Simulator):

    def __init__(self, duration, statsManager):
        super(SimulatorABP, self).__init__(duration, statsManager)
        
    def set_params(self, timeout, H, l, C, tau, BER):
        super(SimulatorABP, self).set_params(C, tau, BER)
        self.receiver = Receiver(H, C, maxSN, self.eventScheduler)
        self.sender = Sender(timeout, H, l, C, maxSN, self.eventScheduler)

    def run(self):
        duration = self.duration
        while(duration):
            status = self.transmission_process()
            if status == EventStatus.TIMEOUT:
                continue
            elif status == EventStatus.ACK_ERROR: # We ignore this and wait till timeout
                currentEvent = self.eventScheduler.dequeue()
                while(currentEvent and currentEvent.type != EventType.TIMEOUT):
                    currentEvent = self.eventScheduler.dequeue()
                if currentEvent is None: # it means that all events are dequeued without finding timeout, which is weird
                    print 'Error: there is no timeout in event'
                    exit(1)
                else:
                    self.sender.update_current_time(currentEvent.time)
            elif status == EventStatus.ACK:
                duration -= 1
            else:
                print 'Error: status not recognized'
                exit(1)



class SimulatorABP_NAK(Simulator):

    def __init__(self, duration, statsManager):
        super(SimulatorABP_NAK, self).__init__(duration, statsManager)
        
    def set_params(self, timeout, H, l, C, tau, BER):
        super(SimulatorABP_NAK, self).set_params(C, tau, BER)
        self.receiver = Receiver(H, C, maxSN, self.eventScheduler)
        self.sender = Sender(timeout, H, l, C, maxSN, self.eventScheduler)

    def run(self):
        duration = self.duration
        while(duration):
            status = self.transmission_process()
            if status == EventStatus.TIMEOUT or status == EventStatus.ACK_ERROR: # Timeout or ack received corrupted
                continue
            elif status == EventStatus.ACK:
                duration -= 1
