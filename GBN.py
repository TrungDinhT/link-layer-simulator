from __future__ import division
from baseclasses import *

# For GBN protocol, we have a buffer 4 packets in the buffer
maxSN = 4

class Sender(EndPoint):

    def __init__(self, timeout, H, l, C, maxSN, eventScheduler):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.buf = Buffer(maxSN, H + l)
        self.departureTime = [0] * maxSN
        self.currentPacketIndex = 0
        self.currentTime = 0
        self.scheduledPacket = None
        self.SN = 0
        self.nextExpectedPackets = [0] * maxSN
        self.timeout = timeout
        self.dataSize = l

    def get_timeout(self):
        return self.timeout 
    
    def update_current_time(self, time):
        self.currentTime = time

    def sending_time(self, packet):
        time = self.currentTime
        if packet is not None:
            time += packet.size() / self.C
        return time

    def prepare(self):
        self.currentPacketIndex = 0
        self.buf.reset_current_block()
        self.scheduledPacket = self.buf.packet()
        self.SN = self.scheduledPacket.sequence_number()
        self.next_expected_packets()
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(EventType.TIMEOUT, self.sending_time(self.scheduledPacket) + self.timeout))

    def next_expected_packets(self):
        for i in range(0, self.maxSN):
            self.nextExpectedPackets[i] = (self.SN + i + 1) % (self.maxSN + 1)

    def schedule(self):
        SN, L = self.scheduledPacket.properties()
        self.currentTime += L / self.C
        self.departureTime[self.currentPacketIndex] = self.currentTime
        self.scheduledPacket = self.buf.packet()
        return SN, L

    def current_packet_index(self):
        return self.currentPacketIndex

    def send_packet(self):
        SN, L = self.schedule()            
        self.currentPacketIndex += 1
        return self.currentTime, SN, L

    def read_event(self):
        currentEvent = self.eventScheduler.next_event()
        nextSendingTime = self.sending_time(self.scheduledPacket)
        if currentEvent.time > nextSendingTime:
            return EventStatus.NO_EVENT
        if self.currentTime == nextSendingTime: # We sent at maximum we can. Now, we have to reach an ack, otherwise timeout
            self.currentTime = currentEvent.time
        self.eventScheduler.dequeue()
        if currentEvent.type == EventType.TIMEOUT:
            return EventStatus.TIMEOUT # return timeout to prepare for retransmission
        if currentEvent.type == EventType.ACK:
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN not in self.nextExpectedPackets:
                return EventStatus.ACK_ERROR # ignore because current protocol is ABP 
            index = (self.nextExpectedPackets.index(currentEvent.SN) + 1) % (self.maxSN + 1)
            self.buf.slide_to_index(index)
            return EventStatus.ACK # return ACK informs Simulator a successfully delivered packet
        print 'Unknown type of event'
        exit(1)



class SimulatorGBN(Simulator):

    def __init__(self, duration, statsManager):
        super(SimulatorGBN, self).__init__(duration, statsManager)
        
    def set_params(self, timeout, H, l, C, tau, BER):
        super(SimulatorGBN, self).set_params(C, tau, BER)
        self.receiver = Receiver(H, C, maxSN + 1, self.eventScheduler)
        self.sender = Sender(timeout, H, l, C, maxSN, self.eventScheduler)

    def run(self):
        duration = self.duration
        while(duration):
            #print 'duratoin'
            self.sender.prepare()
            for i in range(0, maxSN):
                status = self.transmission_process()
                if status == EventStatus.TIMEOUT:
                    break
                elif status == EventStatus.NO_EVENT: # No event so we send next packet in the batch
                    continue
                elif status == EventStatus.ACK_ERROR:
                    if i < maxSN - 1: # That happens in the middle of sending, we pass to send next packet,
                        continue
                    else: # That happens for last packet, we pass to next event because it is timeout
                        currentEvent = self.eventScheduler.dequeue()
                        self.sender.update_current_time(currentEvent.time)
                elif status == EventStatus.ACK:
                    duration -= 1
                    if duration == 0:
                        break
                else:
                    print 'Error: status not recognized'
                    exit(1)
