#!/usr/bin/python

import os
import sys
import gzip
import argparse
import traceback
import subprocess
import datetime
import cPickle
from multiprocessing import Pool

ENV = '/usr/bin/env'
NODE = 'nodejs'
CLIENT = 'client.js'
TIMEOUT = 10000 # 10 seconds

def handle_url(url):
   url = url.strip()
   sys.stderr.write('Parsing (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   try:
      cmd = [ENV, NODE, CLIENT, url, '-fkv', '-t', str(TIMEOUT)]#, '-o', '/dev/null'] Null content
      sys.stderr.write('Running cmd: %s\n' % cmd)
      output = subprocess.check_output(cmd)           
      return url, output
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return url, traceback.format_exc()

def writeLog(agre):
   log = os.path.join(args.directory, 'log-'+datetime.date.today().isoformat()+'.pickle.gz')
   with gzip.open(log, 'wb') as logf:
      cPickle.dump(agre, logf)

def parseOutput(url, output):
   estab = nego = response = redirect = False
   for line in output.split('\n'):
	chunks = line.split()
	if len(chunks) < 2:
		continue
	if chunks[1].startswith('TCP_CONNECTION'):
	   estab = True
        elif chunks[1].startswith('PROTOCOL=h2'):
	   nego = True
        elif chunks[1].startswith('CODE=2'):
	   response = True
        elif chunks[1].startswith('CODE=3'):
	   redirect = True

   if not estab:
	return url+' NO_HANDSHAKE'
   if not nego:
	return url+' NO_H2_SUPPORT'
   if not response and not redirect:
	return url+' PROTOCOL_ERROR'
   if not response and redirect:
	return url+' REDIRECT'
   return url+' FULL_SUPPORT'

      

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, query each domain for HTTP2 support')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-t', '--threads', default=None, type=int, help='number of threads to user')
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
   urls = []
   for line in args.infile:
      urls.append(line.strip())
   args.infile.close()

   pool = Pool(args.threads)
   agre = {}
   try:
     results = pool.imap(handle_url, urls, args.chunk)
     for result in results:
	url = result[0]
	output = result[1]
	if args.directory != None:
	   agre[url] = output
	
        args.outfile.write(parseOutput(url, output)+'\n')
   except KeyboardInterrupt:
     pool.terminate()
     sys.exit()
   if args.directory != None:
     writeLog(agre)
