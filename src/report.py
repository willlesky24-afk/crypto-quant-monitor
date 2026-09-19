from analyzer import MarketAnalyzer
from market_intelligence import MarketIntelligence
from alert_engine import AlertEngine


class MarketReport:


    def __init__(self):

        self.analyzer = MarketAnalyzer()

        self.intelligence = MarketIntelligence()

        self.alert_engine = AlertEngine()



    def generate(
        self,
        symbol: str,
        analysis: dict,
        profile: dict
    ):


        mentor = self.analyzer.generate_summary(
            analysis
        )


        intelligence = self.intelligence.evaluate(
            analysis
        )


        alerts = self.alert_engine.check(
            analysis,
            profile
        )


        report = {


            "symbol": symbol,


            "price": analysis["price"],


            "trend": analysis["trend"],


            "momentum": analysis["momentum"],


            "volatility": analysis["volatility"],


            "volume": analysis["volume"],


            "score": analysis["score"],


            "profile": analysis["profile"],



            # ==========================
            # Mentor
            # ==========================

            "summary": mentor["summary"],

            "conclusion": mentor["conclusion"],



            # ==========================
            # Intelligence
            # ==========================

            "state": intelligence["state"],

            "risk": intelligence["risk"],

            "risk_reason": intelligence["risk_reason"],

            "trend_analysis": intelligence["trend_analysis"],



            # ==========================
            # Alerts
            # ==========================

            "alerts": alerts

        }


        return report

