PyArcPics
=========

Python script that I use to handle, backup and share my huge picture collection.

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

Disclaimer
----------
I wrote this application as a solution to my specific problem, if it is useful to you great! you can
use it and reuse the code if you need it. I do not provide any sort of support.
