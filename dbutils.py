import datetime
import sqlite3
import utils


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
commit_transaction_sql = "COMMIT;"

insert_sql = "INSERT OR REPLACE INTO pictures (name, checksum, size, timestamp, addeondtimestamp) VALUES (?, ?, ?, ?, unixepoch());"

def adapt_datetime_epoch(val):
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())

def convert_timestamp(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val))

sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)
sqlite3.register_converter("timestamp", convert_timestamp)

def insert_picture_record(cur, name, checksum, size, timestamp):
    return cur.execute(insert_sql, (name, checksum, size, timestamp))

def validate_picture_record(cur, name, checksum, size, timestamp):
    res = cur.execute("SELECT checksum, size, timestamp FROM pictures WHERE name = ?", (name,))
    result = res.fetchone()
    if (result is None):
        utils.error(f'INVALID: {name} cheksum record missing', False)
    elif (result[0] != checksum):
        utils.error(f'INVALID: {name} CHECKSUM: {checksum} != {result[0]}', False)
    elif (result[1] != size):
        utils.error(f'INVALID: {name} SIZE: {size} != {result[1]}', False)
    elif (result[2] != int(timestamp.timestamp())):
        utils.error(f'INVALID: {name} TIMESTAMP: {timestamp} != {datetime.datetime.fromtimestamp(int(result[2]))}', False)
    else:
        print(f'VALID: {name}')

class CkSumConnection:
    def __init__(self, con, name) -> None:
        self.con = con
        self.name = name

    def cursor(self):
        return self.con.cursor()
    
    def close(self):
        return self.con.close()

def start_db_transaction(databasename):
    con = sqlite3.connect(databasename, isolation_level=None)
    cur = con.cursor()
    cur.execute(begin_transaction_sql)
    cur.execute(create_table_sql)
    print(f'OPENED: {databasename} connection')
    return CkSumConnection(con, databasename)

def close_db_transaction(con):
    cur = con.cursor()
    cur.execute(commit_transaction_sql)
    con.close();
    print(f'CLOSED: {con.name} connection')


