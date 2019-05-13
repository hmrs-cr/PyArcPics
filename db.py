import os
import sqlite3
import datetime
import utils

last_location_time_key = "last_location_time"
CIPHER_KEY = "buJ&zb2u"


class BuffData:
    def __init__(self):
        buff_folder = os.path.join(os.environ['HOME'], '.hmsoft')
        if not os.path.isdir(buff_folder):
            os.makedirs(buff_folder)

        db_filename = os.path.join(buff_folder, 'picture-data.db')
        self._connection = sqlite3.connect(db_filename, timeout=30.0)
        self._cursor = self._connection.cursor()
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS uploaded (file_name TEXT, photo_id TEXT UNIQUE, md5sum TEXT UNIQUE, "
            "upload_date TEXT )")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS location (timestamp INTEGER PRIMARY KEY, latitude REAL, longitude REAL, "
            "altitude REAL, address TEXT )")
        self._connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self.CIPHER_KEY = utils.get_cipher_key(CIPHER_KEY)

    def set_setting(self, key, value):
        with self._connection:
            if value is None:
                self._connection.execute("DELETE FROM settings WHERE key = ?", (key, ))
            else:
                self._connection.execute("INSERT OR REPLACE INTO settings (key, value) VALUES(?, ?)",
                                         (key, value))

    def save_secure_data(self, key, data):
        value = None
        if data is not None:
            if isinstance(data, dict):
                value = utils.vigenere_encode(self.CIPHER_KEY, utils.dict2csl(data))

        self.set_setting(key, value)

    def get_secure_data(self, key):
        value = self.get_setting(key)
        if value is not None:
            data = utils.csl2dict(utils.vigenere_decode(self.CIPHER_KEY, str(value)))
            return data

        return None

    def get_setting(self, key):
        self._cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = self._cursor.fetchall()
        if len(result) == 1:
            return result[0][0]
        return None

    def add_locations(self, locations):

        c = 0
        last_time = 0
        with self._connection:
            for location in locations:
                if location is None:
                    continue

                self._connection.execute(
                    "INSERT OR IGNORE INTO location (timestamp, latitude, longitude, altitude) VALUES(?, ?, ?, ?) ",
                    location)
                c += 1
                if location[0] > last_time:
                    last_time = location[0]

            if c > 0:
                self._connection.execute("INSERT OR REPLACE INTO settings (key, value) VALUES(?, ?)",
                                         (last_location_time_key, last_time))

        return c

    def get_location_from_timestamp(self, timestamp, offset=None):
        if offset is None:
            offset = 15

        offset *= 1000 * 60
        self._cursor.execute("SELECT latitude, longitude, address, timestamp FROM location WHERE timestamp <= ? AND "
                             "timestamp >= ? ORDER BY ABS(? - timestamp) LIMIT 1",
                             (timestamp + offset, timestamp - offset, timestamp,))
        result = self._cursor.fetchall()
        if len(result) == 1:
            location = result[0]
            lat, lon, add, time = location
            if not add:
                try:
                    from geopy.geocoders import Nominatim
                    geolocator = Nominatim()
                    address = geolocator.reverse(str(lat) + ", " + str(lon), exactly_one=True).address
                    if address:
                        location = lat, lon, address, time
                        with self._connection:
                            self._connection.execute("UPDATE location SET address=? WHERE timestamp = ?",
                                                     (address, time))
                except Exception as e:
                    print e
                    pass

            return location

        return None

    def add_location(self, location):
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO location (timestamp, latitude, longitude, altitude)VALUES(?, ?, ?, ?) ",
                location)

    def _get_file_already_uploaded_dict(self, md5sum=None, file_name=None):

        if md5sum is None and file_name is None:
            return None, None
        elif md5sum is not None:
            self._cursor.execute("SELECT photo_id, upload_date FROM uploaded WHERE md5sum = ? AND photo_id IS NOT NULL", (md5sum, ))
        elif file_name is not None:
            self._cursor.execute("SELECT photo_id, upload_date FROM uploaded WHERE file_name like ? AND photo_id IS NOT NULL", ("%" + file_name, ))

        result = self._cursor.fetchall()
        if len(result) == 1:
            pid, udate = result[0]
            return utils.csl2dict(pid), utils.csl2dict(udate)
        return None, None

    def get_photo_id_from_file_name(self, file_name, service_name):
        d, u = self._get_file_already_uploaded_dict(file_name=file_name)
        if d is not None:
            try:
                return d[service_name]
            except KeyError:
                return 0

        return 0

    def file_already_uploaded(self, service_name, md5sum):
        if service_name is None:
            raise ValueError("service_name is not set")
        d, u = self._get_file_already_uploaded_dict(md5sum)
        if d is not None:
            try:
                return d[service_name] is not None
            except KeyError:
                return False

        return False

    def set_file_uploaded(self, file_name, service_name, photo_id, md5sum):
        if service_name is None:
            raise ValueError("service_name is not set")
        d, u = self._get_file_already_uploaded_dict(md5sum)
        date = datetime.datetime.now().isoformat()
        try:
            if d is not None:
                d[service_name] = photo_id
                u[service_name] = date
                ids = utils.dict2csl(d)
                dates = utils.dict2csl(u)
                with self._connection:
                    self._connection.execute(
                        "UPDATE uploaded SET photo_id = ?, upload_date = ? WHERE md5sum = ?",
                        (ids, dates, md5sum))
            else:
                with self._connection:
                    self._connection.execute(
                        "INSERT OR IGNORE INTO uploaded (file_name, photo_id, md5sum, upload_date)VALUES(?, ?, ?, ?) ",
                        (file_name, service_name + "=" + photo_id, md5sum, service_name + "=" + date,))
        except Exception, e:
            print "Error:", e