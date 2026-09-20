try:
    from .constants import VOLUME_ABOVE_AVERAGE
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import VOLUME_ABOVE_AVERAGE


class AlertEngine:


    def check(self, analysis, profile):


        alerts = []


        price = analysis["price"]

        rsi = analysis["rsi"]

        volume = analysis["volume"]



        # Ruptura VAH

        if price > profile["vah"]:

            alerts.append({

                "type": "BREAKOUT_VAH",

                "message":
                "Precio por encima del área de valor superior (VAH)."

            })



        # Pérdida VAL

        if price < profile["val"]:

            alerts.append({

                "type": "BREAKDOWN_VAL",

                "message":
                "Precio por debajo del área de valor inferior (VAL)."

            })



        # RSI extremo

        if rsi >= 75:

            alerts.append({

                "type": "RSI_OVERBOUGHT",

                "message":
                "RSI elevado, movimiento extendido."

            })


        elif rsi <= 25:

            alerts.append({

                "type": "RSI_OVERSOLD",

                "message":
                "RSI bajo, posible agotamiento vendedor."

            })



        # Volumen

        if volume == VOLUME_ABOVE_AVERAGE:

            alerts.append({

                "type": "VOLUME_CONFIRMATION",

                "message":
                "El volumen acompaña el movimiento."

            })


        return alerts
