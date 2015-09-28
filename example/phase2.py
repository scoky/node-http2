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
NODE = os.path.dirname(os.path.realpath(__file__)) + '/../../node-v0.10.33/node'
CLIENT = os.path.dirname(os.path.realpath(__file__)) + '/client.js'
TIMEOUT = 10

def handle_url(data):
#   sys.stderr.write('Fetching (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   url, ptcl = data
   try:
      cmd = [ENV, NODE, CLIENT, 'https://'+url, '-fkv', '-t', str(TIMEOUT), '-o', '/dev/null', '-r', ptcl] #Null content
#      sys.stderr.write('Running cmd: %s\n' % cmd)
      output = subprocess.check_output(cmd)           
      return url, ptcl, output, False
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return url, ptcl, traceback.format_exc(), True

def parseOutput(url, output, error):
    server='unknown'
    if error:
        return url+' UNKNOWN_ERROR server=' + server
    valid='BADCERT'
    firstcert = True
    # No response, protocol error
    status='PROTOCOL_ERROR'

    estab = nego = cnego = response = redirect = notfound = serverError = False
    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION'):
            estab = True
        elif chunks[1].startswith('PROTOCOL=h2'):
            nego = True
            cnego = True
        elif chunks[1].startswith('CERT_VALID='):
            if chunks[1].split('=')[1] == 'true' and firstcert:
                valid='GOODCERT'
            firstcert = False
        elif chunks[1].startswith('PROTOCOL='):
            cnego = False
        elif chunks[1].startswith('CODE=2') and cnego:
            response = True
        elif chunks[1].startswith('CODE=3') and cnego:
            redirect = True
        elif chunks[1].startswith('CODE=4') and cnego:
            notfound = True
        elif chunks[1].startswith('CODE=5') and cnego:
            serverError = True
        elif chunks[0] == "\"server\":":
            server = '_'.join(chunks[1:]).strip(",")

    # Received a 2xx response
    if response:
        status='H2_SUPPORT'
    # Could not connection
    elif not estab:
        status='NO_TCP_HANDSHAKE'
    # Could not negotiate h2 via NPN/ALPN
    elif not nego:
        status='NO_H2_NEGO'
    # Received a 4xx response
    elif notfound:
        status='4XX_CODE'
    # Received a 5xx response
    elif serverError:
        status='5XX_CODE'
    # Redirected
    elif redirect:
        status='REDIRECT_TO_HTTP'
    
    return url + ' ' + status + ' ' + valid + ' server=' + server
    
def parseOutputSpdy(url, output, error):
    server='unknown'
    if error:
        return url+' UNKNOWN_ERROR server=' + server

    estab = nego = cnego = response = redirect = notfound = serverError = False
    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue
        elif chunks[1].startswith('CODE=2'):
            response = True
        elif chunks[1].startswith('CODE=3'):
            redirect = True
        elif chunks[1].startswith('CODE=4'):
            notfound = True
        elif chunks[1].startswith('CODE=5'):
            serverError = True
        elif chunks[0] == "\"server\":":
            server = '_'.join(chunks[1:]).strip(",")

    # Received a 2xx response
    if response:
        return url+' SPDY_SUPPORT server=' + server
    # Received a 4xx response
    if notfound:
        return url+' 4XX_CODE server=' + server
    # Received a 5xx response
    if serverError:
        return url+' 5XX_CODE server=' + server
    # Redirected
    if redirect:
        return url+' REDIRECT_TO_HTTP server=' + server
    # No response, protocol error
    return url+' NO_TCP_HANDSHAKE server=' + server
   

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, query each domain for HTTP2 support')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-t', '--threads', default=None, type=int, help='number of threads to use')
   parser.add_argument('-c', '--chunk', default=20, help='chunk size to assign to each thread')
   parser.add_argument('-r', '--protocol', default='h2', choices=['h2', 'spdy'], help='which protocol to use when loading the object')
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
   	logfile = os.path.join(args.directory, 'log-'+datetime.date.today().isoformat()+'.pickle.gz')
	log = gzip.open(logfile, 'wb')

   sys.stderr.write('Command process (pid=%s)\n' % os.getpid())

   # Read input into local storage
   urls = set()
   protocols = {}
   for line in args.infile:
      try:
         url, ptcls = line.strip().split(None, 1)
         urls.add( (url, args.protocol) )
         protocols[url] = ptcls
      except Exception as e:
         sys.stderr.write('Input error: (line=%s) %s\n' % (line.strip(), e))
   args.infile.close()

   pool = Pool(args.threads)
   try:
      results = pool.imap(handle_url, urls, args.chunk)
      for result in results:
         url, ptcl, output, error = result
         if log:
            cPickle.dump([url, output], log)
         if ptcl == 'h2':   
            output = parseOutput(url, output, error)
         else:
            output = parseOutputSpdy(url, output, error)
         args.outfile.write(output+'\n') #'+protocols[url]+'
   except KeyboardInterrupt:
      pool.terminate()

   if log:
      log.close()
