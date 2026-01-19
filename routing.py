import openrouteservice
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from haversine import haversine, Unit

from config import admin_secret_key, radius, api_key

geolocator = Nominatim(user_agent=f"car_sharing_bot_{admin_secret_key}")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)


def get_address(la: float, lo: float, language: str = None):
    """
    Resolves a human-readable address from geographic coordinates.

    Uses the Nominatim reverse geocoding service with rate limiting to
    prevent exceeding API limits.

    :param la: Latitude value.
    :param lo: Longitude value.
    :param language: Optional language code for localized address output.
    :return: Address string if found, otherwise None.
    """
    location = reverse((la, lo), language=language)
    return location.address if location else None


def percentage_route_overlap(driver_route: list[float], passenger_route: list[float], tolerance_m: int = 100):
    """
    Calculates the percentage of overlap between two routes.

    Compares each point in the passenger route to the driver route and
    counts how many points fall within a specified distance tolerance.

    :param driver_route: List of (longitude, latitude) points for the driver's route.
    :param passenger_route: List of (longitude, latitude) points for the passenger's route.
    :param tolerance_m: Distance tolerance in meters to consider a point as overlapping.
    :return: A float between 0 and 1 representing the overlap ratio.
    """
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
        driver_coordinates: list[float],
        passenger_coordinates: list[float],
        overlap_threshold: float | int = 0.15,
):
    """
    Determines whether a driver can reasonably pick up a passenger.

    First checks if the start and end coordinates are nearly identical.
    If not, it fetches driving routes from OpenRouteService and computes
    how much of the passenger's route overlaps with the driver's route.

    :param driver_coordinates: Tuple of (start_coord, end_coord) for the driver.
                               Each coord is (latitude, longitude).
    :param passenger_coordinates: Tuple of (start_coord, end_coord) for the passenger.
                                   Each coord is (latitude, longitude).
    :param overlap_threshold: Minimum required overlap ratio (0–1) to allow pickup.
    :return: Tuple (can_pick: bool, overlap_ratio: float).
    """
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
