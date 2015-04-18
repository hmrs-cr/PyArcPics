#!/usr/bin/python
# coding=UTF8
import pyexiv2
import os
import Image
import time

import gdata.photos.service
import gdata.media
import gdata.geo
import sys
from pictureuploader import PictureUploader

import utils


class GoogleUploader(PictureUploader):
    def __init__(self, email, password):
        PictureUploader.__init__(self)
        self._gd_client = gdata.photos.service.PhotosService()
        self._gd_client.email = email  # Set your Picasaweb e-mail address...
        self._gd_client.password = password  # ... and password
        self._autobackup_album = None
        self._set_service_name("gphotos")
        self.original_size = False

    def get_autobackup_album_url(self):
        if self._autobackup_album is None:
            self._autobackup_album = "/data/feed/api/user/default/albumid/default"
            albums = self._gd_client.GetUserFeed()
            for album in albums.entry:
                if album.name.text == "InstantUpload":
                    self._autobackup_album = "/data/feed/api/user/default/albumid/" + album.gphoto_id.text
                    break

        return self._autobackup_album

    def resize_image(self, org_file_name, rez_file_name, max_width=2048):
        img = Image.open(org_file_name)

        w, h = img.size

        if w <= max_width and h <= max_width:
            return False

        if w > h:
            ratio = (max_width / float(w))
            h = int((float(h) * float(ratio)))
            w = max_width
        elif w < h:
            ratio = (max_width / float(h))
            w = int((float(w) * float(ratio)))
            h = max_width
        else:
            w = max_width
            h = max_width

        img = img.resize((w, h), Image.ANTIALIAS)
        img.save(rez_file_name)

        org_exif_data = pyexiv2.ImageMetadata(org_file_name)
        org_exif_data.read()
        rez_exif_data = pyexiv2.ImageMetadata(rez_file_name)
        rez_exif_data.read()

        org_exif_data.copy(rez_exif_data, True, True, True, True)
        rez_exif_data.write()

        datetime = utils.get_date_from_file_date(org_file_name)
        filetime = time.mktime(datetime.timetuple())
        os.utime(rez_file_name, (filetime, filetime))

        return True

    def upload_file(self, file_name, md5sum=None):
        album_url = self.get_autobackup_album_url()
        fname = os.path.basename(file_name)
        temp_file_name = None
        photo_id = 0
        try:
            if not self.original_size:
                path, name = os.path.split(file_name)
                temp_file_name = os.path.join(path, ".resizing___" + name)
                if self.resize_image(file_name, temp_file_name):
                    file_name = temp_file_name
                else:
                    temp_file_name = None

            photo = self._gd_client.InsertPhotoSimple(album_url, fname, "", file_name)
            photo_id = photo.gphoto_id.text
        except Exception as e:
            print "Failed to upload file", fname + ":", e

        if temp_file_name is not None:
            os.remove(temp_file_name)

        return photo_id

    def authenticate(self):
        try:
            self._gd_client.source = 'personal-uploader-hmsoft-com'
            self._gd_client.ProgrammaticLogin()
            return True
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            return False
