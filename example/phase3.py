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

ENV = '/usr/bin/env'
NODE = 'node'
CLIENT = '/home/b.kyle/github/node-http2/example/pageloader_client.js'
TIMEOUT = 10

TSHARK_STAT = 'tshark -q -z io,stat,0.001 -r %s'
TSHARK_CAP = 'tshark -i %s -w %s %s'
FIREFOX_CMD = '/home/b.kyle/Downloads/firefox-36.0a1/firefox -P %s -no-remote "%s"'
#
CAP_LINE = re.compile('^\|\s+[\d\.]+\s+\<\>\s+([\d\.]+)\s+\|\s+\d+\s+\|\s+(\d+)')

#PROFILES
HTTP2 = 'http2'
HTTP1 = 'http1.1'
SPDY = 'spdy'

class Stats(object):
   def __init__(self, url, output):
      self.url = url
      self.output = output
      self.fetches = []
      self.objects = self.connections = self.pushes = None

   def formString(self):
      print self.url, self.filename, self.objects, self.connections, self.pushes
      for fetch in self.fetches:
         fetch.formString()

class Fetch(object):
   def __init__(self, protocol, filename):
      self.protocol = protocol
      self.filename = filename
      self.time_p25th = self.time_p50th = self.time_p75th = self.time = None
      self.size = 0

   def formString(self):
      print self.protocol, self.filename, self.size, self.time_p25th, self.time_p50th, self.time_p75th, self.time

# Clear the cache for a given profile
def clear_cache(profile):
  try:
    subprocess.call('rm /home/b.kyle/.mozilla/firefox/*.%s/*.sqlite' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm /home/b.kyle/.mozilla/firefox/*%s/sessionstore.js' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm -r /home/b.kyle/.cache/mozilla/firefox/*.%s/*' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))

# Fetch the whole page using node js for obtaining statistics
def fetch_url(url):
   sys.stderr.write('Fetching (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   try:
      cmd = [ENV, NODE, CLIENT, 'https://'+url, '-fkv', '-t', str(TIMEOUT)]#, '-o', '/dev/null'] Null content
      sys.stderr.write('Running cmd: %s\n' % cmd)
      output = subprocess.check_output(cmd)           
      return output, False
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return traceback.format_exc(), True

# Generate a unique filename for pcaps
def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
   return ''.join(random.choice(chars) for _ in range(size))
def generate_file():
   return 'dump.pcap'
   while True:
      filename = os.path.join(args.directory, id_generator()+'.pcap')
   if not os.path.isfile(filename):
      return filename

# Fetch the whole page using firefox for obtaining timing information
def measure_loadtime(url, protocol, timeout=15):
   tshark_proc = firefox_proc = None
   filename = generate_file()

   try:
      try:
         cmd = TSHARK_CAP % ('wlan0', filename, 'port 443') #args.interface
         tshark_proc = subprocess.Popen(cmd, shell=True)
      except Exception as e:
         sys.stderr.write('Error starting tshark: %s\n%s\n' % (e, traceback.format_exc()))
         return None

      try:
         cmd = FIREFOX_CMD % (protocol, 'https://'+url)
         firefox_proc = subprocess.Popen(cmd, shell=True)
      except Exception as e:
         sys.stderr.write('Error starting firefox: %s\n%s\n' % (e, traceback.format_exc()))
         return None

      time.sleep(timeout)
      return filename
   finally:
      if tshark_proc != None:
         sys.stderr.write('Killing tshark\n')
         tshark_proc.kill()
         tshark_proc.wait()
      # Make sure tshark died
      try:
         subprocess.check_output('kill -9 `pidof tshark`', shell=True)
      except Exception as e:
         sys.stderr.write('Error killing tshark: %s\n%s\n' % (e, traceback.format_exc()))
      if firefox_proc != None:
         sys.stderr.write('Killing firefox\n')
         firefox_proc.kill()
         firefox_proc.wait()
      # Make sure firefox died
      try:
         subprocess.check_output('kill -9 `pidof firefox`', shell=True)
      except Exception as e:
         sys.stderr.write('Error killing firefox: %s\n%s\n' % (e, traceback.format_exc()))

def writeLog(agre):
   filename = os.path.join(args.directory, 'stats-'+datetime.date.today().isoformat()+'.pickle.gz')
   with gzip.open(filename, 'wb') as logf:
      cPickle.dump(agre, logf)

def parseFetch(url, output):
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

   return stats

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
   filename = measure_loadtime('google.com', 'default')
   parseTshark(Stats('test'), filename).formString()
   sys.exit()

   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, test each url for HTTP2 features and performance')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-n', '--numtrials', default=5, type=int, help='number of trials per URL')
   parser.add_argument('-c', '--chunk', default=20, help='chunk size to assign to each thread')
   args = parser.parse_args()

   if args.directory == None:
	print 'Must specify a directory'
	sys.exit()

   args.directory = os.path.join(args.directory, datetime.date.today().isoformat())
   if not os.path.isdir(args.directory):
        try:
            os.makedirs(args.directory)
        except Exception as e:
            sys.stderr.write('Error making output directory: %s\n' % args.directory)
            sys.exit(-1)

   sys.stderr.write('Command process (pid=%s)\n' % os.getpid())

   # Read input into local storage
   urls = set()
   for line in args.infile:
      if 'H2_SUPPORT' in line.split(None, 1)[1]:
        urls.add(line.strip().split(None, 1)[0])
   args.infile.close()

   agre = {}
   for url in urls:
     output, error = fetch_url(url)
     if error:
        agre[url] = None
	continue

     stats = parseFetch(url, output)
     agre[url] = stats

     # Time the webpage fetch with various protocols
     for i in range(numtrials):
        filename = measure_loadtime(url, HTTP2)
        stats.fetches.append(parseTshark(HTTP2, filename))

        filename = measure_loadtime(url, HTTP1)
        stats.fetches.append(parseTshark(HTTP1, filename))

        filename = measure_loadtime(url, SPDY)
        stats.fetches.append(parseTshark(SPDY, filename))
	
     args.outfile.write(parseOutput(url, output, error)+'\n')

   writeLog(agre)

