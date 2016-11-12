import udt, config, util, threading, time, collections


# Go-Back-N reliable transport protocol.
class GoBackN:
  # "msg_handler" is used to deliver messages to application layer
  # when it's ready.
  def __init__(self, local_port, remote_port, msg_handler):
    self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
    self.msg_handler = msg_handler
    self.base = 1
    self.nextseqnum = 1
    self.rcver_wait_for_seq_num = 1
    self.timer = None
    self.timer_active = False
    self.last_sent_packets = []
    self.last_ack_pkt = util.make_packet(config.MSG_TYPE_ACK, 0, '')

  # "send" is called by application. Return true on success, false
  # otherwise.
  def send(self, msg):
    if self.nextseqnum < self.base + config.WINDOWN_SIZE:
      print repr(msg)
      packet = util.make_packet(config.MSG_TYPE_DATA, self.nextseqnum, msg)
      self.last_sent_packets.append(packet)
      self.network_layer.send(packet)
      print 'after sending packet %s, my last_sent_packets becomes %s' % (packet, self.last_sent_packets)
      print 'waiting for ack,', self.nextseqnum
      if self.base == self.nextseqnum:
        self.start_timer()
        print 'self.base == self.nextseqnum, start the timer %s' % (self.timer)
      self.nextseqnum += 1
      return True
    else:
      return False

  def start_timer(self):
    if self.timer is not None:
      self.timer.cancel()
    self.timer_active = True
    self.timer = threading.Timer(config.TIMEOUT_MSEC / 1000.0, self.timeout_function)
    self.timer.start()

  def timeout_function(self):
    self.start_timer()
    for packet in self.last_sent_packets:
      print 'timeout: iterating, sending packets: %s' % (packet)
      self.network_layer.send(packet)

  # "handler" to be called by network layer when packet is ready.
  def handle_arrival_msg(self):
    msg = self.network_layer.recv()
    print 'MESSAGE Received!', repr(msg)

    # Sender receive ACKs
    if len(msg) == config.ACK_PACKET_LENGTH:
      type, ack_num, receiver_checksum = util.sender_side_unpack_msg(msg)
      print 'sender side: receive msg with ack_num', ack_num
      if not util.rcvpkt_corrupted(type, ack_num, receiver_checksum, '') \
            and type == config.MSG_TYPE_ACK:
        print 'Done waiting for ACK', ack_num
        if ack_num + 1 > self.base:
          for i in range(ack_num + 1 - self.base):
            self.last_sent_packets.pop(0)
          print 'After poping out last_sent_packets is ', self.last_sent_packets

          self.base = ack_num + 1

          if self.base == self.nextseqnum:
            self.timer_active = False
            self.timer.cancel()
          else:
            #self.timer.cancel()
            # print 'sender receive: canceled timer', self.timer
            self.start_timer()
      else:
        print 'pck corrupted!'
    # Receiver Receive from below
    elif len(msg) > config.ACK_PACKET_LENGTH:
      type, sender_seq_num, sender_checksum, received_msg = util.receiver_side_unpack_msg(msg)
      if not util.rcvpkt_corrupted(type, sender_seq_num, sender_checksum, received_msg) and \
                      sender_seq_num == self.rcver_wait_for_seq_num:
        self.msg_handler(received_msg)
        print 'receiver side: received the packet Im waiting for %s and is making packet with ACK=%s' % (self.rcver_wait_for_seq_num, sender_seq_num)
        packet = util.make_packet(config.MSG_TYPE_ACK, self.rcver_wait_for_seq_num, '')
        self.network_layer.send(packet)
        self.last_ack_pkt = packet
        self.rcver_wait_for_seq_num += 1
      elif util.rcvpkt_corrupted(type, sender_seq_num, sender_checksum, received_msg):
        print 'packet corrupted!! sender_seq_num is %s but I am waiting for %s ' % (sender_seq_num, self.rcver_wait_for_seq_num)
        #packet = util.make_packet(config.MSG_TYPE_ACK, self.wait_for_seq_num, '')
        self.network_layer.send(self.last_ack_pkt)
      elif sender_seq_num != self.rcver_wait_for_seq_num:
        # if self.wait_for_seq_num == 1 and sender_seq_num > 1:
        #   print 'we are expecting seq_num = 1'
        # else:
        #   print 'receiver side: waiting for seq_num %s but I got seq_num %s' % (self.wait_for_seq_num, sender_seq_num)
        #   packet = util.make_packet(config.MSG_TYPE_ACK, self.wait_for_seq_num, '')
        #   self.network_layer.send(packet)
        print 'receiver side: waiting for seq_num %s but I got seq_num %s' % (self.rcver_wait_for_seq_num, sender_seq_num)
        self.network_layer.send(self.last_ack_pkt)

  # Cleanup resources.
  def shutdown(self):
    while self.timer_active:
      print 'program is still in process'
      time.sleep(1)
    self.network_layer.shutdown()
