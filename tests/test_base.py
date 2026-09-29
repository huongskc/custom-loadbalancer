"""
Unit Tests for Base Balancer Abstractions
Run: `python tests/test_base.py` or `pytest tests/test_base.py`
"""

import sys
from pathlib import Path

# Thêm thư mục gốc dự án vào sys.path để import balancers khi chạy trực tiếp
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from balancers import Backend, BaseBalancer


def test_backend_initialization():
    """Kiểm tra khởi tạo đối tượng Backend và các thuộc tính cơ bản."""
    b = Backend(id="node-1", host="127.0.0.1", port=9001, weight=5)
    assert b.id == "node-1"
    assert b.host == "127.0.0.1"
    assert b.port == 9001
    assert b.weight == 5
    assert b.alive is True
    assert b.active_conns == 0
    assert b.current_weight == 0
    assert b.url == "http://127.0.0.1:9001"

    data = b.to_dict()
    assert data["id"] == "node-1"
    assert data["weight"] == 5
    print("  [PASS] test_backend_initialization")


def test_backend_track_connection_normal():
    """Kiểm tra context manager track_connection hoạt động chuẩn xác."""
    b = Backend(id="node-1", host="127.0.0.1", port=9001)
    assert b.active_conns == 0

    with b.track_connection():
        assert b.active_conns == 1
        with b.track_connection():
            assert b.active_conns == 2
        assert b.active_conns == 1

    assert b.active_conns == 0
    print("  [PASS] test_backend_track_connection_normal")


def test_backend_track_connection_on_exception():
    """Kiểm tra active_conns tự động giải phóng khi xảy ra ngoại lệ."""
    b = Backend(id="node-1", host="127.0.0.1", port=9001)

    try:
        with b.track_connection():
            assert b.active_conns == 1
            raise RuntimeError("Simulated request handling error")
    except RuntimeError:
        pass

    assert b.active_conns == 0
    print("  [PASS] test_backend_track_connection_on_exception")


def test_base_balancer_is_abstract():
    """Kiểm tra BaseBalancer là abstract class và không thể khởi tạo trực tiếp."""
    backends = [Backend(id="node-1", host="127.0.0.1", port=9001)]
    with pytest.raises(TypeError):
        BaseBalancer(backends)  # type: ignore
    print("  [PASS] test_base_balancer_is_abstract")


class DummyBalancer(BaseBalancer):
    """Lớp con thử nghiệm hiện thực BaseBalancer theo đúng hợp đồng."""

    def __init__(self, backends):
        super().__init__(backends, name="dummy")
        self.hook_called = False

    def on_backends_updated(self):
        self.hook_called = True

    def get_backend(self, client_ip: str = ""):
        alive = self.get_alive_backends()
        return alive[0] if alive else None


def test_base_balancer_concrete_implementation():
    """Kiểm tra hành vi của lớp con kế thừa BaseBalancer."""
    b1 = Backend(id="node-1", host="127.0.0.1", port=9001)
    b2 = Backend(id="node-2", host="127.0.0.1", port=9002)
    balancer = DummyBalancer([b1, b2])

    assert len(balancer.get_alive_backends()) == 2
    assert balancer.get_backend().id == "node-1"

    # Đánh sập node-1
    balancer.update_backend_status("node-1", False)
    assert balancer.hook_called is True
    assert len(balancer.get_alive_backends()) == 1
    assert balancer.get_backend().id == "node-2"

    # Đánh sập cả node-2 -> get_backend trả về None an toàn
    balancer.update_backend_status("node-2", False)
    assert len(balancer.get_alive_backends()) == 0
    assert balancer.get_backend() is None
    print("  [PASS] test_base_balancer_concrete_implementation")


if __name__ == "__main__":
    print(">>> Running Base Balancer Tests...")
    test_backend_initialization()
    test_backend_track_connection_normal()
    test_backend_track_connection_on_exception()
    test_base_balancer_is_abstract()
    test_base_balancer_concrete_implementation()
    print(">>> ALL BASE TESTS PASSED [100%]\n")
