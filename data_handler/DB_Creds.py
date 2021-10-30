import json


class DB_Creds:
    username, password, dsn = None, None, None

    def __init__(self):
        with open('db_connection_info.json') as in_fh:
            info_file = json.load(in_fh)
            self.username = info_file['db_connection']['username']
            self.password = info_file['db_connection']['password']
            self.dsn = info_file['db_connection']['dsn']
