"""Canonical internal labels used by the v1.6 analysis pipeline.

The values intentionally preserve the public Spanish labels consumed by the
Streamlit UI and stored reports. Centralizing them prevents scoring and
classification rules from silently drifting because of spelling differences.
"""

# Trend
TREND_BULLISH = "Alcista"
TREND_BEARISH = "Bajista"
TREND_SIDEWAYS = "Lateral"

# Momentum
MOMENTUM_EXTENDED = "Fuerte pero extendido"
MOMENTUM_POSITIVE = "Positivo"
MOMENTUM_WEAK = "Débil"
MOMENTUM_BEARISH_PRESSURE = "Presión bajista"

# Volatility
VOLATILITY_HIGH = "Alta"
VOLATILITY_MODERATE = "Moderada"
VOLATILITY_LOW = "Baja"

# Volume
VOLUME_ABOVE_AVERAGE = "Superior al promedio"
VOLUME_BELOW_AVERAGE = "Inferior al promedio"

# Volume profile position
PROFILE_NO_DATA = "Sin datos"
PROFILE_ABOVE_VALUE_AREA = "Por encima del área de valor"
PROFILE_BELOW_VALUE_AREA = "Por debajo del área de valor"
PROFILE_INSIDE_VALUE_AREA = "Dentro del área de valor"

# Risk
RISK_HIGH = "Alto"
RISK_MEDIUM = "Medio"
RISK_LOW = "Bajo"

# Signal states
SIGNAL_BULLISH = "🟢 Señal alcista"
SIGNAL_MODERATE = "🟡 Señal moderada"
SIGNAL_WEAK = "🔴 Señal débil"

# Decisions
DECISION_FAVORABLE = "🟢 Condición favorable"
DECISION_WAIT_CONFIRMATION = "🟡 Esperar confirmación"
DECISION_WEAK_CONTEXT = "🔴 Contexto débil"

# Intelligence states
INTELLIGENCE_HIGH_CONFLUENCE = "🟢 Alta confluencia"
INTELLIGENCE_INTERESTING = "🟡 Contexto interesante"
INTELLIGENCE_WEAK = "🔴 Contexto débil"
