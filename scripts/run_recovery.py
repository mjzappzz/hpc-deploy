#!/usr/bin/env python3
"""Run recovery monitor for stuck stress task."""
import sys, os
sys.path.insert(0, '/home/tjzs/projects/hpc-deploy/backend')
os.chdir('/home/tjzs/projects/hpc-deploy/backend')

from app.core.task_runner import _stress_recovery_monitor
import logging
logging.basicConfig(level=logging.INFO)

print("[recovery] Starting...")
_stress_recovery_monitor('task-20260710-180550-6f2b4f')
print("[recovery] Done")
