import udt, util, config, time, threading

# Stop-And-Wait reliable transport protocol.
class StopAndWait:
  # "msg_handler" is used to deliver messages to application layer
  # when it's ready.
  def __init__(self, local_port, remote_port, msg_handler):
    self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
    self.msg_handler = msg_handler
    self.wait_for_seq_num = 0
    self.in_process = False
    self.sender_last_sent_packet = ''
    self.receiver_last_sent_packet = util.make_packet(config.MSG_TYPE_ACK, 1, '')
    self.timer_active = True
    self.timer = None

  # "send" is called by application. Return true on success, false
  # otherwise.
  def send(self, msg):
    # don't execute send() when ther is packet in flight
    if self.in_process == True:
      return False
    self.in_process = True
    print 'sender side: sending %s with %s ' % (msg, self.wait_for_seq_num)
    packet = util.make_packet(config.MSG_TYPE_DATA, self.wait_for_seq_num, msg)
    self.sender_last_sent_packet = packet
    self.network_layer.send(packet)
    self.start_timer()
    return True

  def start_timer(self):
    self.timer_active = True
    self.timer = threading.Timer(config.TIMEOUT_MSEC / 1000.0, self.timeout_function)
    self.timer.start()

  def timeout_function(self):
    if self.timer_active == True and self.in_process == True:
      self.network_layer.send(self.sender_last_sent_packet)
      print 'TIME OUT: resending packet', self.sender_last_sent_packet
      print 'current next_seq_number', self.wait_for_seq_num
      self.start_timer()

  # "handler" to be called by network layer when packet is ready.
  def handle_arrival_msg(self):
    msg = self.network_layer.recv()
    print 'receiver received: ', repr(msg)

    # Sender receive ACKs
    if len(msg) == config.ACK_PACKET_LENGTH:
      type, ack_num, receiver_checksum = util.sender_side_unpack_msg(msg)
      print 'sender side: receive msg with ack_num', ack_num
      if not util.rcvpkt_corrupted(type, ack_num, receiver_checksum, '') \
            and type == config.MSG_TYPE_ACK and ack_num == self.wait_for_seq_num:
        print 'we get the packet we want'
        self.in_process = False
        self.wait_for_seq_num = (self.wait_for_seq_num + 1) % 2
        self.timer_active = False
        self.timer.cancel()
      elif util.rcvpkt_corrupted(type, ack_num, receiver_checksum, ''):
        print 'sender side: received corrupted packet'
      else:
        print 'we are expecting ack_num %s but the incoming ack_num is for %s' \
               % (self.wait_for_seq_num, ack_num)

    # Receiver Receive from below
    elif len(msg) > config.ACK_PACKET_LENGTH:
      type, sender_seq_num, sender_checksum, received_msg = util.receiver_side_unpack_msg(msg)
      if not util.rcvpkt_corrupted(type, sender_seq_num, sender_checksum, received_msg) and \
        sender_seq_num == self.wait_for_seq_num:
        self.msg_handler(received_msg)
        print 'receiver side: received a packet and is making ACK packet'
        packet = util.make_packet(config.MSG_TYPE_ACK, self.wait_for_seq_num, '')
        self.network_layer.send(packet)
        self.wait_for_seq_num = (self.wait_for_seq_num + 1) % 2
        self.receiver_last_sent_packet = packet
      elif util.rcvpkt_corrupted(type, sender_seq_num, sender_checksum, received_msg):
        print 'receiver side: received corrupted packet'
        self.network_layer.send(self.receiver_last_sent_packet)
      else:
        print 'receiver side: we are expecting ack_num %s but incoming ack_num is %s' \
              ', resending packet' % (self.wait_for_seq_num, sender_seq_num)
        self.network_layer.send(self.receiver_last_sent_packet)

  # Cleanup resources.
  def shutdown(self):
    while self.in_process:
      print 'program is still in process'
      time.sleep(1)
    self.network_layer.shutdown()
