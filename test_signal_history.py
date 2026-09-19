from src.signal_history import SignalHistory



analysis = {


    "price": 81000,

    "trend": "Alcista"

}



decision = {


    "decision": "🟡 Esperar confirmación"

}



quant_score = {


    "score": 95

}



risk = {


    "level": "Medio"

}



history = SignalHistory()



saved = history.save(

    "BTCUSDT",

    analysis,

    decision,

    quant_score,

    risk

)


print("SEÑAL GUARDADA:")

print(saved)



print("\nHISTORIAL:")

records = history.get_history()

print("TOTAL REGISTROS:")
print(len(records))

print(records)