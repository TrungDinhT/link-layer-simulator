from __future__ import division
from baseclasses import *

# For GBN protocol, we have a buffer 4 packets in the buffer
maxSN = 4

class Sender(EndPoint):

    def __init__(self, timeout, H, l, C, maxSN, eventScheduler):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.buf = Buffer(maxSN, H + l)
        self.currentTime = [0] * maxSN
        self.timeout = timeout
        self.dataSize = l

    def get_timeout(self):
        return self.timeout
    
    def update_current_time(self, time):
        self.currentTime = time

    def send_packet(self, ith):
        time = None
        index = self.buf.block_index(self.buf.cur_block())
        packet = self.buf.packet()
        if packet is not None:
            SN, L = packet.properties()
            self.currentTime[index] += L / self.C
            time = self.currentTime[index]
        else:
            SN, L = None, None
        return time, SN, L

    def read_event()(self):
        currentEvent = self.eventScheduler.dequeue()
        self.currentTime = currentEvent.time
        if currentEvent.type == EventType.TIMEOUT:
            return EventStatus.TIMEOUT # return timeout to prepare for a retransmission of packet
        elif currentEvent.type == EventType.ACK:
            listOfExpectedPackets = self.buf.next_expected_packets()
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN not in listOfExpectedPackets:
                return EventStatus.ACK_ERROR # ignore because current protocol is ABP 
            else:
                new_start = listOfExpectedPackets.index(currentEvent.SN)
                self.buf.slide_to_index(new_start)
                return EventStatus.ACK # return ACK informs Simulator a successfully delivered packet
        else:
            print 'Unknown type of event'
            exit(1)
    
