# SPDX-License-Identifier: GPL-3.0-or-later
# Custom sensors ES multipistaforma. Ver docs/SENSORES-ES.md
from __future__ import annotations
import math, os, platform, subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple

class CustomDataSource(ABC):
    @abstractmethod
    def as_numeric(self) -> float: pass
    @abstractmethod
    def as_string(self) -> str: pass
    @abstractmethod
    def last_values(self) -> List[float]: pass

class ExampleCustomNumericData(CustomDataSource):
    last_val = [math.nan] * 10
    def as_numeric(self) -> float:
        self.value = 75.845; self.last_val.append(self.value); self.last_val.pop(0); return self.value
    def as_string(self) -> str: return f"{self.value:>5.1f}%"
    def last_values(self) -> List[float]: return self.last_val

class ExampleCustomTextOnlyData(CustomDataSource):
    def as_numeric(self) -> float: return math.nan
    def as_string(self) -> str: return "Python: " + platform.python_version()
    def last_values(self) -> List[float]: return []

_cache = {"ts": 0.0}
def _now():
    import time; return time.time()
def _shorten(name: str, max_len: int = 28) -> str:
    name = (name or "").strip()
    if not name: return "-"
    for p in ("AMD ", "Intel(R) ", "Intel ", "NVIDIA ", "NVIDIA GeForce ", "GeForce "):
        if name.startswith(p): name = name[len(p):]; break
    name = name.replace("(R)", "").replace("(TM)", "").replace("  ", " ").strip()
    return name if len(name) <= max_len else name[:max_len-1] + "..."
def _read_text(path: str):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f: return f.read().strip()
    except Exception: return None

def _linux_cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                low = line.lower()
                if low.startswith("model name") or low.startswith("hardware"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "CPU"

def _linux_gpu_model() -> str:
    try:
        out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, text=True, timeout=2)
        for line in out.splitlines():
            low = line.lower()
            if "vga" in low or "3d" in low or "display" in low:
                return line.split(": ", 1)[1].strip() if ": " in line else line.strip()
    except Exception:
        pass
    return ""

def _linux_ram_info() -> Tuple[str, float]:
    total = 0.0
    try:
        import psutil
        total = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    label = f"{total:.0f} GB" if total else "RAM"
    try:
        meminfo = _read_text("/proc/meminfo") or ""
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                total = kb / (1024 ** 2)
                label = f"{total:.0f} GB"
                break
    except Exception:
        pass
    return label, total

def _linux_disk_info() -> str:
    try:
        base = "/sys/class/nvme"
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                model = _read_text(os.path.join(base, name, "model"))
                if model:
                    return model
    except Exception:
        pass
    try:
        import psutil
        parts = psutil.disk_partitions(all=False)
        if parts:
            usage = psutil.disk_usage(parts[0].mountpoint)
            return f"{parts[0].device} {usage.total / (1024**3):.0f}G"
    except Exception:
        pass
    return "Disco"

def _linux_nvme_temp() -> float:
    try:
        import glob
        for path in glob.glob("/sys/class/nvme/nvme*/device/hwmon/hwmon*/temp1_input"):
            raw = _read_text(path)
            if raw:
                return float(raw) / 1000.0
        for path in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
            name = (_read_text(os.path.join(os.path.dirname(path), "name")) or "").lower()
            label = (_read_text(path.replace("_input", "_label")) or "").lower()
            if "nvme" in name or "composite" in label or "nvme" in label:
                raw = _read_text(path)
                if raw:
                    return float(raw) / 1000.0
    except Exception:
        pass
    return math.nan

def _linux_fan_rpm(prefer_cpu: bool = True) -> float:
    try:
        from library.sensors.sensors_python import sensors_fans, is_cpu_fan
        fans = sensors_fans()
        if not fans:
            return math.nan
        fallback = math.nan
        for name, entries in fans.items():
            for entry in entries:
                rpm = float(getattr(entry, "current", math.nan))
                if math.isnan(rpm):
                    continue
                if prefer_cpu and (is_cpu_fan(entry.label) or is_cpu_fan(name)):
                    return rpm
                if math.isnan(fallback):
                    fallback = rpm
        return fallback
    except Exception:
        return math.nan

