def format_distance(distance_km):
    if distance_km < 1:
        return f"{distance_km * 1000:.0f} m"

    return f"{distance_km:.1f} km"

def format_duration(minutes):
    minutes=round(minutes)

    hours=minutes // 60
    remaining_minutes=minutes % 60

    if hours == 0:
        return f"{remaining_minutes} min"

    if remaining_minutes == 0:
        return f"{hours} hr"

    return f"{hours} hr {remaining_minutes} min"