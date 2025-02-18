export root_dir=$(pwd)
mkdir bin

# Build backend C++ project
cd backend
rm -rf build
mkdir build && cd build
cmake ..
cmake --build . --config Release
cp ./Release/backend $root_dir/bin

# Build two rust projects
cd $root_dir
cd renderer
cargo build --release
cp ./target/release/renderer $root_dir/bin

cd $root_dir
cd renderer_sparse
cargo build --release
cp ./target/release/renderer_sparse $root_dir/bin

# Download map data and generate db file
cd $root_dir/map_data
curl -o map.osm "https://overpass-api.de/api/map?bbox=120.21,30.10,122.32,31.93"
cd .. && python preprocess_osm.py
