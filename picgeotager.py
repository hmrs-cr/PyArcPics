import os
import pyexiv2
import urllib
import urllib2
import time
import sys

import db
import utils


def get_location_generator(resp):
    for line in resp:
        try:
            data = line.strip().split(";")
            yield (long(data[0]), float(data[1]), float(data[2]), float(data[3]))
        except Exception as e:
            yield None


def to_deg(value, loc):
    if value < 0:
        loc_value = loc[0]
    elif value > 0:
        loc_value = loc[1]
    else:
        loc_value = ""

    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min = int(t1)
    sec = round((t1 - min) * 60, 5)

    return deg, min, sec, loc_value


class GeotagStatus:
    tagged, already_tagged, failed = range(3)


def set_gps_location(file_name, lat, lng, overwrite=False, address=None):
    """Adds GPS position as EXIF metadata

    Keyword arguments:
    file_name -- image file
    lat -- latitude (as float)
    lng -- longitude (as float)

    """
    exiv_image = pyexiv2.ImageMetadata(file_name)
    exiv_image.read()

    has_geotag = utils.get_exif_value(exiv_image, "Exif.GPSInfo.GPSLatitude") is not None and \
                    utils.get_exif_value(exiv_image, "Exif.GPSInfo.GPSLatitudeRef") is not None and \
                    utils.get_exif_value(exiv_image, "Exif.GPSInfo.GPSLongitude") is not None and \
                    utils.get_exif_value(exiv_image, "Exif.GPSInfo.GPSLongitudeRef") is not None;

    if not overwrite and has_geotag:
        print file_name, "-> Already tagged"
        return GeotagStatus.already_tagged

    lat_deg = to_deg(lat, ["S", "N"])
    lng_deg = to_deg(lng, ["W", "E"])

    # convert decimal coordinates into degrees, munutes and seconds
    exiv_lat = (pyexiv2.Rational(lat_deg[0] * 60 + lat_deg[1], 60), pyexiv2.Rational(lat_deg[2] * 100, 6000),
                pyexiv2.Rational(0, 1))
    exiv_lng = (pyexiv2.Rational(lng_deg[0] * 60 + lng_deg[1], 60), pyexiv2.Rational(lng_deg[2] * 100, 6000),
                pyexiv2.Rational(0, 1))

    exiv_image["Exif.GPSInfo.GPSLatitude"] = exiv_lat
    exiv_image["Exif.GPSInfo.GPSLatitudeRef"] = lat_deg[3]
    exiv_image["Exif.GPSInfo.GPSLongitude"] = exiv_lng
    exiv_image["Exif.GPSInfo.GPSLongitudeRef"] = lng_deg[3]
    exiv_image["Exif.Image.GPSTag"] = 654
    exiv_image["Exif.GPSInfo.GPSMapDatum"] = "WGS-84"
    exiv_image["Exif.GPSInfo.GPSVersionID"] = '2 0 0 0'

    exiv_image.write(True)

    print file_name, "-> Tagged!", "(overwrited)" if overwrite and has_geotag else "",
    if address:
        print "(" + address + ")",

    print "http://maps.google.com/?ll=%(la)s,%(lo)s" % {"la": str(lat), "lo": str(lng)}

    return GeotagStatus.tagged


class PicGotagger:
    def __init__(self, time_range=15, overwrite=False):
        self._overwrite = False
        self._failed_count = 0
        self._already_tagged_count = 0
        self._tagged_count = 0
        self._db = None
        self._time_range = time_range
        self._overwrite = overwrite

    def _init_db(self):
        if self._db is None:
            self._db = db.BuffData()

    def update_location_data(self, url):
        try:
            if not url.endswith("/getLocations"):
                import urlparse
                url = urlparse.urljoin(url, "/getLocations")

            self._init_db()
            fromdate = self._db.get_setting(db.last_location_time_key)
            if fromdate is not None:
                url += "?" + urllib.urlencode({"fromdate": fromdate})

            req = urllib2.Request(url)
            response = urllib2.urlopen(req)

            return self._db.add_locations(get_location_generator(response))
        except Exception as e:
            print url, e
            return 0

    def geotag_picture(self, picture_path):
        try:
            pic_date = utils.get_picture_date(picture_path)
            if pic_date is None:
                print picture_path, "-> No date found"
                return GeotagStatus.failed

            pic_date_millis = long(time.mktime(pic_date.timetuple()) * 1000)

            self._init_db()
            location = self._db.get_location_from_timestamp(pic_date_millis, self._time_range)
            if location is None:
                print picture_path, "-> No location found"
                return GeotagStatus.failed

            lat, lon, address, t = location
            return set_gps_location(picture_path, lat, lon, self._overwrite, address)
        except Exception as e:
            print picture_path, "-> Error tagging:", e
            return GeotagStatus.failed

    def _geotag_pictures(self, folder_path):
        try:
            dir_list = os.listdir(folder_path)
        except OSError as e:
            sys.stderr.write(str(e) + "\n")
            return

        for filename in dir_list:
            src_file = os.path.join(folder_path, filename)
            if os.path.isdir(src_file):
                self._geotag_pictures(src_file)
                continue

            if not os.path.isfile(src_file) or not utils.is_picture(src_file):
                continue
            
            result = self.geotag_picture(src_file)
            if result == GeotagStatus.tagged:
                self._tagged_count += 1
            elif result == GeotagStatus.already_tagged:
                self._already_tagged_count += 1
            elif result == GeotagStatus.failed:
                self._failed_count += 1

    def geotag_pictures(self, folder_path):
        self._failed_count = 0
        self._already_tagged_count = 0
        self._tagged_count = 0
        self._geotag_pictures(folder_path)
        return self._tagged_count, self._already_tagged_count, self._failed_count
