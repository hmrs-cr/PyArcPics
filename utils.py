import base64
import getpass
import hashlib
import json
import os
import time
import pyexiv2
import re
import datetime
import pwd
import grp


primary_backup_marker = "destination_folder"
secondary_backup_marker = "secondary_backup"

def change_owner(path, owner, group):
    if owner is None or group is None:
        return
    
    uid = pwd.getpwnam(owner).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)

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


def format_eta(bits_per_second, elapsed_bits, total_bits):
    remaining_bits = total_bits - elapsed_bits
    remaining_time = remaining_bits / bits_per_second
    return format_time(remaining_time)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def get_file_size(file_name):
    try:
        return os.path.getsize(file_name)
    except:
        return 0


def has_exif(file_name):
    fname, fext = os.path.splitext(file_name)
    return fext.lower() in [".jpg", ".jpeg", ".png", ".dng", ".orf", ".cr2"]


def is_picture(file_name):
    fname, fext = os.path.splitext(file_name)
    return fext.lower() in [".jpg", ".jpeg", ".png"]


def get_md5sum_from_file(input_file_name):
    dir_name = os.path.dirname(input_file_name)
    file_name = os.path.basename(input_file_name)
    md5_file_name = os.path.join(dir_name, "." + file_name + ".md5")

    if os.path.exists(md5_file_name):
        file_date = get_date_from_file_date(input_file_name)
        md5_file_date = get_date_from_file_date(md5_file_name)
        if file_date <= md5_file_date:        
            with open(md5_file_name, 'r') as content_file:
                md5 = content_file.read()
                if len(md5) == 32:
                    return md5
    
    file_name = os.path.join(dir_name, file_name)
    m = hashlib.md5()
    with open(file_name, "rb") as f:
        while True:
            buf = f.read(128)
            if not buf:
                break
            m.update(buf)

    md5 = m.hexdigest()

    with open(md5_file_name, "w") as text_file:
        text_file.write(md5)

    return md5


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


def get_api_keys_from_config(config_file_name):
    config_file_name = os.path.expanduser(config_file_name)
    try:
        config = json.load(open(config_file_name))
        api_key = unicode(config["api_key"])
        api_secret = unicode(config["api_secret"])
        return api_key, api_secret
    except Exception:
        return None, None


def get_drive_list():
    if os.name == "posix":
        import commands

        mount = commands.getoutput('mount -v')
        lines = mount.split('\n')
        return map(lambda line: line.split()[2], filter(lambda l: l.startswith("/dev"), lines))
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


def find_backup_folder(folder):
    drives = get_drive_list()
    import glob
    for drive in drives:
        if drive == "/" or drive == "/home":
            continue

        paths = glob.glob(os.path.join(drive, "*", folder))
        if len(paths) == 1:
            if os.path.isfile(paths[0]):
                folder, file = os.path.split(paths[0])
                return folder

    return None


def csl2dict(csl):
    return dict(item.split("=") for item in csl.split(";"))


def dict2csl(_dict):
    return ";".join(["=".join([key, str(val)]) for key, val in _dict.items()])


def vigenere_encode(key, string):
    encoded_chars = []
    for i in xrange(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = "".join(encoded_chars)
    return base64.urlsafe_b64encode(encoded_string)


def vigenere_decode(key, string):
    decoded_chars = []
    string = base64.urlsafe_b64decode(string)
    for i in xrange(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(abs(ord(string[i]) - ord(key_c) % 256))
        decoded_chars.append(encoded_c)
    decoded_string = "".join(decoded_chars)
    return decoded_string

MIME_TYPES = {
    "bmp": ["image/bmp", ""],
    "gif": ["image/gif", ""],
    "jpeg": ["image/jpeg", ""],
    "thm": ["image/jpeg", ""],
    "jpg": ["image/jpeg", ""],
    "png": ["image/png", ""],
    "cr2": ["image/tiff", "raw"],
    "dng": ["image/dng", "raw"],
    "orf": ["image/orf", "raw"],
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


def get_cipher_key(base):
    return base + "-" + str(os.getegid()) + "-" + getpass.getuser()


def get_sub_folder(file_name):
    n, e = os.path.splitext(file_name)
    try:
        return MIME_TYPES[e.lower().lstrip(".")][1]
    except KeyError:
        return None
