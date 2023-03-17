import base64
import getpass
import hashlib
import json
import os
import time
import re
import datetime
import pwd
import grp
import statvfs

primary_backup_marker = "destination_folder"
secondary_backup_marker = "secondary_backup"

PA_NEW_OWNER="PA_NEW_OWNER"
PA_NEW_GROUP="PA_NEW_GROUP"
PA_NEW_MODE="PA_NEW_MODE"

error_printed = False

def error(e):    
    print '\033[91mERROR:', e, '\033[0m'


def change_owner(path, owner, group, mod=None):
    if not owner or not group:
        return
    
    uid = pwd.getpwnam(owner).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)

    if mod is not None:
        os.chmod(path, mod)


def makedirs(name, owner=None, group=None):
    head, tail = os.path.split(name)
    if not tail:
        head, tail = os.path.split(head)
    if head and tail and not os.path.exists(head):
        try:
            makedirs(head, owner=owner, group=group)
        except OSError:
            # Defeats race condition when another thread created the path
            pass
        
        if tail == os.curdir:           # xxx/newdir/. exists if xxx/newdir exists
            return
    try:        
        os.mkdir(name)
        change_owner(name, owner=owner, group=group)
    except OSError:
        pass
            
def format_time(_time):
    days = int(_time // 86400)
    hours = int(_time // 3600 % 24)
    minutes = int(_time // 60 % 60)
    seconds = int(_time % 60)

    result = ""

    if days > 0:
        result += str(days) + " days, "

    if hours > 0:
        result += str(hours) + " hours, "

    if minutes > 0:
        result += str(minutes) + " minutes, "

    if seconds > 0:
        result += str(seconds) + " seconds"

    if result:
        return result

    return "0 seconds"


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def has_exif(file_name):
    fname, fext = os.path.splitext(file_name)
    return fext.lower() in [".jpg", ".jpeg", ".png", ".dng", ".orf", ".cr2"]


def is_picture(file_name):
    fname, fext = os.path.splitext(file_name)
    return fext.lower() in [".jpg", ".jpeg", ".png"]


def get_exif_value(exif_data, key):
    try:
        return exif_data[key].value
    except Exception:
        return None


def read_picture_date(exif_data):
    obj_date = get_exif_value(exif_data, 'Exif.Image.DateTime')
    if obj_date is None or type(obj_date) is not datetime.datetime:
        obj_date = get_exif_value(exif_data, 'Exif.Photo.DateTimeOriginal')
        if obj_date is None or type(obj_date) is not datetime.datetime:
            obj_date = get_exif_value(exif_data, 'Exif.Photo.DateTimeDigitized')
            if type(obj_date) is not datetime.datetime:
                obj_date = None

    return obj_date

def date_from_exif_data(filename):
    
    try:
        import pyexiv2
        exif_data = pyexiv2.ImageMetadata(filename)
        exif_data.read()
        obj_date = read_picture_date(exif_data)
    except Exception as ex:           
        obj_date = None

    return obj_date


def get_date_from_foldername(filename):
    dirname = os.path.basename(os.path.dirname(filename))
    if dirname is None or len(dirname) < 4:
        return None

    return get_date_from_filename(dirname)


def get_date_from_filename(filename):
    try:
        date_str = re.sub("[^\\d]", "", os.path.basename(filename))
        if len(date_str) < 8:
            return get_date_from_foldername(filename)

        year = int(date_str[0:4])

        if year < 1971 or year > datetime.datetime.now().year:
            return get_date_from_foldername(filename)

        month = int(date_str[4:6])
        day = int(date_str[6:8])

        hour = 0
        min = 0
        sec = 0

        if len(date_str) >= 12:
            try:
                hour = int(date_str[8:10])
                if hour > 23:
                    hour = 23
                min = int(date_str[10:12])
                if min > 59:
                    min = 59
                if len(date_str) >= 14:
                    sec = int(date_str[12:14])
                    if sec > 59:
                        sec = 59
            except:
                print("Error parsing time")

        date = datetime.datetime(year, month, day, hour, min, sec)
        return date
    except Exception as e:
        return get_date_from_foldername(filename)


def get_date_from_file_date(filename):
    file_date = time.localtime(os.path.getmtime(filename))
    obj_date = datetime.datetime(file_date.tm_year, file_date.tm_mon, file_date.tm_mday,
                                 file_date.tm_hour, file_date.tm_min, file_date.tm_sec)
    return obj_date


def get_picture_date(picture_path):
    obj_date = None
    if has_exif(picture_path):
        obj_date = date_from_exif_data(picture_path)

    if obj_date is None:
        obj_date = get_date_from_filename(picture_path)

        if obj_date is None:
            obj_date = get_date_from_file_date(picture_path)

    return obj_date


def get_drive_list():
    if os.name == "posix":
        import commands

        mount = commands.getoutput('df -Ph')
        lines = mount.split('\n')        
        lines.reverse()     
        uniquelines = dict(map(lambda line: (line.split(None, 5)[0], line), filter(lambda l: l.startswith("/dev") or l.startswith("//"), lines))).values()        
        return map(lambda line: line.split(None, 5)[5], uniquelines)
    elif os.name == "nt":
        import win32api

        dv = win32api.GetLogicalDriveStrings()
        return dv.split('\000')[:-1]
    else:
        return None


def find_camera_folders(folder="DCIM"):
    drives = get_drive_list()
    result = []
    for drive in drives:
        if drive == "/" or drive == "/home":
            continue
        camera_folder = os.path.join(drive, folder)
        if os.path.isdir(camera_folder):
            result.append(camera_folder)
    
    return result

class FolderOptions:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __str__(self):
        return str(self.__dict__)


def read_backup_folder_options(options_file_name=""):

    options = {
        "priority": 100, # Priority of the folder
        "subfolder": None, # Subfolder in main path
        "dest_path": os.path.dirname(options_file_name), # Full backup folder path
        "diagnostics": False, # Diganostics mode (CL)
        "move": False, # Move files insted of copy (CL)
        "min_size": None, # Min size in MB in des_path
        "user": None, # Owner of the files in dest_path
        "group": None, # Group of the files in dest_path
        "mod": None, # File permissions of files in dest_path
        "post_proc_cmd": None, # Shell command to execute in folders after backup. Execute one time for all folders if {{}} found in args or one time for every folder if {} found.
        "post_proc_args": "{}", # Arguments to post_proc_cmd {{}} is replaced with a list of all folders, {} is replaced with current folder only.
        "move_destination": None, # If this is set to a valid path: after the original file is copied to the main destination it will be moved to this location. (CL)
        "log_file": None,  # If set will save statics after all files are copied. (CL)
        "initialized": False,
        "rotate": False, # If true and the drive is full will delete older pictures to make room for new ones.
        "excludeExt": [],
        "excludeOlderThan": None
    }
    
    optionsObj = FolderOptions(**options)
    if options_file_name:
        try:        
            if options_file_name:
                config = json.load(open(options_file_name))
                
                for key, value in config.iteritems():
                    options[key] = value

                optionsObj = FolderOptions(**options)        

                if optionsObj.subfolder is not None:
                    optionsObj.dest_path = os.path.join(optionsObj.dest_path , optionsObj.subfolder)

                optionsObj.initialized = True
        except:     
            pass
        
    return optionsObj


def get_backup_folders(config_file_name=primary_backup_marker):

    def sortPriority(val):
        return val.priority

    drives = get_drive_list()        
    folders = []
    for drive in drives:
        if drive == "/":
            continue        
        
        config_file_path = os.path.join(drive, config_file_name)        
        if os.path.isfile(config_file_path):
            folders.append(read_backup_folder_options(config_file_path))

    folders.sort(key = sortPriority)
    
    return folders
        


def find_backup_folder_options(folder=primary_backup_marker):       
    for folder in get_backup_folders(folder):                  
        if os.path.isdir(folder.dest_path):
            min_size = folder.min_size
            if min_size is not None:
                drive_size = get_free_space_in_mb(folder.dest_path)                
                if drive_size < int(min_size): 
                    error("No enough space in {path}.".format(path=folder.dest_path))
                    continue               

            if folder.user is not None:
                os.environ[PA_NEW_OWNER] = folder.user
            if folder.group is not None:
                os.environ[PA_NEW_GROUP] = folder.group
            if folder.mod is not None:
                os.environ[PA_NEW_MODE] = folder.mod

            return folder
        
    return None


MIME_TYPES = {
    "bmp": ["image/bmp", ""],
    "gif": ["image/gif", ""],
    "jpeg": ["image/jpeg", ""],
    "jpg": ["image/jpeg", ""],
    "png": ["image/png", ""],
    "cr2": ["image/cr2", ""],
    "dng": ["image/dng", ""],
    "orf": ["image/orf", ""],
    "arw": ["image/arw", ""],
    "3gpp": ["video/3gpp", ""],
    "3gp": ["video/3gpp", ""],
    "avi": ["video/avi", ""],
    "mov": ["video/quicktime", ""],
    "mp4": ["video/mp4", ""],
    "lrv": ["video/mp4", ""],
    "mpeg": ["video/mpeg", ""],
    "mpg": ["video/mpeg", ""],
    "mpeg4": ["video/mpeg4", ""],
    "asf": ["video/x-ms-asf", ""],
    "wmv": ["video/x-ms-wmv", ""]
}


def file_name_to_mimetype(file_name):
    n, e = os.path.splitext(file_name)
    try:
        return MIME_TYPES[e.lower().lstrip(".")][0]
    except KeyError:
        return None

	
def is_image(file_name):
	mime = file_name_to_mimetype(file_name)
	return mime is not None and mime.startswith('image')
		

def get_sub_folder(file_name):
    n, e = os.path.splitext(file_name)
    try:
        return MIME_TYPES[e.lower().lstrip(".")][1]
    except KeyError:
        return None

def get_free_space(path):
    stats = os.statvfs(path)
    return (stats[statvfs.F_FRSIZE] * stats[statvfs.F_BAVAIL])

def get_free_space_in_mb(path):
    return get_free_space(path) * 0.000001

def str_to_int(str, defval):
    try:
        return int(str)
    except ValueError:
        return defval

def rmdir(dir):
    try:
        rmfile(os.path.join(dir, '.DS_Store'))
        os.rmdir(dir)        
    except:
        None     

def rmfile(filename):    
    try:
        if os.path.isfile(filename):
            os.remove(filename)
            return True
            
        return False
    except:
        error("Error removing: " + filename)
        return False
        
        

def remove_old_pictures(folder, size_to_claim):
    yearfolders = filter(lambda d: str_to_int(d, 0) > 2010, os.listdir(folder))
    yearfolders.sort()
    yearfolders = map(lambda d: os.path.join(folder, d), yearfolders)
    yearfolders = filter(lambda d: os.path.isdir(d), yearfolders)

    total_deleted_size = 0;
    deleted_count = 0;
    for year in yearfolders:
        #print year
        monthfolders = filter(lambda d: 1 <= str_to_int(d, 0) <= 12, os.listdir(year))
        monthfolders.sort()
        monthfolders = map(lambda d: os.path.join(year, d), monthfolders)
        monthfolders = filter(lambda d: os.path.isdir(d), monthfolders)
        for month in monthfolders:
            #print month
            dayfolders = os.listdir(month)
            dayfolders.sort()
            dayfolders = map(lambda d: os.path.join(month, d), dayfolders)
            dayfolders = filter(lambda d: os.path.isdir(d), dayfolders)   

            for day in dayfolders:
                #print day
                files = os.listdir(day)
                files.sort()
                files = map(lambda d: os.path.join(day, d), files)
                files = filter(lambda d: os.path.isfile(d), files)   
                for file in files:                    
                    size = os.path.getsize(file)

                    print 'Deleting', file
                    if rmfile(file):
                        total_deleted_size = total_deleted_size + size                    
                        deleted_count = deleted_count + 1
                        if total_deleted_size > size_to_claim:
                            print "Deleted count:", deleted_count
                            print "Deleted size:", sizeof_fmt(total_deleted_size)                            
                            return deleted_count
                rmdir(day)
            
            rmdir(month)

        rmdir(year)


    


