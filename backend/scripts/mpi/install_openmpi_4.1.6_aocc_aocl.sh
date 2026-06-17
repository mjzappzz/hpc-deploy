#!/bin/bash
set -e

# ============================================================
# OpenMPI 4.1.6 + AOCC 4.1.0 + AOCL 4.1.0 Auto Installer
#
# Install Path:
#   AOCC    : /opt/AMD/aocc-compiler-4.1.0
#   AOCL    : /opt/AMD/aocl/aocl-linux-aocc-4.1.0
#   OpenMPI : /opt/openmpi-4.1.6-aocc
#
# Download Path:
#   /tmp/openmpi_aocc_aocl_install
#
# Download Policy:
#   1. 先 ping 内网 IP：192.168.130.5
#   2. 内网可达：使用内网地址下载
#   3. 内网不可达：使用公网地址下载
#
# Components:
#   AOCC    : AMD C/C++/Fortran Compiler
#   AOCL    : AMD Optimized Math Libraries
#   OpenMPI : MPI Library built by AOCC
# ============================================================

# Ubuntu/Debian 非交互安装，避免 needrestart 弹窗
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export APT_LISTCHANGES_FRONTEND=none

INNER_IP="192.168.130.5"

DOWNLOAD_DIR="/tmp/openmpi_aocc_aocl_install"

AOCC_DIR="/opt/AMD/aocc-compiler-4.1.0"
AOCL_DIR="/opt/AMD/aocl/aocl-linux-aocc-4.1.0"
OPENMPI_DIR="/opt/openmpi-4.1.6-aocc"

AOCC_ENV="${AOCC_DIR}/setenv_AOCC.sh"
AOCL_ENV="${AOCL_DIR}/aocc/amd-libs.cfg"

FORCE_REBUILD="${FORCE_REBUILD:-0}"

AOCC_CENTOS_FILE="aocc-compiler-4.1.0-1.x86_64.rpm"
AOCL_CENTOS_FILE="aocl-linux-aocc-4.1.0-1.x86_64.rpm"

AOCC_UBUNTU_FILE="aocc-compiler-4.1.0_1_amd64.deb"
AOCL_UBUNTU_FILE="aocl-linux-aocc-4.1.0_1_amd64.deb"

OPENMPI_FILE="openmpi-4.1.6.tar.gz"
OPENMPI_SRC_DIR="openmpi-4.1.6"

# ============================================================
# 内网下载地址
# ============================================================

AOCC_CENTOS_INNER_URL="http://192.168.130.5:2437/chfs/shared/%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6/%E7%BC%96%E8%AF%91%E5%99%A8/amd/centos/aocc-compiler-4.1.0-1.x86_64.rpm"
AOCL_CENTOS_INNER_URL="http://192.168.130.5:2437/chfs/shared%2F%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6%2F%E7%BC%96%E8%AF%91%E5%99%A8/amd/centos/aocl-linux-aocc-4.1.0-1.x86_64.rpm"

AOCC_UBUNTU_INNER_URL="http://192.168.130.5:2437/chfs/shared%2F%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6%2F%E7%BC%96%E8%AF%91%E5%99%A8/amd/ubuntu/aocc-compiler-4.1.0_1_amd64.deb"
AOCL_UBUNTU_INNER_URL="http://192.168.130.5:2437/chfs/shared/%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6/%E7%BC%96%E8%AF%91%E5%99%A8/amd/ubuntu/aocl-linux-aocc-4.1.0_1_amd64.deb"

OPENMPI_INNER_URL="http://192.168.130.5:2437/chfs/shared/%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6/%E7%BC%96%E8%AF%91%E5%99%A8/openmpi/openmpi-4.1.6.tar.gz"

# ============================================================
# 公网下载地址
# ============================================================

AOCC_CENTOS_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/amd/centos/aocc-compiler-4.1.0-1.x86_64.rpm"
AOCL_CENTOS_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/amd/centos/aocl-linux-aocc-4.1.0-1.x86_64.rpm"

AOCC_UBUNTU_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/amd/ubuntu/aocc-compiler-4.1.0_1_amd64.deb"
AOCL_UBUNTU_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/amd/ubuntu/aocl-linux-aocc-4.1.0_1_amd64.deb"

OPENMPI_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/amd/openmpi/openmpi-4.1.6.tar.gz"

