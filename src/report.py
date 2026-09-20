if __package__:
    from .alert_engine import AlertEngine
    from .analyzer import MarketAnalyzer
    from .decision_engine import DecisionEngine
    from .market_intelligence import MarketIntelligence
    from .quant_score import QuantScore
    from .risk_engine import RiskEngine
    from .signal_engine import SignalEngine
    from .signal_history import SignalHistory
else:  # pragma: no cover - exercised by subprocess import compatibility test.
    from alert_engine import AlertEngine
    from analyzer import MarketAnalyzer
    from decision_engine import DecisionEngine
    from market_intelligence import MarketIntelligence
    from quant_score import QuantScore
    from risk_engine import RiskEngine
    from signal_engine import SignalEngine
    from signal_history import SignalHistory



class MarketReport:


    def __init__(self, signal_history=None):

        self.analyzer = MarketAnalyzer()

        self.intelligence = MarketIntelligence()

        self.alert_engine = AlertEngine()

        self.signal_engine = SignalEngine()

        self.risk_engine = RiskEngine()

        self.decision_engine = DecisionEngine()

        self.quant_score = QuantScore()

        self.signal_history = (
            signal_history
            if signal_history is not None
            else SignalHistory()
        )



    def generate(
        self,
        symbol: str,
        analysis: dict,
        profile: dict,
        auto_save: bool = False,
    ):
        mentor = self.analyzer.generate_summary(analysis)
        intelligence = self.intelligence.evaluate(analysis)
        alerts = self.alert_engine.check(analysis, profile)
        signal = self.signal_engine.evaluate(analysis, profile)
        risk = self.risk_engine.evaluate(analysis, profile)
        decision = self.decision_engine.evaluate(signal, risk, intelligence)
        quant_score = self.quant_score.calculate(analysis, signal, risk)

        # Optional persistence, disabled by default for analytical purity
        if auto_save and self.signal_history is not None:
            self.signal_history.save(
                symbol,
                analysis,
                decision,
                quant_score,
                risk,
                signal,
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
            "trend_analysis": intelligence["trend_analysis"],
            # Alertas
            "alerts": alerts,
            # Señal
            "signal": signal,
            # Riesgo
            "risk_engine": risk,
            # Decisión
            "decision": decision,
            # Quant Score
            "quant_score": quant_score,
        }

        return report
