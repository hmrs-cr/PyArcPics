import os
import sqlite3
import datetime

last_location_time_key = "last_location_time"


class BuffData:
    def __init__(self):
        buff_folder = os.path.join(os.environ['HOME'], '.hmsoft')
        if not os.path.isdir(buff_folder):
            os.makedirs(buff_folder)

        db_filename = os.path.join(buff_folder, 'picture-data.db')
        self._connection = sqlite3.connect(db_filename, timeout=30.0)
        self._connection.text_factory = str
        self._cursor = self._connection.cursor()
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS uploaded (file_name TEXT, photo_id TEXT UNIQUE, md5sum TEXT UNIQUE, "
            "upload_date TEXT )")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS location (timestamp INTEGER PRIMARY KEY, latitude REAL, longitude REAL, "
            "altitude REAL )")
        self._connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    def set_setting(self, key, value):
        with self._connection:
            self._connection.execute("INSERT OR REPLACE INTO settings (key, value) VALUES(?, ?)",
                                     (str(key), str(value)))

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
                                         (last_location_time_key, str(last_time)))

        return c

    def get_location_from_timestamp(self, timestamp, offset=None):
        if offset is None:
            offset = 1000 * 60 * 15
        self._cursor.execute("SELECT latitude, longitude FROM location WHERE timestamp <= ? AND "
                             "timestamp >= ? ORDER BY ABS(? - timestamp) LIMIT 1",
                             (timestamp + offset, timestamp - offset, timestamp,))
        result = self._cursor.fetchall()
        if len(result) == 1:
            return result[0]

        return None

    def add_location(self, location):
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO location (timestamp, latitude, longitude, altitude)VALUES(?, ?, ?, ?) ",
                location)

    def file_already_uploaded(self, md5sum):
        self._cursor.execute("SELECT photo_id FROM uploaded WHERE md5sum = ? AND photo_id <> ?", (md5sum, "0",))
        uploaded = len(self._cursor.fetchall()) > 0
        return uploaded

    def set_file_uploaded(self, file_name, photo_id, md5sum):
        date = datetime.datetime.now().isoformat()
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO uploaded (file_name, photo_id, md5sum, upload_date)VALUES(?, ?, ?, ?) ",
                (str(file_name), str(photo_id), str(md5sum), str(date),))