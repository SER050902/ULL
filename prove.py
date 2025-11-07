import GPUtil
import psutil
import ifaddr

# CPU
print("CPU cores:", psutil.cpu_count(logical=True))
print("CPU usage (%):", psutil.cpu_percent(interval=1))

# Memory
mem = psutil.virtual_memory()
print(f"Total memory: {mem.total / 1e9:.2f} GB")
print(f"Available memory: {mem.available / 1e9:.2f} GB")

partitions = psutil.disk_partitions()

print("Disk Partitions and Usage:\n")

for partition in partitions:
    print(f"Device: {partition.device}")
    print(f"File system type: {partition.fstype}")
    usage = psutil.disk_usage(partition.mountpoint)
    print(f"  Total Size: {usage.total / (1024**3):.2f} GB")
    print(f"  Used: {usage.used / (1024**3):.2f} GB")
    print(f"  Free: {usage.free / (1024**3):.2f} GB")
    print(f"  Usage: {usage.percent}%\n")

gpus = GPUtil.getGPUs()
for gpu in gpus:
    print(f"GPU: {gpu.name}")
    print(f"Memory Total: {gpu.memoryTotal}MB")
    print(f"Memory Used: {gpu.memoryUsed}MB")
    print(f"Load: {gpu.load * 100:.1f}%")

#print(psutil.net_io_counters())
#print(psutil.net_connections())

adapters = ifaddr.get_adapters()

for adapter in adapters:
    print(f"adapters:{adapter.nice_name}({adapter.name})")
    for ip in adapter.ips:
        print(f"ip",ip.ip)