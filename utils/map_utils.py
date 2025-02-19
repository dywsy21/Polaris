import xml.etree.ElementTree as ET
import math
import sqlite3

# Function to calculate tile coordinates from latitude and longitude
def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    # print(xtile, ytile)
    return (xtile, ytile)

# Function to calculate visible tiles based on map bounds
def calculate_visible_tiles(bounds, zoom):
    lat_min, lon_min = bounds[0]
    lat_max, lon_max = bounds[1]
    tile_min = lat_lon_to_tile(lat_min, lon_min, zoom)
    tile_max = lat_lon_to_tile(lat_max, lon_max, zoom)
    x_min = min(tile_min[0], tile_max[0])
    x_max = max(tile_min[0], tile_max[0])
    y_min = min(tile_min[1], tile_max[1])
    y_max = max(tile_min[1], tile_max[1])
    visible_tiles = set()
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            visible_tiles.add((x, y))
    # print(f"Bounds: {bounds}, Zoom: {zoom}, Visible Tiles: {visible_tiles}")  # Debug statement
    return visible_tiles

# Function to convert tile coordinates back to latitude and longitude
def tile_to_lat_lon(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat = math.degrees(lat_rad)
    return (lat, lon)

# Function to query nodes within visible tiles from the database
def query_nodes_from_db(db_path, zoom, visible_tiles):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    nodes = []
    for tile in visible_tiles:
        xtile, ytile = tile
        lat_min, lon_min = tile_to_lat_lon(xtile, ytile + 1, zoom)
        lat_max, lon_max = tile_to_lat_lon(xtile + 1, ytile, zoom)
        
        # Ensure lat_min <= lat_max
        if lat_min > lat_max:
            lat_min, lat_max = lat_max, lat_min
        if lon_min > lon_max:
            lon_min, lon_max = lon_max, lon_min

        # Calculate approximation rate based on zoom level
        approximation_rate = {
            20: 0.0000001,
            19: 0.0000001,
            18: 0.00000025,
            17: 0.00000025,
            16: 0.000001,
            15: 0.000001,
            14: 0.000025,
            13: 0.000025,
            12: 0.00015,
            11: 0.00015,
            10: 0.00045,
            9: 0.00045,
            8: 0.00225,
            7: 0.00225,
            6: 0.009,
            5: 0.009,
            4: 0.036,
            3: 0.036,
            2: 0.144,
            1: 0.144,
        }.get(zoom, 0.576)

        cursor.execute(f"""
            SELECT ROUND(lat / {approximation_rate}) * {approximation_rate} AS lat_approx,
                   ROUND(lon / {approximation_rate}) * {approximation_rate} AS lon_approx
            FROM nodes
            WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            GROUP BY lat_approx, lon_approx
        """, (lat_min, lat_max, lon_min, lon_max))
        
        result = cursor.fetchall()
        print(f"Querying tile {tile}: found {len(result)} nodes")  # Debug statement
        nodes.extend(result)
    
    conn.close()
    
    # Limit the number of nodes to ensure even distribution
    if len(nodes) > 100:
        step = len(nodes) // 50
        nodes = nodes[::step]
    
    return nodes

