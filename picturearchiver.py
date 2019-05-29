# coding=UTF8

import os
import shutil
import time
import utils
import datetime


# noinspection PyBroadException
class PictureArchiver:
    _verbose = True
    _debug = False

    def __init__(self, src_path, dest_path):
        self._srcPath = src_path
        self._destPath = dest_path
        self._move_files = False
        self._diagnostics = False
        self._imgCount = 0
        self._currImgIndex = 0
        self._success_count = 0
        self._currImgFileName = None
        self._correct_dates_only = False        
        self._move_destination = None
        self._include_video = False
        self.onAdvance = None
	self.log_file_name = None
	self.log_file = None

    def _change_owner(self, path):
        new_owner = os.environ.get(utils.PA_NEW_OWNER)
        if new_owner is None:
            return
        
        new_group = os.environ.get(utils.PA_NEW_GROUP)
        if new_group is None:
            return

        new_mod = os.environ.get(utils.PA_NEW_MODE)
        if new_mod is not None:
            new_mod = int(new_mod, 8)

        utils.change_owner(path, new_owner, new_group, new_mod)
        
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
        print utils.error(msg)

    def _correct_exif_date(self, filename, date):
        if not utils.is_picture(filename):
            return
        try:
            import pyexiv2
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
            pass

    def _is_valid_backup_file(self, file_name):	
		if self._include_video:
			fname, fext = os.path.splitext(file_name)
			return fext.lower().lstrip(".") in utils.MIME_TYPES.keys()
		
		return utils.is_image(file_name)

    @staticmethod
    def get_dest_folder_name(obj_date):
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

        #self._debug("Corrected: " + picture_path)

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

    def _move_to_move_destination(self, src_file, dest_folder_name):
        if self._move_destination is not None:            
            dest_folder = os.path.join(self._move_destination, dest_folder_name, utils.get_sub_folder(src_file))
            dest_file = os.path.join(dest_folder, os.path.basename(src_file))
            self._create_folder_if_needed(dest_folder)
            self._log("MOVING: '" + src_file + "' to '" + dest_file + "'")
            if not self._diagnostics:
                shutil.move(src_file, dest_file)

    def _create_folder_if_needed(self, dest_folder):
        if not os.path.isdir(dest_folder):
            self._log("CREATING: Folder '" + dest_folder + "'")
            if not self._diagnostics:
                new_owner = os.environ.get(utils.PA_NEW_OWNER)
                new_group = os.environ.get(utils.PA_NEW_GROUP)
                utils.makedirs(dest_folder, new_owner, new_group)


    def _walk_dir(self, root_dir):

        if os.path.isdir(root_dir):
            dir_list = os.listdir(root_dir)
            self._imgCount += len(dir_list)
        else:
            self._imgCount = 1
            dir_list = [os.path.basename(root_dir)]
            root_dir = os.path.dirname(root_dir)

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

            if not self._is_valid_backup_file(src_file):
                self._log("SKIPING: '" + src_file + "'")
                continue

            src_size = os.path.getsize(src_file)

            picture_date = utils.get_picture_date(src_file)
            if not isinstance(picture_date, datetime.datetime):
                picture_date = datetime.datetime.now()

            if picture_date is None:
                self._log("SKIPING: '" + src_file + "' Couldn't determine file date")
                continue

            dest_folder_name = self.get_dest_folder_name(picture_date)

            dest_folder = os.path.join(self._destPath, dest_folder_name, utils.get_sub_folder(src_file))
            dest_file = os.path.join(dest_folder, filename)
            move = self._move_files or src_file.startswith(u"/home/hm/Imágenes/Camara")

            try:
                if os.path.isfile(dest_file) and os.path.samefile(src_file, dest_file):
                    self._log("SKIPING: '" + dest_file + "' Source and destination are the same.")
                    continue

                update = False
                if os.path.isfile(dest_file):
                    update = True
                    dest_size = os.path.getsize(dest_file)
                    if dest_size >= src_size:
                        self._log("SKIPING: '" + dest_file + "' already exists.")
                        self._move_to_move_destination(src_file, dest_folder_name)
                        continue

                self._create_folder_if_needed(dest_folder)                

                if move:                    
                    self._log("MOVING: '" + src_file + "' to '" + dest_file + "'")                    
                    if not self._diagnostics:
                        shutil.move(src_file, dest_folder)
                        self._change_owner(dest_file)
                        self._bytes_copied = self._bytes_copied + src_size

                    files_left -= 1
                    if files_left == 0:
                        try:
                            if not self._diagnostics and os.path.isdir(root_dir):                                
                                os.rmdir(root_dir)
                        except:
                            self._error("Error removing dir")

                else:              
                    action = "UPDATING: '" if update else "COPING: '"      
                    self._log(action + src_file + "' to '" + dest_file + "'")
                    if not self._diagnostics:
                        shutil.copy(src_file, dest_folder)
                        self._change_owner(dest_file)
                        self._bytes_copied = self._bytes_copied + src_size

                success = self._diagnostics or ((not move or not os.path.isfile(src_file)) and os.path.isfile(dest_file) and src_size == os.path.getsize(dest_file))
                if success:
                    self._move_to_move_destination(src_file, dest_folder_name)
                    if not self._diagnostics:
                        self._correct_picture_date(dest_file, picture_date)                    

                    self._success_count += 1

            except Exception as exp:
                self._error(exp)
                continue                

    def archive_pictures(self):

        # Just to report that pyexiv2 does not exists in the system
        try:
            import pyexiv2
        except Exception as ex:
            utils.error(ex)
	
	try:
            self.log_file = open(self.log_file_name, "w")
        except Exception as ex:
            utils.error(ex)

        self._imgCount = 0
        self._currImgIndex = 0
        self._success_count = 0
        self._bytes_copied = 0

        start_time = time.time()
        self._walk_dir(self._srcPath)
        totalTime = utils.format_time(time.time() - start_time)

        self._log(str(self._success_count) + " of " + str(self._currImgIndex) + " files copied.")
        self._log(utils.sizeof_fmt(self._bytes_copied) + " copied in " + totalTime)
	
	if self.log_file is not None:
		self.log_file.close()
		self.log_file = None

    @classmethod
    def do(cls, src_path, dest_path, move_destination, diagnostics, move, log_file):
        obj = cls(src_path, dest_path)
        obj._diagnostics = diagnostics
        obj._move_files = move        
        obj._move_destination = move_destination
	obj.log_file_name =  log_file

        if obj._diagnostics:
            obj._log("WARING: Diagnostics mode activated.")
        obj.archive_pictures()

    @classmethod
    def archive(cls, source, destination_options):
        obj = cls(src_path, destination_options["dest_path"])

        obj._diagnostics = destination_options["diagnostics"]
        obj._move_files = destination_options["move"]
        obj._move_destination = None         

        if obj._diagnostics:
            obj._log("WARING: Diagnostics mode activated.")

        obj.archive_pictures()


    @classmethod
    def correct_dates(cls, src_path):
        obj = cls(src_path, src_path)
        obj._walk_dir_correct_date(src_path)
