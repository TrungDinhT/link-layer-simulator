import numpy as np
from enum import Enum
import os

class PacketStatus(Enum):
    NOERROR = 0
    ERROR = 1
    LOSS = 2
    
class PacketType(Enum):
    ACK = 0
    TIMEOUT = 1

class Protocol(Enum):
    ABP = 0
    ABP_NAK = 1
    GBN = 2

class Packet:
    def __init__(self, pktSize, SN):
        self.packetSize = pktSize
        self.SN = SN
    def properties(self):
        return self.packetSize, self.SN

class BufferBlock:
    def __init__(self, packet=None):
        self.data = packet
        self.next = None

# Buffer in case of GBN should be implemented as a circular linked list
class Buffer:
    def __init__(self, bufSize, bufferBlock=None):
        self.head = bufferBlock
        self.bufSize = bufSize

class Event:
    def __init__(self, type, time, SN=None, errorFlag = None):
        self.type = type
        self.time = time
        if type == PacketType.ACK:
            self.SN = SN
            self.errorFlag = errorFlag
        self.next = None

class EventScheduler: # EventScheduler
    def __init__(self, event=None):
        self.head = event
    def register_event(self, event):
        elm = self.head
        if elm is None: # we have an empty list now
            self.head = event
        else:
            prev = None
            while elm is not None:
                if elm.time > event.time:
                    event.next = elm
                    if prev is None:
                        self.head = event
                    else:
                        prev.next = event
                    return
                prev = elm
                elm = elm.next
            if event.next is None: # event is not inserted in the queue yet, because the tail has been reached already
                    prev.next = event
    def dequeue(self):
        event = self.head
        self.head = self.head.next
        event.next = None # Totally cut off relation between event and the queue
        return event
    def purge_time_out(self):
        elm = self.head
        prev = None
        timeout = None
        while elm is not None:
            if elm.type == PacketType.TIMEOUT:
                if prev is None: # timeout event is at the head, so purge it like doing dequeue()
                    timeout = self.dequeue()
                else:
                    timeout = elm
                    prev.next = timeout.next
                    timeout.next = None
                return timeout
            prev = elm
            elm = elm.next    

class ChannelSide:
    def __init__(self, C, tau, BER):
        self.tau = tau
        self.BER = BER
        self.C = C
    def handle_packet(self, time, SN, L):
        if L == 0: #No packet is sent here
            return 0, 0, PacketStatus.LOSS 
        time = time + self.tau
        errors = np.random.choice([0,1], L, p=[self.BER, 1-self.BER])
        numberOfErrors = np.sum(errors == 0)
        errorFlag = PacketStatus.NOERROR
        if numberOfErrors >= 5:
            errorFlag = PacketStatus.LOSS
            time = time - self.tau
        elif numberOfErrors >= 1:
            errorFlag = PacketStatus.ERROR
        return time, SN, errorFlag

class EndPoint(object):
    def __init__(self, channelSpeed, maxSN, eventScheduler, statsManager):
        self.currentTime = 0
        self.eventScheduler = eventScheduler
        self.statsManager = statsManager
        self.C = channelSpeed
        self.maxSN = maxSN

class Receiver(EndPoint):
    def __init__(self, H, C, maxSN, eventScheduler, statsManager):
        super(Receiver, self).__init__(C, maxSN, eventScheduler, statsManager)
        self.nextExpectedPacket = 0
        self.ackPacketSize = H
    def process_packet(self, time, SN, errorFlag):
        if errorFlag == PacketStatus.LOSS:
            return 0, 0, 0
        else:
            self.currentTime = time + self.ackPacketSize / self.C
            if errorFlag == PacketStatus.NOERROR and SN == self.nextExpectedPacket:
                self.eventScheduler.purge_time_out()
                self.nextExpectedPacket = (self.nextExpectedPacket + 1) % self.maxSN
            return self.currentTime, self.nextExpectedPacket, self.ackPacketSize

class StatsManager:
    output_dir = os.getcwd() + '/output/'
    def __init__(self, protocol, duration):
        self.numberOfDeliveredPackets = 0
        self.throughput = 0
        self.duration = duration # duration is calculated by number of successfully delivered packets
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if protocol == Protocol.ABP:
            self.file_name = self.output_dir + 'ABP.csv'
        elif protocol == Protocol.ABP_NAK:
            self.file_name = self.output_dir + 'ABP_NAK.csv'
        elif protocol == Protocol.GBN:
            self.file_name = self.output_dir + 'GBN.csv'
        else:
            print 'unknown protocol'
            exit(1)
        with open(self.file_name, 'w') as f:
            f.write('timeout,tau,BER,throughput\n')
    def set_params(self, timeout, tau, BER):
        self.timeout = timeout
        self.tau = tau
        self.BER = BER        
    def update_stats(self, packetSize, currentTime):
        self.numberOfDeliveredPackets += 1
        self.throughput += packetSize
        if self.numberOfDeliveredPackets == self.duration:
            self.throughput /= currentTime 
    def save_to_csv(self):
        with open(self.file_name, 'a') as f:
            data = np.around(np.array([self.tau, self.timeout, self.BER, self.throughput]), decimals=5).astype(str)
            f.write(','.join(data))
            f.write('\n')

class Simulator(object):
    def __init__(self, H, C, tau, BER, duration, statsManager):
        self.eventScheduler = EventScheduler()
        self.channelSide = ChannelSide(C, tau, BER)
        self.statsManager = statsManager
        self.receiver = None # Initialized differently for each type of simulator
        self.sender = None # Initialized differently for each type of simulator
        self.duration = duration # number of packets to be delivered successfully
    def SEND(self, time, SN, L):
        event = None
        time, SN, errorFlag = self.channelSide.handle_packet(time, SN, L)
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(PacketType.TIMEOUT, time + self.sender.get_timeout()))
        if errorFlag != PacketStatus.LOSS:
            time, RN, H = self.receiver.process_packet(time, SN, errorFlag)
            time, RN, errorFlag = self.channelSide.handle_packet(time, RN, H)
            if errorFlag != PacketStatus.LOSS: #Here we create ACK event to return if there is an ACK that can reach sender later
                event = Event(PacketType.ACK, time, RN, errorFlag)
        return event # None or an ack

