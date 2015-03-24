#!/usr/bin/python
# coding=UTF8

import argparse
import json
import os
import sys

import utils
import flickruploader


def main():
    def scan(fup):
        print "Scanning folder", options.folder, "..."
        pc, npc, pcs, npcs = fup.scan_directory(options.folder)
        print pc, "total pictures found. (" + utils.sizeof_fmt(pcs) + ")"
        print npc, "other files found. (" + utils.sizeof_fmt(npcs) + ")"

    parser = argparse.ArgumentParser(description='Upload to Flickr all JPEG pictures in the given folder recursively')
    parser.add_argument('folder', help='The folder to search for pictures')
    parser.add_argument('-s', dest='scan_only', action="store_true", help="Scan folder but don't upload pictures")
    parser.add_argument('-a', dest='auth_only', action="store_true", help="Authenticate to Flickr service")
    options = parser.parse_args()

    if not options.folder:
        parser.print_help()
        exit()

    api_key = None
    api_secret = None
    config_file_name = os.path.expanduser("~/.hmsoft/flickr.json")
    try:
        config = json.load(open(config_file_name))
        api_key = unicode(config["api_key"])
        api_secret = unicode(config["api_secret"])
    except Exception as e:
        sys.stderr.write("Error reading config: " + str(e) + "\n")
        exit()

    if api_key is None or api_secret is None:
        sys.stderr.write("Please add flickr API access keys to config file: " + config_file_name + "\n")
        exit()

    fup = flickruploader.FlickrUploader(api_key, api_secret)

    if options.auth_only:
        if fup.authenticate():
            print "Authentication successfully!"
        else:
            print "Authentication failed."
        exit()

    if options.scan_only:
        scan(fup)
        exit()

    if not fup.authenticate():
        sys.stderr.write("Flickr authentication error\n")
        exit()

    print "Starting upload"
    options.folder = unicode(options.folder, "UTF-8")
    if os.path.isfile(options.folder):
        fup.upload_file(options.folder)
        print "Done."
    else:
        scan(fup)
        t = fup.upload_directory(options.folder)
        print "Done in " + utils.format_time(t)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Terminated by user."