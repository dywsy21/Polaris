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

# Download map data
