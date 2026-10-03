"""
Base abstractions for Load Balancer
Cung cấp cấu trúc dữ liệu Backend và lớp trừu tượng BaseBalancer làm nền tảng cho mọi thuật toán.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Backend:
    """Đại diện cho một máy chủ backend trong cụm cân bằng tải."""

    id: str
    host: str
    port: int
    weight: int = 1
    alive: bool = True
    active_conns: int = 0
    current_weight: int = 0  # Phục vụ thuật toán Smooth Weighted Round Robin
    requests_count: int = 0  # Theo dõi tổng số request đã xử lý

    @property
    def url(self) -> str:
        """Đường dẫn URL gốc của backend."""
        return f"http://{self.host}:{self.port}"

    @contextmanager
    def track_connection(self):
        """
        Context manager quản lý số kết nối đang xử lý (active connections).
        Tự động tăng khi nhận request và giảm an toàn khi hoàn thành (kể cả khi gặp exception).
        """
        self.active_conns += 1
        try:
            yield self
        finally:
            self.active_conns = max(0, self.active_conns - 1)

    def to_dict(self) -> dict:
        """Chuyển đổi sang dict phục vụ xuất JSON cho Admin API / Dashboard."""
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "alive": self.alive,
            "active_conns": self.active_conns,
            "current_weight": self.current_weight,
            "requests_count": self.requests_count,
        }


class BaseBalancer(ABC):
    """
    Lớp trừu tượng cơ sở cho tất cả các thuật toán cân bằng tải.
    """

    def __init__(self, backends: List[Backend], name: str = "base"):
        self.name = name
        self.backends = list(backends)

    def get_alive_backends(self) -> List[Backend]:
        """Trả về danh sách các node hiện đang hoạt động bình thường (alive = True)."""
        return [b for b in self.backends if b.alive]

    def update_backend_status(self, backend_id: str, is_alive: bool):
        """Cập nhật trạng thái sống/chết cho backend theo ID (được Health Checker gọi)."""
        for b in self.backends:
            if b.id == backend_id:
                b.alive = is_alive
                self.on_backends_updated()
                break

    def on_backends_updated(self):
        """Hook được kích hoạt khi trạng thái backend thay đổi (dành cho Consistent Hash rebuild ring)."""
        pass

    @abstractmethod
    def get_backend(self, client_ip: str = "") -> Optional[Backend]:
        """
        Phương thức trừu tượng: Chọn 1 backend phù hợp theo thuật toán.
        Trả về None nếu không có node nào còn hoạt động.
        """
        pass

    def explain_decision(self, client_ip: str = "", chosen: Optional[Backend] = None) -> str:
        """
        Hook đa hình: Trả về chuỗi giải thích ngắn gọn quyết định của thuật toán.
        Mặc định trả về chuỗi rỗng để đảm bảo 100% tương thích ngược.
        """
        return ""

