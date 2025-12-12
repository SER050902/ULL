# backend.py
import time
import platform
import psutil
import json
import socket
import subprocess as _sp
import platform as _plat
import sys
import os
import string

# ========= 可选：requests 用来查公网 IP =========
try:
    import requests
except Exception:
    requests = None

# ========= 你原来的：N 卡走 GPUtil =========
try:
    import GPUtil
except Exception:
    GPUtil = None


def _fmt_bytes(n):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.2f} {units[i]}"


# ========= Windows：OS/CPU 友好名称 =========
def _win_os_cpu_pretty():
    """
    只在 Windows 用，返回:
      os_product: Windows 10 Pro
      os_display: 23H2 / 22H2 / ...
      os_build:   19045
      cpu_brand:  Intel(R) ...
    """
    if _plat.system() != "Windows":
        return {}

    os_product = None
    os_display = None
    os_build = None

    # 读注册表拿 OS 信息
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            try:
                os_product = winreg.QueryValueEx(k, "ProductName")[0]
            except Exception:
                pass
            try:
                os_display = winreg.QueryValueEx(k, "DisplayVersion")[0]
            except Exception:
                try:
                    os_display = winreg.QueryValueEx(k, "ReleaseId")[0]
                except Exception:
                    pass
            try:
                os_build = winreg.QueryValueEx(k, "CurrentBuild")[0]
            except Exception:
                pass
    except Exception:
        os_product = None
        os_display = None
        os_build = None

    # CPU 友好名称
    cpu_brand = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            cpu_brand = winreg.QueryValueEx(k, "ProcessorNameString")[0]
    except Exception:
        cpu_brand = platform.processor() or None

    out = {}
    if os_product:
        out["os_product"] = os_product
    if os_display:
        out["os_display"] = os_display
    if os_build:
        out["os_build"] = os_build
    if cpu_brand:
        out["cpu_brand"] = cpu_brand
    return out


# ========= Windows：GPU（Intel/AMD/NVIDIA） =========
def _ps_run(ps_script: str, timeout=2.5) -> str:
    try:
        out = _sp.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stderr=_sp.DEVNULL,
            timeout=timeout,
        )
        return out.decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def _win_gpu_wmi_basic():
    ps = r'''
$gpus = Get-CimInstance Win32_VideoController |
    Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID
$gpus | ConvertTo-Json -Compress
'''
    txt = _ps_run(ps)
    if not txt:
        ps2 = r'''
$gpus = Get-WmiObject Win32_VideoController |
    Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID
$gpus | ConvertTo-Json -Compress
'''
        txt = _ps_run(ps2)
    if not txt:
        return []

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
            "notes": [],
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


# ========= 系统总览 =========
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
                "percent": u.percent,
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
        "uptime_h": f"{uptime // 3600}h {(uptime % 3600) // 60}m",
    }

    win_extra = _win_os_cpu_pretty() if _plat.system() == "Windows" else {}
    if win_extra:
        plat.update(win_extra)

    # GPU
    gpus = []
    if GPUtil:
        try:
            for g in GPUtil.getGPUs():
                gpus.append({
                    "name": g.name,
                    "vendor": "NVIDIA",
                    "memory_total": f"{g.memoryTotal} MB",
                    "memory_used": f"{g.memoryUsed} MB",
                    "load": f"{g.load * 100:.1f}%",
                    "temperature": getattr(g, "temperature", None),
                    "notes": [],
                })
        except Exception:
            pass

    if _plat.system() == "Windows":
        try:
            win_gpus = _collect_gpus_windows()
            known = {g.get("name") for g in gpus}
            for w in win_gpus:
                if w.get("name") not in known:
                    gpus.append(w)
        except Exception:
            pass

    return {
        "platform": plat,
        "cpu": cpu,
        "memory": mem,
        "disks": disks,
        "gpus": gpus,
    }


# ========= 网络部分 =========

def _get_public_ip():
    """尝试获取公网 IP，尽量简单粗暴。"""
    # 优先 requests
    if requests is not None:
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
            try:
                r = requests.get(url, timeout=3)
                ip = r.text.strip()
                if ip:
                    return ip
            except Exception:
                continue
    # 备用：urllib
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=3) as resp:
            ip = resp.read().decode().strip()
            if ip:
                return ip
    except Exception:
        pass
    return None


def _is_private_ipv4(ip: str) -> bool:
    if not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        p0 = int(parts[0])
        p1 = int(parts[1])
    except ValueError:
        return False

    # 10.0.0.0/8
    if p0 == 10:
        return True
    # 172.16.0.0 ~ 172.31.0.0
    if p0 == 172 and 16 <= p1 <= 31:
        return True
    # 192.168.0.0/16
    if p0 == 192 and p1 == 168:
        return True
    return False


