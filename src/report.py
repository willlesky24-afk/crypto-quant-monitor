from analyzer import MarketAnalyzer
from market_intelligence import MarketIntelligence
from alert_engine import AlertEngine
from signal_engine import SignalEngine
from risk_engine import RiskEngine
from decision_engine import DecisionEngine


class MarketReport:


    def __init__(self):

        self.analyzer = MarketAnalyzer()

        self.intelligence = MarketIntelligence()

        self.alert_engine = AlertEngine()

        self.signal_engine = SignalEngine()

        self.risk_engine = RiskEngine()

        self.decision_engine = DecisionEngine()



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


        signal = self.signal_engine.evaluate(
            analysis,
            profile
        )


        risk = self.risk_engine.evaluate(
            analysis,
            profile
        )


        decision = self.decision_engine.evaluate(
            signal,
            risk,
            intelligence
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

            "alerts": alerts,



            # ==========================
            # Signal
            # ==========================

            "signal": signal,



            # ==========================
            # Risk
            # ==========================

            "risk_engine": risk,



            # ==========================
            # Decision
            # ==========================

            "decision": decision

        }


        return report

