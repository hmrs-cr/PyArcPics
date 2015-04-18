#!/usr/bin/python
# coding=UTF8

import argparse
import os
import sys

from gphotosuploader import GoogleUploader
import utils


def main():
    def scan(fup):
        print "Scanning folder", options.folder, "..."
        pc, npc, pcs, npcs = fup.scan_directory(options.folder)
        print pc, "total pictures found. (" + utils.sizeof_fmt(pcs) + ")"
        print npc, "other files found. (" + utils.sizeof_fmt(npcs) + ")"

    parser = argparse.ArgumentParser(description='Upload to Google+ all JPEG pictures in the given folder recursively')
    parser.add_argument('folder', help='The folder to search for pictures')
    parser.add_argument('-s', dest='scan_only', action="store_true", help="Scan folder but don't upload pictures")
    parser.add_argument('-r', dest="small_size", action="store_true", help='Reduce image size before upload.')

    options = parser.parse_args()

    if not options.folder:
        parser.print_help()
        exit()

    if options.scan_only:
        scan(GoogleUploader("", ""))
        exit()

    config_file_name = "~/.hmsoft/gphotos.json"
    api_keys = utils.get_api_keys_from_config(config_file_name)

    api_key, api_secret = api_keys
    if api_key is None or api_secret is None:
        sys.stderr.write("Please add Google API access keys to config file: " + config_file_name + "\n")
        exit()

    gup = GoogleUploader(api_key, api_secret)

    print "Authenticating..."
    if not gup.authenticate():
        sys.stderr.write("Google authentication error\n")
        exit()

    print "Starting upload"
    options.folder = unicode(options.folder, "UTF-8")
    gup.original_size = not options.small_size

    if os.path.isfile(options.folder):
        gup.upload_file(options.folder)
        print "Done."
    else:
        scan(gup)
        t = gup.upload_directory(options.folder)
        print "Done in " + utils.format_time(t)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Terminated by user."