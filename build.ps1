$ErrorActionPreference = "Stop"
$root_dir = Get-Location
New-Item -ItemType Directory -Path "$root_dir/bin" -Force

# Install python dependencies
pip install -r requirements.txt

# Build backend C++ project
Set-Location "$root_dir/backend"
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}
New-Item -ItemType Directory -Path "build" | Out-Null
Set-Location "build"
cmake -G "MinGW Makefiles" ..
mingw32-make -j 16 
Copy-Item -Path ".\backend.exe" -Destination "$root_dir/bin" -Force

# Build rust project: renderer
Set-Location $root_dir
Set-Location "$root_dir/renderer"
cargo build --release
Copy-Item -Path ".\target\release\renderer.exe" -Destination "$root_dir/bin" -Force

# Build rust project: renderer_sparse
Set-Location $root_dir
Set-Location "$root_dir/renderer_sparse"
cargo build --release
Copy-Item -Path ".\target\release\renderer_sparse.exe" -Destination "$root_dir/bin" -Force

# Download map data and generate db file
Set-Location "$root_dir/map_data"
Invoke-WebRequest -Uri "https://overpass-api.de/api/map?bbox=120.21,30.10,122.32,31.93" -OutFile "map.osm"
Set-Location "$root_dir"
python preprocess_osm.py
