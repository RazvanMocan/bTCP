import argparse
import socket
from queue import Queue
from struct import *
import select
from zlib import crc32
from random import randint

SYN = 1
ACK = 2
FIN = 4

short_max = 2 ** 16 - 1


def checkintegrity(payload):
    checksum = unpack("I", payload[12:16])[0]
    to_check = payload[:12] + payload[16:]
    to_check = crc32(to_check)
    if checksum != to_check:
        return False
    return True


def build_acknowlwdge(stream_id, syn_nr, ack_nr, flags):
    f = 0
    win = 0
    d = ''
    length = 0
    packet = []

    if flags == SYN:
        f = SYN + ACK
        ack_nr += 1
        syn_nr = randint(0, 2**16 - 1)
        win = args.window
    elif flags == FIN:
        ack_nr += 1
        packet.append(create_packet(stream_id, syn_nr, ack_nr, ACK, win, length, d))
        f = FIN
    elif flags == ACK:
        length = 0
    else:
        d = 'K'
        length = 1

    print("\nSend:")
    print(stream_id, syn_nr, ack_nr, f, win, length, d)
    print()
    packet.append(create_packet(stream_id, syn_nr, ack_nr, f, win, length, d))
    return ack_nr, packet


def create_packet(stream_id, syn_nr, ack_nr, f, win, length, d):
    d = d.encode()
    syn_nr %= short_max
    ack_nr %= short_max
    aux_data = pack("IHHBBH1000s", stream_id, syn_nr, ack_nr, f, win, length, d)
    check_sum = pack("I", crc32(aux_data))
    return aux_data[:12] + check_sum + aux_data[12:]


def checkorder(syn_nr, prev, addition):
    if prev is None:
        return True
    elif syn_nr != prev + addition:
        return False
    return True


def react(payload, f, s_id, prev, expected):
    if checkintegrity(payload) is False:
        return f, expected, prev
    stream_id, syn_nr, ack_nr, flags, win, length, check, load = unpack(header_format, payload)
    print("\nReceived:")
    print(stream_id, syn_nr, ack_nr, flags, win, length, check, load)
    print()
    if stream_id != s_id:
        print("There was a problem with the session")
        print(stream_id, s_id)
        exit(1)
    if checkorder(syn_nr, expected, 0) is False:
        print("wrong order")
        print(syn_nr, expected)
        return f, expected, prev
    f.write(load[:length])
    f.flush()
    ack_nr, packet = build_acknowlwdge(stream_id, ack_nr, (syn_nr + length) % short_max, flags)
    return flags, ack_nr, packet


def close_connection(connection_socket):
    print("\n\nclosing\n\n")
    poller.unregister(connection_socket)
    aux[connection_socket][0].close()
    del aux[connection_socket]
    del fd_to_socket[connection_socket.fileno()]
    del close[s]
    connection_socket.close()
    # Remove message queue
    del message_queues[connection_socket]


# Handle arguments
parser = argparse.ArgumentParser()
parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=5)
parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=100)
parser.add_argument("-o", "--output", help="Where to store file", default="tmp.file")
args = parser.parse_args()

server_ip = "127.0.0.1"
server_port = 9001
packet_size = 1016

# Define a header format
header_format = "IHHBBHI1000s"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
sock.setblocking(False)
sock.bind((server_ip, server_port))

# Commonly used flag setes
READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR
READ_WRITE = READ_ONLY | select.POLLOUT

message_queues = {}

# Set up the poller
poller = select.poll()
poller.register(sock, READ_ONLY)

fd_to_socket = {sock.fileno(): (sock, server_ip), }
aux = {}
close = {}


while True:
                                                                                                                                            
    # Wait for at least one of the sockets to be ready for processing
    print('\nwaiting for the next event')
    events = poller.poll()

    for fd, flag in events:

        # Retrieve the actual socket from its file descriptor
        (s, client_address) = fd_to_socket[fd]
        print(client_address)

        # Handle inputs
        if flag & (select.POLLIN | select.POLLPRI):

            if s is sock:
                data, client_address = s.recvfrom(packet_size)
                connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                connection.setblocking(False)

                print('new connection from ', client_address)
                fd_to_socket[connection.fileno()] = (connection, client_address)
                poller.register(connection, READ_WRITE)

                file = open(args.output + client_address[0] + str(client_address[1]), "wb")
                aux[connection] = [file, unpack("I", data[:4])[0], None, unpack("H", data[4:6])[0]]
                _, seq_nr, response = react(data, *aux[connection])

                # Give the connection a queue for data we want to send
                message_queues[connection] = Queue()
                for r in response:
                    message_queues[connection].put(r)
                aux[connection][2] = response
                aux[connection][3] = seq_nr
                close[connection] = 0
            else:
                data = s.recv(packet_size)

                if data:
                    # A readable client socket has data
                    print('received "{}" from {}'.format(data, client_address))
                    flag, seq_nr, response = react(data, *aux[s])
                    for r in response:
                        message_queues[s].put(r)
                    aux[s][2] = response
                    aux[s][3] = seq_nr
                    if close[s] == 2 and flag == ACK:
                        close[s] = True
                    else:
                        close[s] = len(response)
                    poller.modify(s, READ_WRITE)
                    # Add output channel for response
                else:
                    # Interpret empty result as closed connection
                    # Stop listening for input on the connection
                    close_connection(s)

        elif flag & select.POLLHUP:
            # Client hung up
            print("hung up")
            # Stop listening for input on the connection
            close_connection(s)

        elif flag & select.POLLOUT:
            # Socket is ready to send data, if there is any to send.
            if message_queues[s].empty():
                print('output queue for', client_address, 'is empty')
                poller.modify(s, READ_ONLY)
            else:
                while not message_queues[s].empty():
                    next_msg = message_queues[s].get_nowait()
                    # No messages waiting so stop checking for writability.
                    print('sending')
                    print(unpack(header_format, next_msg))
                    s.sendto(next_msg, client_address)
                if close[s] is True:
                    close_connection(s)


        elif flag & select.POLLERR:
            print('handling exceptional condition for', client_address)
            # Stop listening for input on the connection
            close_connection(s)


