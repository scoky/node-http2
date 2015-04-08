#!/usr/bin/python

import os
import re
import sys
import time
import string
import argparse
import traceback
import datetime
import cPickle
from urlparse import urlparse
from collections import namedtuple,defaultdict

PROTOCOLS = { 'h2', 'http/1.1', 'spdy' }

Fetch = namedtuple('Fetch', 'request_time new_connection push size')

def parseH1(murl, output):
    objs = {}
    conns = defaultdict(int)
    last = None
    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue

        if chunks[1].startswith('TCP_CONNECTION='):
            objs[last] = Fetch(objs[last].request_time, True, objs[last].push, objs[last].size)
        elif chunks[1].startswith('PUSH='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, True, None)
            last = url
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            url = chunks[1].split('=')[1].rstrip('/')
            domain = urlparse(url).netloc
            if conns[domain] == 0:
                new_conn = True
            else:
                new_conn = False
                conns[domain] -= 1

            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, new_conn, False, None)
            last = url
        elif chunks[1].startswith('RESPONSE='):
            url = chunks[1].split('=')[1].rstrip('/')
            domain = urlparse(url).netloc
            conns[domain] += 1

            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time - objs[url].request_time, objs[url].new_connection, objs[url].push, size)
        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED':
            break

    for url,f in objs.iteritems():
        if f.size:
            args.outfile.write(murl + ' http/1.1 ' + url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + f.size + ' ' + str(f.request_time) + '\n')


def parseOther(murl, output, protocol):
    objs = {}
    last = None
    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION='):
            objs[last] = Fetch(objs[last].request_time, True, objs[last].push, objs[last].size)
        elif chunks[1].startswith('PUSH='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, True, None)
            last = url
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, False, None)
            last = url
        elif chunks[1].startswith('RESPONSE='):
            url = chunks[1].split('=')[1].rstrip('/')
            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time - objs[url].request_time, objs[url].new_connection, objs[url].push, size)
        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED':
            break

    for url,f in objs.iteritems():
        if f.size:
            args.outfile.write(murl + ' ' + protocol + ' ' + url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + f.size + ' ' + str(f.request_time) + '\n')

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    obj = None
    while True:
        try:
            obj = cPickle.load(args.infile)
        except EOFError:
            break
        url, output, protocol = obj
        if protocol == 'http/1.1':
            parseH1(url, output)
        else:
            parseOther(url, output, protocol)

