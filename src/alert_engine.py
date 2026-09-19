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

        if volume == "Superior al promedio":

            alerts.append({

                "type": "VOLUME_CONFIRMATION",

                "message":
                "El volumen acompaña el movimiento."

            })


        return alerts