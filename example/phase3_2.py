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
import signal
from collections import defaultdict

TIMEOUT = 10

STRACE = 'strace -fttte trace=sendto,connect,recvfrom -e signal=kill'
FIREFOX = '/home/b.kyle/Downloads/firefox-36.0a1/firefox -P %s -no-remote --private-window "%s"'

#PROFILES
PROFILE_HTTP2 = 'http2'
PROFILE_HTTP1 = 'http1.1'
PROFILE_SPDY = 'spdy'

HTTP2 = 'h2'
HTTP1 = 'http/1.1'
SPDY = 'spdy'
PROTOCOLS = { HTTP2 : PROFILE_HTTP2, HTTP1 : PROFILE_HTTP1, SPDY : PROFILE_SPDY }

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

class Fetch(object):
   def __init__(self, protocol):
      self.protocol = protocol
      self.time_p25th = self.time_p50th = self.time_p75th = self.time = None
      self.bytesSent = self.bytesRecv = 0

   def formString(self):
      return self.protocol+' sent='+str(self.bytesSent)+' recv='+str(self.bytesRecv)+' 25th='+str(self.time_p25th)+\
	' 50th='+str(self.time_p50th)+' 75th='+str(self.time_p75th)+' total='+str(self.time)

   def parseOutput(self, bytesSent, startTime, recv):
      self.bytesSent = bytesSent
      self.bytesRecv = recv[-1][1]
      startTime = float(startTime)
      self.time = float(recv[-1][0]) - startTime
      self.time_p25th = self.time_p50th = self.time_p75th = None
      for res in recv:
         if not self.time_p25th and res[1] >= 0.25*self.bytesRecv:
            self.time_p25th = float(res[0]) - startTime
         if not self.time_p50th and res[1] >= 0.50*self.bytesRecv:
            self.time_p50th = float(res[0]) - startTime
         if not self.time_p75th and res[1] >= 0.75*self.bytesRecv:
            self.time_p75th = float(res[0]) - startTime
            break   

# Clear the cache for a given profile
def clear_cache(profile):
  try:
    subprocess.call('rm /home/b.kyle/.mozilla/firefox/*.%s/*.sqlite' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm /home/b.kyle/.mozilla/firefox/*.%s/sessionstore.js' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm -r /home/b.kyle/.cache/mozilla/firefox/*.%s/*' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))

# Fetch the whole page using firefox for obtaining timing information
def measure_loadtime(url, profile, timeout=15):
   socks = set()
   pause = {}
   recv = []
   startTime = None
   bytesSent = bytesRecv = 0
   try:
      cmd = STRACE + ' ' + FIREFOX % (profile, 'https://'+url)
      proc = subprocess.Popen(cmd, bufsize=4096, shell=True, stderr=subprocess.PIPE)
      with Timeout(seconds=timeout):
	 for line in proc.stderr:
            chunks = line.split(None, 4)
            if len(chunks) != 5:
               continue
            # _, process id, call time, system function, _
            _, pid, time, cfunc, remainder = chunks

            # return from process interrupt
            if cfunc == '<...':
  	       _, count = remainder.rsplit(None, 1)
               cfunc, fd, remainder = pause[pid]
            else:
               chunks = cfunc.rstrip(',').split('(', 1)
               if len(chunks) != 2:
                  continue
               cfunc, fd = chunks
               _, count = remainder.rsplit(None, 1)

               # Call unfinished due to interrupt, save process state
               if count == '...>':
                  pause[pid] = [cfunc, fd, remainder]
                  continue

            # TLS socket connect call
            if cfunc == 'connect' and 'htons(443)' in remainder:
               if not startTime:
                  startTime = time
               socks.add(fd)
            elif cfunc == 'sendto' and fd in socks:
               # Count bytes sent
               try:
                  bytesSent += int(count)
               except ValueError:
                  pass
            elif cfunc == 'recvfrom' and fd in socks:
               # Count bytes recv'd
               try:
                  c = int(count)
                  if c > 0:
                     bytesRecv += c
                     recv.append([time, bytesRecv])
               except ValueError:
                  pass
   except TimeoutError as e:
      # Normal termination
      pass
   finally:
      try:
         subprocess.check_output('killall firefox', shell=True)
      except Exception as e:
         sys.stderr.write('Error killing firefox: %s\n%s\n' % (e, traceback.format_exc()))      # Make sure tshark died

   if bytesSent < 500 or len(recv) == 0 or recv[-1][1] < 500:
	raise Exception('Failed test')
   return bytesSent, startTime, recv

def writeLog(agre):
   filename = os.path.join(args.directory, 'stats-'+datetime.date.today().isoformat()+'.pickle.gz')
   with gzip.open(filename, 'wb') as logf:
      cPickle.dump(agre, logf)

def parseTshark(protocol, filename):
   output = None
   try:
      cmd = TSHARK_STAT % filename
      output = subprocess.check_output(cmd, shell=True)
   except Exception as e:
      sys.stderr.write('Error running tshark: %s\n%s\n' % (e, traceback.format_exc()))
      return None

   results = []
   fetch = Fetch(protocol, filename)
   fetch.size = 0
   for line in output.split('\n'):
      match = CAP_LINE.match(line)
      if  not match or match.group(2) == '0':
         continue
      fetch.size += int(match.group(2))
      results.append([float(match.group(1)), fetch.size])

   fetch.time = results[-1][0]
   fetch.time_p25th = fetch.time_p50th = fetch.time_p75th = None
   for res in results:
      if not fetch.time_p25th and res[1] >= 0.25*fetch.size:
         fetch.time_p25th = res[0]
      if not fetch.time_p50th and res[1] >= 0.50*fetch.size:
         fetch.time_p50th = res[0]
      if not fetch.time_p75th and res[1] >= 0.75*fetch.size:
         fetch.time_p75th = res[0]
         break
   return fetch

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, test each url for HTTP2 features and performance')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-n', '--numtrials', default=5, type=int, help='number of trials per URL')
   parser.add_argument('-c', '--chunk', default=20, help='chunk size to assign to each thread')
   args = parser.parse_args()

   if args.directory != None and not os.path.isdir(args.directory):
        try:
            os.makedirs(args.directory)
        except Exception as e:
            sys.stderr.write('Error making output directory: %s\n' % args.directory)
            sys.exit(-1)
   logfile = None
   if args.directory != None:
   	logfile = os.path.join(args.directory, 'perf-'+datetime.date.today().isoformat()+'.pickle.gz')

   sys.stderr.write('Command process (pid=%s)\n' % os.getpid())

   # Read input into local storage
   urls = set()
   protocols = {}
   for line in args.infile:
      try:
         url, ptcls = line.rstrip().split(None, 1)
	 protocols[url] = ptcls
         urls.add(url)
      except Exception as e:
         sys.stderr.write('Input error: (line=%s) %s\n' % (line.rstrip(), e))
   args.infile.close()

   agre = defaultdict(list)
   for url in urls:
     # Time the webpage fetch with various protocols
     for i in range(args.numtrials):
	for p in PROTOCOLS.keys():
	  if p not in protocols[url]:
	    continue
	  profile = PROTOCOLS[p]
          try:
            bytesSent, startTime, recv = measure_loadtime(url, profile)
	  except Exception:
            continue
	  f = Fetch(p)
	  f.parseOutput(bytesSent, startTime, recv)

	  args.outfile.write(url+' '+f.formString()+'\n')

	  agre[url].append(f)

   if args.directory != None:
     writeLog(agre, logfile)

