import sys
import webbrowser

import flickrapi
from flickrapi.auth import FlickrAccessToken

from pictureuploader import PictureUploader, FileWithCallback
import utils


md5_tag_prefix = "checksum:md5="
date_tag_prefix = "date:iso="
date_year_tag_prefix = "date:year="
date_month_tag_prefix = "date:month="
date_day_tag_prefix = "date:day="


class FlickrUploader(PictureUploader):
    def __init__(self, api_key, api_secret, user=None):
        PictureUploader.__init__(self)

        self._token_key = "flickr-token"
        if user:
            self._token_key += "-" + user

        self._flickr = flickrapi.FlickrAPI(api_key, api_secret, store_token=False, username=user, cache=False,
                                           token=self._load_token())
        self.check_remote_chksum = True
        self._set_service_name("flickr")

    def _load_token(self):
        try:
            token_data = self._dataHelper.get_secure_data(self._token_key)
            if token_data is not None:
                return FlickrAccessToken(unicode(token_data["oauth_token"]),
                                         unicode(token_data["oauth_token_secret"]),
                                         unicode(token_data["access_level"]),
                                         unicode(token_data["fullname"]),
                                         unicode(token_data["username"]),
                                         unicode(token_data["user_nsid"]))
        except:
            pass
        return None

    def _save_token(self, token):
        if token is None:
            self._dataHelper.save_secure_data(self._token_key, None)
        else:
            token_data = {"oauth_token": token.token, "oauth_token_secret": token.token_secret,
                          "access_level": token.access_level, "fullname": token.fullname, "username": token.username,
                          "user_nsid": token.user_nsid}
            self._dataHelper.save_secure_data(self._token_key, token_data)


    def get_photoid_from_md5sum(self, md5sum):
        for photo in self._flickr.walk(user_id="me", tags=md5_tag_prefix + md5sum):
            return photo.get("id")
        return 0

    def upload_file(self, file_name, md5sum=None):
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
            rsp = self._flickr.upload(file_name, f, title="",
                                      description="", tags=tags, is_public="0", is_family="0",
                                      is_friend="0", format="xmlnode")
            f.all_done()

            sys.stdout.flush()

            if rsp['stat'] == u'ok':
                return rsp.photoid[0].text

            return 0
        except Exception as e:
            try:
                print "Error on: ", file_name
                sys.stderr.write(u"Error on " + file_name + u": " + unicode(e) + u"\n")
            except:
                sys.stderr.write("Error printing error.\n")  # :D

            return 0

    def authenticate(self):

        token_valid = self._flickr.token_valid(perms=u'write')
        if token_valid:
            self.user_name = self._flickr.token_cache.token.fullname + " (" + self._flickr.token_cache.token.username + ")"
            return True

        # Get a request token
        self._flickr.get_request_token(oauth_callback='oob')

        # Open a browser at the authentication URL. Do this however
        # you want, as long as the user visits that URL.
        authorize_url = self._flickr.auth_url(perms=u'write')
        print "Authorize URL:", authorize_url
        webbrowser.open_new_tab(authorize_url)

        # Get the verifier code from the user. Do this however you
        # want, as long as the user gives the application the code.
        verifier = unicode(raw_input('Verifier code: '))

        # Trade the request token for an access token
        self._flickr.get_access_token(verifier)

        valid = self._flickr.token_valid(perms=u'write')
        if valid:
            self.user_name = self._flickr.token_cache.token.fullname + " (" + self._flickr.token_cache.token.username + ")"
            self._save_token(self._flickr.token_cache.token)

        return valid
