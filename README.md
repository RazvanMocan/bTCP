# Issues
There were 2 issues that I found in my code:
* Error detection
* Flow control

## Error detection
This was the error that was causing the BlockingIOError. I have implemented the error detection mechanism as if I would
do it in an oS program. The problem was that the actual error detection was done by the UDP protocol and the packet was
discarded but the pol and select objects were not informed about this and they were expecting data to be present in the 
socket.

### Solution
The solution was very simple: add a try catch block around the reading from the socket. If the error was detected do 
nothing, the packet will be retransmitted when the timeout is reached.

## Flow control
I did not take into account the fact that the acknowledgement may be lost. 

### Solution

I had to add a new case in the if statement.
The only difference between this case and the normal case where the packet is ignored and previous acknowledged packet is
sent is that here the server should properly respond. 