from datetime import datetime


def format_end_reason(reason):
    mapping = {
        "won": "mot trouve",
        "attempts": "plus d'essais",
        "time": "temps ecoule",
    }
    return mapping.get(reason, str(reason))


def format_played_at(value):
    if not value:
        return "-"

    try:
        parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        return str(value)
    return parsed.strftime("%d/%m %H:%M")
