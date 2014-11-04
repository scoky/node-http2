#!/usr/bin/python

import os
import sys
import gzip
import argparse
import traceback
import subprocess
import datetime

ENV = '/usr/bin/env'
NODE = 'node'
CLIENT = 'pageloader_client.js'
TIMEOUT = 10

TSHARK_STAT = 'tshark -q -z io,stat,0.001 -r %s'
TSHARK_CAP = 'tshark -i %s -w %s %s'
FIREFOX_CMD = '/home/b.kyle/Downloads/firefox-35.0a1/firefox -P %s -no-remote "%s"'

#PROFILES
HTTP2 = 'http2'
HTTP1 = 'http1.1'
SPDY = 'spdy'

def clear_cache(profile):
  try:
    subprocess.call('rm ~/.mozilla/firefox/*.%s/*.sqlite' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm ~/.mozilla/firefox/*%s/sessionstore.js' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))
  try:
    subprocess.call('rm -r ~/.cache/mozilla/firefox/*.%s/*' % profile)
  except Exception as e:
    sys.stderr.write('Error clearing cache: %s, %s\n' % (e, traceback.format_exc()))

def fetch_url(url):
   sys.stderr.write('Fetching (url=%s) on (pid=%s)\n' % (url, os.getpid()))
   try:
      cmd = [ENV, NODE, CLIENT, url, '-fkv', '-t', str(TIMEOUT)]#, '-o', '/dev/null'] Null content
      sys.stderr.write('Running cmd: %s\n' % cmd)
      output = subprocess.check_output(cmd)           
      return output, False
   except Exception as e:
      sys.stderr.write('Subprocess returned error: %s\n%s\n' % (e, traceback.format_exc()))
      return traceback.format_exc(), True

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
   return ''.join(random.choice(chars) for _ in range(size))
def generate_file():
   while True:
      filename = os.path.join(args.directory, id_generator()+'.pcap')
   if not os.path.isfile(filename):
      return filename

def measure_loadtime(url, protocol, timeout=15):
   tshark_proc = firefox_proc = None
   filename = generate_file()

   try:
      try:
         cmd = TSHARK_CAP % (args.interface, filename, 'port 443')
         tshark_proc = subprocess.Popen(cmd, shell=True)
      except Exception as e:
         sys.stderr.write('Error starting tshark: %s\n%s\n' % (e, traceback.format_exc()))
         return None

      try:
         cmd = FIREFOX_CMD % (protocol, url)
         firefox_proc = subprocess.Popen(cmd, shell=True)
      except Exception as e:
         sys.stderr.write('Error starting firefox: %s\n%s\n' % (e, traceback.format_exc()))
         return None

      time.sleep(timeout)
      return filename
   finally:
      if tshark_proc:
         tshark_proc.kill()
         tshark_proc.wait()
      # Make sure tshark died
      subprocess.check_output('kill -9 `pidof tshark`', shell=True)
      if firefox_proc:
         firefox_proc.kill()
         firefox_proc.wait()
      # Make sure firefox died
      subprocess.check_output('kill -9 `pidof firefox`', shell=True)

def writeLog(agre):
   log = os.path.join(args.directory, 'log-'+datetime.date.today().isoformat()+'.pickle.gz')
   with gzip.open(log, 'wb') as logf:
      cPickle.dump(agre, logf)

def parseFetch(url, output, error):
   if error:
	return url+' TIMEOUT_ERROR'

   estab = nego = cnego = response = redirect = False
   for line in output.split('\n'):
	chunks = line.split()
	if len(chunks) < 2:
		continue
	if chunks[1].startswith('TCP_CONNECTION'):
	   estab = True
        elif chunks[1].startswith('PROTOCOL=h2'):
	   nego = True
	   cnego = True
	elif chunks[1].startswith('PROTOCOL='):
	   cnego = False
        elif chunks[1].startswith('CODE=2') and cnego:
	   response = True
        elif chunks[1].startswith('CODE=3') and cnego:
	   redirect = True

   if not estab:
	return url+' NO_TCP_HANDSHAKE'
   if not nego:
	return url+' NO_H2_SUPPORT'
   if not response and not redirect:
	return url+' PROTOCOL_ERROR'
   if not response and redirect:
	return url+' REDIRECT_TO_H1'
   return url+' H2_SUPPORT'

if __name__ == "__main__":
   # set up command line args
   parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Using input URL file, test each url for HTTP2 features and performance')
   parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
   parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
   parser.add_argument('-d', '--directory', default=None, help='Directory for writing log')
   parser.add_argument('-t', '--threads', default=None, type=int, help='number of threads to user')
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
	continue

     stats = parseFetch(output)
     filename = measure_loadtime(url, HTTP2)
     download_times(filename)
     filename = measure_loadtime(url, HTTP1)
     download_times(filename)
     filename = measure_loadtime(url, SPDY)
     download_times(filename)

     for result in results:
	url = result[0]
	output = result[1]
	error = results[2]
	if args.directory != None:
	   agre[url] = output
	
        args.outfile.write(parseOutput(url, output, error)+'\n')
   except KeyboardInterrupt:
     pool.terminate()
     sys.exit()
   if args.directory != None:
     writeLog(agre)
