import sqlite3


DATABASE_NAME = "signals.db"



class Database:


    def __init__(self):

        self.connection = sqlite3.connect(
            DATABASE_NAME
        )


        self.create_tables()



    def create_tables(self):

        cursor = self.connection.cursor()


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT,

                symbol TEXT,

                price REAL,

                trend TEXT,

                signal TEXT,

                decision TEXT,

                quant_score INTEGER,

                risk TEXT

            )
            """
        )


        self.connection.commit()



    def insert_signal(
        self,
        data
    ):

        cursor = self.connection.cursor()


        cursor.execute(
            """
            INSERT INTO signals (

                timestamp,
                symbol,
                price,
                trend,
                signal,
                decision,
                quant_score,
                risk

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            """,
            (

                data["timestamp"],

                data["symbol"],

                data["price"],

                data["trend"],

                data["signal"],

                data["decision"],

                data["quant_score"],

                data["risk"]

            )
        )


        self.connection.commit()



    def get_recent_signals(
        self,
        limit=10
    ):

        cursor = self.connection.cursor()


        cursor.execute(
            """
            SELECT *

            FROM signals

            ORDER BY id DESC

            LIMIT ?

            """,
            (limit,)
        )


        return cursor.fetchall()