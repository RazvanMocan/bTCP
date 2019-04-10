import argparse
import socket
from random import randint
from struct import *
from zlib import crc32
from select import select
from queue import Queue


def makepacket(header, payload):
    payload = payload.encode()
    aux_data = pack("IHHBBH1000s", *header, payload)
    check_sum = crc32(aux_data)
    return pack(header_format, *header, check_sum, payload)


# Handle arguments
parser = argparse.ArgumentParser()
parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=100)
parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=100)
parser.add_argument("-i", "--input", help="File to send", default="tmp.file")
args = parser.parse_args()

file = None
try:
    file = open(args.input, "rb")
except FileNotFoundError:
    print("Input file not found")
    exit(1)

destination_ip = "127.0.0.1"
destination_port = 9001

stream_id = randint(0, 2 ** 32 - 1)
syn_nr = randint(0, 2 ** 16 - 1)

# bTCP header

header_format = "IHHBBHI1000s"
bTCP_header = (stream_id, syn_nr, 0, 1, 0, 0)

bTCP_payload = ""

udp_payload = makepacket(bTCP_header, bTCP_payload)
print(udp_payload)
# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# send payload

# Sockets from which we expect to read
inputs = [sock]

# Sockets to which we expect to write
outputs = [sock]
# Outgoing message queues (socket:Queue)
queue = Queue()
sock.sendto(udp_payload, (destination_ip, destination_port))
port = -1
last = [(syn_nr + 1, udp_payload)]
SYN = 1
ACK = 2
FIN = 4
finish = False


def close_socket(soc):
    inputs.remove(soc)
    outputs.remove(soc)
    soc.close()


while inputs:

    # Wait for at least one of the sockets to be ready for processing
    print('\nwaiting for the next event')
    readable, writable, exceptional = select(inputs, outputs, inputs)
    # Handle inputs
    for s in readable:
        data, addr = s.recvfrom(1016)

        if port == -1:
            destination_ip = addr[0]
            destination_port = addr[1]

        if data:
            print('received "%s" from %s' % (data, (destination_ip, destination_port)))
            stream_id, syn_nr, ack_nr, flags, win, length, check, _ = unpack(header_format, data)

            if crc32(bytes(data[:12] + data[16:])) != check:
                continue
            data = ''

            expected = last[0]
            if expected[0] != ack_nr:
                queue.put(expected[1])
                continue

            if finish is True:
                close_socket(s)
                break

            del last[0]
            if flags == SYN + ACK:
                args.window = win
                flags = ACK
                syn_nr += 1
                packet = makepacket((stream_id, ack_nr, syn_nr, ACK, 0, 0), data)
                queue.put(packet)
                last.append((ack_nr + length, packet))
            elif flags == FIN:
                exit(5)
                finish = True
                ack_nr += 1
                packet = makepacket((stream_id, ack_nr, syn_nr, ACK, 0, 0), data)
                queue.put(packet)
                last.append((ack_nr, packet))
            else:
                for i in range(0, win):
                    syn_nr += length
                    d = file.read(1000)
                    length = len(d)
                    packet = makepacket((stream_id, ack_nr, syn_nr, 0, 0, 0), data)
                    queue.put(packet)
                    last.append((ack_nr + length, packet))
                    if length != 1000:
                        ack_nr += 1
                        packet = makepacket((stream_id, ack_nr, syn_nr, FIN, 0, 0), data)
                        queue.put(packet)
                        last.append((ack_nr, packet))
                        print("gata")
                        exit(111)
                        break
                win = 1

    # Handle outputs
    for s in writable:

        while queue.empty() is False:
            next_msg = queue.get_nowait()
            print('sending ')
            s.sendto(next_msg, (destination_ip, destination_port))
            # Handle "exceptional conditions"

    for s in exceptional:
        print('handling exceptional condition for')
        # Stop listening for input on the connection
        close_socket(s)

    if not (readable or writable or exceptional):
        if finish is True:
            close_socket(sock)
        for packet in last:
            queue.put(packet[1])