echo "============================================================"
echo " OpenMPI 4.1.6 + AOCC 4.1.0 + AOCL 4.1.0 Installer"
echo "============================================================"
echo "下载目录：${DOWNLOAD_DIR}"
echo "AOCC 目录：${AOCC_DIR}"
echo "AOCL 目录：${AOCL_DIR}"
echo "OpenMPI 目录：${OPENMPI_DIR}"
echo "FORCE_REBUILD：${FORCE_REBUILD}"
echo "============================================================"

# 必须 root 执行
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] 请使用 root 执行："
    echo "        sudo bash $0"
    exit 1
fi

# 识别系统
if [ ! -f /etc/os-release ]; then
    echo "[ERROR] 无法识别系统：缺少 /etc/os-release"
    exit 1
fi

. /etc/os-release

OS_ID="${ID}"
OS_LIKE="${ID_LIKE:-}"

case "${OS_ID}" in
    ubuntu|debian)
        OS_TYPE="ubuntu"
        ;;
    centos|rocky|almalinux|rhel|fedora)
        OS_TYPE="centos"
        ;;
    *)
        if echo "${OS_LIKE}" | grep -qi "debian"; then
            OS_TYPE="ubuntu"
        elif echo "${OS_LIKE}" | grep -qi "rhel\|fedora"; then
            OS_TYPE="centos"
        else
            echo "[ERROR] 暂不支持该系统：ID=${OS_ID}, ID_LIKE=${OS_LIKE}"
            exit 1
        fi
        ;;
esac

echo
echo "[INFO] 系统识别：${PRETTY_NAME}"
echo "[INFO] OS_TYPE：${OS_TYPE}"

# 创建目录
mkdir -p "${DOWNLOAD_DIR}"
cd "${DOWNLOAD_DIR}"

download_file() {
    local name="$1"
    local file="$2"
    local url="$3"
    local tmp_file="${file}.downloading"

    echo
    echo "[INFO] 检查 ${name} 安装包：${DOWNLOAD_DIR}/${file}"

    # 正式文件存在且非空，直接跳过
    if [ -f "${file}" ] && [ -s "${file}" ]; then
        echo "[INFO] ${name} 已存在且非空，跳过下载：${DOWNLOAD_DIR}/${file}"
        return 0
    fi

    # 正式文件存在但为空，删除
    if [ -f "${file}" ] && [ ! -s "${file}" ]; then
        echo "[WARN] ${name} 文件存在但为空，删除后重新下载：${DOWNLOAD_DIR}/${file}"
        rm -f "${file}"
    fi

    # 删除上次中断遗留的临时文件
    if [ -f "${tmp_file}" ]; then
        echo "[WARN] 发现上次未完成的临时文件，删除：${DOWNLOAD_DIR}/${tmp_file}"
        rm -f "${tmp_file}"
    fi

    echo "[INFO] 下载 ${name}：${file}"
    echo "[INFO] URL：${url}"

    wget -O "${tmp_file}" "${url}"

    # 下载后检查临时文件
    if [ ! -s "${tmp_file}" ]; then
        echo "[ERROR] ${name} 下载失败或临时文件为空：${DOWNLOAD_DIR}/${tmp_file}"
        rm -f "${tmp_file}"
        exit 1
    fi

    # 下载完成后再改名为正式文件
    mv -f "${tmp_file}" "${file}"

    echo "[INFO] ${name} 下载完成：${DOWNLOAD_DIR}/${file}"
}

echo
echo "============================================================"
echo "[1/8] 安装系统依赖"
echo "============================================================"

if [ "${OS_TYPE}" = "ubuntu" ]; then
    apt update

    apt install -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold" \
        build-essential \
        gcc \
        g++ \
        gfortran \
        make \
        cmake \
        wget \
        tar \
        gzip \
        perl \
        python3 \
        libgfortran5 \
        libquadmath0 \
        libopenblas-dev \
        liblapack-dev \
        libfftw3-dev \
        iputils-ping
else
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    else
        PKG_MGR="yum"
    fi

    ${PKG_MGR} install -y \
        wget \
        tar \
        gzip \
        make \
        gcc \
        gcc-c++ \
        gcc-gfortran \
        cmake \
        perl \
        python3 \
        libstdc++-devel \
        libquadmath \
        libquadmath-devel \
        openblas-devel \
        lapack-devel \
        fftw-devel \
        iputils
fi

