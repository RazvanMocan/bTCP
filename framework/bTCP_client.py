import argparse
import socket
from random import randint
from struct import *
from zlib import crc32
from select import select
from queue import Queue

short_max = 2 ** 16 - 1


def makepacket(header, payload):
    stream_id1, syn_nr1, ack_nr1, flags1, win1, len1 = header
    syn_nr1 %= short_max
    ack_nr1 %= short_max
    if type(payload) is not bytes:
        payload = payload.encode()
    aux_data = pack("IHHBBH1000s", stream_id1, syn_nr1, ack_nr1, flags1, win1, len1, payload)
    check_sum = pack("I", crc32(aux_data))
    return aux_data[:12] + check_sum + aux_data[12:]


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
# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)
# send payload

# Sockets from which we expect to read
inputs = [sock]

# Sockets to which we expect to write
outputs = [sock]
# Outgoing message queues (socket:Queue)
queue = Queue()
sock.sendto(udp_payload, (destination_ip, destination_port))
port = -1
last = [((syn_nr + 1) % short_max, udp_payload)]
SYN = 1
ACK = 2
FIN = 4
finish = False
save = None


def close_socket(soc):
    print("close")
    inputs.remove(soc)
    soc.close()


def send_response(head, dat, l):
    packet = makepacket(head, dat)
    queue.put(packet)
    last.append(((ack_nr + l) % short_max, packet))
    outputs.append(sock)


while inputs:
    # Wait for at least one of the sockets to be ready for processing
    # print('\nwaiting for the next event')
    readable, writable, exceptional = select(inputs, outputs, inputs, 1 / args.timeout)
    # Handle inputs
    for s in readable:
        try:
            data, addr = s.recvfrom(1016)
        except BlockingIOError:
            continue

        if port == -1:
            destination_ip = addr[0]
            destination_port = addr[1]

        if data:
            stream_id, syn_nr, ack_nr, flags, win, length, check, _ = unpack(header_format, data)

            print("\nreceived")
            print(stream_id, syn_nr, ack_nr, flags, win, length, check)
            print()
            # sleep(1)

            if crc32(bytes(data[:12] + data[16:])) != check:
                print("corupt")
                continue
            data = ''
            print("integrity ok")

            expected = last[0]
            if expected[0] + (1 if flags == ACK or flags == FIN else 0) != ack_nr:
                # print(expected[0] + (1 if flags == ACK else 0), ack_nr)
                print("\nWrong order")
                print(expected[0], ack_nr)
                continue

            if finish is True:
                close_socket(s)
                continue

            if flags == SYN + ACK:
                args.window = win
                flags = ACK
                syn_nr += 1
                send_response((stream_id, ack_nr, syn_nr, ACK, 0, 0), data, length)
            elif flags == FIN:
                print("Finish")
                finish = True
                syn_nr += 1
                send_response((stream_id, ack_nr, syn_nr, ACK, 0, 0), data, 0)

            elif flags == ACK:
                continue
            else:
                if save is None:
                    save = (syn_nr, ack_nr, ack_nr, length)
                if args.window != 0:
                    syn_nr, ack_nr, expected, length = save
                for i in range(0, args.window):
                    ack_nr += length
                    d = file.read(1000)
                    length = len(d)
                    expected += length
                    send_response((stream_id, ack_nr, syn_nr, 0, 0, length), d, expected - ack_nr)
                    syn_nr += 1
                    save = (syn_nr, ack_nr, expected, length)

                    if length != 1000:
                        args.window = 0
                        break

                if args.window > 0:
                    args.window = 1
                elif len(last) == 1:
                    syn_nr += 1
                    send_response((stream_id, ack_nr, syn_nr, FIN, 0, 0), data, 0)
            del last[0]

    # Handle outputs
    for s in writable:
        while queue.empty() is False:
            next_msg = queue.get_nowait()
            print('\nsending')
            print(unpack(header_format, next_msg))
            print()
            # sleep(1)
            s.sendto(next_msg, (destination_ip, destination_port))
        outputs.remove(s)

    # Handle "exceptional conditions"
    for s in exceptional:
        print('handling exceptional condition for')
        # Stop listening for input on the connection
        close_socket(s)

    if not (readable or writable or exceptional):
        print("timeout", finish, len(last), len(outputs))
        if finish is True and len(last) == 0:
            close_socket(sock)
        else:
            outputs.append(sock)
            for packet in last:
                queue.put(packet[1])
