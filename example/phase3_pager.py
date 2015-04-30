#!/usr/bin/python

import os
import sys
import argparse
import traceback
from urlparse import urlparse
from collections import defaultdict

H2 = 'h2'
H1 = 'http/1.1'
SPDY = 'spdy'
PROTOCOLS = { H2, H1, SPDY }

class Fetch(object):
    def __init__(self, key, page, protocol, url, new_connection, push, size, fetch_time, prior, code):
        self.key = key
        self.page = page
        self.protocol = protocol
        self.url = url
        self.new_connection = new_connection
        self.push = push
        self.size = size
        self.fetch_time = fetch_time
        self.prior = prior
        self.code = code

def getTree(data, root): # Convert a flat list of requests in a webpage into a tree
    children = []
    for f in data:
        if f.prior == root.url:
            ndata = list(data)
            ndata.remove(f) # Prevent circular references
            children.append((f, getTree(ndata, f)))
    return children

def flattenTree(tree): # Convert tree into a flat list
    data = []
    for f,children in tree:
        data.append(f)
        data += flattenTree(children)
    return data

def getLoadTime(tree, root): # Compute the loading time of page via the critical path
    if root.code != 'None' and root.code != 'not_supported': # Object was fetched
        time = 0
        for f,children in tree:
            time = max(time, getLoadTime(children, f))
        return time + root.fetch_time
    else:
        return 0

def getByUrl(data, url): # Find object by its url
    for f in data:
        if f.url == url:
            return f
    return None

def getMedian(datas): # Get the median load times
    group = defaultdict(list) # Eliminates the impact of DNS resolution on load time
    ret = []
    for data in datas:
        for f in data:
            group[f.url].append(f)
    for g in group.itervalues():
        sg = sorted(g, key = lambda x: x.fetch_time)
        median = sg[len(sg)/2]
        if median.prior == 'None': # Make sure the root object remains first
            ret.insert(0, median)
        else:
            ret.append(median)
    return ret

def fillIn(data, filler): # Fill in the webpage fetch with objects from another protocol
    additional = []
    replaced = []
    for f in list(data):
        if f.code == 'not_supported' or f.code == 'None': # Missing object that needs filling in
            i = getByUrl(filler, f.url)
            if i and i.code != 'not_supported' and i.code != 'None': # Found object to fill with
                subtree = flattenTree(getTree(filler, i))
                additional.append(i)
                replaced.append(f)
                for s in subtree: # Add all objects dependent upon the replacing object
                    if not getByUrl(data, s.url):
                        additional.append(s)
    return additional, replaced

def parseData(data):
    time = 0
    objects = { H2:0, H1:0, SPDY:0 }
    conns = { H2:0, H1:0, SPDY:0 }
    size = { H2:0, H1:0, SPDY:0 }
    domains = set()
    push = 0

    tree = getTree(data, data[0])
    # Time depends upon the critical path
    time = getLoadTime(tree, data[0])

    # None of the other metrics do
    for f in data:
        if f.code != 'None' and f.code != 'not_supported':
            domain = urlparse(f.url).netloc
            objects[f.protocol] += 1
            size[f.protocol] += int(f.size)
            # New connection if this request uses a different protocol
            if f.new_connection or domain not in domains:
                conns[f.protocol] += 1
            if f.push:
                push += 1
            domains.add(domain)

    return time, objects, conns, size, len(domains), push

def output(url, protocol, data):
    time, objects, conns, size, domains, push = data
    args.outfile.write( (url + ' ' + protocol + ' objs_h2=' + str(objects[H2]) + ' objs_spdy=' + str(objects[SPDY]) +
        ' objs_h1=' + str(objects[H1]) + ' conns_h2=' + str(conns[H2]) + ' conns_spdy=' + str(conns[SPDY]) +
        ' conns_h1=' + str(conns[H1]) + ' domains=' + str(domains) + ' size_h2=' + str(size[H2]) + ' size_spdy=' + 
        str(size[SPDY]) + ' size_h1=' + str(size[H1]) + ' push=' + str(push) + ' time=' + str(time) + '\n') )

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                     description='Read phase3 log files')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    args = parser.parse_args()

    data = {H2:defaultdict(dict), H1:defaultdict(dict), SPDY:defaultdict(dict)}
    for line in args.infile:
        chunks = line.rstrip().split()
        f = Fetch(chunks[0], chunks[1], chunks[2], chunks[3], chunks[4] == 'True', chunks[5] == 'True', 
            chunks[6], 0 if chunks[7] == 'None' else float(chunks[7]), chunks[8], chunks[9])
        if f.key not in data[f.protocol][f.page]:
            data[f.protocol][f.page][f.key] = []
        data[f.protocol][f.page][f.key].append(f)

    for page,p in data[H1].iteritems():
        result = getMedian(p.itervalues())
        p.clear()
        p['median'] = result
        try:
          d = parseData(result)
          output(page, H1, d)
        except Exception as e:
          sys.stderr.write('Error on %s: %s\n' % (page, e))

    for page,p in data[SPDY].iteritems():
        result = getMedian(p.itervalues())
        additional = []
        if page in data[H1]:
            a, replaced = fillIn(result, data[H1][page]['median'])
            additional += a
            for r in replaced:
                result.remove(r)
        p.clear()
        p['median'] = result
        try:
          d = parseData(result + additional)
          output(page, SPDY, d)
        except Exception as e:
          sys.stderr.write('Error on %s: %s\n' % (page, e))

    for page,p in data[H2].iteritems():
        result = getMedian(p.itervalues())
        additional = []
        if page in data[SPDY]:
            a, replaced = fillIn(result, data[SPDY][page]['median'])
            additional += a
            for r in replaced:
                result.remove(r)
        if page in data[H1]:
            a, replaced = fillIn(result, data[H1][page]['median'])
            additional += a
            for r in replaced:
                result.remove(r)
        try:
          d = parseData(result + additional)
          output(page, H2, d)
        except Exception as e:
          sys.stderr.write('Error on %s: %s\n' % (page, e))

    
