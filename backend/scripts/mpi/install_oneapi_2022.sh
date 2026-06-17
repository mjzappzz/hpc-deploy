#!/bin/bash
set -e

# ============================================================
# Intel oneAPI 2022 Offline Auto Installer
# BaseKit + HPCKit
#
# Install Path:
#   /opt/ohpc/pub/intel/oneapi/2022
#
# Download Path:
#   /tmp/oneapi_install_2022
#
# Download Policy:
#   1. 先 ping 内网 IP：192.168.130.5
#   2. 内网可达：使用内网地址下载
#   3. 内网不可达：使用公网地址下载
#
# Components:
#   BaseKit: MKL
#   HPCKit : DPC++/C++ Compiler, Fortran Compiler, Intel MPI
# ============================================================

INNER_IP="192.168.130.5"

BASEKIT_INNER_URL="http://192.168.130.5:2437/chfs/shared%2F%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6/%E7%BC%96%E8%AF%91%E5%99%A8/intel/2022/l_BaseKit_p_2022.1.2.146_offline.sh"
HPCKIT_INNER_URL="http://192.168.130.5:2437/chfs/shared%2F%E8%B6%85%E7%AE%97%E8%BD%AF%E4%BB%B6/%E7%BC%96%E8%AF%91%E5%99%A8/intel/2022/l_HPCKit_p_2022.1.2.117_offline.sh"

BASEKIT_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/intel/l_BaseKit_p_2022.1.2.146_offline.sh"
HPCKIT_PUBLIC_URL="http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/intel/l_HPCKit_p_2022.1.2.117_offline.sh"

BASEKIT_FILE="l_BaseKit_p_2022.1.2.146_offline.sh"
HPCKIT_FILE="l_HPCKit_p_2022.1.2.117_offline.sh"

DOWNLOAD_DIR="/tmp/oneapi_install_2022"
INSTALL_DIR="/opt/ohpc/pub/intel/oneapi/2022"
MKL_DIR="${INSTALL_DIR}/mkl/latest"

BASEKIT_COMPONENTS="intel.oneapi.lin.mkl.devel"
HPCKIT_COMPONENTS="intel.oneapi.lin.dpcpp-cpp-compiler-pro:intel.oneapi.lin.ifort-compiler:intel.oneapi.lin.mpi.devel"

echo "============================================================"
echo " Intel oneAPI 2022 Offline Installer"
echo "============================================================"
echo "下载目录：${DOWNLOAD_DIR}"
echo "安装目录：${INSTALL_DIR}"
echo "MKL 目录：${MKL_DIR}"
echo "============================================================"

# 必须 root 执行
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] 请使用 root 执行："
    echo "        sudo bash $0"
    exit 1
fi

# 检查基础命令
for cmd in wget bash ping; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[ERROR] 缺少命令：$cmd"
        echo
        echo "Rocky/CentOS 可执行："
        echo "    yum install -y wget iputils"
        echo
        echo "Ubuntu/Debian 可执行："
        echo "    apt install -y wget iputils-ping"
        exit 1
    fi
done

# 创建目录
mkdir -p "${DOWNLOAD_DIR}"
mkdir -p "${INSTALL_DIR}"

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
        chmod +x "${file}"
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
    chmod +x "${file}"

    echo "[INFO] ${name} 下载完成：${DOWNLOAD_DIR}/${file}"
}

echo
echo "============================================================"
echo "[1/7] 检测下载源"
echo "============================================================"

echo "[INFO] 检测内网 IP 是否可达：${INNER_IP}"

if ping -c 2 -W 2 "${INNER_IP}" >/dev/null 2>&1; then
    echo "[INFO] 内网可达，使用内网下载地址"
    BASEKIT_URL="${BASEKIT_INNER_URL}"
    HPCKIT_URL="${HPCKIT_INNER_URL}"
    DOWNLOAD_SOURCE="内网"
else
    echo "[WARN] 内网不可达，使用公网下载地址"
    BASEKIT_URL="${BASEKIT_PUBLIC_URL}"
    HPCKIT_URL="${HPCKIT_PUBLIC_URL}"
    DOWNLOAD_SOURCE="公网"
fi

echo
echo "[INFO] 当前下载源：${DOWNLOAD_SOURCE}"
echo "[INFO] BaseKit 下载地址：${BASEKIT_URL}"
echo "[INFO] HPCKit  下载地址：${HPCKIT_URL}"

echo
echo "============================================================"
echo "[2/7] 下载 oneAPI 离线安装包"
echo "============================================================"

