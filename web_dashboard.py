"""
Web Dashboard Backend Server & Process Coordinator (Port :8001).
Trung tâm Điều khiển Hợp nhất & Bộ tổng hợp dữ liệu thời gian thực.
"""

import argparse
import atexit
import asyncio
import json
import logging
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import aiohttp
from aiohttp import web
import yaml

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("web_dashboard")

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ACCESS_LOG_PATH = PROJECT_ROOT / "logs" / "access.log"
WEB_DIR = PROJECT_ROOT / "web"

PM_KEY = web.AppKey("pm", Any)
SESSION_KEY = web.AppKey("session", Optional[aiohttp.ClientSession])
LOG_PATH_KEY = web.AppKey("log_path", Path)
SHUTDOWN_KEY = web.AppKey("shutdown_event", asyncio.Event)


def load_backend_ports(config_path: Path = CONFIG_PATH) -> List[int]:
    """Đọc danh sách cổng backend từ config.yaml (dự phòng [9001, 9002, 9003] nếu không đọc được)."""
    default_ports = [9001, 9002, 9003]
    if not config_path.exists():
        return default_ports
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            ports = [int(b["port"]) for b in cfg.get("backends", []) if "port" in b]
            return ports if ports else default_ports
    except Exception:
        return default_ports


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    """Kiểm tra socket TCP non-blocking xem cổng đang mở hay đóng."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def kill_process_tree(pid: int):
    """Tiêu diệt toàn bộ cây tiến trình (Process Tree) tương thích Windows và POSIX."""
    if not pid or pid <= 0:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            )
        except Exception:
            pass
    else:
        try:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, 9)
            except Exception:
                pass


def is_pid_running(pid: int) -> bool:
    """Kiểm tra một PID có đang thực sự tồn tại và chạy trên hệ thống hay không."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_process = kernel32.OpenProcess(0x1000, False, pid)
            if not h_process:
                return False
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code)):
                kernel32.CloseHandle(h_process)
                return exit_code.value == 259  # STILL_ACTIVE
            kernel32.CloseHandle(h_process)
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class ProcessManager:
    """Quản lý vòng đời tiến trình con (Mock, Proxy, Traffic) với Force Kill tức thì."""

    def __init__(self, project_root: Path = PROJECT_ROOT, mock_ports: Optional[List[int]] = None):
        self.project_root = project_root
        self.default_ports = load_backend_ports(project_root / "config.yaml")
        self.mock_ports = mock_ports or list(self.default_ports)
        self.mock_proc: Optional[subprocess.Popen] = None
        self.proxy_proc: Optional[subprocess.Popen] = None
        self.traffic_proc: Optional[subprocess.Popen] = None
        self.traffic_config: Dict[str, Any] = {"concurrency": 1, "delay": 0.4, "requests": 0}
        self.traffic_pid_file = self.project_root / "logs" / "traffic.pid"

    def reset_mock_ports(self):
        """Khôi phục danh sách mock_ports về mặc định từ config.yaml."""
        self.mock_ports = list(self.default_ports)
        logger.info(f"[PROCESS] Reset mock_ports to defaults: {self.mock_ports}")

    async def _start_service(self, name: str, script_rel: str, ports: List[int]) -> Dict[str, Any]:
        """Khởi chạy tiến trình nền và thăm dò cổng mạng cho đến khi sẵn sàng."""
        ports_open = all(is_port_open(p) for p in ports)
        proc: Optional[subprocess.Popen] = getattr(self, f"{name}_proc", None)

        if proc and proc.poll() is None:
            if ports_open:
                return {"status": "already_running", "message": f"{name} is already running"}
            # Tiến trình con bị treo hoặc chưa mở cổng -> dọn dẹp để khởi động lại
            self.force_kill(name)
        elif ports_open:
            return {"status": "already_running", "message": f"{name} is already running on ports {ports}"}

        cmd = [sys.executable, str(self.project_root / script_rel)]
        logger.info(f"Starting {name}: {cmd}")
        setattr(self, f"{name}_proc", subprocess.Popen(
            cmd, cwd=str(self.project_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ))

        start_t = time.time()
        while time.time() - start_t < 3.0:
            if all(is_port_open(p) for p in ports):
                logger.info(f"{name} is READY on ports: {ports}")
                return {"status": "ok", "message": f"{name} started successfully"}
            await asyncio.sleep(0.1)

        return {"status": "started", "message": f"{name} process started, awaiting readiness"}

    async def start_mock(self) -> Dict[str, Any]:
        """Khởi chạy cụm Mock Servers theo danh sách cổng cấu hình mặc định."""
        self.reset_mock_ports()
        return await self._start_service("mock", "mock/mock_servers.py", self.mock_ports)

    async def start_proxy(self) -> Dict[str, Any]:
        """Khởi chạy Reverse Proxy (:8000)."""
        self.reset_mock_ports()
        return await self._start_service("proxy", "proxy.py", [8000])

    def start_traffic(self, delay: float = 0.4, requests: int = 0, concurrency: int = 1) -> Dict[str, Any]:
        """Khởi chạy bộ sinh tải độc lập (scripts/test_traffic.py). URL cố định tại port 8000."""
        self.force_kill("traffic")
        self.traffic_config = {
            "delay": max(0.01, float(delay)),
            "requests": max(0, int(requests)),
            "concurrency": max(1, int(concurrency)),
        }
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "test_traffic.py"),
            "--url", "http://127.0.0.1:8000/api/order",
            "--delay", str(self.traffic_config["delay"]),
            "--requests", str(self.traffic_config["requests"]),
            "--concurrency", str(self.traffic_config["concurrency"]),
        ]
        logger.info(f"Starting traffic generator: {cmd}")
        self.traffic_proc = subprocess.Popen(
            cmd, cwd=str(self.project_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            self.traffic_pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.traffic_pid_file.write_text(str(self.traffic_proc.pid), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist traffic PID: {e}")
        return {"status": "ok", "message": "Traffic generator started", "config": self.traffic_config}

    def force_kill(self, name: str, is_teardown: bool = False) -> bool:
        """Dừng cưỡng chế tức thì (Immediate Force Kill) tiến trình con chỉ định."""
        if name in ("mock", "proxy"):
            self.reset_mock_ports()

        proc: Optional[subprocess.Popen] = getattr(self, f"{name}_proc", None)
        setattr(self, f"{name}_proc", None)
        killed = False

        if proc:
            pid = proc.pid
            logger.info(f"Force killing process tree: {name} (PID: {pid})")
            kill_process_tree(pid)
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=1.0)
            except Exception as e:
                logger.warning(f"Error while killing process {name}: {e}")
            killed = True

        if name == "traffic":
            if self.traffic_pid_file.exists():
                try:
                    old_pid = int(self.traffic_pid_file.read_text(encoding="utf-8").strip())
                    if is_pid_running(old_pid):
                        logger.info(f"Force killing persisted traffic PID: {old_pid}")
                        kill_process_tree(old_pid)
                        killed = True
                except Exception as e:
                    logger.warning(f"Error reading persisted traffic PID: {e}")
                finally:
                    try:
                        self.traffic_pid_file.unlink(missing_ok=True)
                    except Exception:
                        pass

            # Dọn dẹp triệt để các tiến trình test_traffic.py mồ côi (chỉ chạy khi không phải teardown)
            if sys.platform == "win32" and not is_teardown:
                try:
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*test_traffic.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                except (KeyboardInterrupt, SystemExit, Exception):
                    pass

        return killed

    def stop_all(self):
        """Dừng toàn bộ các tiến trình con đang quản lý."""
        for name in ("traffic", "proxy", "mock"):
            try:
                self.force_kill(name, is_teardown=True)
            except (KeyboardInterrupt, SystemExit, Exception):
                pass

    def get_process_status(self) -> Dict[str, Any]:
        """Tổng hợp trạng thái sống/chết của các tiến trình."""
        mock_on = (self.mock_proc is not None and self.mock_proc.poll() is None) or all(is_port_open(p) for p in self.mock_ports)
        proxy_on = (self.proxy_proc is not None and self.proxy_proc.poll() is None) or is_port_open(8000)

        traffic_pid = self.traffic_proc.pid if (self.traffic_proc and self.traffic_proc.poll() is None) else None
        if not traffic_pid and self.traffic_pid_file.exists():
            try:
                file_pid = int(self.traffic_pid_file.read_text(encoding="utf-8").strip())
                if is_pid_running(file_pid):
                    traffic_pid = file_pid
                else:
                    self.traffic_pid_file.unlink(missing_ok=True)
            except Exception:
                pass

        traffic_on = traffic_pid is not None

        return {
            "mock_servers": {
                "status": "running" if mock_on else "stopped",
                "pid": self.mock_proc.pid if (self.mock_proc and self.mock_proc.poll() is None) else None,
                "ports": self.mock_ports,
            },
            "proxy": {
                "status": "running" if proxy_on else "stopped",
                "pid": self.proxy_proc.pid if (self.proxy_proc and self.proxy_proc.poll() is None) else None,
                "port": 8000,
            },
            "traffic": {
                "status": "running" if traffic_on else "stopped",
                "pid": traffic_pid,
                "config": self.traffic_config,
            },
        }


class StatsAggregator:
    """Đọc tệp access.log và tổng hợp số liệu thời gian thực."""

    @staticmethod
    def read_recent_events(log_path: Path = ACCESS_LOG_PATH, max_lines: Optional[int] = None) -> List[Dict]:
        if not log_path.exists():
            return []
        events: List[Dict] = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if max_lines is not None and max_lines > 0:
                    lines = lines[-max_lines:]
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.warning(f"Failed to read access log: {e}")
        return events

    @staticmethod
    def calculate_metrics(events: List[Dict]) -> Dict[str, Any]:
        total = len(events)
        now = time.time()
        recent_5s = [r for r in events if now - r.get("ts", now) <= 5.0]
        rps = round(len(recent_5s) / 5.0, 1) if recent_5s else 0.0

        success = sum(1 for r in events if 200 <= r.get("status", 0) < 400 or r.get("success", False))
        node_counts: Dict[str, int] = {}
        for r in events:
            node = r.get("node", "unknown")
            if node:
                node_counts[node] = node_counts.get(node, 0) + 1

        node_dist = {
            node: {"count": c, "pct": round((c / total * 100), 1) if total > 0 else 0.0}
            for node, c in node_counts.items()
        }

        return {
            "total_requests": total,
            "success_count": success,
            "failed_count": total - success,
            "success_pct": round((success / total * 100), 1) if total > 0 else 100.0,
            "rps": rps,
            "node_distribution": node_dist,
        }

    @staticmethod
    async def check_mock_health(session: aiohttp.ClientSession, ports: Optional[List[int]] = None, weights: Optional[Dict[int, int]] = None) -> Dict[str, Any]:
        nodes_info = {}
        target_ports = ports or load_backend_ports()
        w_map = weights or {}
        for idx, port in enumerate(target_ports, 1):
            fallback_id = f"mock-node-{port - 9000 if 9000 < port < 10000 else idx}"
            start_t = time.perf_counter()
            try:
                async with session.get(f"http://127.0.0.1:{port}/healthz", timeout=aiohttp.ClientTimeout(total=0.5)) as resp:
                    lat = round((time.perf_counter() - start_t) * 1000, 2)
                    data = {}
                    try:
                        data = await resp.json()
                    except Exception:
                        pass
                    node_id = data.get("node") or fallback_id
                    nodes_info[node_id] = {
                        "port": port, "alive": resp.status == 200, "status_code": resp.status, "latency_ms": lat,
                        "weight": w_map.get(port, 1),
                    }
            except Exception:
                nodes_info[fallback_id] = {
                    "port": port, "alive": False, "status_code": 0, "latency_ms": 0.0,
                    "weight": w_map.get(port, 1),
                }
        return nodes_info

    @classmethod
    async def get_stats(
        cls, pm: ProcessManager, session: aiohttp.ClientSession, log_path: Path = ACCESS_LOG_PATH
    ) -> Dict[str, Any]:
        events = cls.read_recent_events(log_path)
        metrics = cls.calculate_metrics(events)
        services = pm.get_process_status()
        target_ports = getattr(pm, "mock_ports", load_backend_ports())

        balancer_state = None
        if services["proxy"]["status"] == "running":
            try:
                async with session.get("http://127.0.0.1:8000/api/balancer/state", timeout=aiohttp.ClientTimeout(total=0.5)) as b_resp:
                    if b_resp.status == 200:
                        balancer_state = await b_resp.json()
            except Exception:
                pass

        # Trích xuất trọng số của từng node từ Proxy hoặc config mặc định
        weights = {}
        if balancer_state and balancer_state.get("backends"):
            for b in balancer_state["backends"]:
                weights[b.get("port")] = b.get("weight", 1)
        elif balancer_state and balancer_state.get("ring"):
            for v in balancer_state["ring"]:
                weights[v.get("backend_port")] = v.get("weight", 1)
        else:
            try:
                cfg_backends = load_config(pm.project_root / "config.yaml").get("backends", [])
                for b in cfg_backends:
                    weights[b.get("port")] = b.get("weight", 1)
            except Exception:
                pass

        if services["mock_servers"]["status"] == "running":
            services["mock_servers"]["nodes"] = await cls.check_mock_health(session, target_ports, weights)
        else:
            default_ports = getattr(pm, "default_ports", load_backend_ports())
            services["mock_servers"]["nodes"] = {
                f"mock-node-{p - 9000 if 9000 < p < 10000 else idx}": {
                    "port": p, "alive": False, "status_code": 0, "latency_ms": 0.0,
                    "weight": weights.get(p, 5 if idx == 1 else 1),
                }
                for idx, p in enumerate(default_ports, 1)
            }

        detected_algo = "consistent_hash"
        if balancer_state and balancer_state.get("algorithm"):
            detected_algo = balancer_state["algorithm"]
        else:
            for r in reversed(events):
                if r.get("algo") and r["algo"] != "unknown":
                    detected_algo = r["algo"]
                    break

        if not balancer_state:
            default_ports = getattr(pm, "default_ports", load_backend_ports())
            default_backends = [
                {"id": f"mock-node-{idx}", "port": p, "weight": weights.get(p, 5 if idx == 1 else 1), "alive": False, "active_conns": 0}
                for idx, p in enumerate(default_ports, 1)
            ]
            balancer_state = {
                "type": detected_algo,
                "algorithm": detected_algo,
                "backends": default_backends,
            }

        last_event = events[-1] if events else None

        return {
            "timestamp": time.time(),
            "active_algo": detected_algo,
            "services": services,
            "metrics": metrics,
            "recent_events": events[-20:][::-1],
            "balancer_state": balancer_state,
            "last_event": last_event,
        }


# ==============================================================================
# Helper & Route Handlers
# ==============================================================================

async def _parse_json(request: web.Request) -> Dict[str, Any]:
    try:
        return await request.json()
    except Exception:
        return {}


async def _service_lifecycle(request: web.Request, service: str, start_coro) -> web.Response:
    action = (await _parse_json(request)).get("action", "start")
    if action == "start":
        return web.json_response(await start_coro())
    if action == "stop":
        request.app[PM_KEY].force_kill(service)
        return web.json_response({"status": "ok", "message": f"{service.capitalize()} stopped (force killed)"})
    return web.json_response({"error": f"Unknown action: {action}"}, status=400)


async def _forward_post(session: aiohttp.ClientSession, url: str, data: Optional[Dict] = None) -> web.Response:
    try:
        async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
            return web.json_response(await resp.json(), status=resp.status)
    except Exception as e:
        err_msg = str(e) if str(e) else f"{type(e).__name__} (service may not be running or reachable)"
        return web.json_response({"error": f"Failed to forward to {url}: {err_msg}"}, status=502)


async def handle_get_stats(request: web.Request) -> web.Response:
    stats = await StatsAggregator.get_stats(request.app[PM_KEY], request.app[SESSION_KEY], request.app[LOG_PATH_KEY])
    return web.json_response(stats)


async def handle_control_mock(request: web.Request) -> web.Response:
    res = await _service_lifecycle(request, "mock", request.app[PM_KEY].start_mock)
    if is_port_open(8000):
        try:
            await _forward_post(request.app[SESSION_KEY], "http://127.0.0.1:8000/api/backend", {"action": "reset"})
        except Exception:
            pass
    return res


async def handle_control_proxy(request: web.Request) -> web.Response:
    return await _service_lifecycle(request, "proxy", request.app[PM_KEY].start_proxy)


async def handle_control_traffic(request: web.Request) -> web.Response:
    pm: ProcessManager = request.app[PM_KEY]
    data = await _parse_json(request)
    action = data.get("action", "start")
    if action == "start":
        cfg = data.get("config", {}) if isinstance(data.get("config"), dict) else data
        concurrency = cfg.get("concurrency", data.get("concurrency", 1))
        delay = cfg.get("delay", data.get("delay", 0.4))
        requests = cfg.get("requests", data.get("requests", 0))
        res = pm.start_traffic(delay=delay, requests=requests, concurrency=concurrency)
        return web.json_response(res)
    if action == "stop":
        pm.force_kill("traffic")
        return web.json_response({"status": "ok", "message": "Traffic generator stopped (force killed)"})
    return web.json_response({"error": f"Unknown action: {action}"}, status=400)


async def handle_control_algorithm(request: web.Request) -> web.Response:
    data = await _parse_json(request)
    if not data.get("algorithm"):
        return web.json_response({"error": "Missing 'algorithm' parameter"}, status=400)
    return await _forward_post(request.app[SESSION_KEY], "http://127.0.0.1:8000/api/algorithm", {"algorithm": data["algorithm"]})


async def handle_control_chaos(request: web.Request) -> web.Response:
    data = await _parse_json(request)
    port, action = data.get("port"), data.get("action")
    if not port or not action:
        return web.json_response({"error": "Missing 'port' or 'action' parameter"}, status=400)

    url = f"http://127.0.0.1:{port}/chaos/{'delay?ms=' + str(data.get('ms', 500.0)) if action == 'delay' else action}"
    res = await _forward_post(request.app[SESSION_KEY], url)

    # Nếu action là down hoặc up, lập tức thông báo sang Proxy (:8000) để Hash Ring và Balancer cập nhật ngay lập tức!
    if res.status == 200 and action in ("down", "up") and is_port_open(8000):
        try:
            await _forward_post(
                request.app[SESSION_KEY],
                "http://127.0.0.1:8000/api/backend/status",
                {"port": int(port), "alive": action == "up"},
            )
        except Exception as e:
            logger.warning(f"Failed to sync backend status to proxy: {e}")

    return res


async def handle_control_backend(request: web.Request) -> web.Response:
    pm: ProcessManager = request.app[PM_KEY]
    session: aiohttp.ClientSession = request.app[SESSION_KEY]
    data = await _parse_json(request)
    action = data.get("action", "add")

    if action == "add":
        b_id = data.get("id")
        port = data.get("port")
        if not b_id or not port:
            return web.json_response({"error": "Missing required fields: 'id' and 'port'"}, status=400)
        try:
            port = int(port)
        except (ValueError, TypeError):
            return web.json_response({"error": "'port' must be an integer"}, status=400)

        # 1. Kiểm tra điều kiện tiên quyết: Mock cluster và Proxy phải đang RUNNING
        services = pm.get_process_status()
        if services["mock_servers"]["status"] != "running":
            return web.json_response({
                "error": "Mock cluster is not running. Please start Mock servers before adding backend nodes"
            }, status=409)

        if services["proxy"]["status"] != "running":
            return web.json_response({
                "error": "Proxy is not running. Please start Proxy before adding backend nodes"
            }, status=409)

        if port in pm.mock_ports:
            return web.json_response({
                "error": f"Backend node with port {port} already exists in cluster"
            }, status=400)

        # 2. Yêu cầu cụm Mock Server spawn thêm server con mới
        spawn_port = pm.mock_ports[0] if pm.mock_ports else 9001
        spawn_url = f"http://127.0.0.1:{spawn_port}/chaos/spawn"
        try:
            async with session.post(spawn_url, json={"name": b_id, "port": port}, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status not in (200, 201):
                    return web.json_response({"error": f"Failed to spawn mock node: HTTP {resp.status}"}, status=502)
        except Exception as e:
            return web.json_response({"error": f"Failed to communicate with mock cluster: {e}"}, status=502)

        # 3. Chuyển tiếp lệnh sang Proxy (:8000) để thêm vào thuật toán cân bằng tải
        res = await _forward_post(session, "http://127.0.0.1:8000/api/backend", data)
        if res.status == 200:
            if port not in pm.mock_ports:
                pm.mock_ports.append(port)
        return res

    elif action == "weight":
        b_id = data.get("id")
        weight = data.get("weight")
        if not b_id or weight is None:
            return web.json_response({"error": "Missing required fields: 'id' and 'weight'"}, status=400)
        return await _forward_post(session, "http://127.0.0.1:8000/api/backend", data)

    elif action == "reset":
        pm.reset_mock_ports()
        return await _forward_post(session, "http://127.0.0.1:8000/api/backend", data)

    return web.json_response({"error": f"Unknown action: '{action}'. Available: 'add', 'weight', 'reset'"}, status=400)


async def handle_events_stream(request: web.Request) -> web.StreamResponse:
    """
    Server-Sent Events (SSE) endpoint: Phát trực tiếp các sự kiện truy cập mới (Realtime 0ms)
    từ logs/access.log tới Web Dashboard để visualizer cập nhật ngay lập tức.
    """
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    log_path: Path = request.app[LOG_PATH_KEY]
    last_pos = log_path.stat().st_size if log_path.exists() else 0

    try:
        # Gửi thông điệp ping kết nối ban đầu
        await response.write(b": connected\n\n")

        shutdown_event: Optional[asyncio.Event] = request.app.get(SHUTDOWN_KEY)
        while shutdown_event is None or not shutdown_event.is_set():
            if request.transport is None or request.transport.is_closing():
                break

            if log_path.exists():
                curr_size = log_path.stat().st_size
                if curr_size > last_pos:
                    with open(log_path, "r", encoding="utf-8") as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        last_pos = f.tell()

                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                evt = json.loads(line)
                                msg = f"data: {json.dumps(evt)}\n\n".encode("utf-8")
                                await response.write(msg)
                            except Exception:
                                pass
                elif curr_size < last_pos:
                    # Tệp log bị truncate / reset
                    last_pos = 0

            await asyncio.sleep(0.04)  # 40ms kiểm tra một lần - siêu nhẹ và mượt mà (~25fps)
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    return response


async def handle_static_fallback(request: web.Request) -> web.Response:
    """Phục vụ file web/ hoặc trả về landing page HTML đơn giản."""
    path = request.match_info.get("path", "")
    target = WEB_DIR / path if path else WEB_DIR / "index.html"
    if target.exists() and target.is_file():
        return web.FileResponse(target)
    fallback = "<!DOCTYPE html><html><body><h1>Web Dashboard Backend</h1><p>API Ready on Port 8001</p></body></html>"
    return web.Response(text=fallback, content_type="text/html")


def create_dashboard_app(
    pm: Optional[ProcessManager] = None,
    session: Optional[aiohttp.ClientSession] = None,
    log_path: Optional[Path] = None,
) -> web.Application:
    """Factory khởi tạo ứng dụng Web Dashboard."""
    app = web.Application()
    app[PM_KEY] = pm or ProcessManager()
    app[SESSION_KEY] = session
    app[LOG_PATH_KEY] = log_path or ACCESS_LOG_PATH
    shutdown_event = asyncio.Event()
    app[SHUTDOWN_KEY] = shutdown_event

    async def on_startup(app: web.Application):
        if app[SESSION_KEY] is None or app[SESSION_KEY].closed:
            app[SESSION_KEY] = aiohttp.ClientSession()

    async def on_cleanup(app: web.Application):
        shutdown_event.set()
        try:
            if app.get(SESSION_KEY) and not app[SESSION_KEY].closed:
                await app[SESSION_KEY].close()
        except Exception:
            pass
        try:
            app[PM_KEY].stop_all()
        except (KeyboardInterrupt, SystemExit, Exception):
            pass

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Đăng ký các endpoints API
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/events/stream", handle_events_stream)
    app.router.add_post("/api/control/mock", handle_control_mock)
    app.router.add_post("/api/control/proxy", handle_control_proxy)
    app.router.add_post("/api/control/traffic", handle_control_traffic)
    app.router.add_post("/api/control/algorithm", handle_control_algorithm)
    app.router.add_post("/api/control/chaos", handle_control_chaos)
    app.router.add_post("/api/control/backend", handle_control_backend)
    app.router.add_route("*", "/{path:.*}", handle_static_fallback)
    return app


def main():
    parser = argparse.ArgumentParser(description="Load Balancer Web Dashboard Server")
    parser.add_argument("--port", type=int, default=8001, help="Dashboard port (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Dashboard host (default: 0.0.0.0)")
    args = parser.parse_args()

    pm = ProcessManager()
    atexit.register(pm.stop_all)
    logger.info(f"Starting Load Balancer Web Dashboard on http://{args.host}:{args.port}...")
    try:
        web.run_app(create_dashboard_app(pm=pm), host=args.host, port=args.port)
    except (KeyboardInterrupt, SystemExit):
        logger.info("[SHUTDOWN] Web Dashboard stopped gracefully.")


if __name__ == "__main__":
    main()