def _try_lhm():
    if platform.system() != "Windows":
        return None
    try:
        import library.sensors.sensors_librehardwaremonitor as lhm
        return lhm
    except Exception:
        return None

def _hw_snapshot(force: bool = False) -> dict:
    if not force and _cache.get("data") and (_now() - _cache["ts"] < 30):
        return _cache["data"]
    data = {
        "cpu": "", "gpu": "", "ram": "", "disk": "",
        "nvme_temp": math.nan, "cpu_fan_rpm": math.nan, "gpu_fan_rpm": math.nan,
        "cpu_temp": math.nan, "gpu_temp": math.nan,
    }
    lhm = _try_lhm()
    if lhm is not None:
        try:
            from LibreHardwareMonitor import Hardware  # type: ignore
            handle = lhm.handle
            for hardware in handle.Hardware:
                hardware.Update()
                ht = hardware.HardwareType
                if ht == Hardware.HardwareType.Cpu:
                    data["cpu"] = str(hardware.Name)
                    for sensor in hardware.Sensors:
                        if sensor.Value is None:
                            continue
                        st, sn = sensor.SensorType, str(sensor.Name)
                        if st == Hardware.SensorType.Temperature and sn.startswith(
                            ("Core Average", "Tctl", "CPU Package", "CPU Tctl", "Core Max")
                        ):
                            data["cpu_temp"] = float(sensor.Value)
                        if st == Hardware.SensorType.Fan and ("CPU" in sn.upper() or "Processor" in sn):
                            data["cpu_fan_rpm"] = float(sensor.Value)
                elif ht in (Hardware.HardwareType.GpuNvidia, Hardware.HardwareType.GpuAmd, Hardware.HardwareType.GpuIntel):
                    if not data["gpu"]:
                        data["gpu"] = str(hardware.Name)
                    for sensor in hardware.Sensors:
                        if sensor.Value is None:
                            continue
                        st, sn = sensor.SensorType, str(sensor.Name)
                        if st == Hardware.SensorType.Temperature and ("Core" in sn or "Hot Spot" in sn or sn.startswith("GPU")):
                            if math.isnan(data["gpu_temp"]) or "Core" in sn:
                                data["gpu_temp"] = float(sensor.Value)
                        if st == Hardware.SensorType.Fan:
                            data["gpu_fan_rpm"] = float(sensor.Value)
                elif ht == Hardware.HardwareType.Memory:
                    if not data["ram"]:
                        data["ram"] = str(hardware.Name)
                elif ht == Hardware.HardwareType.Storage:
                    name = str(hardware.Name)
                    if not data["disk"] or "nvme" in name.lower() or "ssd" in name.lower():
                        data["disk"] = name
                    for sensor in hardware.Sensors:
                        if sensor.Value is not None and sensor.SensorType == Hardware.SensorType.Temperature:
                            data["nvme_temp"] = float(sensor.Value)
                elif ht == Hardware.HardwareType.Motherboard:
                    for sh in hardware.SubHardware:
                        sh.Update()
                        for sensor in sh.Sensors:
                            if sensor.Value is None:
                                continue
                            sn = str(sensor.Name)
                            if sensor.SensorType == Hardware.SensorType.Fan and ("CPU" in sn.upper() or "#2" in sn):
                                data["cpu_fan_rpm"] = float(sensor.Value)
            if not data["gpu"]:
                try:
                    data["gpu"] = lhm.get_gpu_name() or ""
                except Exception:
                    pass
            try:
                import psutil
                gb = psutil.virtual_memory().total / (1024 ** 3)
                data["ram"] = f"{_shorten(data['ram'], 18)} {gb:.0f} GB" if data["ram"] else f"{gb:.0f} GB"
            except Exception:
                pass
        except Exception:
            pass
    if platform.system() != "Windows" or not data["cpu"]:
        if not data["cpu"]:
            data["cpu"] = _linux_cpu_model()
        if not data["gpu"]:
            data["gpu"] = _linux_gpu_model()
        if not data["ram"]:
            data["ram"], _ = _linux_ram_info()
        if not data["disk"]:
            data["disk"] = _linux_disk_info()
        if math.isnan(data["nvme_temp"]):
            data["nvme_temp"] = _linux_nvme_temp()
        if math.isnan(data["cpu_fan_rpm"]):
            data["cpu_fan_rpm"] = _linux_fan_rpm(True)
    _cache["data"] = data
    _cache["ts"] = _now()
    return data

