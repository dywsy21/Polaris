cmake_minimum_required(VERSION 3.10)
project(Backend)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Include directories
include_directories(${CMAKE_SOURCE_DIR})

# Add pugixml source files
set(PUGIXML_SOURCES
    pugixml/pugixml.cpp
)

# Add executable with all source files
add_executable(backend main.cpp path_finding.cpp k-dtree.cpp ${PUGIXML_SOURCES})

# use O3 optimization
target_compile_options(backend PRIVATE -O3)