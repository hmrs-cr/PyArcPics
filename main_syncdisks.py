#!/usr/bin/python
# coding=UTF8

import argparse
import os
import subprocess
import utils

rsync = "rsync"
rsync_options = "-vrtui --stats"
rsync_exclude = "--exclude=%(primary)s --exclude=%(secondary)s --exclude=.thumbs" % \
                {"primary": utils.primary_backup_marker, "secondary": utils.secondary_backup_marker}





def test_storage_available_space(source, destination):
	subprocess.check_output([rsync, "-anrtu", "--stats", source, destination], shell=True)


def main():
    parser = argparse.ArgumentParser(description='Sync backup from one disc to another.')
    parser.add_argument('source', help='The source folder.', nargs='?', default=None)
    parser.add_argument('destination', help='The destination folder.', nargs='?', default=None)

    options = parser.parse_args()

    if options.source is None:
        options.source = utils.find_backup_folder(utils.primary_backup_marker)
        if options.source is None:
            print "Could not determine source folder."
            exit()

    if options.destination is None:
        options.destination = utils.find_backup_folder(utils.secondary_backup_marker)
        if options.destination is None:
            print "Could not determine destination folder."
            exit()


    if not os.path.isfile(os.path.join(options.source, utils.primary_backup_marker)):
        print options.source, " is not the primary backup folder."
        exit()

    if not os.path.isfile(os.path.join(options.destination, utils.secondary_backup_marker)):
        print options.destination, " is not the secondary backup folder."
        exit()

    print "Storage location:"
    print "    Primary:  ", options.source
    print "    Secondary:", options.destination

    source=os.path.join(options.source, "")
    destination=os.path.join(options.destination, "")

    #test_storage_available_space(source, destination)

    rsync_cmd = "%(rsync_cmd)s %(rsync_opts)s %(exclude)s %(src)s %(dest)s" % \
                {"rsync_cmd": rsync,
                 "rsync_opts": rsync_options,
                 "exclude": rsync_exclude,
                 "src": source,
                 "dest": destination}

    subprocess.call(rsync_cmd, shell=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Terminated by user."
