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
import zlib

hasexifread = False
try:
    import exifread
    hasexifread = True
except Exception as ex:
    pass

def crc32(filename, chunksize=65536):
    """Compute the CRC-32 checksum of the contents of the given filename"""
    with open(filename, "rb") as f:
        checksum = 0
        while (chunk := f.read(chunksize)) :
            checksum = zlib.crc32(chunk, checksum)
        return checksum

primary_backup_marker = "destination_folder"
secondary_backup_marker = "secondary_backup"

PA_NEW_OWNER="PA_NEW_OWNER"
PA_NEW_GROUP="PA_NEW_GROUP"
PA_NEW_MODE="PA_NEW_MODE"

error_printed = False
log_debug_enabled = False

def debug(text):
    if log_debug_enabled:
        print(text)

def error(e, errorLabel=True):  
    if errorLabel:  
        print('\033[91mERROR:', e, '\033[0m')
    else:
        print('\033[91m' + e + '\033[0m')

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
    return fext.lower() in [".jpg", ".jpeg", ".png", ".dng", ".orf", ".cr2", ".arw"]


def is_picture(file_name):
    fname, fext = os.path.splitext(file_name)
    return fext.lower() in [".jpg", ".jpeg", ".png"]


def get_exif_value_date(exif_data, key):
    try:
        val = exif_data[key].values
        return datetime.datetime.strptime(val, '%Y:%m:%d %H:%M:%S')
    except Exception as e:
        return None


def read_picture_date(exif_data):
    obj_date = get_exif_value_date(exif_data, 'Image DateTime')
    if obj_date is None or type(obj_date) is not datetime.datetime:
        obj_date = get_exif_value_date(exif_data, 'EXIF DateTimeOriginal')        
        if obj_date is None or type(obj_date) is not datetime.datetime:
            obj_date = get_exif_value_date(exif_data, 'EXIF DateTimeDigitized')
            if type(obj_date) is not datetime.datetime:
                obj_date = None
    
    return obj_date

def date_from_exif_data(filename):
    if not hasexifread:
        return None
    
    try:
        with open(filename, 'rb') as f:
            exif_data = exifread.process_file(f, details=False, stop_tag='DateTime')        

        obj_date = read_picture_date(exif_data)             
        #print(filename, obj_date)
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
        import subprocess

        mount = subprocess.getoutput('df -Ph')
        lines = mount.split('\n')        
        lines.reverse()     
        uniquelines = list(dict([(line.split(None, 5)[0], line) for line in [l for l in lines if l.startswith("/dev") or l.startswith("//")]]).values())        
        return [line.split(None, 5)[5] for line in uniquelines]
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

    def overwrite(self, options):
        optionsdict = vars(options)
        for option in optionsdict.keys():
            value = optionsdict[option]
            if (value):
                if option in self.__dict__.keys():
                    self.__dict__[option] = value

    def __str__(self):
        return str(self.__dict__)


def read_backup_folder_options(options_file_name=""):

    options = {
        "priority": 100, # Priority of the folder
        "subfolder": None, # Subfolder in main path
        "dest_path": os.path.dirname(options_file_name) if options_file_name is not None else "", # Full backup folder path
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
        "excludeOlderThan": None,
        "update_checksums": None,
        "validate_checksums": None,
        "no_checksums": None,
        "debug_logs": False
    }
    
    optionsObj = FolderOptions(**options)
    if options_file_name is not None:
        if options_file_name:
            try:        
                if options_file_name:
                    config = json.load(open(options_file_name))
                    
                    for key, value in config.items():
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
        
    return read_backup_folder_options("")


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
    return (stats.f_frsize * stats.f_bavail)

def get_free_space_in_mb(path):
    return get_free_space(path) * 0.000001

def str_to_date(str):
    try:
        return datetime.datetime.strptime(str, '%Y-%m-%d')
    except:
        return None

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
        error("Failed to remove " + filename)
        return False
        
        

def remove_old_pictures(folder, size_to_claim):
    yearfolders = [d for d in os.listdir(folder) if str_to_int(d, 0) > 2010]
    yearfolders.sort()
    yearfolders = [os.path.join(folder, d) for d in yearfolders]
    yearfolders = [d for d in yearfolders if os.path.isdir(d)]

    total_deleted_size = 0
    deleted_count = 0
    for year in yearfolders:
        #print year
        monthfolders = [d for d in os.listdir(year) if 1 <= str_to_int(d, 0) <= 12]
        monthfolders.sort()
        monthfolders = [os.path.join(year, d) for d in monthfolders]
        monthfolders = [d for d in monthfolders if os.path.isdir(d)]
        for month in monthfolders:
            #print month
            dayfolders = os.listdir(month)
            dayfolders.sort()
            dayfolders = [os.path.join(month, d) for d in dayfolders]
            dayfolders = [d for d in dayfolders if os.path.isdir(d)]   

            for day in dayfolders:
                #print day
                files = os.listdir(day)
                files.sort()
                files = [os.path.join(day, d) for d in files]
                files = [d for d in files if os.path.isfile(d)]   
                for file in files:                    
                    size = os.path.getsize(file)

                    if rmfile(file):
                        total_deleted_size = total_deleted_size + size                    
                        deleted_count = deleted_count + 1
                        print('DELETED:', file, f'({sizeof_fmt(size)})')
                        if total_deleted_size > size_to_claim:                            
                            return total_deleted_size
                rmdir(day)
            
            rmdir(month)

        rmdir(year)

    return total_deleted_size

def get_checksum_db_folder(src_path):
    if os.path.isfile(src_path):
        src_path = os.path.dirname(src_path)

    src_path = src_path.rstrip(os.sep)

    dest_path = src_path
    number = str_to_int(os.path.basename(src_path), 0)
    if 2010 < number < 2100:
        dest_path = os.path.dirname(src_path)
    elif 1 < number < 12 and 2010 < str_to_int(os.path.basename(os.path.dirname(src_path)), 0) < 2100:
        dest_path = os.path.dirname(os.path.dirname(src_path))
    elif (date := str_to_date(os.path.basename(src_path))) is not None:
        month = os.path.dirname(src_path)
        year = os.path.dirname(month)
        dest_path = os.path.dirname(year)
    else:
        yeardirs = [y for y in [str_to_int(d, 0) for d in os.listdir(src_path) if os.path.isdir(os.path.join(src_path, d))] if 2010 < y < 2100 ]
        if not len(yeardirs):
            error(f'{src_path} is not a valid picture archive folder.')
            exit(1)
    
    return dest_path

