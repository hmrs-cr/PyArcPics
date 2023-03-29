# coding=UTF8

import errno
import os
import shutil
import time
import utils
import datetime
import datetime
import dbutils
import atexit

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
        self._excludeExt = []
        self.onAdvance = None
        self.log_file_name = None
        self.log_file = None
        self.folder_list = {}
        self.post_proc_cmd = None
        self.post_proc_args = None
        self.enable_post_proc_cmd = False
        self._delete_old_pics = False
        self._excludeOlderThan = None
        self._finished = False
        self._invalid_count = 0

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
            print(text)
	
    def _debug(self, text):
        if self._debug:
            print(text)

    def _error(self, msg):
        utils.error(msg)

    def _correct_exif_date(self, filename, date):
        if not utils.is_picture(filename):
            return
        try:
            import exifread
            f = open(filename, 'rb')
            exif_data = exifread.process_file(f, details=False)
            f.close()
            need_write = False

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
        fname, fext = os.path.splitext(file_name)
        fext = fext.lower().lstrip(".")
        if len(self._excludeExt) > 0 and self._excludeExt.count(fext) > 0:
            return False

        if self._include_video:            
            return fext in list(utils.MIME_TYPES.keys())
		
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
        #self._correct_exif_date(picture_path, datetime)

        filetime = time.mktime(datetime.timetuple())
        os.utime(picture_path, (filetime, filetime))

        #self._debug("Corrected: " + picture_path)

    def _validate_against_database(self, dest_relative_filename, src_checksum, src_size, picture_date, validate_only=False):
        return self._save_to_database(dest_relative_filename, src_checksum, src_size, picture_date, True)
    
    def _save_to_database(self, dest_relative_filename, src_checksum, src_size, picture_date, validate_only=False):
        if self._no_checksums or src_checksum is None:
            return

        if self._database_connections is None:
            self._database_connections = {}
        
        databasename = os.path.join(self._destPath, str(picture_date.year), f'checksums-{picture_date.year}.db')
        con = self._database_connections.get(picture_date.year) or dbutils.start_db_transaction(databasename)
        self._database_connections[picture_date.year] = con

        if validate_only:
            self._invalid_count = self._invalid_count + (1 if not con.is_picture_valid(dest_relative_filename, src_checksum, src_size, picture_date) else 0)
        else:
            con.insert_picture_record(dest_relative_filename, src_checksum, src_size, picture_date)

        self._success_count = self._success_count + 1
        self._bytes_copied = self._bytes_copied + src_size
        if self._last_year != picture_date.year:
            if self._last_year is not None:
                con = self._database_connections[self._last_year]
                if con is not None:
                    dbutils.close_db_transaction(con)
                    del self._database_connections[self._last_year]
            self._last_year = picture_date.year



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
            dir_list = [d for d in os.listdir(root_dir) if not d.startswith('@')]
            dir_list.sort()
            self._imgCount += len(dir_list)
        else:
            self._imgCount = 1
            dir_list = [os.path.basename(root_dir)]
            root_dir = os.path.dirname(root_dir)

        self._files_left = len(dir_list)
        for filename in dir_list:
            self._currImgIndex += 1
            self._currImgFileName = filename
            self._do_advance()

            src_file = os.path.join(root_dir, filename)

            if os.path.isdir(src_file):
                if self._excludeOlderThan is not None and 2010 < utils.str_to_int(filename, 2100) < self._excludeOlderThan.year:
                    continue

                self._walk_dir(src_file)
                continue

            if not os.path.isfile(src_file):
                continue

            if not self._is_valid_backup_file(src_file):
                self._log("SKIPING: '" + src_file + "'")
                continue            

            try:
                self.copy(root_dir, src_file, filename)
            except Exception as exp:                
                self._error(exp)
                continue

    def copy(self, root_dir, src_file, filename):
        picture_date = utils.get_picture_date(src_file)
        if not isinstance(picture_date, datetime.datetime):
            picture_date = datetime.datetime.now()

        if picture_date is None:
            self._log("SKIPING: '" + src_file + "' Couldn't determine file date")
            return
        
        if self._excludeOlderThan is not None and picture_date < self._excludeOlderThan:
            self._log("SKIPING: '" + src_file + "' is older than " + self._excludeOlderThan.strftime('%Y-%m-%d %H:%M'))
            return
        
        retries = 5
        src_size = os.path.getsize(src_file)
        dest_folder_name = self.get_dest_folder_name(picture_date)
        dest_folder = os.path.join(self._destPath, dest_folder_name, utils.get_sub_folder(src_file))
        dest_file = os.path.join(dest_folder, filename)
        move = self._move_files or src_file.startswith("/home/hm/Imágenes/Camara")

        while retries > 0:
            retries = retries - 1
            try:
                update = False
                if not (self._update_checksum_db_only or self._validate_checksum_db_only):
                    if os.path.isfile(dest_file) and os.path.samefile(src_file, dest_file):
                        self._log("SKIPING: '" + dest_file + "' Source and destination are the same.")
                        return

                    if os.path.isfile(dest_file):
                        update = True
                        dest_size = os.path.getsize(dest_file)
                        if dest_size >= src_size:
                            self._log("SKIPING: '" + dest_file + "' already exists.")
                            self._move_to_move_destination(src_file, dest_folder_name)
                            return
                    
                src_checksum = None if self._no_checksums else utils.crc32(src_file)
                dest_relative_filename = dest_file.replace(self._destPath, '.', 1)

                if self._validate_checksum_db_only:
                    self._validate_against_database(dest_relative_filename, src_checksum, src_size, picture_date)
                    return

                if self._update_checksum_db_only:
                    self._save_to_database(dest_relative_filename, src_checksum, src_size, picture_date)
                    self._log(f'UPDATED CKSUM: {dest_relative_filename}, {src_checksum}, {src_size}, {picture_date}')
                    return
      
                if self._rotate and (self._delete_old_pics or utils.get_free_space(self._destPath) < src_size):                
                    utils.remove_old_pictures(self._destPath, src_size)
                    self._delete_old_pics = False

                self._create_folder_if_needed(dest_folder)
                self.folder_list[dest_folder_name] = self.folder_list.get(dest_folder_name, 0) + 1

                if move:                    
                    self._log("MOVING: '" + src_file + "' to '" + dest_file + "'")                    
                    if not self._diagnostics:
                        shutil.move(src_file, dest_folder)
                        self._change_owner(dest_file)
                        self._bytes_copied = self._bytes_copied + src_size

                    self._files_left -= 1
                    if self._files_left == 0:
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
                        self._save_to_database(dest_relative_filename, src_checksum, src_size, picture_date)                    

                    self._success_count += 1

                return
            except IOError as ioerror:                
                if ioerror.errno == errno.ENOSPC:                    
                    if self._rotate:
                        print("WARN: No space left deleting older pictures")
                        self._delete_old_pics = True
                        continue
                    else:
                        self._error(ioerror)
                        exit(1)
                else:
                    self._error(ioerror)
                    return

    def archive_pictures(self):
        # Just to report that exifread does not exists in the system
        try:
            import exifread
        except Exception as ex:
            utils.error(ex)   

        self._imgCount = 0
        self._currImgIndex = 0
        self._success_count = 0
        self._bytes_copied = 0
        self._start_time = time.time()
        self._database_connections = None
        self._last_year = None

        atexit.register(self._finish)
        try:            
            self._walk_dir(self._srcPath)
            self._finish()            
        except KeyboardInterrupt as ki:
            self._finish(True, ki)
        except Exception as e:
            self._finish(True, e)
            utils.error(e)
        
    def _execute_post_proc_cmd(self, command):

        # Do not execute arbitrary commands from world writable config file
        # by default, it´s dangerous
        #if self.enable_post_proc_cmd:
        #    self._log("Excuting command: " + command)
        #    subprocess.call(rsync_cmd)
        #else:
        self._log("Command not executed (disabled): " + command)

    def _finish(self, canceled=False, error=None):
        if self._finished:
            return

        atexit.unregister(self._finish)
        self._finished = True
        self.cleanup()

        totalSeconds = time.time() - self._start_time
        totalTime = utils.format_time(totalSeconds)        
        try:
            if self.log_file_name:
                self._log("Saving result logs: " + os.path.abspath(self.log_file_name))
                self.log_file = open(self.log_file_name, "w")

                self.log_file.write("COPIED_NUMBER=" + str(self._success_count) + "\n")
                self.log_file.write("TOTAL_NUMBER=" + str(self._currImgIndex) + "\n")
                self.log_file.write("DATA_AMOUNT='" + utils.sizeof_fmt(self._bytes_copied) + "'\n")
                self.log_file.write("DESTINATION_PATH='" + self._destPath + "'\n")
                self.log_file.write("FREE_SPACE_IN_DESTINATION_PATH='" + utils.sizeof_fmt(utils.get_free_space(self._destPath)) + "'\n")
                self.log_file.write("DURATION_TIME='" + totalTime + "'\n")
                self.log_file.write("CANCELED=" + str(canceled) + "\n")
                self.log_file.write("ERROR='" + str(error) + "'\n")
                self.log_file.write("FOLDERS='" + ";".join(list(self.folder_list.keys())) + "'\n")
                if self._diagnostics:
                    self.log_file.write("DIAGNOSTICS=True\n")

                self.log_file.close()		 
                
        except Exception as ex:
            utils.error(ex)	
                
        if self.post_proc_cmd and self.post_proc_args:       
            if '{{}}' in self.post_proc_args:
                for folder in list(self.folder_list.keys()):
                    shell_command = self.post_proc_cmd + " " +  self.post_proc_args.replace("{{}}", folder)
                    self._execute_post_proc_cmd(shell_command)                
            else:
                shell_command = self.post_proc_cmd + " " + self.post_proc_args.replace("{}", " ".join(list(self.folder_list.keys())))
                self._execute_post_proc_cmd(shell_command)

        if self._validate_checksum_db_only:
            print(f'{self._success_count} ({utils.sizeof_fmt(self._bytes_copied)}) of {self._currImgIndex} validated in {totalTime} ({int(self._success_count/totalSeconds)} files/s, {utils.sizeof_fmt(self._bytes_copied/totalSeconds)}/s)')
            print(f'\033[91m{self._invalid_count} invalid!\033[0m' if self._invalid_count > 0 else '\033[92mAll of them valid.\033[0m')
        elif self._update_checksum_db_only:
            print(f'{self._success_count} ({utils.sizeof_fmt(self._bytes_copied)}) of {self._currImgIndex} updated checksums in {totalTime} ({int(self._success_count/totalSeconds)} files/s, {utils.sizeof_fmt(self._bytes_copied/totalSeconds)}/s)')
        else:
            self._log(str(self._success_count) + " of " + str(self._currImgIndex) + " files copied." + f'({int(self._success_count/totalSeconds)} files/s)')
            self._log(utils.sizeof_fmt(self._bytes_copied) + " copied in " + totalTime + f' ({utils.sizeof_fmt(self._bytes_copied/totalSeconds)}/s)')
		

    @classmethod
    def do(cls, src_path, options):        
        obj = cls(src_path, options.dest_path)
        obj._diagnostics = options.diagnostics
        obj._move_files = options.move        
        obj._move_destination = options.move_destination
        obj.log_file_name = options.log_file
        obj._rotate = options.rotate
        obj._excludeExt = options.excludeExt
        obj._no_checksums = options.no_checksums
        obj._update_checksum_db_only = options.update_checksums
        obj._validate_checksum_db_only = options.validate_checksums
        obj._excludeOlderThan = datetime.datetime.strptime(options.excludeOlderThan, '%Y-%m-%d %H:%M') if options.excludeOlderThan is not None else None

        obj.post_proc_cmd = options.post_proc_cmd
        obj.post_proc_args = options.post_proc_args

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

    def cleanup(self):
        if self._database_connections is not None:
            connections = self._database_connections
            self._database_connections = None
            for key in connections.keys():
                dbutils.close_db_transaction(connections[key])