echo
echo "============================================================"
echo "[2/8] 检测下载源"
echo "============================================================"

echo "[INFO] 检测内网 IP 是否可达：${INNER_IP}"

if ping -c 2 -W 2 "${INNER_IP}" >/dev/null 2>&1; then
    echo "[INFO] 内网可达，使用内网下载地址"
    DOWNLOAD_SOURCE="内网"

    AOCC_CENTOS_URL="${AOCC_CENTOS_INNER_URL}"
    AOCL_CENTOS_URL="${AOCL_CENTOS_INNER_URL}"
    AOCC_UBUNTU_URL="${AOCC_UBUNTU_INNER_URL}"
    AOCL_UBUNTU_URL="${AOCL_UBUNTU_INNER_URL}"
    OPENMPI_URL="${OPENMPI_INNER_URL}"
else
    echo "[WARN] 内网不可达，使用公网下载地址"
    DOWNLOAD_SOURCE="公网"

    AOCC_CENTOS_URL="${AOCC_CENTOS_PUBLIC_URL}"
    AOCL_CENTOS_URL="${AOCL_CENTOS_PUBLIC_URL}"
    AOCC_UBUNTU_URL="${AOCC_UBUNTU_PUBLIC_URL}"
    AOCL_UBUNTU_URL="${AOCL_UBUNTU_PUBLIC_URL}"
    OPENMPI_URL="${OPENMPI_PUBLIC_URL}"
fi

if [ "${OS_TYPE}" = "ubuntu" ]; then
    AOCC_FILE="${AOCC_UBUNTU_FILE}"
    AOCL_FILE="${AOCL_UBUNTU_FILE}"
    AOCC_URL="${AOCC_UBUNTU_URL}"
    AOCL_URL="${AOCL_UBUNTU_URL}"
else
    AOCC_FILE="${AOCC_CENTOS_FILE}"
    AOCL_FILE="${AOCL_CENTOS_FILE}"
    AOCC_URL="${AOCC_CENTOS_URL}"
    AOCL_URL="${AOCL_CENTOS_URL}"
fi

echo
echo "[INFO] 当前下载源：${DOWNLOAD_SOURCE}"
echo "[INFO] AOCC 下载地址：${AOCC_URL}"
echo "[INFO] AOCL 下载地址：${AOCL_URL}"
echo "[INFO] OpenMPI 下载地址：${OPENMPI_URL}"

echo
echo "============================================================"
echo "[3/8] 下载 AOCC / AOCL / OpenMPI 安装包"
echo "============================================================"

download_file "AOCC" "${AOCC_FILE}" "${AOCC_URL}"
download_file "AOCL" "${AOCL_FILE}" "${AOCL_URL}"
download_file "OpenMPI" "${OPENMPI_FILE}" "${OPENMPI_URL}"

echo
echo "============================================================"
echo "[4/8] 检查安装包"
echo "============================================================"

if [ ! -s "${AOCC_FILE}" ]; then
    echo "[ERROR] AOCC 文件不存在或为空：${DOWNLOAD_DIR}/${AOCC_FILE}"
    exit 1
fi

if [ ! -s "${AOCL_FILE}" ]; then
    echo "[ERROR] AOCL 文件不存在或为空：${DOWNLOAD_DIR}/${AOCL_FILE}"
    exit 1
fi

if [ ! -s "${OPENMPI_FILE}" ]; then
    echo "[ERROR] OpenMPI 文件不存在或为空：${DOWNLOAD_DIR}/${OPENMPI_FILE}"
    exit 1
fi

echo "[INFO] AOCC OK：${DOWNLOAD_DIR}/${AOCC_FILE}"
echo "[INFO] AOCL OK：${DOWNLOAD_DIR}/${AOCL_FILE}"
echo "[INFO] OpenMPI OK：${DOWNLOAD_DIR}/${OPENMPI_FILE}"

echo
echo "============================================================"
echo "[5/8] 安装 AOCC 和 AOCL"
echo "============================================================"

if [ "${OS_TYPE}" = "ubuntu" ]; then
    echo "[INFO] 安装 AOCC：${AOCC_FILE}"
    dpkg -i "${AOCC_FILE}" || apt install -f -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold"

    echo
    echo "[INFO] 安装 AOCL：${AOCL_FILE}"
    dpkg -i "${AOCL_FILE}" || apt install -f -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold"
