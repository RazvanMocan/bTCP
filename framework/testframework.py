import unittest
import socket
import time
import sys

timeout = 100
winsize = 100
intf = "lo"
netem_add = "sudo tc qdisc add dev {} root netem".format(intf)
netem_change = "sudo tc qdisc change dev {} root netem {}".format(intf, "{}")
netem_del = "sudo tc qdisc del dev {} root netem".format(intf)


def run_command_with_output(command, input=None, cwd=None, shell=True):
    """run command and retrieve output"""
    import subprocess

    try:
        process = subprocess.Popen(command, cwd=cwd, shell=shell, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        [stdoutdata, stderrdata] = process.communicate(input)
        # no pipes set for stdin/stdout/stdout streams so does effectively only just wait for process ends  (
        # same as process.wait()

        if process.returncode:
            print(stderrdata)
            print("problem running command : \n   ", str(command), " ", process.returncode)

        return stdoutdata
    except Exception as inst:
        print("problem running command : \n   ", str(command))


def run_command(command, cwd=None, shell=True):
    """run command with no output piping"""
    import subprocess
    process = None
    try:
        process = subprocess.Popen(command, shell=shell, cwd=cwd)
        print(str(process))
    except Exception as inst:
        print("1. problem running command : \n   ", str(command), "\n problem : ", str(inst))

    process.communicate()  # wait for the process to end

    if process.returncode:
        print("2. problem running command : \n   ", str(command), " ", process.returncode)


class TestbTCPFramework(unittest.TestCase):
    """Test cases for bTCP"""

    def setUp(self):
        """Prepare for testing"""
        # default netem rule (does nothing)
        run_command(netem_add)

        # launch localhost server

    def tearDown(self):
        """Clean up after testing"""
        # clean the environment
        run_command(netem_del)

        # close server

    def test_ideal_network(self):
        """reliability over an ideal framework"""
        # setup environment (nothing to set)

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_flipping_network(self):
        """reliability over network with bit flips 
        (which sometimes results in lower layer packet loss)"""
        # setup environment
        run_command(netem_change.format("corrupt 1%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_duplicates_network(self):
        """reliability over network with duplicate packets"""
        # setup environment
        run_command(netem_change.format("duplicate 10%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_lossy_network(self):
        """reliability over network with packet loss"""
        # setup environment
        run_command(netem_change.format("loss 10% 25%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_reordering_network(self):
        """reliability over network with packet reordering"""
        # setup environment
        run_command(netem_change.format("delay 20ms reorder 25% 50%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_delayed_network(self):
        """reliability over network with delay relative to the timeout value"""
        # setup environment
        run_command(netem_change.format("delay " + str(timeout) + "ms 20ms"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_allbad_network(self):
        """reliability over network with all of the above problems"""

        # setup environment
        run_command(netem_change.format("corrupt 1% duplicate 10% loss 10% 25% delay 20ms reorder 25% 50%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client   


#    def test_command(self):
#        #command=['dir','.']
#        out = run_command_with_output("dir .")
#        print(out)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="bTCP tests")
    parser.add_argument("-w", "--window", help="Define bTCP window size used", type=int, default=100)
    parser.add_argument("-t", "--timeout", help="Define the timeout value used (ms)", type=int, default=timeout)
    args, extra = parser.parse_known_args()
    timeout = args.timeout
    winsize = args.window

    # Pass the extra arguments to unittest
    sys.argv[1:] = extra

    # Start test suite
    unittest.main()
