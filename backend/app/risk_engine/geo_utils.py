import math

def validate_coordinates(lat, lon):
    """
    Validates GPS coordinates and returns their status.
    Returns: 'VALID', 'INVALID', or 'UNAVAILABLE'
    """
    if lat is None or lon is None:
        return 'UNAVAILABLE'
    
    try:
        lat_float = float(lat)
        lon_float = float(lon)
    except (ValueError, TypeError):
        return 'INVALID'
        
    # Check for placeholder 0,0 which is likely invalid/placeholder in India
    if lat_float == 0.0 and lon_float == 0.0:
        return 'INVALID'
        
    if not (-90 <= lat_float <= 90):
        return 'INVALID'
        
    if not (-180 <= lon_float <= 180):
        return 'INVALID'
        
    return 'VALID'

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points 
    on the Earth surface using the Haversine formula.
    Returns distance in kilometers.
    """
    if validate_coordinates(lat1, lon1) != 'VALID' or validate_coordinates(lat2, lon2) != 'VALID':
        return None
        
    # Earth radius in kilometers
    R = 6371.0
    
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance
