# coding=UTF8

import os
import shutil
import pyexiv2
import time
import utils


# noinspection PyBroadException
class PictureArchiver:
    _move_files = False
    _diagnostics = False

    _verbose = True
    _debug = False

    _imgCount = 0
    _currImgIndex = 0
    _success_count = 0
    _currImgFileName = None
    _correct_dates_only = False

    onAdvance = None

    def __init__(self, src_path, dest_path):
        self._srcPath = src_path
        self._destPath = dest_path

    def _do_advance(self):
        try:
            if self.onAdvance is not None:
                self.onAdvance(self)
        except Exception:
            pass

    def _log(self, text):
        if self._verbose:
            print text

    def _debug(self, text):
        if self._debug:
            print text

    def _error(self, msg):
        print "ERROR:", msg

    def _correct_exif_date(self, filename, date):
        try:
            exif_data = pyexiv2.ImageMetadata(filename)
            need_write = False
            exif_data.read()

            if utils.get_exif_value(exif_data, 'Exif.Image.DateTime') is None:
                exif_data['Exif.Image.DateTime'] = date
                need_write = True

            if utils.get_exif_value(exif_data, 'Exif.Photo.DateTimeOriginal') is None:
                exif_data['Exif.Photo.DateTimeOriginal'] = date
                need_write = True

            if utils.get_exif_value(exif_data, 'Exif.Photo.DateTimeDigitized') is None:
                exif_data['Exif.Photo.DateTimeDigitized'] = date
                need_write = True

            if need_write:
                exif_data.write(True)
        except Exception as e:
            self._error(e)

    def _is_picture(self, file_name):
        fname, fext = os.path.splitext(file_name)
        return fext.lower() in [".jpg", ".jpeg", ".png", ".mov", ".avi", ".mp4", ".mpg", ".mpeg", ".lrv", ".thm"]

    def _get_dest_folder_name(self, obj_date):
        if obj_date is not None:
            year = obj_date.strftime("%Y")
            month = obj_date.strftime("%m")
            day = obj_date.strftime("%Y-%m-%d")
            destpath = os.path.join(year, month, day)
            return destpath
        else:
            return ""

    def _correct_picture_date(self, picture_path, datetime):
        self._correct_exif_date(picture_path, datetime)

        filetime = time.mktime(datetime.timetuple())
        os.utime(picture_path, (filetime, filetime))

        self._debug("Corrected: " + picture_path)

    def _walk_dir_correct_date(self, root_dir):
        dir_list = os.listdir(root_dir)
        for filename in dir_list:
            src_file = os.path.join(root_dir, filename)

            if os.path.isdir(src_file):
                self._walk_dir_correct_date(src_file)
                continue

            if os.path.isfile(src_file):
                picture_date = utils.get_picture_date(src_file)
                self._correct_picture_date(src_file, picture_date)

    def _walk_dir(self, root_dir):
        dir_list = os.listdir(root_dir)
        self._imgCount += len(dir_list)

        files_left = len(dir_list)
        for filename in dir_list:
            self._currImgIndex += 1
            self._currImgFileName = filename
            self._do_advance()

            src_file = os.path.join(root_dir, filename)

            if os.path.isdir(src_file):
                self._walk_dir(src_file)
                continue

            if not os.path.isfile(src_file):
                continue

            if not self._is_picture(src_file):
                self._log("SKIPING: '" + src_file + "' is not a picture or video")
                continue

            picture_date = utils.get_picture_date(src_file)
            if picture_date is None:
                self._log("SKIPING: '" + src_file + "' No se pudo determinar la fecha.")
                continue

            dest_folder_name = self._get_dest_folder_name(picture_date)

            dest_folder = os.path.join(self._destPath, dest_folder_name)
            dest_file = os.path.join(dest_folder, filename)
            move = self._move_files or src_file.startswith(u"/home/hm/Imágenes/Camara")

            try:
                if os.path.isfile(dest_file) and os.path.samefile(src_file, dest_file):
                    self._log("SKIPING: '" + dest_file + "' Source and destination are the same.")
                    continue

                if os.path.isfile(dest_file):
                    self._log("SKIPING: '" + dest_file + "' already exists.")
                    if not self._diagnostics:
                        self._correct_picture_date(dest_file, picture_date)
                    continue

                if not os.path.isdir(dest_folder):
                    self._log("CREATING: Folder '" + dest_folder + "'")
                    if not self._diagnostics:
                        os.makedirs(dest_folder)

                if move:
                    self._log("MOVING: '" + src_file + "' to '" + dest_file + "'")
                    if not self._diagnostics:
                        shutil.move(src_file, dest_folder)

                    files_left -= 1
                    if files_left == 0:
                        try:
                            if not self._diagnostics:
                                os.rmdir(root_dir)
                        except:
                            self._error("Error removing dir")

                else:
                    self._log("COPING: '" + src_file + "' to '" + dest_file + "'")
                    if not self._diagnostics:
                        shutil.copy(src_file, dest_folder)

                if not self._diagnostics:
                    self._correct_picture_date(dest_file, picture_date)

                self._success_count += 1
            except Exception as exp:
                self._error(exp)
                continue

    def archive_pictures(self):
        self._imgCount = 0
        self._currImgIndex = 0
        self._success_count = 0
        self._walk_dir(self._srcPath)

        self._log(str(self._success_count) + " of " + str(self._currImgIndex) + " files copied.")

    @classmethod
    def do(cls, src_path, dest_path, diagnostics, move):
        obj = cls(src_path, dest_path)
        obj._diagnostics = diagnostics
        obj._move_files = move
        if obj._diagnostics:
            obj._log("WARING: Diagnostics mode activated.")
        obj.archive_pictures()

    @classmethod
    def correct_dates(cls, src_path):
        obj = cls(src_path, src_path)
        obj._walk_dir_correct_date(src_path)