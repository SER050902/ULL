# backend.py
import time
import platform
import psutil
import json
import subprocess as _sp
import platform as _plat
import sys

# ========= 你原来的：N 卡走 GPUtil =========
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

# ========= Windows：OS/CPU 友好名称 =========
def _win_os_cpu_pretty():
    """
    返回 dict:
      os_product: Windows 10 Pro
      os_display: 23H2 或 None
      os_build:   19045 等
      cpu_brand:  Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz
    全部纯系统自带能力，无额外依赖。
    """
    if _plat.system() != "Windows":
        return {}

    # 1) 读注册表拿 OS 版本与显示版本
    os_product = None
    os_display = None
    os_build = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            try:
                os_product = winreg.QueryValueEx(k, "ProductName")[0]       # Windows 10 Pro
            except Exception:
                pass
            # 23H2 在 DisplayVersion；老版本在 ReleaseId
            try:
                os_display = winreg.QueryValueEx(k, "DisplayVersion")[0]   # 23H2
            except Exception:
                try:
                    os_display = winreg.QueryValueEx(k, "ReleaseId")[0]    # 2009 等
                except Exception:
                    pass
            try:
                os_build = winreg.QueryValueEx(k, "CurrentBuild")[0]       # 19045
            except Exception:
                pass
    except Exception:
        # 注册表失败就退化到 powershell
        os_product = None
        os_display = None
        os_build = None

    # 2) CPU 友好名称：注册表 ProcessorNameString
    cpu_brand = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            cpu_brand = winreg.QueryValueEx(k, "ProcessorNameString")[0]
    except Exception:
        # 兜底：仍然可用 platform.processor()
        cpu_brand = platform.processor() or None

    out = {}
    if os_product: out["os_product"] = os_product
    if os_display: out["os_display"] = os_display
    if os_build:   out["os_build"]   = os_build
    if cpu_brand:  out["cpu_brand"]  = cpu_brand
    return out

# ========= Windows：GPU（Intel/AMD/NVIDIA） =========
def _ps_run(ps_script: str, timeout=2.5) -> str:
    try:
        out = _sp.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stderr=_sp.DEVNULL, timeout=timeout
        )
        return out.decode("utf-8", "ignore").strip()
    except Exception:
        return ""

def _win_gpu_wmi_basic():
    # 优先 CIM
    ps = r'''
$gpus = Get-CimInstance Win32_VideoController |
    Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID
$gpus | ConvertTo-Json -Compress
'''
    txt = _ps_run(ps)
    if not txt:
        # 退化到旧的 WMI
        ps2 = r'''
$gpus = Get-WmiObject Win32_VideoController |
    Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID
$gpus | ConvertTo-Json -Compress
'''
        txt = _ps_run(ps2)
    if not txt:
        # 再退到 wmic（部分系统仍可用）
        txt_wmic = _ps_run(r"wmic path win32_VideoController get Name,AdapterRAM,DriverVersion /format:list")
        if txt_wmic:
            blocks = [b for b in txt_wmic.split("\n\n") if "Name=" in b]
            res = []
            for b in blocks:
                d = {}
                for line in b.splitlines():
                    if "=" in line:
                        k,v = line.split("=",1)
                        d[k.strip()] = v.strip()
                if d:
                    res.append({
                        "Name": d.get("Name"),
                        "AdapterRAM": int(d["AdapterRAM"]) if d.get("AdapterRAM","").isdigit() else None,
                        "DriverVersion": d.get("DriverVersion"),
                        "PNPDeviceID": None
                    })
            return _normalize_wmi_list(res)
        return []  # 全部失败

    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            data = [data]
        return _normalize_wmi_list(data)
    except Exception:
        return []

def _normalize_wmi_list(data_list):
    out = []
    for d in data_list or []:
        name = (d.get("Name") or "").strip()
        vendor = "Unknown"
        n_low = name.lower()
        if "nvidia" in n_low:
            vendor = "NVIDIA"
        elif "amd" in n_low or "advanced micro devices" in n_low or "ati" in n_low:
            vendor = "AMD"
        elif "intel" in n_low:
            vendor = "Intel"
        mem = d.get("AdapterRAM")
        mem_mb = f"{int(mem)//(1024*1024)} MB" if isinstance(mem, int) and mem > 0 else None
        item = {
            "name": name or "GPU",
            "vendor": vendor,
            "memory_total": mem_mb,
            "memory_used": None,
            "load": None,
            "temperature": None,
            "notes": []
        }
        drv = d.get("DriverVersion")
        if drv:
            item["notes"].append(f"Driver {drv}")
        out.append(item)
    return out

def _win_gpu_load_perf():
    ps = r'''
$cs = Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -SampleInterval 1 -MaxSamples 1
$avg = ($cs.CounterSamples | Measure-Object CookedValue -Average).Average
if ($avg -ne $null) { [math]::Round($avg,1) } else { "" }
'''
    txt = _ps_run(ps, timeout=3.0)
    if not txt:
        return None
    try:
        return f"{float(txt):.1f}%"
    except Exception:
        return None

def _collect_gpus_windows():
    basics = _win_gpu_wmi_basic()
    load = _win_gpu_load_perf()
    out = []
    for b in basics:
        item = dict(b)
        if load and not item.get("load"):
            item["load"] = load
        out.append(item)
    return out

# ========= 主函数 =========
def get_system_overview():
    boot = psutil.boot_time()
    vm = psutil.virtual_memory()
    uptime = int(time.time() - boot)

    # CPU
    cpu = {
        "logical": psutil.cpu_count(True),
        "physical": psutil.cpu_count(False) or psutil.cpu_count(True),
        "usage_percent": psutil.cpu_percent(interval=0.5),
        "freq_current": (psutil.cpu_freq().current if psutil.cpu_freq() else None),
    }

    # 内存
    mem = {
        "total": _fmt_bytes(vm.total),
        "available": _fmt_bytes(vm.available),
        "used": _fmt_bytes(vm.used),
        "percent": vm.percent,
    }

    # 磁盘
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

    # 平台
    plat = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot)),
        "uptime_h": f"{uptime//3600}h {(uptime%3600)//60}m",
    }

    # Windows 上补充更友好的 OS/CPU 名称
    win_extra = _win_os_cpu_pretty() if _plat.system() == "Windows" else {}
    if win_extra:
        plat.update(win_extra)

    # GPU：先走 GPUtil（N 卡最准）
    gpus = []
    if GPUtil:
        try:
            for g in GPUtil.getGPUs():
                gpus.append({
                    "name": g.name,
                    "vendor": "NVIDIA",
                    "memory_total": f"{g.memoryTotal} MB",
                    "memory_used": f"{g.memoryUsed} MB",
                    "load": f"{g.load*100:.1f}%",
                    "temperature": getattr(g, "temperature", None),
                    "notes": []
                })
        except Exception:
            pass

    # Windows 再补 Intel/AMD（或没被 GPUtil覆盖的 NVIDIA）
    if _plat.system() == "Windows":
        try:
            win_gpus = _collect_gpus_windows()
            known = {g.get("name") for g in gpus}
            for w in win_gpus:
                if w.get("name") not in known:
                    gpus.append(w)
        except Exception:
            pass

    return {"platform": plat, "cpu": cpu, "memory": mem, "disks": disks, "gpus": gpus}
