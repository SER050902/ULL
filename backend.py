# backend.py
import time
import platform
import psutil

try:
    import GPUtil
except Exception:
    GPUtil = None

def _fmt_bytes(n):
    units = ["B","KB","MB","GB","TB","PB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024
        i += 1
    return f"{f:.2f} {units[i]}"

def get_system_overview():
    boot = psutil.boot_time()
    vm = psutil.virtual_memory()
    uptime = int(time.time() - boot)

    cpu = {
        "logical": psutil.cpu_count(True),
        "physical": psutil.cpu_count(False) or psutil.cpu_count(True),
        "usage_percent": psutil.cpu_percent(interval=0.5),
        "freq_current": (psutil.cpu_freq().current if psutil.cpu_freq() else None),
    }

    mem = {
        "total": _fmt_bytes(vm.total),
        "available": _fmt_bytes(vm.available),
        "used": _fmt_bytes(vm.used),
        "percent": vm.percent,
    }

    disks = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks.append({
                "device": p.device,
                "mount": p.mountpoint,
                "fstype": p.fstype,
                "total": _fmt_bytes(u.total),
                "used": _fmt_bytes(u.used),
                "free": _fmt_bytes(u.free),
                "percent": u.percent
            })
        except Exception:
            continue

    plat = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot)),
        "uptime_h": f"{uptime//3600}h {(uptime%3600)//60}m",
    }

    gpus = []
    if GPUtil:
        try:
            for g in GPUtil.getGPUs():
                gpus.append({
                    "name": g.name,
                    "memory_total": f"{g.memoryTotal} MB",
                    "memory_used": f"{g.memoryUsed} MB",
                    "load": f"{g.load*100:.1f}%",
                    "temperature": getattr(g, "temperature", None),
                })
        except Exception:
            pass

    return {"platform": plat, "cpu": cpu, "memory": mem, "disks": disks, "gpus": gpus}
