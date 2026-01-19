import openrouteservice
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from haversine import haversine, Unit

from config import admin_secret_key, radius, api_key

geolocator = Nominatim(user_agent=f"car_sharing_bot_{admin_secret_key}")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)


def get_address(la: float, lo: float, language: str = None):
    location = reverse((la, lo), language=language)
    return location.address if location else None


def percentage_route_overlap(driver_route, passenger_route, tolerance_m=100):
    overlap = 0
    for lon, lat in passenger_route:
        for dlon, dlat in driver_route:
            dist = haversine((lat, lon), (dlat, dlon), unit=Unit.METERS)
            if dist < tolerance_m:
                overlap += 1
                break
    if not passenger_route:
        return 0
    return overlap / len(passenger_route)


def can_driver_pick_passenger(
        driver_coordinates,
        passenger_coordinates,
        overlap_threshold=0.15,
):
    d_start, d_end = driver_coordinates
    p_start, p_end = passenger_coordinates
    if (abs(d_start[0] - p_start[0]) < 0.0005 and abs(d_start[1] - p_start[1]) < 0.0005
            and abs(d_end[0] - p_end[0]) < 0.0005 and abs(d_end[1] - p_end[1]) < 0.0005):
        return True, 1.0  # координаты старта и финиша совпадают — точно по пути
    client = openrouteservice.Client(key=api_key)
    route_driver = client.directions([d_start[::-1], d_end[::-1]], profile='driving-car', format_out='geojson')
    route_passenger = client.directions([p_start[::-1], p_end[::-1]], profile='driving-car', format_out='geojson')
    driver_coords = route_driver['features'][0]['geometry']['coordinates']
    passenger_coords = route_passenger['features'][0]['geometry']['coordinates']
    perc = percentage_route_overlap(driver_coords, passenger_coords, tolerance_m=radius)
    return perc >= overlap_threshold, perc
