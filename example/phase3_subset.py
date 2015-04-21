#!/usr/bin/python

import os
import re
import sys
import time
import string
import argparse
import traceback
import datetime
from urlparse import urlparse
from collections import namedtuple,defaultdict

PROTOCOLS = { 'h2', 'http/1.1', 'spdy' }

Fetch = namedtuple('Fetch', 'key page protocol url new_connection push size request_time prior code')

def getTree(data, root):
    children = []
    for f in data:
        if f.prior == root.url:
            ndata = list(data)
            ndata.remove(f)
            children.append((f, getTree(ndata, f)))
    return children

def flattenTree(tree):
    data = []
    for f,children in tree:
        data.append(f)
        data += flattenTree(children)
    return data

def getLoadTime(tree, root):
    if root.code != 'None' and root.code != 'not_supported':
        time = 0
        for f,children in tree:
            time = max(time, getLoadTime(children, f))
        return time + root.request_time
    else:
        return 0

def getByUrl(data, url):
    for f in data:
        if f.url == url:
            return f
    return None

def getMedian(datas):
    group = defaultdict(list)
    ret = []
    for data in datas:
        for f in data:
            group[f.url].append(f)
    for g in group.itervalues():
        sg = sorted(g, key = lambda x: x.request_time)
        median = sg[len(sg)/2]
        if median.prior == 'None': # Make sure the root object remains first
            ret.insert(0, median)
        else:
            ret.append(median)
    return ret
        

def fillIn(data, filler):
    additional = []
    replaced = []
    for f in list(data):
        if f.code == 'not_supported' or f.code == 'None':
            i = getByUrl(filler, f.url)
            if i and i.code != 'not_supported' and i.code != 'None':
                subtree = flattenTree(getTree(filler, i))
                additional.append(i)
                replaced.append(f)
                for s in subtree:
                    if not getByUrl(data, s.url):
                        additional.append(s)
    return additional, replaced

def parseData(data):
    time = 0
    objects = 0
    conns = 0
    size = 0
    domains = set()
    push = 0

    #if data[0].prior != 'None':
    #  raise Exception('Circular link!')
    tree = getTree(data, data[0])
    # Time depends upon the critical path
    time = getLoadTime(tree, data[0])

    # None of the other metrics do
    for f in data:
        if f.code != 'None' and f.code != 'not_supported':
            objects += 1
            size += int(f.size)
            # New connection if this request uses a different protocol
            if f.new_connection or f.protocol != data[0].protocol:
                conns += 1
            if f.push:
                push += 1
            domains.add(urlparse(f.url).netloc)

    return time, objects, conns, size, len(domains), push

def output(url, protocol, data):
    time, objects, conns, size, domains, push = data
    args.outfile.write( (url + ' ' + protocol + ' objs=' + str(objects) + ' conns=' + str(conns) + ' domains=' + str(domains) + 
        ' size=' + str(size) + ' push=' + str(push) + ' time=' + str(time) + '\n') )

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    data = {'h2':defaultdict(dict), 'http/1.1':defaultdict(dict), 'spdy':defaultdict(dict)}
    for line in args.infile:
        chunks = line.rstrip().split()
        f = Fetch(chunks[0], chunks[1], chunks[2], chunks[3], chunks[4] == 'True', chunks[5] == 'True', chunks[6], float(chunks[7]), chunks[8], chunks[9])
        if f.key not in data[f.protocol][f.page]:
            data[f.protocol][f.page][f.key] = []
        data[f.protocol][f.page][f.key].append(f)

    h2_data = {}
    h2_objs = {}
    for page,p in data['h2'].iteritems():
        result = getMedian(p.itervalues())
        try:
          d = parseData(result)
          output(page, 'h2', d)
          h2_data[page] = [r.url for r in result]
          h2_objs[page] = d[1]
        except Exception as e:
          sys.stderr.write('Error on %s: %s\n' % (page, e))

    for page,p in data['http/1.1'].iteritems():
        if page in h2_data:
            result = getMedian(p.itervalues())
            subset = []
            for r in result:
                if r.url in h2_data[page]:
                    subset.append(r)
            # All objects from h2 also available over h1
            if len(subset) == len(h2_data[page]):
                try:
                    d = parseData(subset)
                    if d[1] == h2_objs[page]:
                        output(page, 'http/1.1', d)
                except Exception as e:
                    sys.stderr.write('Error on %s: %s\n' % (page, e))

    for page,p in data['spdy'].iteritems():
        if page in h2_data:
            result = getMedian(p.itervalues())
            subset = []
            for r in result:
                if r.url in h2_data[page]:
                    subset.append(r)
            # All objects from h2 also available over spdy
            if len(subset) == len(h2_data[page]):
                try:
                    d = parseData(subset)
                    if d[1] == h2_objs[page]:
                        output(page, 'spdy', d)
                except Exception as e:
                    sys.stderr.write('Error on %s: %s\n' % (page, e))

    
