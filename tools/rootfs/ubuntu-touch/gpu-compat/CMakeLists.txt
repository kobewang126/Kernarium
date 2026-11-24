# SPDX-License-Identifier: GPL-2.0-or-later
cmake_minimum_required(VERSION 3.27)
project(TouchariumGuestGpuCompat LANGUAGES CXX)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR
   NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
    message(FATAL_ERROR "The guest compatibility library requires arm64 Linux")
endif()
find_package(Threads REQUIRED)
add_library(toucharium-mir-gpu SHARED gpu_compat.cpp)
target_compile_features(toucharium-mir-gpu PRIVATE cxx_std_20)
target_compile_options(toucharium-mir-gpu PRIVATE -Wall -Wextra -Werror)
target_link_libraries(toucharium-mir-gpu PRIVATE ${CMAKE_DL_LIBS} Threads::Threads)
install(TARGETS toucharium-mir-gpu LIBRARY DESTINATION lib)
