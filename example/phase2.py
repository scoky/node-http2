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

class CODES:
    H2_SUPPORT='H2_SUPPORT'
    NO_TCP_HANDSHAKE='NO_TCP_HANDSHAKE'
    NO_H2_NEGO='NO_H2_NEGO'
    CODE_400='4XX_CODE'
    CODE_500='5XX_CODE'
    REDIRECT_TO_HTTP='REDIRECT_TO_HTTP'
    PROTOCOL_ERROR='PROTOCOL_ERROR'
    UNKNOWN_ERROR='UNKNOWN_ERROR'
    
class CERT:
    GOOD='GOODCERT'
    BAD='BADCERT'

class SiteData(object):
    def __init__(self, url, ptcl):
        self.url = url
        self.ptcl = ptcl
        self.output = None
        self.code = CODES.UNKNOWN_ERROR
        self.cert = CERT.BAD
        self.server = None

    def output(self):
        return self.url + ' ' + self.code + ' ' + self.cert + ' server=' + self.server

def fetch_url(url, ptcl):
    data = SiteData(url, ptcl)
    try:
        cmd = [ENV, NODE, CLIENT, 'https://'+url, '-fkv', '-t', str(TIMEOUT), '-o', '/dev/null', '-r', ptcl] #Null content
        data.output = subprocess.check_output(cmd)
        data.code,data.cert,data.server = parseOutput(data.output, False)
    except Exception as e:
        sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
        data.output = traceback.format_exc()
    return data
    
def run_url(data):
    url,ptcl = data
    data = fetch_url(url, ptcl)
    if data.code != CODES.H2_SUPPORT:
        wwwdata = fetch_url('www.'+url, ptcl)
        if wwwdata.code == CODES.H2_SUPPORT:
            return wwwdata
    return data

def parseOutput(output):
    server='unknown'
    valid=CERT.BAD
    firstcert = True
    # No response, protocol error
    status=CODES.PROTOCOL_ERROR

    estab = nego = cnego = response = redirect = notfound = serverError = False
    for line in output.split('\n'):
        chunks = line.split()
        if len(chunks) < 2:
            continue
        if chunks[1].startswith('TCP_CONNECTION'):
            estab = True
            cnego = False
        elif chunks[1].startswith('PROTOCOL=h2'):
            nego = True
            cnego = True
        elif chunks[1].startswith('CERT_VALID='):
            if chunks[1].split('=')[1] == 'true' and firstcert:
                valid=CERT.GOOD
            firstcert = False
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
        status = CODES.H2_SUPPORT
    # Could not connection
    elif not estab:
        status = CODES.NO_TCP_HANDSHAKE
    # Could not negotiate h2 via NPN/ALPN
    elif not nego:
        status = CODES.NO_H2_NEGO
    # Received a 4xx response
    elif notfound:
        status = CODES.CODE_400
    # Received a 5xx response
    elif serverError:
        status = CODES.CODE_500
    # Redirected
    elif redirect:
        status = CODES.REDIRECT_TO_HTTP
    
    return status, valid, server

# UNUSED CODE FOR SPDY SITES, DEPRECATED AND PROBABLY DOESN'T WORK ANYMORE!!!
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
   for line in args.infile:
      try:
         url = line.strip().split(None, 1)[0]
         urls.add( (url, args.protocol) )
      except Exception as e:
         sys.stderr.write('Input error: (line=%s) %s\n' % (line.strip(), e))
   args.infile.close()

   pool = Pool(args.threads)
   try:
      results = pool.imap(run_url, urls, args.chunk)
      for data in results:
         if log:
            cPickle.dump([data.url, data.output], log)
         args.outfile.write(data.output()+'\n')
   except KeyboardInterrupt:
      pool.terminate()

   if log:
      log.close()