def get_network_overview():
    """
    返回结构大概：
    {
      "public_ip": "...",
      "lan_ip": "...",
      "interfaces": [
         {"name": "...", "ipv4": "...", "ipv6": "...", "is_up": True, "speed": 1000}
      ],
      "listeners": [
         {"laddr_ip": "0.0.0.0", "laddr_port": 8000, "pid": 1234, "process": "python", "status": "LISTEN"}
      ]
    }
    """
    # 公网 IP
    public_ip = _get_public_ip()

    # 网卡信息
    if_addrs = psutil.net_if_addrs()
    if_stats = psutil.net_if_stats()

    interfaces = []
    candidate_lan_ips = []

    for name, addrs in if_addrs.items():
        ipv4 = None
        ipv6 = None
        for a in addrs:
            if a.family == socket.AF_INET:
                ipv4 = a.address
                if _is_private_ipv4(ipv4):
                    candidate_lan_ips.append(ipv4)
            elif a.family == socket.AF_INET6:
                ipv6 = a.address.split("%")[0]  # 去掉 scope_id

        st = if_stats.get(name)
        is_up = st.isup if st else False
        speed = st.speed if st and st.speed > 0 else None

        interfaces.append({
            "name": name,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "is_up": is_up,
            "speed": speed,
        })

    # 选一个“主”局域网 IP
    lan_ip = candidate_lan_ips[0] if candidate_lan_ips else None

    # 监听端口信息
    listeners = []
    try:
        conns = psutil.net_connections(kind="inet")
        for c in conns:
            if c.status != psutil.CONN_LISTEN:
                continue
            laddr_ip = c.laddr.ip if c.laddr else ""
            laddr_port = c.laddr.port if c.laddr else None
            pid = c.pid
            pname = None
            if pid:
                try:
                    pname = psutil.Process(pid).name()
                except Exception:
                    pname = None
            listeners.append({
                "laddr_ip": laddr_ip,
                "laddr_port": laddr_port,
                "pid": pid,
                "process": pname or "unknown",
                "status": "LISTEN",
            })
    except Exception:
        listeners = []

    # 为了在 Jinja 里好用，返回 dict
    return {
        "public_ip": public_ip,
        "lan_ip": lan_ip,
        "interfaces": interfaces,
        "listeners": listeners,
    }

from pathlib import Path
from werkzeug.utils import secure_filename

from pathlib import Path

def _safe_join(root: str, rel: str) -> Path:
    r"""
    支持：
    - rel == ""        → 虚拟根（盘符视图）
    - rel == "C:"      → C:\
    - rel == "C:/xx"   → C:\xx
    """
    if not rel:
        raise ValueError("Virtual root")

    rel = (rel or "").replace("\\", "/").strip("/")

    if len(rel) >= 2 and rel[1] == ":":
        return Path(rel.replace("/", "\\") + "\\").resolve()

    root_path = Path(root).resolve()
    target = (root_path / rel).resolve()
    if root_path != target and root_path not in target.parents:
        raise ValueError("Unsafe path")
    return target

def list_dir(root: str, rel: str = ""):
    # 👉 空路径：返回盘符
    if not rel:
        return list_roots_windows()

    p = _safe_join(root, rel)

    if not p.exists():
        raise FileNotFoundError("Path not found")
    if not p.is_dir():
        raise NotADirectoryError("Not a directory")

    items = []
    for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        try:
            stat = child.stat()
            items.append({
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": stat.st_size if child.is_file() else None,
                "mtime": stat.st_mtime,
            })
        except Exception:
            items.append({
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": None,
                "mtime": None,
            })
    return items

def delete_path(root: str, rel: str):
    p = _safe_join(root, rel)
    if not p.exists():
        return
    if p.is_dir():
        # 只允许删空目录（更安全）
        p.rmdir()
    else:
        p.unlink()

def make_dir(root: str, rel_dir: str, name: str):
    base = _safe_join(root, rel_dir)
    base.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(name) or name  # 中文名 secure_filename 可能变空，这里保底
    target = (base / safe)
    target.mkdir(exist_ok=False)

def rename_path(root: str, rel: str, new_name: str):
    p = _safe_join(root, rel)
    if not p.exists():
        raise FileNotFoundError("Not found")
    safe = secure_filename(new_name) or new_name
    newp = p.parent / safe
    p.rename(newp)

def save_upload(root: str, rel_dir: str, file_storage):
    base = _safe_join(root, rel_dir)
    base.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file_storage.filename) or file_storage.filename
    if not filename:
        raise ValueError("Empty filename")
    dst = (base / filename)
    file_storage.save(str(dst))
    return filename

def build_breadcrumbs(rel: str):
    rel = (rel or "").replace("\\", "/").strip("/")
    crumbs = []
    if not rel:
        return crumbs
    parts = rel.split("/")
    acc = []
    for part in parts:
        acc.append(part)
        crumbs.append({"name": part, "path": "/".join(acc)})
    return crumbs


def list_roots_windows():
    """返回 Windows 盘符列表，如 C:, D:"""
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:"
        if os.path.exists(drive + "\\"):
            drives.append({
                "name": drive,
                "is_dir": True,
                "size": None,
                "mtime": None,
            })
    return drives
