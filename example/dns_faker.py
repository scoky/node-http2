#!/usr/bin/python

import logging
import argparse
import sys
import traceback
import os
import socket
from dnslib import *

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))

    while True:
      try:
        data, addr = sock.recvfrom(2048)
        query = DNSRecord.parse(data)
        logging.info('%s sent %s', addr, query)

        # Generate a response with a single answer record
        question = query.questions[0]
        ans = DNSRecord(DNSHeader(id=query.header.id, qr=1, aa=1, ra=1),
	    q=question,
	    a=RR(question.qname, ttl=3600, rdata=A(args.address)))

        # Send answer
        logging.info('response %s', ans)
        sock.sendto(ans.pack(), addr)
      except KeyboardInterrupt:	
        sys.exit()
      except Exception as e:
 	logging.error('Error in processing: %s', e)

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Listen for DNS queries and respond to all with same answer.')
    parser.add_argument('address', help='address to return in answer')
    parser.add_argument('-p', '--port', default=53, type=int, help='port number to listen upon')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        format = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        level = level
    )

    main()

