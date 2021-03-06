#!/usr/bin/python

import os
import re
import sys
import gzip
import time
import string
import argparse
import traceback
import subprocess
import datetime
import cPickle
import signal
from multiprocessing import Pool
from urlparse import urlparse
from collections import defaultdict

ENV = '/usr/bin/env'
NODE = os.path.dirname(os.path.realpath(__file__)) + '/../../node-v0.10.33/node'
CLIENT = os.path.dirname(os.path.realpath(__file__)) + '/pageloader_client.js'
TIMEOUT = 20

PROTOCOLS = { 'h2', 'http/1.1', 'spdy' }

class TimeoutError(Exception):
    pass

class Timeout:
    '''Can be used w/ 'with' to make arbitrary function calls with timeouts'''
    def __init__(self, seconds=10, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

class Stats(object):
   def __init__(self, url, output):
      self.url = url
      self.output = output
      self.domains = self.objects = self.connections = self.pushes = self.size = self.time = None

   def formString(self):
      return "objs="+str(self.objects)+" conns="+str(self.connections)+" domains="+str(self.domains)+\
	" pushes="+str(self.pushes)+" size="+str(self.size)+" time="+str(self.time)+\
	" partial="+str(self.partial)

# Fetch the whole page using node js for obtaining statistics
def handle_url(url, ptcl):
#   sys.stderr.write('Fetching (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   try:
      cmd = [ENV, NODE, CLIENT, 'https://'+url, '-fkv', '-t', str(TIMEOUT), '-r', ptcl]#, '-o', '/dev/null'] Null content
      if args.useragent:
        cmd += ['-u', args.useragent]
      if args.limittcp:
        cmd += ['-l', args.limittcp]
#      sys.stderr.write('Running cmd: %s\n' % cmd)
      with Timeout(seconds=TIMEOUT+5):
        output = subprocess.check_output(cmd)
      return url, output, False
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return url, traceback.format_exc(), True

def parseFetch(url, output, error):
    if error:
        return 'ERROR'
    domains = set()
    stats = Stats(url, output)
    stats.objects = 0
    stats.connections = 0
    stats.pushes = 0
    stats.size = 0
    stats.time = 0
    stats.partial = False
    
    h1conns = 0
    conns = defaultdict(int)

    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION='):
            stats.connections += 1
        elif chunks[1].startswith('PUSH='):
            stats.pushes += 1
        elif chunks[1].startswith('REQUEST=') or chunks[1].startswith('REDIRECT='):
            stats.objects += 1
            stats.time = float(chunks[0].strip('[s]'))
            domain = urlparse(chunks[1].split('=')[1]).netloc
            domains.add(domain)

            if conns[domain] == 0:
                h1conns += 1
            else:
                conns[domain] -= 1
        elif chunks[1].startswith('RESPONSE='):
            stats.size += int(chunks[2].split('=')[1])
            stats.time = float(chunks[0].strip('[s]'))

            domain = urlparse(chunks[1].split('=')[1]).netloc
            conns[domain] += 1
        elif chunks[1] == 'PROTOCOL_NEGOTIATE_FAILED':
            stats.partial = True

    stats.domains = len(domains)
    if stats.connections == 0 and h1conns > 0:
        stats.connections = h1conns
    return stats.formString()

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, test each URL for HTTP2 features')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-n', '--numtrials', default=3, type=int, help='number of trials per URL')
   parser.add_argument('-p', '--prefix', default='stats-', help='prefix for log files')
   parser.add_argument('-u', '--useragent', default=None, help='user-agent string to use in experiment')
   parser.add_argument('-l', '--limittcp', default=None, help='limit on number of tcp connections simulaneous')
   args = parser.parse_args()

   if args.directory != None and not os.path.isdir(args.directory):
        try:
            os.makedirs(args.directory)
        except Exception as e:
            sys.stderr.write('Error making output directory: %s\n' % args.directory)
            sys.exit(-1)
   logfile = None
   log = None
   if args.directory != None:
   	logfile = os.path.join(args.directory, args.prefix+datetime.date.today().isoformat()+'.pickle.gz')
	log = gzip.open(logfile, 'wb')

   sys.stderr.write('Command process (pid=%s)\n' % os.getpid())

   # Read input into local storage
   protocols = {}
   for line in args.infile:
      try:
         url, ptcls = line.strip().split(None, 1)
         protocols[url] = ptcls
      except Exception as e:
         sys.stderr.write('Input error: (line=%s) %s\n' % (line.strip(), e))
   args.infile.close()

   for url, ptcls in protocols.iteritems():
     # Time the webpage fetch with various protocols
     for i in range(args.numtrials):
       for p in PROTOCOLS:
          if p not in ptcls:
            continue
          url, output, error = handle_url(url, p)
          if log:
            cPickle.dump([url, output, p], log)
          args.outfile.write(url+' '+p+' '+parseFetch(url, output, error)+'\n')

   # Close log
   if log:
     log.close()


