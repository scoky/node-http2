#!/usr/bin/python

import os
import sys
import cPickle
import argparse
import traceback
from urlparse import urlparse
from collections import defaultdict

def parseWebPageFetch(key, main_url, output, protocol):
    server = 'unknown'
    for line in output.split('\n'):
        chunks = line.split()
        # Look for keyword lines only
        if len(chunks) < 2:
            continue
        if chunks[0] == "\"server\":":
            server = chunks[1].strip("\",")
            break

        args.outfile.write(url + ' server=' + server + '\n')

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    visited = set()
    while True:
        try:
            url, output, protocol = cPickle.load(args.infile)
            if url+protocol not in visited:
                parseWebPageFetch(url, output, protocol)
                visited.add(url+protocol)
        except EOFError:
            break
        except Exception as e:
            sys.stderr.write('Error: %s\n%s\n' % (e, traceback.format_exc()))

