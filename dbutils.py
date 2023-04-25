import datetime
import sqlite3
import utils
import time
import os


create_table_sql = """
CREATE TABLE IF NOT EXISTS pictures (
    name             TEXT (128) PRIMARY KEY NOT NULL,
    checksum         INTEGER KEY NOT NULL,
    size             INTEGER KEY NOT NULL,
    timestamp        INTEGER KEY NOT NULL,
    addeondtimestamp INTEGER KEY NOT NULL
) WITHOUT ROWID;
"""

begin_transaction_sql = "BEGIN TRANSACTION;"
begin_exclusive_transaction_sql = 'BEGIN EXCLUSIVE;'
commit_transaction_sql = "COMMIT;"

insert_sql = "INSERT OR REPLACE INTO pictures (name, checksum, size, timestamp, addeondtimestamp) VALUES (?, ?, ?, ?, ?);"
select_sql = "SELECT checksum, size, timestamp FROM pictures WHERE name = ?"
find_duplicate_sql = "SELECT name FROM pictures WHERE checksum = ? AND size = ?"

def _adapt_datetime_epoch(val):
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())

def _convert_timestamp(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val))

sqlite3.register_adapter(datetime.datetime, _adapt_datetime_epoch)
sqlite3.register_converter("timestamp", _convert_timestamp)

def _insert_picture_record(cur, name, checksum, size, timestamp):
    return cur.execute(insert_sql, (name, checksum, size, timestamp, int(time.time())))

def _is_picture_valid(cur, name, checksum, size, timestamp):
    res = cur.execute(select_sql, (name,))
    result = res.fetchone()
    if (result is None):
        utils.error(f'INVALID: {name} cheksum record missing', False)
        return False
    elif (result[0] != checksum):
        utils.error(f'INVALID: {name} CHECKSUM: {checksum} != {result[0]}', False)
        return False
    elif (result[1] != size):
        utils.error(f'INVALID: {name} SIZE: {size} != {result[1]}', False)
        return False
    elif (result[2] != int(timestamp.timestamp())):
        utils.error(f'INVALID: {name} TIMESTAMP: {timestamp} != {datetime.datetime.fromtimestamp(int(result[2]))}', False)
        return False
    else:
        print(f'VALID: {name}')
        return True
    
def _already_exists(cur, checksum, size):
    res = cur.execute(find_duplicate_sql, (checksum,size))
    result = res.fetchone()
    return result[0] if result is not None else ""

class CkSumConnection:
    def __init__(self, name) -> None:
        self.name = name
        try:
            self.con = sqlite3.connect(name, isolation_level=None)        
            cur =  self.con.cursor()
            cur.execute(begin_exclusive_transaction_sql) # Just to test if the database is locked.
            cur.execute(commit_transaction_sql)
            cur.execute(begin_transaction_sql)
            cur.execute(create_table_sql)
            print(f'OPENED: {name} connection')
        except sqlite3.OperationalError as e:            
            utils.error(e)
            os._exit(1)
    
    def close(self):
        return self.con.close()
    
    def insert_picture_record(self, name, checksum, size, timestamp):
        _insert_picture_record(self.con.cursor(), name, checksum, size, timestamp)

    def is_picture_valid(self, name, checksum, size, timestamp):
        return _is_picture_valid(self.con.cursor(), name, checksum, size, timestamp)
    
    def picture_already_exists(self, checksum, size):
        return _already_exists(self.con.cursor(), checksum, size)

def start_db_transaction(databasename):
    return CkSumConnection(databasename)

def close_db_transaction(con):
    cur = con.con.cursor()
    cur.execute(commit_transaction_sql)
    con.close();
    print(f'CLOSED: {con.name} connection')


