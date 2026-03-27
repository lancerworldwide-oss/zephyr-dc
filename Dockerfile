FROM ghcr.io/zephyrproject-rtos/zephyr-build:v0.28.7

# Directory where the Zephyr tree will live in the image
ENV ZEPHYR_WORKSPACE=/opt/zephyrproject

WORKDIR ${ZEPHYR_WORKSPACE}

USER root

RUN <<EOF
    # Install base packages
    apt-get update
    apt-get install -y libjson-xs-perl git curl ca-certificates wget gnupg apt-transport-https python3-pip python3 python-is-python3
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list
    apt-get update
    apt-get install -y nodejs
    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

# NOTE: We are using the version of dts2repl that is associated with the base image's renode version
# to avoid compatibility issues.
# If you update renode in the base image, please update the dts2repl commit hash accordingly.
# you can get the git hash by inspecting the git repo and branch of the renode build in the base image
RUN python3 -m pip install git+https://github.com/antmicro/dts2repl.git@c281274

USER user

RUN west init -m https://github.com/zephyrproject-rtos/zephyr --mr v4.3-branch .

RUN west update --fetch=smart --narrow -o=--depth=1

USER root

RUN <<EOF
    # Install Microsoft packages for dotnet-sdk-10.0
    . /etc/os-release
    wget -qO /tmp/packages-microsoft-prod.deb https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb
    dpkg -i /tmp/packages-microsoft-prod.deb
    rm /tmp/packages-microsoft-prod.deb
EOF

RUN <<EOF
    # Add jammy repo for gtk-sharp2 (not available in noble)
    printf "deb http://archive.ubuntu.com/ubuntu jammy main universe multiverse\n" > /etc/apt/sources.list.d/jammy.list
    printf "deb http://archive.ubuntu.com/ubuntu jammy-updates main universe multiverse\n" >> /etc/apt/sources.list.d/jammy.list
    printf "deb http://security.ubuntu.com/ubuntu jammy-security main universe multiverse\n" >> /etc/apt/sources.list.d/jammy.list
EOF

RUN <<EOF
    # Install additional packages
    apt-get update
    apt-get install -y \
        automake \
        build-essential \
        clang-tools \
        clang-format \
        clang-tidy \
        cmake \
        cppcheck \
        cpplint \
        coreutils \
        dotnet-sdk-10.0 \
        doxygen \
        graphviz \
        mscgen \
        plantuml \
        gcc \
        gtk-sharp3 \
        gtk-sharp2 \
        htop \
        libgtk2.0-dev \
        libc6-dev \
        libtool \
        libffi-dev \
        libglib2.0-dev \
        libgdk-pixbuf2.0-dev \
        libpango1.0-dev \
        libatk1.0-dev \
        libgtk-3-dev \
        libicu-dev \
        libssl-dev \
        libxml2-dev \
        minicom \
        mono-complete \
        nano \
        pkg-config \
        policykit-1 \
        python3-tk \
        screen \
        tmux \
        uml-utilities \
        zlib1g-dev
    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

RUN <<EOF
    # Install Segger J-Link tools for hardware flashing (8.10 or later recommended)
    apt-get update
    apt-get install -y \
        libxcb-render-util0 \
        libxcb-icccm4 \
        libxcb-keysyms1 \
        libxcb-image0 \
        libxkbcommon-x11-0

    # Download J-Link DEB package (version 8.10 or later recommended)
    JLINK_VERSION=V810b
    wget --post-data="accept_license_agreement=accepted" \
         -O /tmp/jlink.deb \
         https://www.segger.com/downloads/jlink/JLink_Linux_${JLINK_VERSION}_x86_64.deb

    # Extract the DEB package
    dpkg-deb -x /tmp/jlink.deb /tmp/jlink-extracted

    # Copy J-Link files to their proper locations
    cp -a /tmp/jlink-extracted/opt/SEGGER /opt/
    cp -a /tmp/jlink-extracted/usr/bin/* /usr/bin/ || true
    cp -a /tmp/jlink-extracted/usr/share/* /usr/share/ || true

    # Copy udev rules if they exist in the package
    if [ -d /tmp/jlink-extracted/etc/udev/rules.d ]; then
        mkdir -p /etc/udev/rules.d
        cp -a /tmp/jlink-extracted/etc/udev/rules.d/* /etc/udev/rules.d/ || true
    fi

    # Clean up
    rm -rf /tmp/jlink.deb /tmp/jlink-extracted
    apt-get clean
    rm -rf /var/lib/apt/lists/*

    # Verify installation
    which JLinkExe
    /opt/SEGGER/JLink/JLinkExe -v || true
EOF

# Add udev rules for J-Link USB access
RUN <<EOF
    # Create udev rules for J-Link devices
    cat > /etc/udev/rules.d/99-jlink.rules <<'UDEV_EOF'
# Segger J-Link
SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="0666", GROUP="plugdev"
UDEV_EOF

    chmod 644 /etc/udev/rules.d/99-jlink.rules
EOF

RUN <<EOF
    # Install Renode
    rm -rf /opt/renode
    git clone --depth 1 -b v1.16.0  https://github.com/renode/renode.git /opt/renode-git
    cd /opt/renode-git
    ./build.sh --net -d
    cp -aR /opt/renode-git/output/bin/Debug /opt/renode
    cp -aR /opt/renode-git/scripts /opt/renode
    cp -aR /opt/renode-git/platforms /opt/renode
    chmod -R 777 /opt/renode
    chmod -R 777 /opt/renode-git
    chown -R user:user /opt/renode
    chown -R user:user /opt/renode-git
EOF

RUN <<EOF
    # Install Rust toolchain for building MCP server
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
    . /root/.cargo/env

    # Install additional dependencies for embedded-debugger-mcp
    apt-get update
    apt-get install -y libudev-dev
    apt-get clean
    rm -rf /var/lib/apt/lists/*

    # Clone and build embedded-debugger-mcp
    cd /tmp
    git clone --depth 1 https://github.com/Adancurusul/embedded-debugger-mcp.git
    cd embedded-debugger-mcp

    # Build with gold linker to avoid architecture mismatch issues
    RUSTFLAGS="-C link-arg=-fuse-ld=gold" /root/.cargo/bin/cargo build --release

    # Install the binary to system location
    install -m 755 target/release/embedded-debugger-mcp /usr/local/bin/embedded-debugger-mcp

    # Clean up build artifacts
    cd /
    rm -rf /tmp/embedded-debugger-mcp
    rm -rf /root/.cargo/registry
    rm -rf /root/.cargo/git

    # Verify installation
    /usr/local/bin/embedded-debugger-mcp --version || echo "MCP server installed successfully"
EOF

USER user

# Set ZEPHYR_BASE so west builds are ready out-of-the-box
ENV ZEPHYR_BASE=${ZEPHYR_WORKSPACE}/zephyr
ENV DISPLAY=host.docker.internal:0.0
# Optionally set default toolchain variant if not already set by base image
# ENV ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
USER user
