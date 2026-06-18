#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] MPI/Compiler test script"
echo "[INFO] hostname: $(hostname)"
echo "[INFO] user: $(whoami)"
echo "[INFO] pwd: $(pwd)"

echo "[INFO] gcc:"
which gcc || true
gcc --version | head -1 || true

echo "[INFO] g++:"
which g++ || true
g++ --version | head -1 || true

echo "[INFO] gfortran:"
which gfortran || true
gfortran --version | head -1 || true

echo "[INFO] mpirun:"
which mpirun || true
mpirun --version | head -2 || true

echo "[OK] mpi env test finished"
