import folium, os

import folium.map
from app.common.config import *

def prepare_map():
    # Define the coordinates for Shanghai
    coords = [31.2304, 121.4737]

    # Create a map centered around Shanghai with a specific map ID
    map_id = 'map'
    map = folium.Map(location=coords, zoom_start=12, control_scale=True)

    # Add a custom div with the specific `id` for the map and include QWebChannel script
    map.get_root().html.add_child(folium.Element(f'''
        <div id="{map_id}" style="width: 100%; height: 100%;"></div>
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    '''))

    # Adjust the map rendering to use the custom div
    map.get_root().render()

    # Save the map to an HTML file
    map.save(map_html_path)
    return map

print(folium.Map(path=os.path.abspath(map_html_path)).get_name())