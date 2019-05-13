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

    def GetFeed(self, uri, **kwargs):

        def converter(response):
            body = response.read()
            return gdata.photos.AnyFeedFromString(body)

        uri = '%s://%s%s' % (self.scheme, self.server, uri)
        return self.get_feed(uri, auth_token=None,
                             converter=converter, **kwargs)

    def GetPhotosInAlbum(self, album_id, user='default', **kwargs):
        uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (user, album_id)
        return self.GetFeed(uri, **kwargs)

    def GetUserFeed(self, kind='album', user='default', **kwargs):
        if isinstance(kind, (list, tuple)):
            kind = ",".join(kind)

        uri = '/data/feed/api/user/%s?kind=%s' % (user, kind)
        return self.GetFeed(uri, **kwargs)

    def InsertPhotoSimple(self, album_uri, title, summary, fileobj,
                          content_type='image/jpeg', keywords=None):
        http_request = atom.http_core.HttpRequest()

        size = 0
        if hasattr(fileobj, "len"):
            size = fileobj.len

        if isinstance(fileobj, str):
            size = os.path.getsize(fileobj)
            fileobj = open(fileobj, 'rb')

        if size == 0:
            raise ValueError("Could not determine data size")

        uri = '%s://%s%s' % (self.scheme, self.server, album_uri)

        metadata = gdata.photos.PhotoEntry()
        metadata.title = atom.Title(text=title)
        metadata.summary = atom.Summary(text=summary, summary_type='text')
        if keywords is not None:
            if isinstance(keywords, list):
                keywords = ','.join(keywords)
            metadata.media.keywords = gdata.media.Keywords(text=keywords)

        http_request.add_body_part(str(metadata), "application/atom+xml")
        http_request.add_body_part(fileobj, content_type, size)

        def converter(response):
            body = response.read()
            return gdata.photos.AnyEntryFromString(body)

        return self.request(method='POST', uri=uri, auth_token=None,
                            http_request=http_request, converter=converter,
                            desired_class=None)

