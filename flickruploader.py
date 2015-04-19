import sys
import webbrowser

import flickrapi

from pictureuploader import PictureUploader, FileWithCallback
import utils


md5_tag_prefix = "checksum:md5="
date_tag_prefix = "date:iso="
date_year_tag_prefix = "date:year="
date_month_tag_prefix = "date:month="
date_day_tag_prefix = "date:day="


class FlickrUploader(PictureUploader):
    def __init__(self, api_key, api_secret):
        PictureUploader.__init__(self)
        self._flickr = flickrapi.FlickrAPI(api_key, api_secret, cache=False)
        self.check_remote_chksum = True
        self._set_service_name("flickr")

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
