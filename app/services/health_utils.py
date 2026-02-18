import time
import os
from typing import Dict, Any

def collect_system_metrics() -> Dict[str, Any]:
    """Collect lightweight system metrics. Uses psutil if available,
    otherwise returns fallback None values."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        boot = psutil.boot_time()
        uptime = time.time() - boot
        return {
            "system_memory_usage_mb": int(mem.used / 1024 / 1024),
            "system_cpu_usage_percent": float(cpu),
            "uptime_seconds": int(uptime),
        }
    except Exception:
        # Fallbacks when psutil not available
        try:
            # approximate uptime via /proc on Unix
            if os.name == 'posix' and os.path.exists('/proc/uptime'):
                with open('/proc/uptime', 'r') as f:
                    uptime = float(f.readline().split()[0])
            else:
                uptime = None
        except Exception:
            uptime = None

        return {
            "system_memory_usage_mb": None,
            "system_cpu_usage_percent": None,
            "uptime_seconds": uptime,
        }
