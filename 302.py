#!/usr/bin/env python
from os import environ
from sys import argv, executable
from twisted.internet import reactor
from twisted.python import log
from twisted.protocols import sip
from twisted.internet.protocol import ServerFactory
from twisted.application import internet, service
from pprint import pprint
import txredisapi as redis 
from twisted.internet import defer
import re
import socket

from socket import AF_INET
ip = '127.0.0.1'
# port to bind this redirect server to
myport = 5060

UserAgent = "amazingness"

class SipProxy(sip.Proxy):

    def connect(self):
        self.pool = redis.lazyConnectionPool(host="localhost",port=6379,poolsize=5,reconnect=True)
    def __init__(self):
        self.connect()
        self.findtn = re.compile('(?<=sip:)(.*?)(?=@)')
        sip.Proxy.__init__(self, host=ip, port=myport) 
        
    # generate a SIP redirection response to every SIP request and send it to the originator of the request 
    
    @defer.inlineCallbacks
    def handle_request(self, message, addr):
        if message.method not in  ['INVITE']:return
        TN = self.findtn.search(message.headers["to"][0]).group(1) # use regex to pull out number
        #print ("\n TN IS: " + str(TN))
        """ Yielding the redis results should allow the reactor to continue processing other 
        requests while waiting for response
        """
        if len(TN) == 11: LRN = yield self.pool.get(TN[1:]) 
        else: LRN = yield self.pool.get(TN)
        r = self.responseFromRequest(302, message)
        r.addHeader("Contact", "<sip:" + str(TN) + ";rn=+1" + str(LRN) + ">")
        r.addHeader("User-Agent",UserAgent)
        r.creationFinished()
        self.deliverResponse(r)
        

# wrapper factory for our SipProxy
class sipfactory(ServerFactory):
    protocol = SipProxy

def main(fd=None):  
    if fd is None: 
        port = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Make the port non-blocking and start it listening.
        port.setblocking(False)
        port.bind((ip, myport))
        for i in range(3):
            arglist = [executable, __file__, str(port.fileno())]
            #arglist = [executable,str(port.fileno())]
            reactor.spawnProcess(None, executable, arglist,
                childFDs={0: 0, 1: 1, 2: 2, port.fileno(): port.fileno()},env=environ)
        # pass the port file descriptor to the reactor
        port = reactor.adoptDatagramPort(port.fileno(), socket.AF_INET, SipProxy())
    else:
        # start listening on already created port                                                                          
        port = reactor.adoptDatagramPort(fd, AF_INET, SipProxy())
    reactor.run()
if __name__ == '__main__':
    if len(argv) == 1:
        main()
    else:
        main(int(argv[1]))


