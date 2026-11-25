#!/bin/bash
# GPUGuard Installation Script for Ubuntu 22.04/24.04
# Installs all dependencies including NVIDIA drivers, ROS 2, and Python packages

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Configuration
ROS_DISTRO="${ROS_DISTRO:-jazzy}"
PYTHON_VERSION="3.10"
GPUGUARD_DIR="/home/darshan/GPUGuard"

# Check Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs)
log_info "Detected Ubuntu $UBUNTU_VERSION"

if [[ "$UBUNTU_VERSION" != "22.04" && "$UBUNTU_VERSION" != "24.04" ]]; then
    log_warn "This script is tested on Ubuntu 22.04 and 24.04. Proceeding anyway..."
fi

# Check for NVIDIA GPU
check_nvidia_gpu() {
    log_info "Checking for NVIDIA GPU..."
    if lspci | grep -i nvidia > /dev/null; then
        log_success "NVIDIA GPU detected:"
        lspci | grep -i nvidia
        return 0
    else
        log_warn "No NVIDIA GPU detected. GPUGuard will run in mock mode."
        return 1
    fi
}

# Install NVIDIA driver
install_nvidia_driver() {
    if check_nvidia_gpu; then
        log_info "Installing NVIDIA driver..."
        ubuntu_drivers install 2>/dev/null || {
            log_info "Adding graphics-drivers PPA..."
            add-apt-repository -y ppa:graphics-drivers/ppa
            apt update
            ubuntu_drivers install
        }
        log_success "NVIDIA driver installed. Reboot required."
    fi
}

# Install NVML development headers
install_nvml() {
    log_info "Installing NVML development headers..."
    apt install -y nvidia-cuda-toolkit 2>/dev/null || {
        log_info "Installing from NVIDIA repository..."
        wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${UBUNTU_VERSION//./}/x86_64/cuda-keyring_1.1-1_all.deb
        dpkg -i cuda-keyring_1.1-1_all.deb
        apt update
        apt install -y cuda-nvml-dev-${CUDA_VERSION:-12-2}
    }
}

# Install ROS 2
install_ros2() {
    log_info "Installing ROS 2 $ROS_DISTRO..."

    # Add ROS 2 apt repository
    apt update && apt install -y curl gnupg lsb-release
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

    apt update
    apt install -y ros-$ROS_DISTRO-desktop ros-$ROS_DISTRO-ros2-control ros-$ROS_DISTRO-ros2-controllers

    # Source ROS 2
    echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> /home/darshan/.bashrc
    source /opt/ros/$ROS_DISTRO/setup.bash

    log_success "ROS 2 $ROS_DISTRO installed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."

    # Ensure pip is up to date
    python3 -m pip install --upgrade pip

    # Install GPUGuard in development mode
    cd "$GPUGUARD_DIR"
    pip install -e .[dev]

    log_success "Python dependencies installed"
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."

    apt update
    apt install -y \
        build-essential \
        cmake \
        git \
        python3-dev \
        python3-venv \
        python3-pip \
        libssl-dev \
        libffi-dev \
        pkg-config \
        libyaml-cpp-dev \
        nlohmann-json3-dev \
        libeigen3-dev \
        libboost-all-dev \
        wget \
        curl \
        htop \
        nvtop \
        gpustat
}

# Setup GPUGuard workspace
setup_workspace() {
    log_info "Setting up GPUGuard workspace..."

    cd "$GPUGUARD_DIR"

    # Create virtual environment if not exists
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        log_success "Created virtual environment"
    fi

    # Activate and install
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e .[dev]

    log_success "Workspace setup complete"
}

# Build ROS 2 package
build_ros2_package() {
    log_info "Building ROS 2 package..."

    # Source ROS 2
    source /opt/ros/$ROS_DISTRO/setup.bash

    # Create workspace if needed
    mkdir -p /home/darshan/ros2_ws/src
    ln -sf "$GPUGUARD_DIR/src/gpuguard/ros2" /home/darshan/ros2_ws/src/gpuguard_ros2

    cd /home/darshan/ros2_ws
    rosdep install --from-paths src --ignore-src -r -y
    colcon build --packages-select gpuguard_ros2 --event-handlers console_direct+

    log_success "ROS 2 package built"
}

# Main installation
main() {
    log_info "Starting GPUGuard installation..."

    # Check if running as root for system packages
    if [[ $EUID -eq 0 ]]; then
        log_error "Don't run this script as root! Run as regular user with sudo access."
        exit 1
    fi

    # Install system dependencies
    install_system_deps

    # Install NVIDIA driver (optional, requires reboot)
    read -p "Install NVIDIA driver? (requires reboot) [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_nvidia_driver
        install_nvml
        log_warn "Please reboot after driver installation, then re-run this script"
        exit 0
    fi

    # Install ROS 2
    read -p "Install ROS 2 $ROS_DISTRO? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_ros2
    fi

    # Setup workspace
    setup_workspace

    # Build ROS 2 package
    if [[ -d "/opt/ros/$ROS_DISTRO" ]]; then
        read -p "Build ROS 2 package? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            build_ros2_package
        fi
    fi

    log_success "GPUGuard installation complete!"
    log_info "Next steps:"
    log_info "  1. Source ROS 2: source /opt/ros/$ROS_DISTRO/setup.bash"
    log_info "  2. Activate venv: source $GPUGUARD_DIR/.venv/bin/activate"
    log_info "  3. Run GPUGuard: gpuguard-collector --mock  (for testing without GPU)"
    log_info "  4. Run dashboard: gpuguard-dashboard"
    log_info "  5. Run ROS 2 nodes: ros2 launch gpuguard_ros2 gpuguard.launch.py"
}

# Run main
main "$@"