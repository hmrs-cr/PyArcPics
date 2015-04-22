#!/usr/bin/python
# coding=UTF8

import argparse

import os
import sys
from picturearchiver import PictureArchiver
import utils


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Backup pictures from source to destination, sorting them in a folder '
                                                 'structure by date and keeping date time accurate')
    parser.add_argument('source', help='The source folder.', nargs='?', default=None)
    parser.add_argument('destination', help='The destination folder.', nargs='?', default=None)
    parser.add_argument('-c', dest="config", help='The config file', default="~/.hmsoft/arcpics.json")
    parser.add_argument('-z', dest="start_size", help='Take in account only files bigger than START_SIZE megabytes', default="0")
    parser.add_argument('-m', dest='move', action="store_true", help="Move files instead of copy them.")
    parser.add_argument('-d', dest='diagnostics', action="store_true", help="Don't run the actual actions.")
    parser.add_argument('-s', dest='scan_only', action="store_true", help="Scan folder but don't perform backup")

    options = parser.parse_args()

    import json
    config = None
    dest_folder = None
    src_folders = None

    if options.source is not None:
        src_folders = [unicode(options.source, "UTF-8")]
    else:
        try:
            config = json.load(open(os.path.expanduser(options.config)))
            src_folders = config["source_folders"]
        except:
            pass

        if config is None:
            sys.stderr.write("Can't open config file: " + options.config + "\n")
            exit()

    if options.destination is not None:
        dest_folder = unicode(options.destination, "UTF-8")
    else:
        dest_folder = utils.find_backup_folder(utils.primary_backup_marker)
        if dest_folder is None:
            sys.stderr.write("Could not determine backup folder\n")
            exit()

    if not isinstance(src_folders, list):
        sys.stderr.write("Source folders in config is not a valid list: " + src_folders + "\n")
        exit()

    for path in src_folders:
        import glob
        expanded_paths = glob.glob(path)
        for exp_path in expanded_paths:
            if os.path.isdir(exp_path):
                if not os.path.isfile(os.path.join(exp_path, ".no_backup")):
                    print "Starting import from ", exp_path
                    if not options.scan_only:
                        PictureArchiver.do(exp_path, dest_folder, options.diagnostics, options.move, options.start_size)
            else:
                print path, " not found."