class CpuModel(CustomDataSource):
    def as_numeric(self) -> float: return math.nan
    def as_string(self) -> str: return _shorten(_hw_snapshot()["cpu"], 26)
    def last_values(self) -> List[float]: return []

class GpuModel(CustomDataSource):
    def as_numeric(self) -> float: return math.nan
    def as_string(self) -> str: return _shorten(_hw_snapshot()["gpu"], 26)
    def last_values(self) -> List[float]: return []

class RamInfo(CustomDataSource):
    def as_numeric(self) -> float:
        try:
            import psutil
            return float(psutil.virtual_memory().percent)
        except Exception:
            return math.nan
    def as_string(self) -> str: return _shorten(_hw_snapshot()["ram"], 24)
    def last_values(self) -> List[float]: return []

class DiskModel(CustomDataSource):
    def as_numeric(self) -> float:
        try:
            import psutil
            return float(psutil.disk_usage(os.path.abspath(os.sep)).percent)
        except Exception:
            return math.nan
    def as_string(self) -> str: return _shorten(_hw_snapshot()["disk"], 24)
    def last_values(self) -> List[float]: return []

class NvmeTemp(CustomDataSource):
    last_val = [math.nan] * 10
    def as_numeric(self) -> float:
        t = _hw_snapshot(force=True)["nvme_temp"]
        self.last_val.append(t if not math.isnan(t) else math.nan)
        self.last_val.pop(0)
        return t
    def as_string(self) -> str:
        t = self.as_numeric()
        return "- C" if math.isnan(t) else f"{t:>4.0f}C"
    def last_values(self) -> List[float]: return self.last_val

class CpuFanRpm(CustomDataSource):
    last_val = [math.nan] * 10
    def as_numeric(self) -> float:
        rpm = _hw_snapshot(force=True)["cpu_fan_rpm"]
        self.last_val.append(rpm if not math.isnan(rpm) else math.nan)
        self.last_val.pop(0)
        return rpm
    def as_string(self) -> str:
        rpm = self.as_numeric()
        return "- RPM" if math.isnan(rpm) or rpm <= 0 else f"{int(rpm):>4d} RPM"
    def last_values(self) -> List[float]: return self.last_val

class GpuFanRpm(CustomDataSource):
    last_val = [math.nan] * 10
    def as_numeric(self) -> float:
        rpm = _hw_snapshot(force=True)["gpu_fan_rpm"]
        self.last_val.append(rpm if not math.isnan(rpm) else math.nan)
        self.last_val.pop(0)
        return rpm
    def as_string(self) -> str:
        rpm = self.as_numeric()
        return "- RPM" if math.isnan(rpm) or rpm <= 0 else f"{int(rpm):>4d} RPM"
    def last_values(self) -> List[float]: return self.last_val

class PreciseTime(CustomDataSource):
    def as_numeric(self) -> float:
        now = datetime.now()
        return float(now.hour * 3600 + now.minute * 60 + now.second)
    def as_string(self) -> str: return datetime.now().strftime("%H:%M:%S")
    def last_values(self) -> List[float]: return []

class PreciseDate(CustomDataSource):
    def as_numeric(self) -> float: return math.nan
    def as_string(self) -> str:
        months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
        now = datetime.now()
        return f"{now.day:02d} {months[now.month - 1]}"
    def last_values(self) -> List[float]: return []

class HostName(CustomDataSource):
    def as_numeric(self) -> float: return math.nan
    def as_string(self) -> str: return _shorten(platform.node() or "PC", 18)
    def last_values(self) -> List[float]: return []
