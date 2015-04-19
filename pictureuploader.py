import os
import sys
import time

from db import BuffData
import utils


class FileWithCallback(object):
    def __init__(self, filename, org_filename=None):
        if org_filename is None:
            org_filename = filename

        self.file = open(filename, 'rb')
        self.filename = filename
        self._org_filename = org_filename
        self._lastp = 0
        # the following attributes and methods are required
        self.len = os.path.getsize(filename)
        self.fileno = self.file.fileno
        self.tell = self.file.tell
        self._start_time = time.time()
        self._done_called = False

    def callback(self, p):
        if self._lastp != p:
            print "Uploading file " + self._org_filename, str(p) + "%\r",
            sys.stdout.flush()
            self._lastp = p

    def all_done(self):
        if self._done_called:
            return

        print "Done with file " + self._org_filename, " - Uploaded ", utils.sizeof_fmt(self.len), "in", \
            utils.format_time(time.time() - self._start_time), "\r",
        print
        self._done_called = True

    def read(self, size):
        self.callback(self.tell() * 100 // self.len)
        r = self.file.read(size)
        done = r is None or r == ""
        if done:
            self.all_done()
        return r


class PictureUploader:
    def __init__(self):
        self._cloud_service_name = None
        self._dataHelper = BuffData()
        self._count = 0
        self._total_pics_count = 0
        self._nonpiccount = 0
        self._total_pics_size = 0
        self._nonpic_size = 0
        self._sizecount = 0
        self._failcount = 0
        self._starttime = 0

    def _set_service_name(self, service_name):
        self._cloud_service_name = service_name

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
        self._nonpiccount = 0
        self._total_pics_size = 0
        self._nonpic_size = 0
        self._total_pics_count = 0
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

            uploaded = self._dataHelper.file_already_uploaded(self._cloud_service_name, md5sum)
            if uploaded:
                print "File", src_file, "already uploaded. 1"
                continue

            stt = time.time()
            photo_id = self.upload_file(src_file, md5sum)
            secondstoupload = time.time() - stt
            bits_per_second = file_size / secondstoupload

            if photo_id != 0:
                self._dataHelper.set_file_uploaded(src_file, self._cloud_service_name, photo_id, md5sum)
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

    def upload_file(self, file_name, md5sum=None):
        raise NotImplementedError("upload_file not implement")

    def authenticate(self):
        return True