download_file "BaseKit" "${BASEKIT_FILE}" "${BASEKIT_URL}"
download_file "HPCKit" "${HPCKIT_FILE}" "${HPCKIT_URL}"

echo
echo "============================================================"
echo "[3/7] 检查安装包"
echo "============================================================"

if [ ! -s "${BASEKIT_FILE}" ]; then
    echo "[ERROR] BaseKit 文件不存在或为空：${DOWNLOAD_DIR}/${BASEKIT_FILE}"
    exit 1
fi

if [ ! -s "${HPCKIT_FILE}" ]; then
    echo "[ERROR] HPCKit 文件不存在或为空：${DOWNLOAD_DIR}/${HPCKIT_FILE}"
    exit 1
fi

chmod +x "${BASEKIT_FILE}" "${HPCKIT_FILE}"

echo "[INFO] BaseKit OK：${DOWNLOAD_DIR}/${BASEKIT_FILE}"
echo "[INFO] HPCKit  OK：${DOWNLOAD_DIR}/${HPCKIT_FILE}"

echo
echo "============================================================"
echo "[4/7] 安装 BaseKit：MKL"
echo "============================================================"

bash "${BASEKIT_FILE}" \
    -a --action install \
    --components "${BASEKIT_COMPONENTS}" \
    -s --eula accept \
    --install-dir "${INSTALL_DIR}"

echo
echo "============================================================"
echo "[5/7] 安装 HPCKit：C/C++、Fortran、Intel MPI"
echo "============================================================"

bash "${HPCKIT_FILE}" \
    -a --action install \
    --components "${HPCKIT_COMPONENTS}" \
    -s --eula accept \
    --install-dir "${INSTALL_DIR}"

echo
echo "============================================================"
echo "[6/7] 临时加载 oneAPI 环境变量用于验证"
echo "============================================================"

if [ -f "${INSTALL_DIR}/setvars.sh" ]; then
    source "${INSTALL_DIR}/setvars.sh" --force
else
    echo "[ERROR] 未找到 setvars.sh：${INSTALL_DIR}/setvars.sh"
    exit 1
fi

echo
echo "============================================================"
echo "[7/7] 验证安装结果"
echo "============================================================"

echo
echo "[CHECK] oneAPI 安装目录："
ls -ld "${INSTALL_DIR}" || true

echo
echo "[CHECK] setvars.sh："
ls -l "${INSTALL_DIR}/setvars.sh" || true

echo
echo "[CHECK] MKL 目录："
if [ -d "${MKL_DIR}" ]; then
    echo "MKL OK：${MKL_DIR}"
else
    echo "[WARN] 未找到 MKL 目录：${MKL_DIR}"
fi

echo
echo "============================================================"
echo "[TEST] which 命令测试"
echo "============================================================"

echo "+ which icc"
which icc || true

echo
echo "+ which icx"
which icx || true

echo
echo "+ which ifort"
which ifort || true

echo
echo "+ which mpiicc"
which mpiicc || true

echo
echo "+ which mpiifort"
which mpiifort || true

echo
echo "+ which mpirun"
which mpirun || true

echo
echo "============================================================"
echo "[TEST] version 命令测试"
echo "============================================================"

echo "+ icc --version"
icc --version || true

echo
echo "+ ifort --version"
ifort --version || true

echo
echo "+ mpirun --version"
mpirun --version || true

echo
echo "============================================================"
echo "[DONE] Intel oneAPI 2022 安装完成"
echo "============================================================"
echo
echo "本次下载源："
echo "  ${DOWNLOAD_SOURCE}"
echo
echo "安装包下载目录："
echo "  ${DOWNLOAD_DIR}"
echo
echo "BaseKit 安装包："
echo "  ${DOWNLOAD_DIR}/${BASEKIT_FILE}"
echo
echo "HPCKit 安装包："
echo "  ${DOWNLOAD_DIR}/${HPCKIT_FILE}"
echo
echo "oneAPI 安装目录："
echo "  ${INSTALL_DIR}"
echo
echo "MKL 目录："
echo "  ${MKL_DIR}"
echo
echo "当前脚本没有自动写入 ~/.bashrc"
echo
echo "如需当前用户永久加载 oneAPI 环境，请手动执行："
echo
echo "  echo 'source ${INSTALL_DIR}/setvars.sh --force' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo
echo "如需仅当前终端临时加载，请执行："
echo
echo "  source ${INSTALL_DIR}/setvars.sh --force"
echo
echo "如需删除安装包释放空间，请执行："
echo
echo "  sudo rm -rf ${DOWNLOAD_DIR}"
echo
echo "============================================================"
