from __future__ import division
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
        if event is not None:
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
        if L is None: #No packet is sent here
            return None, None, PacketStatus.LOSS 
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

    def __init__(self, channelSpeed, maxSN, eventScheduler):
        self.currentTime = 0
        self.eventScheduler = eventScheduler
        self.C = channelSpeed
        self.maxSN = maxSN



class Receiver(EndPoint):

    def __init__(self, H, C, maxSN, eventScheduler):
        super(Receiver, self).__init__(C, maxSN, eventScheduler)
        self.nextExpectedPacket = 0
        self.ackPacketSize = H

    def process_packet(self, time, SN, errorFlag):
        if errorFlag == PacketStatus.LOSS:
            return None, None, None
        else:
            self.currentTime = time + self.ackPacketSize / self.C
            if errorFlag == PacketStatus.NOERROR and SN == self.nextExpectedPacket:
                self.nextExpectedPacket = (self.nextExpectedPacket + 1) % self.maxSN
            return self.currentTime, self.nextExpectedPacket, self.ackPacketSize



class StatsManager:

    output_dir = os.getcwd() + '/output/'

    def __init__(self, protocol, delta_rate, n_cols):
        self.throughput = 0
        self.duration = 0 # real duration in seconds of the simulation
        self.stats = np.empty([delta_rate.shape[0], n_cols + 1])
        for i in range(0, delta_rate.shape[0]):
            self.stats[i, 0] = delta_rate[i]
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

    def reset(self):
        self.throughput = 0
        self.duration = 1

    def update_stats(self, packetSize, currentTime):
        self.throughput += packetSize
        self.duration = currentTime        

    def record_stats(self, row_index, col_index):
        self.stats[row_index, col_index] = np.around(self.throughput / self.duration, decimals=3)

    def save_to_csv(self):
        with open(self.file_name, 'w') as f:
            for elm in self.stats:
                f.write(','.join(elm.astype(str)) + '\n')



class Simulator(object):

    def __init__(self, duration, statsManager):
        self.statsManager = statsManager
        self.eventScheduler = EventScheduler()
        self.channelSide = None
        self.receiver = None # Initialized differently for each type of simulator
        self.sender = None # Initialized differently for each type of simulator
        self.duration = duration # number of packets to be delivered successfully

    def set_params(self, C, tau, BER):
        self.channelSide = ChannelSide(C, tau, BER)

    def SEND(self, time, SN, L):
        event = None
        time1, SN, errorFlag = self.channelSide.handle_packet(time, SN, L)
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(PacketType.TIMEOUT, time + self.sender.get_timeout()))
        if errorFlag != PacketStatus.LOSS:
            time2, RN, H = self.receiver.process_packet(time1, SN, errorFlag)
            time3, RN, errorFlag = self.channelSide.handle_packet(time2, RN, H)
            if errorFlag != PacketStatus.LOSS: #Here we create ACK event to return if there is an ACK that can reach sender later
                self.statsManager.update_stats(L - H, time3)
                event = Event(PacketType.ACK, time3, RN, errorFlag)
        return event # None or an ack