else
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    else
        PKG_MGR="yum"
    fi

    echo "[INFO] 安装 AOCC：${AOCC_FILE}"
    ${PKG_MGR} install -y "./${AOCC_FILE}"

    echo
    echo "[INFO] 安装 AOCL：${AOCL_FILE}"
    ${PKG_MGR} install -y "./${AOCL_FILE}"
fi

echo
echo "============================================================"
echo "[6/8] 编译安装 OpenMPI 4.1.6"
echo "============================================================"

if [ ! -f "${AOCC_ENV}" ]; then
    echo "[ERROR] 未找到 AOCC 环境文件：${AOCC_ENV}"
    exit 1
fi

if [ ! -f "${AOCL_ENV}" ]; then
    echo "[ERROR] 未找到 AOCL 环境文件：${AOCL_ENV}"
    exit 1
fi

if [ ! -x "${AOCC_DIR}/bin/clang" ]; then
    echo "[ERROR] 未找到 clang：${AOCC_DIR}/bin/clang"
    exit 1
fi

if [ ! -x "${AOCC_DIR}/bin/clang++" ]; then
    echo "[ERROR] 未找到 clang++：${AOCC_DIR}/bin/clang++"
    exit 1
fi

if [ ! -x "${AOCC_DIR}/bin/flang" ]; then
    echo "[ERROR] 未找到 flang：${AOCC_DIR}/bin/flang"
    exit 1
fi

if [ "${FORCE_REBUILD}" = "1" ]; then
    echo "[WARN] FORCE_REBUILD=1，删除已有 OpenMPI 安装目录：${OPENMPI_DIR}"
    rm -rf "${OPENMPI_DIR}"
fi

if [ -x "${OPENMPI_DIR}/bin/mpicc" ] && [ "${FORCE_REBUILD}" != "1" ]; then
    echo "[INFO] OpenMPI 已存在，跳过编译：${OPENMPI_DIR}"
else
    cd "${DOWNLOAD_DIR}"

    rm -rf "${OPENMPI_SRC_DIR}"
    tar xzf "${OPENMPI_FILE}"
    cd "${OPENMPI_SRC_DIR}"

    echo "[INFO] 加载 AOCC 环境：${AOCC_ENV}"
    source "${AOCC_ENV}"

    echo "[INFO] 加载 AOCL 环境：${AOCL_ENV}"
    source "${AOCL_ENV}"

    unset CC
    unset CXX
    unset FC
    unset F77
    unset CFLAGS
    unset CXXFLAGS
    unset FCFLAGS
    unset FFLAGS

    GCC_LIBSTDCPP="$(gcc -print-file-name=libstdc++.so 2>/dev/null || true)"
    if [ -n "${GCC_LIBSTDCPP}" ] && [ "${GCC_LIBSTDCPP}" != "libstdc++.so" ]; then
        GCC_LIB_DIR="$(dirname "${GCC_LIBSTDCPP}")"
        export LDFLAGS="-L${GCC_LIB_DIR} ${LDFLAGS:-}"
        echo "[INFO] LDFLAGS=${LDFLAGS}"
    fi

    export CXXFLAGS="--gcc-toolchain=/usr ${CXXFLAGS:-}"
    echo "[INFO] CXXFLAGS=${CXXFLAGS}"

    echo
    echo "[INFO] configure OpenMPI"

    ./configure \
        CC="${AOCC_DIR}/bin/clang" \
        CXX="${AOCC_DIR}/bin/clang++" \
        FC="${AOCC_DIR}/bin/flang" \
        F77="${AOCC_DIR}/bin/flang" \
        --prefix="${OPENMPI_DIR}" \
        --enable-mpi-fortran=all

    echo
    echo "[INFO] make -j$(nproc)"
    make -j"$(nproc)"

    echo
    echo "[INFO] make install"
    make install
fi

echo
echo "============================================================"
echo "[7/8] 临时加载环境变量用于验证"
echo "============================================================"

source "${AOCC_ENV}"
source "${AOCL_ENV}"
export PATH="${OPENMPI_DIR}/bin:$PATH"

if [ -z "${LD_LIBRARY_PATH:-}" ]; then
    export LD_LIBRARY_PATH="${OPENMPI_DIR}/lib"
else
    export LD_LIBRARY_PATH="${OPENMPI_DIR}/lib:${LD_LIBRARY_PATH}"
fi

export OPAL_PREFIX="${OPENMPI_DIR}"

