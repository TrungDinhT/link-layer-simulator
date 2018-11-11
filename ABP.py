from __future__ import division
from baseclasses import *

# For ABP protocol, we only have packet 0 and 1
maxSN = 2

class Sender(EndPoint):
    def __init__(self, timeout, H, l, C, maxSN, eventScheduler, statsManager):
        super(Sender, self).__init__(C, maxSN, eventScheduler, statsManager)
        self.buffer = Buffer(1)
        self.currentTime = 0
        self.SN = 0
        self.nextExpectedPacket = 1
        self.timeout = timeout
        self.packetSize = H + l
    def get_timeout(self):
        return self.timeout
    def send_packet(self):
        self.currentTime = self.currentTime + self.packetSize/self.C
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
                self.statsManager.update_stats(self.packetSize, self.currentTime)
                self.SN = (self.SN + 1) % maxSN
                self.nextExpectedPacket = (self.SN + 1) % maxSN
                return PacketType.ACK # return ACK informs Simulator a successfully delivered packet
        else:
            print 'Unknown type of event'
            exit(1)



class SimulatorABP(Simulator):
    def __init__(self, timeout, H, l, C, tau, BER, duration, statsManager):
        super(SimulatorABP, self).__init__(H, C, tau, BER, duration, statsManager)
        self.receiver = Receiver(H, C, maxSN, self.eventScheduler, statsManager)
        self.sender = Sender(timeout, H, l, C, maxSN, self.eventScheduler, statsManager)
    def run(self):
        while(self.duration):
            time, SN, L = self.sender.send_packet()
            ack = self.SEND(time, SN, L)
            status = self.sender.process_feedback(ack)
            if status == PacketType.TIMEOUT:
                continue
            elif status == None: # We ignore this and wait till timeout
                while(self.eventScheduler.dequeue().type != PacketType.TIMEOUT):
                    continue
            elif status == PacketType.ACK:
                self.duration -= 1
        self.statsManager.save_to_csv()
