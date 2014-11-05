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
from multiprocessing import Pool

ENV = '/usr/bin/env'
NODE = 'node'
CLIENT = '/home/b.kyle/github/node-http2/example/pageloader_client.js'
TIMEOUT = 10

class Stats(object):
   def __init__(self, url, output):
      self.url = url
      self.output = output
      self.objects = self.connections = self.pushes = None

   def formString(self):
      print self.url, self.objects, self.connections, self.pushes

# Fetch the whole page using node js for obtaining statistics
def handle_url(url):
   sys.stderr.write('Fetching (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   try:
      cmd = [ENV, NODE, CLIENT, 'https://'+url, '-fkv', '-t', str(TIMEOUT)]#, '-o', '/dev/null'] Null content
      sys.stderr.write('Running cmd: %s\n' % cmd)
      output = subprocess.check_output(cmd)           
      return url, output, False
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return url, traceback.format_exc(), True

def writeLog(agre):
   filename = os.path.join(args.directory, 'stats-'+datetime.date.today().isoformat()+'.pickle.gz')
   with gzip.open(filename, 'wb') as logf:
      cPickle.dump(agre, logf)

def parseFetch(url, output, error):
   if error:
      return 'UNKNOWN_ERROR'
   stats = Stats(url, output)
   stats.objects = 0
   stats.connections = 0
   stats.pushes = 0

   for line in output.split('\n'):
	chunks = line.split()
	if len(chunks) < 2:
		continue
	if chunks[1].startswith('TCP_CONNECTION='):
	   stats.connections += 1
        elif chunks[1].startswith('PUSH='):
	   stats.pushes += 1
        elif chunks[1].startswith('REQUEST='):
	   stats.objects += 1

   return stats.formString()

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, test each URL for HTTP2 features')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-n', '--numtrials', default=5, type=int, help='number of trials per URL')
   parser.add_argument('-t', '--threads', default=None, type=int, help='number of threads to use')
   parser.add_argument('-c', '--chunk', default=20, help='chunk size to assign to each thread')
   args = parser.parse_args()

   if args.directory != None and not os.path.isdir(args.directory):
        try:
            os.makedirs(args.directory)
        except Exception as e:
            sys.stderr.write('Error making output directory: %s\n' % args.directory)
            sys.exit(-1)

   sys.stderr.write('Command process (pid=%s)\n' % os.getpid())

   # Read input into local storage
   urls = set()
   protocols = {}
   for line in args.infile:
      try:
         url, supported, ptcls = line.strip().split(None, 2)
         if 'H2_SUPPORT' == supported:
           urls.add(url)
           protocols[url] = ptcls
      except Exception as e:
         sys.stderr.write('Input error: (line=%s) %s\n' % (line.strip(), args.directory))
   args.infile.close()

   pool = Pool(args.threads)
   agre = {}
   try:
     results = pool.imap(handle_url, urls, args.chunk)
     for result in results:
	url, output, error = result
	if args.directory != None:
	   agre[url] = output
	
        args.outfile.write(url+' '+parseFetch(url, output, error)+' '+protocols[url]+'\n')
   except KeyboardInterrupt:
     pool.terminate()
     sys.exit()

   # Write log
   if args.directory != None:
     writeLog(agre)


