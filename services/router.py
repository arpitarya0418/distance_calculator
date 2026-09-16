import requests
from config import CAR_ROUTER_URL,BIKE_ROUTER_URL,FOOT_ROUTER_URL,REQUEST_TIMEOUT

ROUTERS={
    "Car":(CAR_ROUTER_URL,"driving"),
    "Bicycle":(BIKE_ROUTER_URL,"driving"),
    "Walking":(FOOT_ROUTER_URL,"driving")
}

def calculate_route(source_lat,source_lon,destination_lat,destination_lon,mode):
    if mode not in ROUTERS:
        raise ValueError(f"Unsupported mode: {mode}")

    base_url,profile=ROUTERS[mode]

    coordinates=f"{source_lon},{source_lat};{destination_lon},{destination_lat}"

    url=f"{base_url}/route/v1/{profile}/{coordinates}"

    params={
        "overview":"false",
        "steps":"false",
        "alternatives":"false"
    }

    response=requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent":"DistanceCalculator/1.0"}
    )

    response.raise_for_status()

    data=response.json()

    if data.get("code")!="Ok":
        raise RuntimeError(data.get("message","No route found."))

    routes=data.get("routes",[])

    if not routes:
        raise RuntimeError("No route found.")

    route=routes[0]

    return {
        "distance_km":route["distance"]/1000,
        "duration_minutes":route["duration"]/60
    }

def validate_results(results):
    available=[r for r in results if not r.get("error")]

    if len(available)<2:
        return

    for i in range(len(available)):
        for j in range(i+1,len(available)):
            a=available[i]
            b=available[j]

            if (
                abs(a["distance_km"]-b["distance_km"])<0.01
                and abs(a["duration_minutes"]-b["duration_minutes"])<0.01
            ):
                b["error"]="Suspiciously identical route result."