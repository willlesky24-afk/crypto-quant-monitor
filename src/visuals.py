def score_to_confidence(score):

    if score >= 5:
        return {
            "label": "Alta",
            "emoji": "🟢",
            "percent": 90
        }

    elif score >= 3:
        return {
            "label": "Moderada",
            "emoji": "🟡",
            "percent": 60
        }

    elif score >= 1:
        return {
            "label": "Baja",
            "emoji": "🟠",
            "percent": 40
        }

    else:
        return {
            "label": "Débil",
            "emoji": "🔴",
            "percent": 20
        }