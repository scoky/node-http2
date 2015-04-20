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

Fetch = namedtuple('Fetch', 'url request_time new_connection push size order prior code')

def parseH1(key, murl, output):
    objs = {}
    urlToCount = {}
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
            objs[last] = Fetch(objs[last].url, objs[last].request_time, True, objs[last].push, objs[last].size, objs[last].order, objs[last].prior, objs[last].code)
        elif chunks[1].startswith('PUSH='):
            url = getURL(chunks[1].split('=', 1)[1])
            time = float(chunks[0].strip('[s]'))
            objs[count] = Fetch(url, time, False, True, None, count, (objs[resp].url is resp else None), None)
            last = count
            urlToCount[url] = count
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            url = getURL(chunks[1].split('=', 1)[1])
            domain = urlparse(url).netloc
            if conns[domain] == 0:
                new_conn = True
            else:
                new_conn = False
                conns[domain] -= 1

            time = float(chunks[0].strip('[s]'))
            objs[count] = Fetch(url, time, new_conn, False, None, count, (objs[resp].url is resp else None), None)
            last = count
            urlToCount[url] = count
        elif chunks[1].startswith('RESPONSE='):
            url = getURL(chunks[1].split('=', 1)[1])
            domain = urlparse(url).netloc
            conns[domain] += 1

            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            resp = urlToCount[url]
            objs[resp] = Fetch(url, time - objs[resp].request_time, objs[resp].new_connection, objs[resp].push, size, objs[resp].order, objs[resp].prior, '200')
        elif chunks[1].startswith('CODE='):
            code = chunks[1].split('=')[1]
            objs[resp] = Fetch(objs[resp].url, objs[resp].request_time, objs[resp].new_connection, objs[resp].push, objs[resp].size, objs[resp].order, objs[resp].prior, code)

    for count,f in sorted(objs.iteritems(), key = lambda v: v[0]):
        args.outfile.write(key + ' ' + murl + ' http/1.1 ' + f.url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + str(f.size) + ' ' + str(f.request_time) + ' ' + str(f.prior) + ' ' + str(f.code) + '\n')


def getURL(uri):
    return uri.rstrip('/')

def parseOther(key, murl, output, protocol):
    objs = {}
    urlToCount = {}
    last = None
    resp = None
    protocol_fail = False
    count = 0
    for line in output.split('\n'):
        chunks = line.split()
        count += 1
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION='):
            objs[last] = Fetch(objs[last].url, objs[last].request_time, True, objs[last].push, objs[last].size, objs[last].order, objs[last].prior, objs[last].code)
        elif chunks[1].startswith('PUSH='):
            url = getURL(chunks[1].split('=', 1)[1])
            time = float(chunks[0].strip('[s]'))
            objs[count] = Fetch(url, time, False, True, None, count, (objs[resp].url is resp else None), None)
            last = count
            urlToCount[url] = count
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            url = getURL(chunks[1].split('=', 1)[1])
            time = float(chunks[0].strip('[s]'))
            objs[count] = Fetch(url, time, False, False, None, count, (objs[resp].url is resp else None), None)
            last = count
            urlToCount[url] = count
        elif chunks[1].startswith('RESPONSE='):
            url = getURL(chunks[1].split('=', 1)[1])
            size = chunks[2].split('=')[1]
            time = float(chunks[0].strip('[s]'))
            resp = urlToCount[url]
            objs[resp] = Fetch(url, time - objs[resp].request_time, objs[resp].new_connection, objs[resp].push, size, objs[resp].order, objs[resp].prior, 200)
        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED':
            protocol_fail = True
        elif chunks[1].startswith('CODE='):
            code = chunks[1].split('=', 1)[1]
            objs[resp] = Fetch(objs[resp].url, objs[resp].request_time, objs[resp].new_connection, objs[resp].push, objs[resp].size, objs[resp].order, objs[resp].prior, code)

    for count,f in sorted(objs.iteritems(), key = lambda v: v[0]):
        code = f.code
        if not code and (f.url.startswith('http:') or protocol_fail):
            code = 'not_supported'
        args.outfile.write(key + ' ' + murl + ' ' + protocol + ' ' + f.url + ' ' + str(f.new_connection) + ' ' + str(f.push) + ' ' + str(f.size) + ' ' + str(f.request_time) + ' ' + str(f.prior) + ' ' + str(code) + '\n')

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

