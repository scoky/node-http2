#!/usr/bin/python

import os
import sys
import cPickle
import argparse
import traceback
from urlparse import urlparse
from collections import defaultdict

H2 = 'h2'
H1 = 'http/1.1'
SPDY = 'spdy'
PROTOCOLS = { H2, H1, SPDY }

class Fetch(object):
    def __init__(self, url, request_time, new_connection, push, size, ident, prior, code):
        self.url = url
        self.request_time = request_time
        self.new_connection = new_connection
        self.push = push
        self.size = size
        self.ident = ident
        self.prior = prior
        self.code = code
        self.response_time = None

def parseWebPageFetch(key, main_url, output, protocol):
    objs = {}
    urlToIdent = {}
    h1Connections = defaultdict(int) # State of TCP connections for a domain
    ident = 0
    last_request = None
    last_response = None
    protocol_fail = False
    # Go line by line through the pageloader output
    for line in output.split('\n'):
        chunks = line.split()
        # Look for keyword lines only
        if len(chunks) < 2:
            continue
        try:
            time = float(chunks[0].strip('[s]'))
        except:
            continue
        ident += 1

        if chunks[1].startswith('TCP_CONNECTION='): # Last request caused a new TCP connection to be created
            objs[last_request].new_connection = True

        elif chunks[1].startswith('PUSH='): # Accepted a push request (this never happens)
            url = getURL(chunks[1].split('=', 1)[1])
            objs[ident] = Fetch(url, time, False, True, None, ident, (objs[last_response].ident if last_response else None), None)
            last_request = ident
            urlToIdent[url] = ident

        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='): # Making a new request (possibly due to a redirect)
            url = getURL(chunks[1].split('=', 1)[1])
            objs[ident] = Fetch(url, time, False, False, None, ident, (objs[last_response].ident if last_response else None), None)
            last_request = ident
            urlToIdent[url] = ident

            if protocol == H1: # H1 connections must be handled in post because there is no event from the h1 library
                domain = urlparse(url).netloc # This implementation assumes unlimited connections
                if h1Connections[domain] == 0:
                    objs[ident].new_connection = True
                else:
                    objs[ident].new_connection = False
                    h1Connections[domain] -= 1

        elif chunks[1].startswith('RESPONSE='): # Received a response
            url = getURL(chunks[1].split('=', 1)[1])
            last_response = urlToIdent[url]
            objs[last_response].size = chunks[2].split('=')[1]
            objs[last_response].response_time = time

            if protocol == H1: # Free TCP connection now available
                domain = urlparse(url).netloc
                h1Connections[domain] += 1

        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED': # There has been a protocl error on one of the connections.
            protocol_fail = True # There is no indication given as to which, so we are left to guess

        elif chunks[1].startswith('CODE='): # Response code value for the last response
            objs[last_response].code = chunks[1].split('=')[1]

    for obj in sorted(objs.itervalues(), key = lambda v: v.ident):
        if not obj.code and protocol != H1 and (obj.url.startswith('http://') or protocol_fail): 
            code = 'not_supported' # The object was never fetched. Likely cause is that it cannot be loaded over this protocol

        fetch_time = None
        if obj.response_time: # Calculate the time to fetch the object
            fetch_time = obj.response_time - obj.request_time
            if obj.prior: # If there was a prior object, then calculate the time from when it received (i.e., include processing time)
                fetch_time = obj.response_time - objs[obj.prior].response_time
                
        prior = objs[obj.prior].url if obj.prior else None

        args.outfile.write(key + ' ' + main_url + ' ' + protocol + ' ' + obj.url + ' ' + str(obj.new_connection) + ' ' + 
            str(obj.push) + ' ' + str(obj.size) + ' ' + str(fetch_time) + ' ' + str(prior) + ' ' + str(code) + '\n')

def getURL(uri):
    return uri.rstrip('/') # Sometimes present, sometimes not. Make consistent

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    count = 0
    while True:
        try:
            url, output, protocol = cPickle.load(args.infile)
            parseWebPageFetch('fetch'+str(count), url, output, protocol)
            count += 1
        except EOFError:
            break
        except Exception as e:
            sys.stderr.write('Error: %s\n%s\n' % (e, traceback.format_exc()))

