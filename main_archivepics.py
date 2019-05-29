#!/usr/bin/python
# coding=UTF8

import argparse

import os
import sys
import pwd
import grp
from picturearchiver import PictureArchiver
import utils

DEFAUL_CONFIG = "~/.hmsoft/arcpics.json"
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Backup pictures from source to destination, sorting them in a folder '
                                                 'structure by date and keeping date time accurate')
    parser.add_argument('source', help='The source folder.', nargs='?', default=None)
    parser.add_argument('destination', help='The destination folder.', nargs='?', default=None)
    parser.add_argument('move_destination', help='The move destination folder...', nargs='?', default=None)
    parser.add_argument('-c', dest="config", help='The config file', default=None)
    parser.add_argument('-l', dest="log_file", help='Log operation result values to file', default=None)
    parser.add_argument('-m', dest='move', action="store_true", help="Move files instead of copy them.")
    parser.add_argument('-d', dest='diagnostics', action="store_true", help="Don't run the actual actions.")
    parser.add_argument('-s', dest='scan_only', action="store_true", help="Scan folder but don't perform backup")

    options = parser.parse_args()

    import json
    config = None
    dest_folder = None
    src_folders = None
    move_destination = None

    if options.move_destination:
        move_destination = unicode(options.move_destination, "UTF-8")

    if options.source is not None:
        if options.source != "ALL":
            src_folders = [unicode(options.source, "UTF-8")]
    else:
        try:
            if not options.config:
                options.config = DEFAUL_CONFIG
            config = json.load(open(os.path.expanduser(options.config)))
            src_folders = config["source_folders"]
        except:
            pass

    if src_folders is None or src_folders == "ALL":
        src_folders = utils.find_camera_folders() + utils.find_camera_folders("SD Card Imports")    

    if options.destination is not None and options.destination != "AUTO":
        dest_folder = unicode(options.destination, "UTF-8")
    else:
        dest_folder = utils.find_backup_folder(utils.primary_backup_marker)
        if dest_folder is None:
            sys.stderr.write("Could not determine backup folder\n")
            exit(1)

    if not isinstance(src_folders, list):
        sys.stderr.write("Source folders in config is not a valid list: " + src_folders + "\n")
        exit(1)
    
    newusergroup = ""
    new_owner = os.environ.get(utils.PA_NEW_OWNER)
    if new_owner is not None:
        try:
            pwd.getpwnam(new_owner)
            new_group = os.environ.get(utils.PA_NEW_GROUP)
            if new_group is not None:
                grp.getgrnam(new_group)
                newusergroup = "(" + new_owner + ":" + new_group + ")"
        except Exception as e:
            os.environ[utils.PA_NEW_OWNER] = ""
            os.environ[utils.PA_NEW_GROUP] = ""
            utils.error(e)

    print "Backup location:", dest_folder, newusergroup
    
    for path in src_folders:
        import glob
        try:
            expanded_paths = glob.glob(path)
        except UnicodeEncodeError as e:
            continue
        for exp_path in expanded_paths:
            if os.path.isdir(exp_path) or os.path.isfile(exp_path):
                if not os.path.isfile(os.path.join(exp_path, ".no_backup")):
                    print "SOURCE FOLDER:", exp_path
                    if not options.scan_only:
                        PictureArchiver.do(exp_path, dest_folder, move_destination, options.diagnostics, options.move, options.log_file)
                else:
                    print "IGNORING:", exp_path
            else:
                print "NOT FOUND:", path

