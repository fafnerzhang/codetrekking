#!/usr/bin/env python3
"""
Stop the development Celery worker.

This script finds and gracefully terminates the development Celery worker
process started by dev.py.
"""

import os
import sys
import signal
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stop_dev")


def find_celery_processes() -> List[dict]:
    """Find all running Celery worker processes."""
    try:
        # Use ps to find Celery processes
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            logger.error("Failed to list processes")
            return []

        processes = []
        for line in result.stdout.split('\n'):
            # Look for celery worker processes
            if 'celery' in line and 'worker' in line and 'peakflow_tasks' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        processes.append({
                            'pid': pid,
                            'cmdline': ' '.join(parts[10:])
                        })
                    except (ValueError, IndexError):
                        continue

        return processes

    except subprocess.TimeoutExpired:
        logger.error("Process listing timed out")
        return []
    except Exception as e:
        logger.error(f"Error finding processes: {e}")
        return []


def find_flower_processes() -> List[dict]:
    """Find all running Flower monitoring processes."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return []

        processes = []
        for line in result.stdout.split('\n'):
            if 'celery' in line and 'flower' in line and 'peakflow_tasks' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        processes.append({
                            'pid': pid,
                            'cmdline': ' '.join(parts[10:])
                        })
                    except (ValueError, IndexError):
                        continue

        return processes

    except Exception as e:
        logger.error(f"Error finding Flower processes: {e}")
        return []


def kill_process(pid: int, name: str = "process", force: bool = False) -> bool:
    """Kill a process by PID."""
    try:
        # First try graceful termination
        if not force:
            logger.info(f"🛑 Sending SIGTERM to {name} (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)

            # Wait for graceful shutdown
            for i in range(10):
                time.sleep(1)
                try:
                    # Check if process still exists
                    os.kill(pid, 0)
                except ProcessLookupError:
                    logger.info(f"✅ {name} (PID: {pid}) stopped gracefully")
                    return True

            logger.warning(f"⚠️  {name} (PID: {pid}) didn't stop gracefully")

        # Force kill
        logger.info(f"🔪 Sending SIGKILL to {name} (PID: {pid})...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)

        try:
            os.kill(pid, 0)
            logger.error(f"❌ Failed to kill {name} (PID: {pid})")
            return False
        except ProcessLookupError:
            logger.info(f"✅ {name} (PID: {pid}) terminated forcefully")
            return True

    except ProcessLookupError:
        logger.info(f"✅ {name} (PID: {pid}) already stopped")
        return True
    except PermissionError:
        logger.error(f"❌ Permission denied to kill {name} (PID: {pid})")
        return False
    except Exception as e:
        logger.error(f"❌ Error killing {name} (PID: {pid}): {e}")
        return False


def stop_all(force: bool = False) -> int:
    """Stop all development Celery processes."""
    logger.info("🔍 Searching for Celery development processes...")

    # Find all processes
    celery_processes = find_celery_processes()
    flower_processes = find_flower_processes()

    all_processes = celery_processes + flower_processes

    if not all_processes:
        logger.info("✅ No running Celery development processes found")
        return 0

    logger.info(f"Found {len(all_processes)} process(es) to stop:")
    for proc in all_processes:
        logger.info(f"  - PID {proc['pid']}: {proc['cmdline'][:80]}...")

    # Stop all processes
    success_count = 0
    for proc in all_processes:
        process_type = "Flower" if 'flower' in proc['cmdline'] else "Celery worker"
        if kill_process(proc['pid'], process_type, force):
            success_count += 1

    if success_count == len(all_processes):
        logger.info(f"✅ Successfully stopped {success_count} process(es)")
        return 0
    else:
        failed = len(all_processes) - success_count
        logger.warning(f"⚠️  Stopped {success_count} process(es), {failed} failed")
        return 1


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Stop development Celery worker and Flower processes"
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force kill processes immediately (SIGKILL)'
    )
    parser.add_argument(
        '--pid',
        type=int,
        help='Stop specific process by PID'
    )

    args = parser.parse_args()

    if args.pid:
        logger.info(f"Stopping process with PID {args.pid}...")
        success = kill_process(args.pid, "process", args.force)
        return 0 if success else 1
    else:
        return stop_all(args.force)


if __name__ == "__main__":
    sys.exit(main())
