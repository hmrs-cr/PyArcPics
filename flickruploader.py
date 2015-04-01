import os
import sys
import time
import flickrapi
import webbrowser
from db import BuffData
import utils

md5_tag_prefix = "checksum:md5="
date_tag_prefix = "date:iso="
date_year_tag_prefix = "date:year="
date_month_tag_prefix = "date:month="
date_day_tag_prefix = "date:day="


class FlickrUploader:
    def __init__(self, api_key, api_secret):
        self._flickr = flickrapi.FlickrAPI(api_key, api_secret, cache=False)
        self._dataHelper = BuffData()
        self._count = 0
        self._total_pics_count = 0
        self._nonpiccount = 0
        self._total_pics_size = 0
        self._nonpic_size = 0
        self._sizecount = 0
        self._failcount = 0
        self._starttime = 0
        self.check_remote_chksum = True

    def get_photoid_from_md5sum(self, md5sum):
        for photo in self._flickr.walk(user_id="me", tags=md5_tag_prefix + md5sum):
            return photo.get("id")
        return 0

    def upload_file(self, file_name, md5sum=None):
        class FileWithCallback(object):
            def __init__(self, filename):
                self.file = open(filename, 'rb')
                self._lastp = 0
                # the following attributes and methods are required
                self.len = os.path.getsize(filename)
                self.fileno = self.file.fileno
                self.tell = self.file.tell

            def _callback(self, p):
                if self._lastp != p:
                    print "Uploading file " + file_name, str(p) + "%\r",
                    sys.stdout.flush()
                    self._lastp = p

            def read(self, size):
                self._callback(self.tell() * 100 // self.len)
                return self.file.read(size)

        try:
            if md5sum is None:
                md5sum = utils.get_md5sum_from_file(file_name)
                pass

            photoid = 0
            if self.check_remote_chksum:
                photoid = self.get_photoid_from_md5sum(md5sum)
            if photoid != 0:
                print "File", file_name, "already uploaded. ID:", photoid
                return photoid

            tags = md5_tag_prefix + md5sum
            date = utils.get_picture_date(file_name)
            if date is not None:
                tags += " " + date_tag_prefix + date.isoformat()
                tags += " " + date_year_tag_prefix + date.strftime("%Y")
                tags += " " + date_month_tag_prefix + date.strftime("%Y-%m")
                tags += " " + date_day_tag_prefix + date.strftime("%Y-%m-%d")

            f = FileWithCallback(file_name)
            t = time.time()
            rsp = self._flickr.upload(file_name, f, title="",
                                      description="", tags=tags, is_public="0", is_family="0",
                                      is_friend="0", format="xmlnode")

            print "Done with file " + file_name, " - Uploaded ", utils.sizeof_fmt(f.len), "in", \
                utils.format_time(time.time() - t), "\r",
            print

            sys.stdout.flush()

            if rsp['stat'] == u'ok':
                return rsp.photoid[0].text

            return 0
        except Exception as e:
            try:
                print "Error on: ", file_name
                sys.stderr.write(u"Error on " + file_name + u": " + unicode(e) + u"\n")
            except:
                sys.stderr.write("Error printing error.\n")
                
            return 0

    def _internal_scan_directory(self, dir_name):
        if not os.path.isdir(dir_name):
            sys.stderr.write(dir_name + " is not a directory.\n")
            return

        try:
            dir_list = os.listdir(dir_name)
        except OSError as e:
            sys.stderr.write(str(e) + "\n")
            return

        for filename in dir_list:
            src_file = os.path.join(dir_name, filename)
            if os.path.isdir(src_file):
                self._internal_scan_directory(src_file)
                continue

            if not os.path.isfile(src_file) or not utils.is_picture(src_file):
                self._nonpic_size += utils.get_file_size(src_file)
                self._nonpiccount += 1
                continue

            self._total_pics_size += utils.get_file_size(src_file)
            self._total_pics_count += 1

    def scan_directory(self, dir_name):
        self._total_pics_count = 0
        self._nonpiccount = 0
        self._total_pics_size = 0
        self._nonpic_size = 0
        self._internal_scan_directory(dir_name)
        return self._total_pics_count, self._nonpiccount, self._total_pics_size, self._nonpic_size

    def _internal_upload_directory(self, dir_name):
        if not os.path.isdir(dir_name):
            sys.stderr.write(dir_name + " is not a directory.\n")
            return

        try:
            dir_list = os.listdir(dir_name)
        except OSError as e:
            sys.stderr.write(str(e) + "\n")
            return

        for filename in dir_list:
            src_file = os.path.join(dir_name, filename)
            if os.path.isdir(src_file):
                self._internal_upload_directory(src_file)
                continue

            if not os.path.isfile(src_file):
                continue

            # if file is not jpg then continue
            if not utils.is_picture(src_file):
                print("File " + filename + " is not an image.\n")
                continue

            self._count += 1
            file_size = utils.get_file_size(src_file)
            self._sizecount += file_size

            md5sum = utils.get_md5sum_from_file(src_file)

            uploaded = self._dataHelper.file_already_uploaded(md5sum)
            if uploaded:
                print "File", src_file, "already uploaded. 1"
                continue

            stt = time.time()
            photo_id = self.upload_file(src_file, md5sum)
            secondstoupload = time.time() - stt
            bits_per_second = file_size / secondstoupload

            if photo_id != 0:
                self._dataHelper.set_file_uploaded(src_file, photo_id, md5sum)
            else:
                self._failcount += 1

            if self._total_pics_count > 0:
                p = float(self._count) / float(self._total_pics_count) * 100.0
                print str(int(p)) + "% done. (" + str(self._count), "of", self._total_pics_count, \
                    "pictures,", self._failcount, "fails - " + utils.sizeof_fmt(self._sizecount) + \
                                                  " of " + utils.sizeof_fmt(self._total_pics_size) + ") ETA: " + \
                                                  utils.format_eta(bits_per_second, self._sizecount,
                                                                   self._total_pics_size)

    def upload_directory(self, dir_name):
        self._starttime = time.time()
        self._internal_upload_directory(dir_name)
        return time.time() - self._starttime

    def authenticate(self):
        token_valid = self._flickr.token_valid(perms=u'write')
        if token_valid:
            return True

        # Get a request token
        self._flickr.get_request_token(oauth_callback='oob')

        # Open a browser at the authentication URL. Do this however
        # you want, as long as the user visits that URL.
        authorize_url = self._flickr.auth_url(perms=u'write')
        webbrowser.open_new_tab(authorize_url)

        # Get the verifier code from the user. Do this however you
        # want, as long as the user gives the application the code.
        verifier = unicode(raw_input('Verifier code: '))

        # Trade the request token for an access token
        self._flickr.get_access_token(verifier)

        return self._flickr.token_valid(perms=u'write')
