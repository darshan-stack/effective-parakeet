cmake_minimum_required(VERSION 3.8)
project(gpuguard_ros2)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Generate ROS 2 messages
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GPUState.msg"
  "msg/TopicStats.msg"
  "msg/Correlation.msg"
  "msg/Anomaly.msg"
  DEPENDENCIES builtin_interfaces
)

# Install Python nodes
ament_python_install_package(${PROJECT_NAME})

# Install launch files
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()