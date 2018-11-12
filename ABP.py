from __future__ import division
from baseclasses import *

# For ABP protocol, we only have packet 0 and 1
maxSN = 2

class Sender(EndPoint):

    def __init__(self, timeout, H, l, C, maxSN, eventScheduler):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.buffer = Buffer(1)
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
        return self.currentTime, self.SN, self.packetSize

    def process_feedback(self, ack):
        if ack is not None:
            self.eventScheduler.register_event(ack)
        currentEvent = self.eventScheduler.dequeue()
        self.currentTime = currentEvent.time
        if currentEvent.type == PacketType.TIMEOUT:
            return PacketType.TIMEOUT # return timeout to prepare for a retransmission of packet
        elif currentEvent.type == PacketType.ACK:
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN != self.nextExpectedPacket:
                return None # ignore because current protocol is ABP 
            else:
                self.SN = (self.SN + 1) % maxSN
                self.nextExpectedPacket = (self.SN + 1) % maxSN
                return PacketType.ACK # return ACK informs Simulator a successfully delivered packet
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
            time, SN, L = self.sender.send_packet()
            ack = self.SEND(time, SN, L)
            status = self.sender.process_feedback(ack)
            if status == PacketType.TIMEOUT:
                continue
            elif status == None: # We ignore this and wait till timeout
                currentEvent = self.eventScheduler.dequeue()
                while(currentEvent and currentEvent.type != PacketType.TIMEOUT):
                    currentEvent = self.eventScheduler.dequeue()
                if currentEvent is None: # it means that all events are dequeued without finding timeout, which is weird
                    print 'Error: there is no timeout in event'
                    exit(1)
                else:
                    self.sender.update_current_time(currentEvent.time)
            elif status == PacketType.ACK:
                duration -= 1



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
            time, SN, L = self.sender.send_packet()
            ack = self.SEND(time, SN, L)
            status = self.sender.process_feedback(ack)
            if status == PacketType.TIMEOUT or status == None: # Timeout or ack received corrupted
                continue
            elif status == PacketType.ACK:
                duration -= 1