echo "[INFO] 当前脚本内环境变量已加载，仅用于验证"
echo "[INFO] 未写入 /etc/profile.d"
echo "[INFO] 未写入 ~/.bashrc"

echo
echo "============================================================"
echo "[8/8] 验证安装结果"
echo "============================================================"

echo
echo "[CHECK] AOCC 目录："
ls -ld "${AOCC_DIR}" || true

echo
echo "[CHECK] AOCL 目录："
ls -ld "${AOCL_DIR}" || true

echo
echo "[CHECK] OpenMPI 目录："
ls -ld "${OPENMPI_DIR}" || true

echo
echo "============================================================"
echo "[TEST] which 命令测试"
echo "============================================================"

echo "+ which clang"
which clang || true

echo
echo "+ which clang++"
which clang++ || true

echo
echo "+ which flang"
which flang || true

echo
echo "+ which mpicc"
which mpicc || true

echo
echo "+ which mpicxx"
which mpicxx || true

echo
echo "+ which mpif90"
which mpif90 || true

echo
echo "+ which mpirun"
which mpirun || true

echo
echo "============================================================"
echo "[TEST] version 命令测试"
echo "============================================================"

echo "+ clang --version"
clang --version || true

echo
echo "+ flang --version"
flang --version || true

echo
echo "+ mpirun --version"
mpirun --version || true

echo
echo "============================================================"
echo "[TEST] OpenMPI wrapper 测试"
echo "============================================================"

echo "+ mpicc --showme"
mpicc --showme || true

echo
echo "+ mpif90 --showme"
mpif90 --showme || true

echo
echo "============================================================"
echo "[DONE] OpenMPI + AOCC + AOCL 安装完成"
echo "============================================================"
echo
echo "本次下载源："
echo "  ${DOWNLOAD_SOURCE}"
echo
echo "安装包下载目录："
echo "  ${DOWNLOAD_DIR}"
echo
echo "AOCC 安装包："
echo "  ${DOWNLOAD_DIR}/${AOCC_FILE}"
echo
echo "AOCL 安装包："
echo "  ${DOWNLOAD_DIR}/${AOCL_FILE}"
echo
echo "OpenMPI 源码包："
echo "  ${DOWNLOAD_DIR}/${OPENMPI_FILE}"
echo
echo "AOCC 安装目录："
echo "  ${AOCC_DIR}"
echo
echo "AOCL 安装目录："
echo "  ${AOCL_DIR}"
echo
echo "OpenMPI 安装目录："
echo "  ${OPENMPI_DIR}"
echo
echo "当前脚本没有自动写入 /etc/profile.d 或 ~/.bashrc"
echo
echo "如需仅当前终端临时加载，请执行："
echo
echo "  source ${AOCC_ENV}"
echo "  source ${AOCL_ENV}"
echo "  export PATH=${OPENMPI_DIR}/bin:\$PATH"
echo "  export LD_LIBRARY_PATH=${OPENMPI_DIR}/lib:\$LD_LIBRARY_PATH"
echo "  export OPAL_PREFIX=${OPENMPI_DIR}"
echo
echo "如需当前用户永久加载 OpenMPI + AOCC + AOCL 环境，请手动执行："
echo
echo "  echo 'source ${AOCC_ENV}' >> ~/.bashrc"
echo "  echo 'source ${AOCL_ENV}' >> ~/.bashrc"
echo "  echo 'export PATH=${OPENMPI_DIR}/bin:\$PATH' >> ~/.bashrc"
echo "  echo 'export LD_LIBRARY_PATH=${OPENMPI_DIR}/lib:\$LD_LIBRARY_PATH' >> ~/.bashrc"
echo "  echo 'export OPAL_PREFIX=${OPENMPI_DIR}' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo
echo "如需验证环境，请执行："
echo
echo "  which clang"
echo "  which flang"
echo "  which mpicc"
echo "  which mpif90"
echo "  which mpirun"
echo "  mpirun --version"
echo "  mpicc --showme"
echo "  mpif90 --showme"
echo
echo "如需删除安装包和源码目录释放空间，请执行："
echo
echo "  sudo rm -rf ${DOWNLOAD_DIR}"

echo
echo "如需强制重新编译 OpenMPI，请执行："
echo
echo "  FORCE_REBUILD=1 sudo bash $0"
echo
echo "============================================================"

