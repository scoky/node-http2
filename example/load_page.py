#!/usr/bin/python

import logging
import argparse
import sys
import traceback
import os
from urlparse import urljoin
from bs4 import BeautifulSoup

def load_obj(url):
    # TODO: hook this into the objloaders
    pass

def main():
    base_html = load_obj(args.webpage)
    soup = BeautifulSoup(base_html)

    # Find all embedded resources
    res = []
    for r in res:
      url = urljoin(args.webpage, r)
      obj = load_obj(url) # TODO: order?

    # TODO: write to HAR?

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Load a webpage with all embedded resources.')
    parser.add_argument('webpage', help='the base URL from which to load the page')
    parser.add_argument('output', type=argparse.FileType('w'), default=sys.stdout, help='file to write results')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        format = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        level = level
    )

    main()

