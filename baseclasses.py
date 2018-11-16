from __future__ import division
import numpy as np
from enum import Enum
import os


class PacketStatus(Enum):

    NOERROR = 0
    ERROR = 1
    LOSS = 2
    


class EventType(Enum):

    ACK = 0
    TIMEOUT = 1



class EventStatus(Enum):
    
    TIMEOUT = 0
    ACK_ERROR = 1
    ACK = 2
    NO_EVENT = 3


class Protocol(Enum):

    ABP = 0
    ABP_NAK = 1
    GBN = 2



class Packet:

    def __init__(self, pktSize, SN):
        self.packetSize = pktSize
        self.SN = SN

    def size(self):
        return self.packetSize

    def sequence_number(self):
        return self.SN

    def properties(self):
        return self.SN, self.packetSize



class BufferBlock:

    def __init__(self, packet):
        self.data = packet
        self.next = None



# Buffer in case of GBN should be implemented as a circular linked list
class Buffer:

    def __init__(self, bufSize, blockSize):
        self.bufSize = bufSize

        # Init blocks in buffer, we keep head and tail to limit the length of block
        self.head = BufferBlock(Packet(blockSize, 0))
        cur = self.head
        for i in range(1, bufSize):
            cur.next = BufferBlock(Packet(blockSize, i))
            cur = cur.next
        self.tail = cur
        self.tail.next = BufferBlock(Packet(blockSize, bufSize))
        self.tail.next.next = self.head

        # Set current block to first block of buffer
        self.currentBlock = self.head


    def size(self):
        return self.bufSize


    def reset_current_block(self):
        self.currentBlock = self.head


    def reset_buffer(self):
        while(self.head.data.sequence_number() != 0):
            self.head = self.head.next
            self.tail = self.tail.next
        self.currentBlock = self.head


    def slide_to_index(self, index):
        for i in range(0, index):
            self.head = self.head.next
            self.tail = self.tail.next
        self.currentBlock = self.head


    def packet(self):
        if self.currentBlock.next == self.head:
            return None
        else:
            packet = self.currentBlock
            self.currentBlock = self.currentBlock.next
            return packet.data

        
    def block_index(self, pointer_block):
        blk = self.head
        index = 0
        while(blk != pointer_block):
            blk = blk.next
            index += 1
        if index > bufSize:
            index = None
        return index



class Event:

    def __init__(self, type, time, SN=None, errorFlag = None):
        self.type = type
        self.time = time
        if type == EventType.ACK:
            self.SN = SN
            self.errorFlag = errorFlag
        self.next = None



class EventScheduler: # EventScheduler
    
    def __init__(self, event=None):
        self.head = event

        
    def register_event(self, event):
        elm = self.head

        # If the list is empty, we add event to the head of the list
        # Otherwise we loop through all event to find where we can put new event (in increasing time order)
        # If we don't find any element happening later than the event, we put it to the tail
        if elm is None:
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

            # Here we reach the end of the list => we add event to the tail of the list
            if event.next is None: 
                    prev.next = event

    
    def next_event(self):
        return self.head


    def dequeue(self):
        event = self.head
        if event is not None:
            self.head = self.head.next
            event.next = None
        return event

    
    def purge_time_out(self):
        elm = self.head
        prev = None
        timeout = None
        while elm is not None:
            if elm.type == EventType.TIMEOUT:
                if prev is None: # timeout event is at the head of the list
                    timeout = self.dequeue()
                else:
                    timeout = elm
                    prev.next = timeout.next
                    timeout.next = None
                return timeout
            prev = elm
            elm = elm.next    



class ChannelSide:

    def __init__(self, C):
        self.C = C


    def set_params(self, tau, BER):
        self.tau = tau
        self.BER = BER


    def handle_packet(self, time, SN, L):
        # No packet is sent here
        if L is None:
            return None, None, PacketStatus.LOSS

        # We increase the time by propagation delay
        time = time + self.tau

        # Here we try to simulate channel with error probabilities BER per bit
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

    def __init__(self, C, maxSN, eventScheduler):
        self.currentTime = 0
        self.eventScheduler = eventScheduler
        self.maxSN = maxSN
        self.C = C


    def setMaxSN(self, maxSN):
        self.maxSN = maxSN



