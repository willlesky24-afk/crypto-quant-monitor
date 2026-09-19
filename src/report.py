from src.analyzer import MarketAnalyzer
from src.market_intelligence import MarketIntelligence

class MarketReport:


    def __init__(self):

        self.analyzer = MarketAnalyzer()

        self.intelligence = MarketIntelligence()



    def generate(
        self,
        symbol: str,
        analysis: dict
    ):


        mentor = self.analyzer.generate_summary(
            analysis
        )


        intelligence = self.intelligence.evaluate(
            analysis
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


            # Mentor

            "summary": mentor["summary"],

            "conclusion": mentor["conclusion"],


            # Intelligence

            "state": intelligence["state"],

            "risk": intelligence["risk"],

            "risk_reason": intelligence["risk_reason"],

            "trend_analysis": intelligence["trend_analysis"]

        }


        return report

