import assert from 'node:assert/strict'
import test from 'node:test'

import { formatCpuHardware, formatGpuHardware } from './serverHardware.ts'

test('formats CPU model and core count as separate hierarchy levels', () => {
  assert.deepEqual(
    formatCpuHardware('Intel(R) Xeon(R) Gold 6430 / 64C'),
    {
      title: 'Intel(R) Xeon(R) Gold 6430',
      meta: ['64 核'],
      fullText: 'Intel(R) Xeon(R) Gold 6430 / 64C',
      tone: 'default',
    },
  )
})

test('keeps legacy localized CPU probe values readable', () => {
  assert.deepEqual(
    formatCpuHardware('Model name: AMD EPYC 9654 CPU(s): 192'),
    {
      title: 'AMD EPYC 9654',
      meta: ['192 核'],
      fullText: 'Model name: AMD EPYC 9654 CPU(s): 192',
      tone: 'default',
    },
  )
})

test('formats GPU models separately from driver and CUDA metadata', () => {
  assert.deepEqual(
    formatGpuHardware('NVIDIA GeForce RTX 4090 x8 / Driver 590.48.01 / CUDA 12.8', 'driver_ok'),
    {
      title: 'NVIDIA GeForce RTX 4090 × 8',
      meta: ['驱动 590.48.01', 'CUDA 12.8'],
      fullText: 'NVIDIA GeForce RTX 4090 x8 / Driver 590.48.01 / CUDA 12.8',
      tone: 'default',
    },
  )
})

test('preserves multiple GPU models without mixing them with software metadata', () => {
  const hardware = formatGpuHardware(
    'NVIDIA GeForce RTX 4090 x5 / NVIDIA RTX 6000 Ada Generation x1 / Driver 550.90.07 / CUDA 12.4',
    'driver_ok',
  )

  assert.deepEqual(
    hardware,
    {
      title: 'NVIDIA GeForce RTX 4090 × 5\nNVIDIA RTX 6000 Ada Generation × 1',
      meta: ['驱动 550.90.07', 'CUDA 12.4'],
      fullText: 'NVIDIA GeForce RTX 4090 x5 / NVIDIA RTX 6000 Ada Generation x1 / Driver 550.90.07 / CUDA 12.4',
      tone: 'default',
    },
  )
})

test('uses explicit text states for missing GPU and unavailable driver', () => {
  assert.deepEqual(
    formatGpuHardware('无 NVIDIA GPU', 'none'),
    {
      title: '无 NVIDIA GPU',
      meta: [],
      fullText: '无 NVIDIA GPU',
      tone: 'muted',
    },
  )
  assert.deepEqual(
    formatGpuHardware('检测到 NVIDIA GPU，驱动不可用或 nvidia-smi 不存在', 'hardware_only'),
    {
      title: '检测到 NVIDIA GPU',
      meta: ['驱动不可用或 nvidia-smi 不存在'],
      fullText: '检测到 NVIDIA GPU，驱动不可用或 nvidia-smi 不存在',
      tone: 'warning',
    },
  )
})
