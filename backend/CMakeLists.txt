# Force GCC on Windows
set(CMAKE_C_COMPILER "gcc")
set(CMAKE_CXX_COMPILER "g++")

cmake_minimum_required(VERSION 3.10)
project(Backend)

# Ensure Windows doesn't add any unwanted flags
if(WIN32)
    set(CMAKE_C_FLAGS_INIT "")
    set(CMAKE_CXX_FLAGS_INIT "")
    set(CMAKE_C_FLAGS "")
    set(CMAKE_CXX_FLAGS "")
endif()

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

# use O3 optimization and add GCC-specific flags
target_compile_options(backend PRIVATE 
    -O3
    -Wall
    $<$<CXX_COMPILER_ID:GNU>:-fexec-charset=GBK>  # Handle Chinese characters in Windows
)
