from data_handler.DB_Creds import DB_Creds
import cx_Oracle


class DB_Connection_Provider:
    creds = None

    def __init__(self):
        super()
        self.creds = DB_Creds()

    def get_db_connection(self):
        try:
            conn = cx_Oracle.connect(self.creds.username, self.creds.password, self.creds.dsn)
            print("**********  Database Connected Successfully  ********** ")
            return conn
        except cx_Oracle.DatabaseError as de:
            print(f"{de}\n")


if __name__ == '__main__':
    connector = DB_Connection_Provider()
    conn = connector.get_db_connection()
    cs1 = conn.cursor()
    cs2 = conn.cursor()
    rs1 = cs1.execute("Select * from sales PARTITION (P1)")
    rs2 = cs2.execute("Select * from sales PARTITION (P2)")
    print('result')
