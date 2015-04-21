#!/usr/bin/python
# coding=UTF8

import pyexiv2
import os
import Image
import time
import webbrowser
import sys

import gdata.gauth
import gdata.photos.service
import gdata.media
import gdata.geo

from picasaclient import PicasaClient
from pictureuploader import PictureUploader, FileWithCallback
import utils


SCOPES = "https://picasaweb.google.com/data/"
USER_AGENT = "personal-photo/video-uploader"
TOKEN_KEY = "gphotos-token"
NICKNAME_KEY = "nickname"
ALBUM_KEY = "albumid"

MAX_VIDEO_SIZE = 104857600


class GoogleUploader(PictureUploader):
    def __init__(self, client_id, client_secret, user=None):
        PictureUploader.__init__(self)
        self._client_id = client_id
        self._client_secret = client_secret
        self._gd_client = PicasaClient()
        self._autobackup_album = None
        self._set_service_name("gphotos")
        self.original_size = False
        self._user_name = user or ""
        self._allowed_file_exts += [".mov", ".mp4", ".avi", ".mpg", ".mpeg", ".3gp", ".3gpp"]
        self._user_data = None
        self._token_key = TOKEN_KEY
        if user:
            self._token_key += "-" + user

    def get_user_feed_data(self):
        if self._user_data is None:
            albumid = "default"
            feed = self._gd_client.GetUserFeed()
            user_name = feed.nickname.text
            for album in feed.entry:
                if album.name.text == "InstantUpload":
                    albumid = album.gphoto_id.text
                    break

            self._user_data = {NICKNAME_KEY: user_name, ALBUM_KEY: albumid}

        self.user_name = self._user_data[NICKNAME_KEY]
        return self._user_data

    def get_autobackup_album_url(self):
        if self._autobackup_album is None:
            data = self.get_user_feed_data()
            self._autobackup_album = "/data/feed/api/user/default/albumid/" + data[ALBUM_KEY]

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
        img.save(rez_file_name, None, quality=88)

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
            content = utils.file_name_to_mimetype(file_name)
            if content is None:
                sys.stderr.write("Can't determine mime type for file " + file_name + "\n")
                return 0

            if content.startswith("image") and not self.original_size:
                path, name = os.path.split(file_name)
                temp_file_name = os.path.join(path, ".resizing___" + name)
                if self.resize_image(file_name, temp_file_name):
                    file_name = temp_file_name
                else:
                    temp_file_name = None


            f = FileWithCallback(file_name)
            if content.startswith("video") and f.len > MAX_VIDEO_SIZE:
                sys.stderr.write("File " + file_name + " is bigger than " + utils.sizeof_fmt(MAX_VIDEO_SIZE) + "\n")
                return 0

            photo = self._gd_client.InsertPhotoSimple(album_url, fname, "", f, content)
            photo_id = photo.gphoto_id.text
        except Exception as e:
            print "Failed to upload file", fname + ":", e

        if temp_file_name is not None:
            os.remove(temp_file_name)

        return photo_id

    def _load_token(self):
        try:
            token_data = self._dataHelper.get_secure_data(self._token_key)
            if token_data is not None:
                self._user_data = token_data
                return gdata.gauth.token_from_blob(token_data[TOKEN_KEY])
        except :
            pass

        return None

    def _save_token(self, token):
        if token is None:
            self._dataHelper.save_secure_data(self._token_key, None)
        else:
            tokenb = gdata.gauth.token_to_blob(token)
            user_feed = self.get_user_feed_data()
            user_feed[TOKEN_KEY] = tokenb
            self._dataHelper.save_secure_data(self._token_key, user_feed)

    def refresh_token(self, token):
        # Hack to fix possible bug in Google SDK (I have no idea what I'm doing)
        token._refresh(self._gd_client.http_client.request)
        self._save_token(token)

    def authenticate(self):
        try:
            token = self._load_token()
            if token is None:
                token = gdata.gauth.OAuth2Token(
                    client_id=self._client_id, client_secret=self._client_secret, scope=SCOPES,
                    user_agent=USER_AGENT)

                authorize_url = token.generate_authorize_url()
                print "Authorize URL:", authorize_url
                webbrowser.open_new_tab(authorize_url)
                token.get_access_token(unicode(raw_input('Verifier code: ')))
                token.authorize(self._gd_client)
                self._save_token(token)
                return True

            self.refresh_token(token)
            if token.invalid:
                self._save_token(None)
            else:
                token.authorize(self._gd_client)
                return True

        except gdata.gauth.OAuth2AccessTokenError as e:
            self._save_token(None)
            sys.stderr.write(str(e) + "\n")
        except Exception as e:
            sys.stderr.write(str(e) + "\n")

        return False