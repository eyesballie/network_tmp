import dummy
import gbn
import ss, struct

def get_transport_layer_by_name(name, local_port, remote_port, msg_handler):
  assert name == 'dummy' or name == 'ss' or name == 'gbn'
  if name == 'dummy':
    return dummy.DummyTransportLayer(local_port, remote_port, msg_handler)
  if name == 'ss':
    return ss.StopAndWait(local_port, remote_port, msg_handler)
  if name == 'gbn':
    return gbn.GoBackN(local_port, remote_port, msg_handler)

def cal_checksum(type, seq_num, msg):
  result = type + seq_num
  if len(msg) % 2 != 0:
    msg += '0'
  i = 0
  while i < len(msg):
    num1 = ord(msg[i])
    num2 = ord(msg[i + 1]) << 8 # shift to meet big endian
    result += (num1 + num2)

    # Deal with overflow
    result = (result >> 16) + (result & 0xffff)
    i += 2
  return result

def rcvpkt_corrupted(type, seq_num, sender_checksum, received_msg):
  if len(received_msg) % 2 != 0:
    received_msg += '0'
  receiver_checksum = cal_checksum(type, seq_num, received_msg)
  return receiver_checksum != sender_checksum

def make_packet(type, seq_num, msg):
  checksum = cal_checksum(type, seq_num, msg)
  packet = struct.pack('!HHH', type, seq_num, checksum) + msg
  return packet

def sender_side_unpack_msg(msg):
  type = (struct.unpack('!H', msg[:2]))[0]
  ack_num = (struct.unpack('!H', msg[2:4]))[0]
  receiver_checksum = (struct.unpack('!H', msg[4:6]))[0]
  return type, ack_num, receiver_checksum

def receiver_side_unpack_msg(msg):
  type = (struct.unpack('!H', msg[:2]))[0]
  sender_seq_num = (struct.unpack('!H', msg[2:4]))[0]
  sender_checksum = (struct.unpack('!H', msg[4:6]))[0]
  received_msg = msg[6:]
  return type, sender_seq_num, sender_checksum, received_msg