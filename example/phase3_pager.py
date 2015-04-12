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
            children.append((f, getTree(data, f)))
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

def fillIn(data, filler):
    additional = []
    replaced = []
    for f in list(data):
        if f.code == 'not_supported':
            i = getByUrl(filler, f.url)
            if i and i.code != 'not_supported':
                subtree = flattenTree(getTree(filler, i))
                additional.append(i)
                replaced.append(f)
                for s in subtree:
                    if not getByUrl(data, s.url):
                        additional.append(s)
    return additional, replaced

def parseData(data):
    time = 0
    objects = {'h2':0, 'http/1.1':0, 'spdy':0}
    conns = {'h2':0, 'http/1.1':0, 'spdy':0}
    size = {'h2':0, 'http/1.1':0, 'spdy':0}
    domains = set()
    push = 0

    tree = getTree(data, data[0])
    # Time depends upon the critical path
    time = getLoadTime(tree, data[0])

    # None of the other metrics do
    for f in data:
        if f.code != 'None' and f.code != 'not_supported':
            objects[f.protocol] += 1
            size[f.protocol] += int(f.size)
            if f.new_connection:
                conns[f.protocol] += 1
            if f.push:
                push += 1
            domains.add(urlparse(f.url).netloc)
            
    return time, objects, conns, size, len(domains), push
    
def output(url, protocol, data):
    time, objects, conns, size, domains, push = data
    args.outfile.write( (url + ' ' + protocol + ' objs_h2=' + str(objects['h2']) + ' objs_spdy=' + str(objects['spdy']) +
        ' objs_h1=' + str(objects['http/1.1']) + ' conns_h2=' + str(conns['h2']) + ' conns_spdy=' + str(conns['spdy']) +
        ' conns_h1=' + str(conns['http/1.1']) + ' domains=' + str(domains) + ' size_h2=' + str(size['h2']) + ' size_spdy=' + 
        str(size['spdy']) + ' size_h1=' + str(size['http/1.1']) + ' push=' + str(push) + ' time=' + str(time) + '\n') )

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
        
    for page,p in data['http/1.1'].iteritems():
        for k in p.itervalues():
            d = parseData(k)
            output(page, 'http/1.1', d)
            
    for page,p in data['spdy'].iteritems():
        for k in p.itervalues():
            additional = []
            if page in data['http/1.1']:
                a, replaced = fillIn(k, data['http/1.1'][page].values()[0])
                additional += a
                for r in replaced:
                    k.remove(r)
            d = parseData(k + additional)
            output(page, 'spdy', d)

    for page,p in data['h2'].iteritems():
        for k in p.itervalues():
            additional = []
            if page in data['spdy']:
                a, replaced = fillIn(k, data['spdy'][page].values()[0])
                additional += a
                for r in replaced:
                    k.remove(r)
            if page in data['http/1.1']:
                a, replaced = fillIn(k, data['http/1.1'][page].values()[0])
                additional += a
                for r in replaced:
                    k.remove(r)
            d = parseData(k + additional)
            output(page, 'h2', d)

    
