import mysql.connector as mysql
from mysql.connector import Error
from configparser import ConfigParser


class Database(object):

        def __init__(self, connection_config=None):

            if connection_config is None:
                connection_config = read_db_config()

            self.host = connection_config["host"]
            self.database_name = connection_config["database"]
            self.user = connection_config["user"]
            self.password = connection_config["password"]

            self.connection = self.connect()

        def connect(self):
            try:
                connection = mysql.Connect(
                    host=self.host,
                    database=self.database_name,
                    user=self.user,
                    password=self.password,
                )

                if connection.is_connected():
                    return connection

            except Error as e:
                print(e)

        def disconnect(self):
            if self.connection is not None:
                return self.connection.close()

        def get_item(self, sql: str):
            if not self.connection.is_connected():
                return {}

            cursor = self.connection.cursor()
            cursor.execute(sql)
            return cursor.fetchone()

        def get_all(self, sql: str):
            if not self.connection.is_connected():
                return {}

            cursor = self.connection.cursor()
            cursor.execute(sql)
            return cursor.fetchall()

        def __del__(self):
            self.disconnect()


def read_db_config(filename='config.ini', section='mysql'):
    """ Read database configuration file and return a dictionary object
    :param filename: name of the configuration file
    :param section: section of database configuration
    :return: a dictionary of database parameters
    """
    # create parser and read ini configuration file
    parser = ConfigParser()
    parser.read(filename)

    # get section, default to mysql
    config = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            config[item[0]] = item[1]
    else:
        raise Exception('{0} not found in the {1} file'.format(section, filename))

    return config


def connect():
    db = Database()

    return db
