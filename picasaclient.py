import os
import atom.http_core
import gdata.client
import gdata.photos

"""Provides a client to interact with Google Picasa Web API v2.

Not all operations are implemented at this time.

"""


class PicasaClient(gdata.client.GDClient):
    api_version = '2'
    auth_service = 'lh2'
    server = "picasaweb.google.com"
    scheme = "https"
    auth_scopes = gdata.gauth.AUTH_SCOPES['lh2']

    def __init__(self, domain=None, auth_token=None, **kwargs):
        """Constructs a new client for the Picasa API.

        Args:
          domain: string The Google Apps domain (if any).
          kwargs: The other parameters to pass to the gdata.client.GDClient
              constructor.
        """
        gdata.client.GDClient.__init__(self, auth_token=auth_token, **kwargs)
        self.domain = domain

    def GetUserFeed(self, kind='album', user='default', **kwargs):
        if isinstance(kind, (list, tuple)):
            kind = ",".join(kind)

        def converter(response):
            body = response.read()
            return gdata.photos.AnyFeedFromString(body)

        uri = '%s://%s/data/feed/api/user/%s?kind=%s' % (self.scheme, self.server, user, kind)
        return self.get_feed(uri, auth_token=None,
                             converter=converter, **kwargs)

    def InsertPhotoSimple(self, album_uri, title, summary, filename,
                          content_type='image/jpeg', keywords=None):
        http_request = atom.http_core.HttpRequest()
        f = open(filename, 'rb')
        http_request.add_body_part(f, content_type, os.path.getsize(filename))
        http_request.headers['Slug'] = title
        uri = '%s://%s%s' % (self.scheme, self.server, album_uri)

        def converter(response):
            body = response.read()
            return gdata.photos.AnyEntryFromString(body)

        return self.request(method='POST', uri=uri, auth_token=None,
                            http_request=http_request, converter=converter,
                            desired_class=None)

