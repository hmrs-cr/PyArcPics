#!/usr/bin/python
# coding=UTF8

import argparse
import os
import urllib
import picgeotager

default_port = 8383


def main():
    parser = argparse.ArgumentParser(description='Geotag pictures in the given folder.')
    parser.add_argument('folder', help='The source with pictures to geotag.', nargs='?', default=None)
    parser.add_argument('-d', dest="download_url", help='Download location data from url.', nargs='?', default=None)
    parser.add_argument('-o', dest="overwrite", action="store_true", help='Overwrite location tag if exists.')
    parser.add_argument('-r', dest="time_range", help='Location query time range in minutes. (default 15)', type=int,
                        default=15)

    options = parser.parse_args()

    if options.folder is None and options.download_url is None:
        parser.print_help()
        exit()

    tagger = picgeotager.PicGotagger(options.time_range, options.overwrite)

    if options.download_url is not None:
        if not options.download_url.startswith("http://"):
            options.download_url = "http://" + options.download_url

        port = urllib.splitnport(urllib.splithost(urllib.splittype(options.download_url)[1])[0])[1]
        if port is None or port < 0:
            options.download_url += ":" + str(default_port)

        print "Downloading location data from", options.download_url
        added = tagger.update_location_data(options.download_url)
        print "Added", added, "locations to database."

    tagged_count, already_tagged_count, error_count = (0, 0, 0)
    if options.folder is not None:
        options.folder = unicode(options.folder, "UTF-8")
        if os.path.isfile(options.folder):
            result = tagger.geotag_picture(options.folder)
            if result == picgeotager.GeotagStatus.tagged:
                tagged_count += 1
            elif result == picgeotager.GeotagStatus.already_tagged:
                already_tagged_count += 1
            elif result == picgeotager.GeotagStatus.failed:
                error_count += 1
        else:
            tagged_count, already_tagged_count, error_count = tagger.geotag_pictures(options.folder)

        print tagged_count, "pictures tagged."
        print already_tagged_count, "pictures were already tagged."
        print error_count, "errors."


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Terminated by user."