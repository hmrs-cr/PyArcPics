PyArcPics
=========

Collection of Python scripts that I use to handle, backup and share my huge picture collection.

GeotagPictures
---------------
Download location data from [Android application](https://github.com/hmrs-cr/android-nmea-logger) and add a geo-location exif tag to each picture in the given
    directory recursively.

    Usage:
    
        geotagpics [-d [DOWNLOAD_URL]] [folder]

        folder             The source with pictures to geotag.

        optional arguments:
          -d [DOWNLOAD_URL]  Download location data from url. (Address of Android phone with the NMEALogger App running in server mode)
          -o                 Overwrite location tag if exists.



ArchivePics
-----------
Backup pictures and videos from cameras, SD cards, and other configured folders to backup media, sorting them in a folder structure by date and keeping date time accurate.

The source media is determined by configuration settings, destination backup disk is determined automatically.

    Usage:
        arcpics [-c CONFIG] [-m] [-d] [-s]

        optional arguments:
          -c CONFIG   The config file (default ~/.hmsoft/arcpics.json)
          -m          Move files instead of copy them.
          -d          Don't run the actual actions.
          -s          Scan folder but don't perform backup

SyncDisks
---------
Sync primary backup media to secondary backup media (redundant backup).

    Usage:
        syncdisks [source] [destination]

        source       The primary backup disk, if not specified it is determined automatically.
        destination  The secondary backup disk, if not specified it is determined automatically.

FlickrUploader
--------------
 Upload all the pictures in the given folder recursively to Flickr. Keeps track the pictures already uploaded.

    Usage:
        flickrup [-s] [-a] folder
        
        folder      The folder to search for pictures
        
        optional arguments:
          -s          Scan folder but don't upload pictures
          -a          Authenticate to Flickr service
                    
Google+Uploader
--------------
 Upload all the pictures in the given folder recursively to Google+ autobackup folder. Keeps track the pictures already uploaded.

    Usage:
        gphotosup [-h] [-s] [-r] [-u USER_NAME] [-p PASSWORD] folder
        
        folder      The folder to search for pictures
        
        optional arguments:
           -s            Scan folder but don't upload pictures
           -r            Reduce image size to 2048x2048 before upload.
           -u USER_NAME  Google account user name.
           -p PASSWORD   Google account password.


Disclaimer
----------
I wrote this application as a solution to my specific problem, if it is useful to you great! you can
use it and reuse the code if you need it. I do not provide any sort of support.
