from __future__ import division
from baseclasses import *


class Sender(EndPoint):

    def __init__(self, H, l, C, maxSN, eventScheduler, statsManager):
        super(Sender, self).__init__(C, maxSN, eventScheduler)
        self.statsManager = statsManager
        self.buf = Buffer(maxSN, H + l)
        self.departureTime = [0] * maxSN
        self.currentPacketIndex = 0
        self.currentTime = 0
        self.scheduledPacket = None
        self.SN = 0
        self.nextExpectedPackets = [0] * maxSN
        self.dataSize = l


    def get_timeout(self):
        return self.timeout

    def batch_size(self):
        return self.maxSN

    def reset(self, timeout):
        self.timeout = timeout
        self.buf.reset_buffer() # Reset the buffer to initial state
        self.departureTime = [0] * self.maxSN
        self.currentPacketIndex = 0
        self.currentTime = 0
        self.scheduledPacket = None
        self.SN = 0
        self.nextExpectedPackets = [0] * self.maxSN


    def update_current_time(self, time):
        self.currentTime = time


    def sending_time(self, packet):
        # If we still have packet to send, we compute the transmission delay
        # Otherwise, it stays at 0
        tDelay = 0
        if packet is not None:
            tDelay = packet.size() / self.C
        return self.currentTime + tDelay


    def prepare(self):
        # Reset currentPacketIndex to the 0
        self.currentPacketIndex = 0

        # Reset the buffer to the oldest unacked packet
        self.buf.reset_current_block()

        # Return the packet scheduled to be send next, and its sequence number
        self.scheduledPacket = self.buf.packet()
        self.SN = self.scheduledPacket.sequence_number()
        
        # Recompute next expected sequence numbers from the SN above
        self.next_expected_packets()

        # Recompute the timeout based on transmission time of first packet in the batch
        self.eventScheduler.purge_time_out()
        self.eventScheduler.register_event(Event(EventType.TIMEOUT, self.sending_time(self.scheduledPacket) + self.timeout))


    def next_expected_packets(self):
        for i in range(0, self.maxSN):
            self.nextExpectedPackets[i] = (self.SN + i + 1) % (self.maxSN + 1)


    def schedule(self):
        # Get the properties of packet (scheduled for sending): sequence number and size
        SN, L = self.scheduledPacket.properties()
        
        # Update current time and save it to departureTime for further use
        self.currentTime += L / self.C
        self.departureTime[self.currentPacketIndex] = self.currentTime

        # Get next packet to send from buffer and put it to scheduledPacket
        self.scheduledPacket = self.buf.packet()
        
        # Return the properties of packet to send
        return SN, L


    def current_packet_index(self):
        return self.currentPacketIndex


    def send_packet(self):
        # Get he properties of packet to send
        SN, L = self.schedule()

        # Increase currentPacketIndex to 1 as if we have sent a packet
        self.currentPacketIndex += 1

        # Return the time, SN and size of packet to function SEND()
        return self.currentTime, SN, L


    def read_event(self):
        # We inspect next event in ES, but not dequeue yet
        currentEvent = self.eventScheduler.next_event()

        # Compute the time to send scheduled packet. 
        # If we don't have any other packet to send, it returns the currentTime
        nextSendingTime = self.sending_time(self.scheduledPacket)

        # If it's smaller than the time of the event, it means that we don't have to treat the event yet, 
        # so just return with no event and prepare to send next packet 
        if currentEvent.time > nextSendingTime:
            return EventStatus.NO_EVENT
        
        # When we have to process the event, first compare currentTime and next sending time
        # If they are equal, it means that we don't have any packet it the batch to send.
        # Therefore, update currentTime with even's time. The event can be an ack or a timeout.
        if self.currentTime == nextSendingTime:
            self.currentTime = currentEvent.time
        
        # Dequeue event for inspection
        self.eventScheduler.dequeue()

        # Base on event's type, return appropriate status for simulator to handle it
        # In case we get a successful ack, we have to slide the buffer and update the statistics
        if currentEvent.type == EventType.TIMEOUT:
            return EventStatus.TIMEOUT
        if currentEvent.type == EventType.ACK:
            if currentEvent.errorFlag == PacketStatus.ERROR or currentEvent.SN not in self.nextExpectedPackets:
                return EventStatus.ACK_ERROR
            else:
                self.statsManager.update_stats(self.dataSize, self.currentTime)
                index = (self.nextExpectedPackets.index(currentEvent.SN) + 1) % (self.maxSN + 1)
                self.buf.slide_to_index(index)
                return EventStatus.ACK # return ACK informs Simulator a successfully delivered packet



class SimulatorGBN(Simulator):

    def __init__(self, H, l, C, maxSN, duration, statsManager):
        super(SimulatorGBN, self).__init__(H, C, maxSN, duration, statsManager)
        self.sender = Sender(H, l, C, maxSN, self.eventScheduler, self.statsManager)
        self.receiver.setMaxSN(maxSN + 1)


    def set_params(self, timeout, tau, BER):
        super(SimulatorGBN, self).set_params(tau, BER)
        self.sender.reset(timeout)


    def run(self):
        duration = self.duration
        while(duration > 0):
            # We prepare sender, before sending a batch, even if it's for a timeout or and ack
            self.sender.prepare()

            # Each time we try to send at most maxSN packets
            for i in range(0, self.sender.batch_size()):

                # This is the return from sender.read_event()
                status = self.transmission_process()

                # If it's a corrupted ACK: 
                ### if that happens in the middle of sending, we pass to send next packet
                ### if that happens for last packet, we pass to next event because it is timeout
                if status == EventStatus.ACK_ERROR:
                    if i < self.sender.batch_size() - 1:
                        continue
                    else:
                        status = self.sender.read_event() 
                        while(status == EventStatus.ACK_ERROR):
                            status = self.sender.read_event()

                # If it's a timeout, we break to for loop, move on to retransmission
                if status == EventStatus.TIMEOUT:
                    break

                # It there is no event happening, move on and send next packet in the batch
                elif status == EventStatus.NO_EVENT:
                    continue

                # This is a successful ACK, so we count 1 more packet successfully transmitted
                elif status == EventStatus.ACK:
                    duration -= 1
                    break
