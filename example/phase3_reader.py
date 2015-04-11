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

Fetch = namedtuple('Fetch', 'request_time new_connection push size order prior code')

def parseH1(key, murl, output):
    objs = {}
    conns = defaultdict(int)
    count = 0
    last = None
    resp = None
    for line in output.split('\n'):
        count += 1
        chunks = line.split()
        if len(chunks) < 2:
            continue

        if chunks[1].startswith('TCP_CONNECTION='):
            objs[last] = Fetch(objs[last].request_time, True, objs[last].push, objs[last].size, objs[last].order, objs[last].prior, objs[last].code)
        elif chunks[1].startswith('PUSH='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, True, None, count, resp, None)
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
            objs[url] = Fetch(time, new_conn, False, None, count, resp, None)
            last = url
        elif chunks[1].startswith('RESPONSE='):
            url = chunks[1].split('=')[1].rstrip('/')
            domain = urlparse(url).netloc
            conns[domain] += 1

            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time - objs[url].request_time, objs[url].new_connection, objs[url].push, size, objs[url].order, objs[url].prior, '200')
            resp = url
        elif chunks[1].startswith('CODE='):
            code = chunks[1].split('=')[1]
            objs[resp] = Fetch(objs[resp].request_time, objs[resp].new_connection, objs[resp].push, objs[resp].size, objs[resp].order, objs[resp].prior, code)

    for url,f in sorted(objs.iteritems(), key = lambda v: v[1].order):
        if f.size:
            args.outfile.write(key + ' ' + murl + ' http/1.1 ' + url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + f.size + ' ' + str(f.request_time) + ' ' + str(f.prior) + ' ' + str(f.code) + '\n')


def parseOther(key, murl, output, protocol):
    objs = {}
    last = None
    resp = None
    count = 0
    for line in output.split('\n'):
        chunks = line.split()
        count += 1
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION='):
            objs[last] = Fetch(objs[last].request_time, True, objs[last].push, objs[last].size, objs[last].order, objs[last].prior, objs[last].code)
        elif chunks[1].startswith('PUSH='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, True, None, count, resp, None)
            last = url
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            url = chunks[1].split('=')[1].rstrip('/')
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time, False, False, None, count, resp, None)
            last = url
        elif chunks[1].startswith('RESPONSE='):
            url = chunks[1].split('=')[1].rstrip('/')
            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            objs[url] = Fetch(time - objs[url].request_time, objs[url].new_connection, objs[url].push, size, objs[url].order, objs[url].prior, 200)
            resp = url
        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED':
            protocol_fail = True
        elif chunks[1].startswith('CODE='):
            code = chunks[1].split('=')[1]
            objs[resp] = Fetch(objs[resp].request_time, objs[resp].new_connection, objs[resp].push, objs[resp].size, objs[resp].order, objs[resp].prior, code)

    for url,f in sorted(objs.iteritems(), key = lambda v: v[1].order):
        code = f.code
        if not code and protocol_fail:
            code = 'PROTOCOL_NEGOTIATE_FAILED'
        if f.size:
            args.outfile.write(key + ' ' + murl + ' ' + protocol + ' ' + url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + f.size + ' ' + str(f.request_time) + ' ' + str(f.prior) + ' ' + str(code) + '\n')

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    obj = None
    count = 0
    while True:
        try:
            obj = cPickle.load(args.infile)
            url, output, protocol = obj
            if protocol == 'http/1.1':
                parseH1('fetch'+str(count), url, output)
            else:
                parseOther('fetch'+str(count), url, output, protocol)
            count += 1
        except EOFError:
            break
        except Exception as e:
            sys.stderr.write('Error: %s\n%s\n' % (e, traceback.format_exc()))

