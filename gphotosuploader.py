#!/usr/bin/python
# coding=UTF8

import pyexiv2
import os
import Image
import time
import webbrowser

import gdata.gauth
import gdata.photos.service
import gdata.media
import gdata.geo
import sys

from picasaclient import PicasaClient
from pictureuploader import PictureUploader
import utils


SCOPES = "https://picasaweb.google.com/data/"
USER_AGENT = "personal-photo/video-uploader"


class GoogleUploader(PictureUploader):
    def __init__(self, client_id, client_secret):
        PictureUploader.__init__(self)
        self._client_id = client_id
        self._client_secret = client_secret
        self._gd_client = PicasaClient()
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

    def _load_token(self):
        tokenb = self._dataHelper.get_setting("gphotos-token")
        if tokenb is not None:
            return gdata.gauth.token_from_blob(tokenb)
        return None

    def _save_token(self, token):
        tokenb = gdata.gauth.token_to_blob(token)
        self._dataHelper.set_setting("gphotos-token", tokenb)

    def authenticate(self):
        try:
            token = self._load_token()
            if token is None:
                token = gdata.gauth.OAuth2Token(
                    client_id=self._client_id, client_secret=self._client_secret, scope=SCOPES,
                    user_agent=USER_AGENT)

                authorize_url = token.generate_authorize_url()
                webbrowser.open_new_tab(authorize_url)
                token.get_access_token(unicode(raw_input('Verifier code: ')))
                self._save_token(token)

            token.authorize(self._gd_client)
            return True
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            return False