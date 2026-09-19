from analyzer import MarketAnalyzer


class MarketReport:


    def __init__(self):
        self.analyzer = MarketAnalyzer()


    def generate(
        self,
        symbol: str,
        analysis: dict
    ):

        mentor = self.analyzer.generate_summary(
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

            "summary": mentor["summary"],

            "conclusion": mentor["conclusion"]

        }


        return report