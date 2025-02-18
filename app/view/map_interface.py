# coding: utf-8
from multiprocessing import process
from PyQt5.QtCore import * # type: ignore
from PyQt5.QtGui import * # type: ignore
from PyQt5.QtWidgets import * # type: ignore
from inquirer import Checkbox
from numpy import signbit
from qfluentwidgets import * # type: ignore
from PyQt5.QtWebEngineWidgets import * # type: ignore
from PyQt5.QtWebChannel import * # type: ignore
from ..common.config import *
from ..common.style_sheet import StyleSheet
from ..common.icon import Icon
import os, shutil
import subprocess
from ..common.signal_bus import signalBus
import math
from map_utils import *
from ..common.config import *
import concurrent.futures
import json  # Add this import
from qframelesswindow.webengine import FramelessWebEngineView

class MapInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mapInterface")
        self.begin_collecting_output = False
        self.pedestrain_enabled = True
        self.riding_enabled = True
        self.driving_enabled = True
        self.pubTransport_enabled = True
        self.enable_time_first_mode = False
        self.selectedAlgorithm = None  # Add this line
        self.algorithmWarningShown = False  # Add this line
        # self.on_start_line_edit_changed = pyqtBoundSignal()
        # self.on_end_line_edit_changed = pyqtBoundSignal()
        # self.on_checkbox_state_changed = pyqtBoundSignal()
        self.thread_pool = QThreadPool()
        self.namesDic = {}
        signalBus.finishRenderingTile.connect(self.on_tiles_fetched)
        self.middlePoints = []  # Add this line
        self.sorted_middle_points = []  # Add this line
        self.max_distance = 0.01  # Max distance limit for removing nodes
        self.custom_tile_layer_ids = []  # Store layer IDs instead of layer objects
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)  # Add this line
        self.currentLayerType = "default"  # Store the current layer type
        self.drawnPaths = []  # Add this line to store drawn paths
        self.backend_output_buffer = []  # Add this line to store backend output

        signalBus.backendOutputReceived.connect(self.handle_backend_response)  # Connect the signal to the handler
        signalBus.backendGraphLoaded.connect(self.handle_graph_loaded)
        signalBus.backendNoPathFound.connect(self.handle_no_path_found)
        signalBus.backendPathFound.connect(self.handle_path_found)
        signalBus.backendEndOutput.connect(self.handle_end_output)
        
        self.initUI()

    def initUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.setLayout(self.mainLayout)  # Ensure the layout is set to the widget

        # Map View (75% height)
        # self.browser = QWebEngineView()
        self.browser = FramelessWebEngineView(self)
        self.browser.loadFinished.connect(self.on_load_finished)

        # Expose Python object to JavaScript
        self.channel = QWebChannel()
        self.channel.registerObject('pyObj', self)
        self.browser.page().setWebChannel(self.channel)
        self.browser.page().javaScriptConsoleMessage = self.handleConsoleMessage  # Add this line
        
        # Load the generated HTML file
        self.browser.setUrl(QUrl(f"file:///{os.path.abspath(map_html_path).replace(os.sep, '/')}"))

        self.mainLayout.addWidget(self.browser, 4)  # Ensure the browser is added to the layout

        # Clear the displayed names when initializing the map
        self.selectedNodes = []  # List to store selected node IDs
        self.pinItems = []       # List to store pin icons

        # Lower Area (25% height)
        self.lowerWidget = QWidget(self)
        self.lowerLayout = QHBoxLayout(self.lowerWidget)

        # Left Layout for LineEdits and Algorithm Button
        self.leftLayout = QVBoxLayout()
        self.startLineEdit = SearchLineEdit(self.lowerWidget)
        self.endLineEdit = SearchLineEdit(self.lowerWidget)
        self.algorithmButton = SplitPushButton('Select Algorithm', self.lowerWidget)

        self.startLineEdit.setPlaceholderText("Select the start node")
        self.endLineEdit.setPlaceholderText("Select the end node")
        
        self.startLineEdit.setMaximumWidth(230)
        self.endLineEdit.setMaximumWidth(230)

        self.startLineEdit.searchButton.clicked.connect(self.start_line_edit_search_clicked)
        self.endLineEdit.searchButton.clicked.connect(self.end_line_edit_search_clicked)

        self.leftLayout.addWidget(self.algorithmButton)
        self.leftLayout.addWidget(self.startLineEdit)
        self.leftLayout.addWidget(self.endLineEdit)

        self.startCompleterModel = QStringListModel()
        self.startCompleter = QCompleter(self.startCompleterModel, self)
        self.startCompleter.setCaseSensitivity(Qt.CaseInsensitive)
        self.startCompleter.setMaxVisibleItems(10)
        self.startLineEdit.setCompleter(self.startCompleter)

        self.endCompleterModel = QStringListModel()
        self.endCompleter = QCompleter(self.endCompleterModel, self)
        self.endCompleter.setCaseSensitivity(Qt.CaseInsensitive)
        self.endCompleter.setMaxVisibleItems(10)
        self.endLineEdit.setCompleter(self.endCompleter)

        # Middle Layout for CheckBoxes
        self.middleLayout = QGridLayout()
        self.pedestrianCheckBox = CheckBox('Pedestrian', self.lowerWidget)
        self.ridingCheckBox = CheckBox('Riding', self.lowerWidget)
        self.drivingCheckBox = CheckBox('Driving', self.lowerWidget)
        self.pubTransportCheckBox = CheckBox('Public Transport', self.lowerWidget)
        self.refreshCheckBox = CheckBox('Refresh Custom Layers (1s interval)', self.lowerWidget)
        self.switchModeCheckBox = CheckBox('Enable Time-First Mode', self.lowerWidget)

        self.pedestrianCheckBox.setChecked(self.pedestrain_enabled)
        self.ridingCheckBox.setChecked(self.riding_enabled)
        self.drivingCheckBox.setChecked(self.driving_enabled)
        self.pubTransportCheckBox.setChecked(self.pubTransport_enabled)

        self.pedestrianCheckBox.stateChanged.connect(self.on_checkbox_state_changed)
        self.ridingCheckBox.stateChanged.connect(self.on_checkbox_state_changed)
        self.drivingCheckBox.stateChanged.connect(self.on_checkbox_state_changed)
        self.pubTransportCheckBox.stateChanged.connect(self.on_checkbox_state_changed)
        self.refreshCheckBox.stateChanged.connect(self.on_refresh_checkbox_state_changed)  # Connect the signal
        self.switchModeCheckBox.stateChanged.connect(self.on_checkbox_state_changed)

        self.middleLayout.addWidget(self.pedestrianCheckBox, 0, 0)
        self.middleLayout.addWidget(self.ridingCheckBox, 0, 1)
        self.middleLayout.addWidget(self.drivingCheckBox, 1, 0)
        self.middleLayout.addWidget(self.pubTransportCheckBox, 1, 1)
        self.middleLayout.addWidget(self.refreshCheckBox, 2, 0, 1, 2)
        self.middleLayout.addWidget(self.switchModeCheckBox, 3, 0, 1, 2)

        # Right Layout for Buttons
        self.rightLayout = QVBoxLayout()
        self.showPathButton = PushButton('Show Shortest Path', self.lowerWidget)
        self.showPathButton.setMinimumSize(150, 40)  # Set minimum size
        self.showPathButton.clicked.connect(self.sendDataToBackend)
        self.resetButton = PushButton('Reset', self.lowerWidget)
        # self.resetButton.clicked.connect(self.reset)
        self.resetButton.setMinimumSize(150, 40)  # Set minimum size
        self.resetButton.clicked.connect(self.reset)
        self.rightLayout.addWidget(self.showPathButton)
        self.rightLayout.addWidget(self.resetButton)


        # Add a SplitPushButton to toggle layer visibility
        self.layerToggleButton = SplitPushButton("Select Map Layer", self.lowerWidget)
        self.addLayersToButton()
        self.layerToggleButton.clicked.connect(self.onLayerToggleButtonClicked)
        self.rightLayout.addWidget(self.layerToggleButton)

        self.progressBar = ProgressBar(self.lowerWidget)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)

        self.rightLayout.addWidget(self.progressBar)

        # Add spacing between layouts
        self.lowerLayout.addLayout(self.leftLayout)
        self.lowerLayout.addSpacing(100)
        self.lowerLayout.addLayout(self.middleLayout)
        self.lowerLayout.addSpacing(100)
        self.lowerLayout.addLayout(self.rightLayout)

        self.mainLayout.addWidget(self.lowerWidget, 1)  # Stretch factor 1

        # Add algorithms to the algorithmButton
        self.addAlgorithmsToButton()

        # Add a button to control the base map layer visibility
        self.addBaseLayerControlButton()

        self.loadNamesDic()
        self.updateLineSearchCompleter()

    def addAlgorithmsToButton(self):
            self.menu = RoundMenu(parent=self)
            algorithms = ["Dijkstra", "A*", "Bellman-Ford"]
            for algorithm in algorithms:
                action = Action(algorithm, self)
                action.triggered.connect(lambda checked, alg=algorithm: self.setAlgorithm(alg))
                self.menu.addAction(action)
            self.algorithmButton.setFlyout(self.menu)

    def addLayersToButton(self):
        self.layerMenu = RoundMenu(parent=self)
        layers = [("Default Map", "default"), ("Custom Rendered Map", "custom"), ("Custom Rendered Map (Sparse)", "custom_sparse")]
        for layer_name, layer_type in layers:
            action = Action(layer_name, self)
            action.triggered.connect(lambda checked, lt=layer_type: self.setLayer(lt))
            self.layerMenu.addAction(action)
        self.layerToggleButton.setFlyout(self.layerMenu)

    def setAlgorithm(self, algorithm):
        self.selectedAlgorithm = algorithm
        self.algorithmButton.setText(f"Algorithm: {algorithm}")

    def setLayer(self, layerType):
        self.layerToggleButton.setText(f"Layer: {layerType.replace('_', ' ').title()}")
        self.toggleLayerVisibility(layerType)
        self.currentLayerType = layerType  # Store the current layer type

    @pyqtSlot(str)
    def toggleLayerVisibility(self, layerType):
        self.browser.page().runJavaScript(f"toggleLayerVisibility('{layerType}');")

    def onLayerToggleButtonClicked(self):
        current_text = self.layerToggleButton.text()
        if "Default Map" in current_text:
            self.toggleLayerVisibility("default")
        elif "Custom Rendered Map" in current_text:
            self.toggleLayerVisibility("custom")
        elif "Custom Rendered Map (Sparse)" in current_text:
            self.toggleLayerVisibility("custom_sparse")

    @pyqtSlot(int, str, int, str)
    def handleConsoleMessage(self, level, message, lineNumber, sourceID):
        level_str = {
            0: "DEBUG",
            1: "INFO",
            2: "WARNING",
            3: "ERROR"
        }.get(level, "UNKNOWN")
        
        print(f"[JS {level_str}] {message}")
        signalBus.sendCommonInfo.emit(f"[JS {level_str}] {message}")
        if sourceID or lineNumber:
            print(f"Source: {sourceID}, Line: {lineNumber}")
            signalBus.sendCommonInfo.emit(f"Source: {sourceID}, Line: {lineNumber}")

    @pyqtSlot()
    def on_load_finished(self):
        pass
        # Initialize JavaScript code to access the Folium map
        self.browser.page().runJavaScript("""
            // Redirect console messages to Python
            var originalConsole = window.console;
            window.console = {
                log: function() {
                    try {
                        var args = Array.prototype.slice.call(arguments);
                        var message = args.map(String).join(' ');
                        window.pyObj.handleConsoleMessage(1, message, 0, '');
                        originalConsole.log.apply(originalConsole, args);
                    } catch(e) {
                        originalConsole.error('Error in console.log override:', e);
                    }
                },
                warn: function() {
                    try {
                        var args = Array.prototype.slice.call(arguments);
                        var message = args.map(String).join(' ');
                        window.pyObj.handleConsoleMessage(2, message, 0, '');
                        originalConsole.warn.apply(originalConsole, args);
                    } catch(e) {
                        originalConsole.error('Error in console.warn override:', e);
                    }
                },
                error: function() {
                    try {
                        var args = Array.prototype.slice.call(arguments);
                        var message = args.map(String).join(' ');
                        window.pyObj.handleConsoleMessage(3, message, 0, '');
                        originalConsole.error.apply(originalConsole, args);
                    } catch(e) {
                        originalConsole.error('Error in console.error override:', e);
                    }
                }
            };

            // Initialize window.drawnPaths
            window.drawnPaths = [];

            // Access the global map instance
            var map = window.map;

            // Initialize markers array
            var markers = [];
            var yellow_markers = [];

            // Define custom signal class
            function Signal() {
                this.listeners = [];
            }
            Signal.prototype.connect = function(listener) {
                this.listeners.push(listener);
            };
            Signal.prototype.emit = function(data) {
                this.listeners.forEach(function(listener) {
                    listener(data);
                });
            };

            // Define mapProperties object
            var mapProperties = {
                bounds: null,
                zoom: null,
                boundsChanged: new Signal(),
                zoomChanged: new Signal()
            };

            // Connect to the PyQt WebChannel
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pyObj = channel.objects.pyObj;
                window.mapProperties = mapProperties;

                // Listen for property changes
                mapProperties.boundsChanged.connect(function(bounds) {
                    pyObj.updateVisibleTiles(JSON.stringify(bounds), mapProperties.zoom);
                });
                mapProperties.zoomChanged.connect(function(zoom) {
                    pyObj.updateVisibleTiles(JSON.stringify(mapProperties.bounds), zoom);
                });
            });

            // Listen for moveend events
            map.on('moveend', function() {
                try {
                    var bounds = map.getBounds();
                    // Extract only the necessary data from bounds
                    var boundsData = {
                        _southWest: {
                            lat: bounds.getSouth(),
                            lng: bounds.getWest()
                        },
                        _northEast: {
                            lat: bounds.getNorth(),
                            lng: bounds.getEast()
                        }
                    };
                    var zoom = map.getZoom();
                    
                    // Store values separately to avoid circular references
                    mapProperties.bounds = boundsData;
                    mapProperties.zoom = zoom;
                    
                    // Emit events with simple data
                    mapProperties.boundsChanged.emit(boundsData);
                    mapProperties.zoomChanged.emit(zoom);
                } catch(e) {
                    console.error('Error in moveend handler:', e);
                }
            });

            // Define custom icons
            var yellowIcon = L.icon({
                iconUrl: './assets/yellow_icon.svg',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
            });

            console.log("Yellow icon created:", yellowIcon);

            // Initialize custom tile layer group
            window.customTileLayerGroup = L.layerGroup().addTo(map);

            // Listen for click events
            map.on('click', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                var isCtrlPressed = e.originalEvent.ctrlKey;
                if (isCtrlPressed) {
                    // Add yellow pin for middle points
                    var marker = L.marker([lat, lng], {icon: yellowIcon}).addTo(map);
                    yellow_markers.push(marker);
                    console.log("Added yellow marker at:", lat, lng);
                    window.pyObj.addMiddlePoint(lat, lng);
                } else {
                    if (markers.length >= 2) {
                        markers.forEach(function(marker) {
                            map.removeLayer(marker);
                        });
                        markers = [];
                        window.pyObj.clearSelectedNodes();
                    }
                    // Add default pin for selected nodes
                    var marker = L.marker([lat, lng]).addTo(map);
                    markers.push(marker);
                    console.log("Added default marker at:", lat, lng);
                    window.pyObj.addSelectedNode(lat, lng);
                }
            });

            map.on('contextmenu', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                window.pyObj.removeNearestNode(lat, lng);
                window.pyObj.removeNearestMiddlePoint(lat, lng);

                // Remove the nearest marker
                var nearestMarker = null;
                var minDistance = Infinity;
                markers.forEach(function(marker) {
                    var markerLatLng = marker.getLatLng();
                    var distance = map.distance([lat, lng], markerLatLng);
                    if (distance < minDistance) {
                        minDistance = distance;
                        nearestMarker = marker;
                    }
                });
                if (nearestMarker && minDistance <= {self.max_distance * 100000}) {
                    map.removeLayer(nearestMarker);
                    markers = markers.filter(function(marker) {
                        return marker !== nearestMarker;
                    });
                    console.log("Removed marker at:", nearestMarker.getLatLng());
                }

                // Remove the nearest yellow marker
                var nearestYellowMarker = null;
                var minYellowDistance = Infinity;
                yellow_markers.forEach(function(marker) {
                    var markerLatLng = marker.getLatLng();
                    var distance = map.distance([lat, lng], markerLatLng);
                    if (distance < minYellowDistance) {
                        minYellowDistance = distance;
                        nearestYellowMarker = marker;
                    }
                });
                if (nearestYellowMarker && minYellowDistance <= {self.max_distance * 100000}) {
                    map.removeLayer(nearestYellowMarker);
                    yellow_markers = yellow_markers.filter(function(marker) {
                        return marker !== nearestYellowMarker;
                    });
                    console.log("Removed yellow marker at:", nearestYellowMarker.getLatLng());
                }
            });

            // Define variables to store interval IDs
            var refreshIntervalCustomLayer = null;
            var refreshIntervalCustomSparseLayer = null;

            function startRefreshing() {
                if (!refreshIntervalCustomLayer) {
                    refreshIntervalCustomLayer = setInterval(refreshCustomLayerGroup, 1000); // Refresh every second
                }
                if (!refreshIntervalCustomSparseLayer) {
                    refreshIntervalCustomSparseLayer = setInterval(refreshCustomSparseLayerGroup, 1000); // Refresh every second
                }
            }

            function stopRefreshing() {
                if (refreshIntervalCustomLayer) {
                    clearInterval(refreshIntervalCustomLayer);
                    refreshIntervalCustomLayer = null;
                }
                if (refreshIntervalCustomSparseLayer) {
                    clearInterval(refreshIntervalCustomSparseLayer);
                    refreshIntervalCustomSparseLayer = null;
                }
            }

            function refreshCustomLayerGroup() {
                window.customLayerGroup.eachLayer(function (layer) {
                    Object.values(layer._tiles).forEach(function(tile) {
                        if (true) {
                            var img = tile.el;
                            var src = img.src;
                            img.src = ''; // Clear the src to force reload
                            img.src = src; // Set the src back to reload the tile
                        }
                    });
                });
            }

            function refreshCustomSparseLayerGroup() {
                window.customLayerGroup_sparse.eachLayer(function (layer) {
                    Object.values(layer._tiles).forEach(function(tile) {
                        if (true) {
                            var img = tile.el;
                            var src = img.src;
                            img.src = ''; // Clear the src to force reload
                            img.src = src; // Set the src back to reload the tile
                        }
                    });
                });
            }
        """)

        
        self.browser.page().runJavaScript(f"""
            // Access the global map instance
            var map = window.map;

            // Initialize markers array
            var markers = [];
            var yellow_markers = [];

            // Define custom signal class
            function Signal() {{
                this.listeners = [];
            }}
            Signal.prototype.connect = function(listener) {{
                this.listeners.push(listener);
            }};
            Signal.prototype.emit = function(data) {{
                this.listeners.forEach(function(listener) {{
                    listener(data);
                }});
            }};

            // Define mapProperties object
            var mapProperties = {{
                bounds: null,
                zoom: null,
                boundsChanged: new Signal(),
                zoomChanged: new Signal()
            }};

            // Connect to the PyQt WebChannel
            new QWebChannel(qt.webChannelTransport, function(channel) {{
                window.pyObj = channel.objects.pyObj;
                window.mapProperties = mapProperties;

                // Listen for property changes
                mapProperties.boundsChanged.connect(function(bounds) {{
                    pyObj.updateVisibleTiles(JSON.stringify(bounds), mapProperties.zoom);
                }});
                mapProperties.zoomChanged.connect(function(zoom) {{
                    pyObj.updateVisibleTiles(JSON.stringify(mapProperties.bounds), zoom);
                }});
            }});

            // Listen for moveend events
            map.on('moveend', function() {{
                try {{
                    var bounds = map.getBounds();
                    // Extract only the necessary data from bounds
                    var boundsData = {{
                        _southWest: {{
                            lat: bounds.getSouth(),
                            lng: bounds.getWest()
                        }},
                        _northEast: {{
                            lat: bounds.getNorth(),
                            lng: bounds.getEast()
                        }}
                    }};
                    var zoom = map.getZoom();
                    
                    // Store values separately to avoid circular references
                    mapProperties.bounds = boundsData;
                    mapProperties.zoom = zoom;
                    
                    // Emit events with simple data
                    mapProperties.boundsChanged.emit(boundsData);
                    mapProperties.zoomChanged.emit(zoom);
                }} catch(e) {{
                    console.error('Error in moveend handler:', e);
                }}
            }});

            // Define custom icons
            var yellowIcon = L.icon({{
                iconUrl: './assets/yellow_icon.svg',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
            }});

            console.log("Yellow icon created:", yellowIcon);

            // Initialize custom tile layer group
            window.customTileLayerGroup = L.layerGroup().addTo(map);

            // Listen for click events
            map.on('click', function(e) {{
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                var isCtrlPressed = e.originalEvent.ctrlKey;
                if (isCtrlPressed) {{
                    // Add yellow pin for middle points
                    var marker = L.marker([lat, lng], {{icon: yellowIcon}}).addTo(map);
                    yellow_markers.push(marker);
                    console.log("Added yellow marker at:", lat, lng);
                    window.pyObj.addMiddlePoint(lat, lng);
                }} else {{
                    if (markers.length >= 2) {{
                        markers.forEach(function(marker) {{
                            map.removeLayer(marker);
                        }});
                        markers = [];
                        window.pyObj.clearSelectedNodes();
                    }}
                    // Add default pin for selected nodes
                    var marker = L.marker([lat, lng]).addTo(map);
                    markers.push(marker);
                    console.log("Added default marker at:", lat, lng);
                    window.pyObj.addSelectedNode(lat, lng);
                }}
            }});
            

            map.on('contextmenu', function(e) {{
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                window.pyObj.removeNearestNode(lat, lng);
                window.pyObj.removeNearestMiddlePoint(lat, lng);

                // Remove the nearest marker
                var nearestMarker = null;
                var minDistance = Infinity;
                markers.forEach(function(marker) {{
                    var markerLatLng = marker.getLatLng();
                    var distance = map.distance([lat, lng], markerLatLng);
                    if (distance < minDistance) {{
                        minDistance = distance;
                        nearestMarker = marker;
                    }}
                }});
                if (nearestMarker && minDistance <= {self.max_distance * 100000}) {{
                    map.removeLayer(nearestMarker);
                    markers = markers.filter(function(marker) {{
                        return marker !== nearestMarker;
                    }});
                    console.log("Removed marker at:", nearestMarker.getLatLng());
                }}

                // Remove the nearest yellow marker
                var nearestYellowMarker = null;
                var minYellowDistance = Infinity;
                yellow_markers.forEach(function(marker) {{
                    var markerLatLng = marker.getLatLng();
                    var distance = map.distance([lat, lng], markerLatLng);
                    if (distance < minYellowDistance) {{
                        minYellowDistance = distance;
                        nearestYellowMarker = marker;
                    }}
                }});
                if (nearestYellowMarker && minYellowDistance <= {self.max_distance * 100000}) {{
                    map.removeLayer(nearestYellowMarker);
                    yellow_markers = yellow_markers.filter(function(marker) {{
                        return marker !== nearestYellowMarker;
                    }});
                    console.log("Removed yellow marker at:", nearestYellowMarker.getLatLng());
                }}
            }});

        """)

    def on_refresh_checkbox_state_changed(self, state):
        if state == Qt.Checked:
            self.browser.page().runJavaScript("startRefreshing();")
        else:
            self.browser.page().runJavaScript("stopRefreshing();")

    @pyqtSlot()
    def clearSelectedNodes(self):
        self.selectedNodes.clear()
        self.middlePoints.clear()
        self.browser.page().runJavaScript("""
            var yellowMarkers = window.yellow_markers || [];
            yellowMarkers.forEach(function(marker) {
                map.removeLayer(marker);
            });
            window.yellow_markers = [];
        """)
        print("Cleared all selected nodes and markers")
        signalBus.sendCommonInfo.emit("[INFO] Cleared all selected nodes and markers")

    @pyqtSlot(str, int)
    def updateVisibleTiles(self, bounds_json, zoom):
        bounds = json.loads(bounds_json)
        lat_min = bounds['_southWest']['lat']
        lon_min = bounds['_southWest']['lng']
        lat_max = bounds['_northEast']['lat']
        lon_max = bounds['_northEast']['lng']
        visible_tiles = calculate_visible_tiles([(lat_min, lon_min), (lat_max, lon_max)], zoom)
        
        # Start a worker for each tile to fetch nodes from the database
        for tile in visible_tiles:
            self.begin_rendering_tile(zoom, tile[0], tile[1])
    
    def begin_rendering_tile(self, z, x, y):
        if self.currentLayerType == "custom" and z <= 13:
            renderer_path = renderer_path_cfg
        else:
            renderer_path = renderer_sparse_path_cfg

        if os.path.exists(f"{renderer_path}/cache/{z}/{x}_{y}.png"):
            if self.currentLayerType == "custom" and z > 13:
                # copy the tile to the custom layer
                os.makedirs(f"renderer/cache/{z}", exist_ok=True)
                shutil.copyfile(f"renderer_sparse/cache/{z}/{x}_{y}.png", f"renderer/cache/{z}/{x}_{y}.png")
            return

        if os.path.exists(f"renderer/cache/{z}/{x}_{y}.png") and os.path.exists(f"renderer_sparse/cache/{z}/{x}_{y}.png"):
            return

        # Render the tile using the appropriate renderer executable asynchronously
        def render_tile(z, x, y):
            process = subprocess.Popen(
                [renderer_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            input_data = f"{z} {x} {y}\n".encode()
            stdout, stderr = process.communicate(input=input_data)
            process.wait()
            if process.returncode != 0:
                print(f"Error rendering tile {z}/{x}/{y}: {stderr.decode()}")
                signalBus.sendRendererInfo.emit(f"[ERROR] Failed to render tile {z}/{x}/{y}: {stderr.decode()}")
            else:
                if self.currentLayerType == "custom" and z <= 13:
                    print(f"\rSuccessfully rendered tile {z}/{x}/{y}", end="")
                    signalBus.sendRendererInfo.emit(f"[INFO] Successfully rendered tile {z}/{x}/{y}")
                else:
                    print(f"\rSuccessfully rendered sparse tile {z}/{x}/{y}", end="")
                    signalBus.sendRendererInfo.emit(f"[INFO] Successfully rendered sparse tile {z}/{x}/{y}")
                if self.currentLayerType == "custom" and z > 13:
                    # copy the tile to the custom layer
                    os.makedirs(f"renderer/cache/{z}", exist_ok=True)
                    shutil.copyfile(f"renderer_sparse/cache/{z}/{x}_{y}.png", f"renderer/cache/{z}/{x}_{y}.png")
            signalBus.finishRenderingTile.emit(z, x, y)

        # Submit the rendering task to the executor
        self.executor.submit(render_tile, z, x, y)

    def on_tiles_fetched(self, z, x, y):
        pass
        # # Refresh the custom tile layer
        # self.browser.page().runJavaScript(f"""
        #     var layerId = 'tile_{z}_{x}_{y}';
        #     window.customLayerGroup.eachLayer(function (layer) {{
        #         if (layer.options.id === layerId) {{
        #             var url = layer.getTileUrl({{x: {x}, y: {y}, z: {z}}});
        #             layer.redraw();
        #             console.log("Custom tile layer refreshed with ID:", layerId);
        #         }}
        #     }});
        # """)

    @pyqtSlot(str)
    def addCustomTileLayerId(self, layer_id):
        self.custom_tile_layer_ids.append(layer_id)

    def closeEvent(self, a0):
        # Shutdown the executor
        self.executor.shutdown(wait=False)
        self.browser.page().runJavaScript("""
            window.customLayerGroup.clearLayers();
            window.baseLayerGroup.clearLayers();
        """)
        super().closeEvent(a0)

    @pyqtSlot(float, float)
    def addSelectedNode(self, lat, lng):
        if len(self.selectedNodes) >= 2:
            self.clearSelectedNodes()
            # also clear the drawn paths
            self.clearDrawnPaths()
        self.selectedNodes.append((lat, lng))

    @pyqtSlot(float, float)
    def addMiddlePoint(self, lat, lng):
        self.middlePoints.append((lat, lng))

    @pyqtSlot(float, float)
    def removeNearestNode(self, lat, lng):
        def distance(node):
            return math.sqrt((node[0] - lat) ** 2 + (node[1] - lng) ** 2)

        if self.selectedNodes:
            nearest_node = min(self.selectedNodes, key=distance)
            if distance(nearest_node) <= self.max_distance:
                self.selectedNodes.remove(nearest_node)
                print(f"Removed node at: {nearest_node}")
                signalBus.sendCommonInfo.emit(f"[INFO] Removed node at: {nearest_node}")

    @pyqtSlot(float, float)
    def removeNearestMiddlePoint(self, lat, lng):
        def distance(point):
            return math.sqrt((point[0] - lat) ** 2 + (point[1] - lng) ** 2)

        if self.middlePoints:
            nearest_point = min(self.middlePoints, key=distance)
            if distance(nearest_point) <= self.max_distance:
                if nearest_point in self.middlePoints:
                    self.middlePoints.remove(nearest_point)
                    print(f"Removed middle point at: {nearest_point}")
                    signalBus.sendCommonInfo.emit(f"[INFO] Removed middle point at: {nearest_point}")

    def addBaseLayerControlButton(self):
        pass

    # def sortMiddlePoints(self):
    #     start, end = self.selectedNodes
    #     def distance(node1, node2):
    #         return math.sqrt((node1[0] - node2[0]) ** 2 + (node1[1] - node2[1]) ** 2)

    #     sorted_nodes = [start]
    #     remaining_nodes = self.middlePoints.copy()

    #     current_node = start
    #     while remaining_nodes:
    #         nearest_node = min(remaining_nodes, key=lambda node: distance(current_node, node))
    #         sorted_nodes.append(nearest_node)
    #         remaining_nodes.remove(nearest_node)
    #         current_node = nearest_node

    #     sorted_nodes.append(end)
    #     for node in sorted_nodes:
    #         if node != start and node != end:
    #             self.sorted_middle_points.append(node)

    def sendDataToBackend(self):
        if self.selectedAlgorithm is None:
            if not self.algorithmWarningShown:
                InfoBar.warning(
                    title="Warning",
                    content="No algorithm selected, using Dijkstra as default.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                signalBus.sendCommonInfo.emit("[INFO] No algorithm selected, using Dijkstra as default.")
                self.algorithmWarningShown = True
                self.selectedAlgorithm = "Dijkstra"

        if len(self.selectedNodes) < 2:
            InfoBar.warning(
                title="Warning",
                content="Please select both start and end nodes.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            return

        start, end = self.selectedNodes

        def distance(node1, node2):
            return math.sqrt((node1[0] - node2[0]) ** 2 + (node1[1] - node2[1]) ** 2)

        sorted_nodes = [start]
        remaining_nodes = self.middlePoints.copy()

        current_node = start
        while remaining_nodes:
            nearest_node = min(remaining_nodes, key=lambda node: distance(current_node, node))
            sorted_nodes.append(nearest_node)
            remaining_nodes.remove(nearest_node)
            current_node = nearest_node

        sorted_nodes.append(end)
        self.sorted_middle_points.clear()
        for node in sorted_nodes:
            if node != start and node != end:
                self.sorted_middle_points.append(node)

        backend_command = f'{self.selectedAlgorithm} {1 if self.pedestrain_enabled else 0} {1 if self.riding_enabled else 0} {1 if self.driving_enabled else 0} {1 if self.pubTransport_enabled else 0} {1 if self.enable_time_first_mode else 0} {cfg.pedestrianSpeed.value} {cfg.ridingSpeed.value} {cfg.drivingSpeed.value} {cfg.pubTransportSpeed.value} {len(sorted_nodes)}'
        for node in sorted_nodes:
            backend_command += f' {node[0]} {node[1]}'

        backend_command += '\r\n'
        print(f"Sending command to backend: {backend_command}")
        signalBus.sendCommonInfo.emit(f"[INFO] Sending command to backend: {backend_command}")
        signalBus.sendBackendRequest.emit(backend_command)
        self.clearDrawnPaths()  # Clear previously drawn paths

    def handle_backend_response(self, output):
        lines = output.strip().split('\r\n')
        # print(lines)
        for line in lines:
            if line.isdigit() and int(line) <= 100:
                progress = int(line)
                self.progressBar.setValue(progress)
                return

            if '%' in line or "Progress:" in line:
                self.progressBar.setVisible(True)
                value = int(line.strip('\r\n').strip('%').split(' ')[-1])
                self.progressBar.setValue(value)
                if value == 100:
                    self.progressBar.setVisible(False)
                print('\r' + line, end='')
                signalBus.sendCommonInfo.emit(f"[INFO] {line}")
                return

            # if 'Loading graph:' in line:
            #     self.progressBar.setVisible(True)
            #     t = line.strip('%').split(' ')[-1]
            #     self.progressBar.setValue(int(t))
            #     if t == 100:
            #         self.progressBar.setVisible(False)
            #     return

            if 'Graph loaded in' in line:
                self.handle_graph_loaded(line)
                return

            if line.startswith("TIME"):
                time_elapsed = line.split()[1]
                InfoBar.info(
                    title="Time Elapsed",
                    content=f"Time taken to find the path: {time_elapsed}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                signalBus.sendBackendInfo.emit(f"[INFO] Time taken to find the path: {time_elapsed}")
                self.begin_collecting_output = True

        if self.begin_collecting_output:
            self.backend_output_buffer.extend(lines)

        if "END" in lines:
            self.begin_collecting_output = False
            # end_index = lines.index("END")
            path = self.backend_output_buffer.copy()
            self.backend_output_buffer.clear()
            if path and path[0] != '':
                # remove '\r' from each node id
                for i in range(len(path)):
                    path[i] = path[i].strip('\r')
                self.drawPath('\n'.join(path))
                InfoBar.success(
                    title="Success",
                    content="Shortest path found successfully!",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                signalBus.sendCommonInfo.emit("[INFO] Shortest path found successfully!")
            else:
                InfoBar.error(
                    title="Error",
                    content="No path found between the selected nodes.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                signalBus.sendCommonInfo.emit("[ERROR] No path found between the selected nodes.")

        elif "NO PATH" in lines:
            InfoBar.error(
                title="Error",
                content="No path found between the selected nodes.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            signalBus.sendCommonInfo.emit("[ERROR] No path found between the selected nodes.")

        # Re-enable the button
        self.showPathButton.setEnabled(True)
        self.progressBar.setVisible(False)

    def handle_backend_error(self, error):
        InfoBar.error(
            title="Error",
            content=f"An error occurred while communicating with the backend: {error}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )
        self.showPathButton.setEnabled(True)
        signalBus.sendCommonInfo.emit(f"[ERROR] An error occurred while communicating with the backend: {error}")

    def handle_graph_loaded(self, output):
        t = output.split(' ')[-1]
        InfoBar.success(
            title="Success",
            content=f"Successfully loaded graph in {t}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=None
        )
        signalBus.sendCommonInfo.emit(f"[INFO] Successfully loaded graph in {t}")

    def handle_no_path_found(self):
        InfoBar.error(
            title="Error",
            content="No path found between selected nodes.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=None
        )
        signalBus.sendCommonInfo.emit("[ERROR] No path found between selected nodes.")

    def handle_path_found(self, output):
        self.begin_collecting_output = True
        t = output.split(' ')[-1]
        InfoBar.success(
            title="Success",
            content=f"Successfully found path in {t}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=None
        )
        signalBus.sendCommonInfo.emit(f"[INFO] Successfully found path in {t}")

    def handle_end_output(self):
        # # self.backend_output_buffer.pop()  # Remove 'END' from the output buffer
        # self.begin_collecting_output = False
        # self.drawPath('\n'.join(self.backend_output_buffer))  # Draw the path from collected backend output
        # self.backend_output_buffer.clear()  # Clear the buffer after drawing the path
        pass

    def drawPath(self, output):
        lines = output.strip().split('\n')
        path = []
        cur_middle_point_index = 0
        start, end = self.selectedNodes.copy()
        path.append(start)  # Add start node
        for line in lines:
            if 'NO PATH' in line:
                return
            if not line or 'TIME' in line or 'END' in line: 
                continue
            if line == "MIDPOINT":
                if cur_middle_point_index < len(self.middlePoints):
                    lat, lng = self.sorted_middle_points[cur_middle_point_index]
                    cur_middle_point_index += 1
                    path.append((lat, lng))
                else:
                    continue
            else:
                lat, lng = map(float, line.split())
                path.append((lat, lng))

        path.append(end)  # Add end node
        
        print(path)
        signalBus.sendBackendInfo.emit(f"[INFO] Path found: {path}")
        path_json = json.dumps(path)  # Convert path to JSON string
        self.browser.page().runJavaScript(f"""
            var latlngs = {path_json};
            var polyline = L.polyline(latlngs, {{color: 'blue'}}).addTo(map);
            window.drawnPaths.push(polyline);
        """)
        self.drawnPaths.append(path)

    def clearDrawnPaths(self):
        self.browser.page().runJavaScript("""
            if (window.drawnPaths) {
                window.drawnPaths.forEach(function(path) {
                    map.removeLayer(path);
                });
                window.drawnPaths = [];
            }
        """)
        self.drawnPaths.clear()

    def reset(self):
        # self.startLineEdit.clear()
        # self.endLineEdit.clear()
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        self.showPathButton.setEnabled(True)
        self.clearDrawnPaths()
        self.clearSelectedNodes()
        self.browser.page().runJavaScript("""
            var markers = window.markers || [];
            markers.forEach(function(marker) {
                map.removeLayer(marker);
            });
            window.markers = [];

            var yellowMarkers = window.yellow_markers || [];
            yellowMarkers.forEach(function(marker) {
                map.removeLayer(marker);
            });
            window.yellow_markers = [];
        """)

        InfoBar.info(
            title="Info",
            content="Cleared all selected nodes and displayed paths.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )
        signalBus.sendCommonInfo.emit("[INFO] Cleared all selected nodes and displayed paths.")

    def on_checkbox_state_changed(self):
        self.pedestrain_enabled = self.pedestrianCheckBox.isChecked()
        self.riding_enabled = self.ridingCheckBox.isChecked()
        self.driving_enabled = self.drivingCheckBox.isChecked()
        self.pubTransport_enabled = self.pubTransportCheckBox.isChecked()
        self.enable_time_first_mode = self.switchModeCheckBox.isChecked()

    def loadNamesDic(self):
        with open("E:\\BaiduSyncdisk\\Code Projects\\PyQt Projects\\Data Structure Project\\backend\\data\\place_names.txt", 'r', encoding='utf-8') as f:
            for line in f:
                if line:
                    parts = line.strip().rsplit(' ', 2)
                    name, lat, lon = parts[0], parts[1], parts[2]
                    self.namesDic[name] = (float(lat), float(lon))

    def updateLineSearchCompleter(self):
        completer = QCompleter(self.namesDic.keys())
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.startLineEdit.setCompleter(completer)
        self.endLineEdit.setCompleter(completer)

    def start_line_edit_search_clicked(self):
        text = self.startLineEdit.text()
        if text in self.namesDic:
            lat, lon = self.namesDic[text]
            self.addSelectedNode(lat, lon)
            self.browser.page().runJavaScript(f"""
                var marker = L.marker([{lat}, {lon}]).addTo(map);
                window.markers.push(marker);
            """)
            print(f"Added start node: {text} at ({lat}, {lon})")
            signalBus.sendCommonInfo.emit(f"[INFO] Added start node: {text} at ({lat}, {lon})")

    def end_line_edit_search_clicked(self):
        text = self.endLineEdit.text()
        if text in self.namesDic:
            lat, lon = self.namesDic[text]
            self.addSelectedNode(lat, lon)
            self.browser.page().runJavaScript(f"""
                var marker = L.marker([{lat}, {lon}]).addTo(map);
                window.markers.push(marker);
            """)
            print(f"Added end node: {text} at ({lat}, {lon})")
            signalBus.sendCommonInfo.emit(f"[INFO] Added end node: {text} at ({lat}, {lon})")
