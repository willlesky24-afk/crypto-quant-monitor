try:
    from .database import Database
except ImportError:
    from database import Database
from datetime import datetime


class SignalHistory:


    def __init__(
        self,
        database=None,
        database_name=None
    ):

        if database is not None and database_name is not None:

            raise ValueError(
                "Use database or database_name, not both."
            )


        if isinstance(database, Database):

            self.db = database

        else:

            path = (
                database
                if database is not None
                else database_name
            )

            self.db = (
                Database(path)
                if path is not None
                else Database()
            )



    def save(
        self,
        symbol,
        analysis,
        decision,
        quant_score,
        risk,
        signal=None
    ):


        data = {


            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),


            "symbol": symbol,


            "price": analysis["price"],


            "trend": analysis["trend"],


            "signal": (
                signal["state"]
                if signal is not None
                else decision["decision"]
            ),


            "decision": decision["decision"],


            "quant_score": quant_score["score"],


            "risk": risk["level"]

        }


        self.db.insert_signal(
            data
        )


        return data



    def get_history(
        self,
        limit=10
    ):


        return self.db.get_recent_signals(
            limit
        )



    def close(self):

        self.db.close()



    def __enter__(self):

        return self



    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        self.close()

        return False
