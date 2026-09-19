try:
    from database import Database
except ModuleNotFoundError:
    from src.database import Database
from datetime import datetime



class SignalHistory:


    def __init__(self):

        self.db = Database()



    def save(
        self,
        symbol,
        analysis,
        decision,
        quant_score,
        risk
    ):


        data = {


            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),


            "symbol": symbol,


            "price": analysis["price"],


            "trend": analysis["trend"],


            "signal": decision["decision"],


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