class Receiver(EndPoint):

    def __init__(self, H, C, maxSN, eventScheduler):
        super(Receiver, self).__init__(C, maxSN, eventScheduler)
        self.nextExpectedPacket = 0
        self.ackPacketSize = H


    def process_packet(self, time, SN, errorFlag):
        # If packet lost before coming to receiver, we send nothing assuming that we received nothing
        if errorFlag == PacketStatus.LOSS:
            return None, None, None
        
        # We update current time on receiver size to the moment it sent the ack away
        self.currentTime = time + self.ackPacketSize / self.C
        if errorFlag == PacketStatus.NOERROR and SN == self.nextExpectedPacket:
            self.nextExpectedPacket = (self.nextExpectedPacket + 1) % self.maxSN
        return self.currentTime, self.nextExpectedPacket, self.ackPacketSize



class StatsManager:

    outputDir = os.getcwd() + '/output/'

    def __init__(self, protocol, delta_rate, n_cols):
        # Init 3 attributes for StatsManager class
        ### totalDataSent -> all data successfully sent
        self.totalDataSent = 0
        ### duration -> the real amount of time needed to send all of those data
        self.duration = 0 
        ### stats -> save throughput for each cases of BER, delta/tau
        self.stats = np.empty([delta_rate.shape[0], n_cols + 1])
        for i in range(0, delta_rate.shape[0]):
            self.stats[i, 0] = delta_rate[i]

        # Create output directory if not exist
        if not os.path.exists(self.outputDir):
            os.makedirs(self.outputDir)

        # Create appropriate output file name for each protocol 
        if protocol == Protocol.ABP:
            self.fileName = self.outputDir + 'ABP.csv'
        elif protocol == Protocol.ABP_NAK:
            self.fileName = self.outputDir + 'ABP_NAK.csv'
        elif protocol == Protocol.GBN:
            self.fileName = self.outputDir + 'GBN.csv'
        else:
            print 'unknown protocol'
            exit(1)


    def reset(self):
        self.totalDataSent = 0
        self.duration = 1


    def update_stats(self, packetSize, currentTime):
        self.totalDataSent += packetSize
        self.duration = currentTime        


    def record_stats(self, row_index, col_index):
        print 'totalDataSent: ' + str(self.totalDataSent)
        print 'time: ' + str(self.duration)
        self.stats[row_index, col_index] = np.around(self.totalDataSent / self.duration, decimals=3)


    def save_to_csv(self):
        with open(self.fileName, 'w') as f:
            for elm in self.stats:
                f.write(','.join(elm.astype(str)) + '\n')



class Simulator(object):

    def __init__(self, H, C, maxSN, duration, statsManager):
        self.statsManager = statsManager
        self.eventScheduler = EventScheduler()
        self.channelSide = ChannelSide(C)
        self.receiver = Receiver(H, C, maxSN, self.eventScheduler)
        self.sender = None # Sender class is defined differently for each protocol
        self.duration = duration # number of packets to be delivered successfully


    def set_params(self, tau, BER):
        self.channelSide.set_params(tau, BER)


    def SEND(self, time, SN, L):
        event = None
        time1, SN, errorFlag = self.channelSide.handle_packet(time, SN, L)
        if errorFlag != PacketStatus.LOSS:
            time2, RN, H = self.receiver.process_packet(time1, SN, errorFlag)
            time3, RN, errorFlag = self.channelSide.handle_packet(time2, RN, H)
            if errorFlag != PacketStatus.LOSS:
                event = Event(EventType.ACK, time3, RN, errorFlag)
        return event # None or an ack


    def transmission_process(self):
        time, SN, L = self.sender.send_packet()
        ack = self.SEND(time, SN, L)
        if ack is not None:
            self.eventScheduler.register_event(ack)
        status = self.sender.read_event()
        return status

