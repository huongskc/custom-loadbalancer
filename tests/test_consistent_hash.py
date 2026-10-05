"""
Unit Tests for Consistent Hashing Balancer
Run: `python tests/test_consistent_hash.py` or `pytest tests/test_consistent_hash.py`
"""

import sys
from collections import Counter
from pathlib import Path

# Thêm thư mục gốc vào sys.path để chạy trực tiếp
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from balancers import Backend, ConsistentHashBalancer


def test_determinism_sticky_routing():
    """Kiểm tra tính đơn định: Cùng 1 IP luôn luôn trỏ về đúng 1 backend duy nhất."""
    backends = [
        Backend(id="node-1", host="127.0.0.1", port=9001),
        Backend(id="node-2", host="127.0.0.1", port=9002),
        Backend(id="node-3", host="127.0.0.1", port=9003),
    ]
    lb = ConsistentHashBalancer(backends, vnodes=100)

    test_ips = ["192.168.1.10", "192.168.1.25", "10.0.0.1", "172.16.5.99"]
    for ip in test_ips:
        first_pick = lb.get_backend(ip)
        assert first_pick is not None
        # Kiểm tra 100 lần liên tiếp phải ra cùng kết quả
        for _ in range(100):
            assert lb.get_backend(ip).id == first_pick.id

    print("  [PASS] test_determinism_sticky_routing")


def test_load_distribution_virtual_nodes():
    """Kiểm tra độ phân tán đồng đều khi có 100 Virtual Nodes mỗi server."""
    backends = [
        Backend(id="node-1", host="127.0.0.1", port=9001),
        Backend(id="node-2", host="127.0.0.1", port=9002),
        Backend(id="node-3", host="127.0.0.1", port=9003),
    ]
    lb = ConsistentHashBalancer(backends, vnodes=100)

    # Sinh 1,000 Client IP ngẫu nhiên
    counts = Counter()
    total_samples = 1000
    for i in range(total_samples):
        ip = f"10.0.{i // 256}.{i % 256}"
        node = lb.get_backend(ip)
        assert node is not None
        counts[node.id] += 1

    # Cả 3 node đều phải nhận được traffic và nằm trong khoảng hợp lý (không bị đói hoặc thắt cổ chai)
    assert len(counts) == 3
    for node_id, count in counts.items():
        percentage = count / total_samples
        # Kỳ vọng lý thuyết 33.3%, với V=100 dao động trong khoảng 22% - 45%
        assert 0.22 <= percentage <= 0.45, f"{node_id} nhận {percentage:.2%}, ngoài khoảng an toàn"

    print("  [PASS] test_load_distribution_virtual_nodes")


def test_weighted_virtual_nodes():
    """Kiểm tra hỗ trợ trọng số: Node có weight=2 nhận được nhiều vnodes và traffic hơn."""
    backends = [
        Backend(id="node-heavy", host="127.0.0.1", port=9001, weight=2),
        Backend(id="node-light", host="127.0.0.1", port=9002, weight=1),
    ]
    lb = ConsistentHashBalancer(backends, vnodes=100)

    counts = Counter()
    total_samples = 1000
    for i in range(total_samples):
        ip = f"192.168.{i // 256}.{i % 256}"
        counts[lb.get_backend(ip).id] += 1

    # node-heavy phải nhận được nhiều traffic hơn hẳn node-light (xấp xỉ tỉ lệ 2:1)
    heavy_ratio = counts["node-heavy"] / total_samples
    assert heavy_ratio > 0.55, f"node-heavy chỉ nhận {heavy_ratio:.2%}, kỳ vọng > 55%"
    print("  [PASS] test_weighted_virtual_nodes")


def test_minimal_disruption_on_failover():
    """
    Kiểm chứng tính chất cốt lõi: Minimal Disruption khi có node sập.
    Chỉ các client của node sập bị phân phối lại; các client của node còn sống giữ nguyên 100%.
    """
    backends = [
        Backend(id="node-1", host="127.0.0.1", port=9001),
        Backend(id="node-2", host="127.0.0.1", port=9002),
        Backend(id="node-3", host="127.0.0.1", port=9003),
    ]
    lb = ConsistentHashBalancer(backends, vnodes=100)

    # Ghi nhận ánh xạ ban đầu của 300 IP
    initial_map = {}
    for i in range(300):
        ip = f"172.16.{i // 256}.{i % 256}"
        initial_map[ip] = lb.get_backend(ip).id

    # Đánh sập node-2
    lb.update_backend_status("node-2", False)

    # Kiểm tra lại ánh xạ sau khi node-2 sập
    for ip, old_node_id in initial_map.items():
        new_node_id = lb.get_backend(ip).id
        if old_node_id == "node-1":
            # Phải 100% giữ nguyên ở node-1
            assert new_node_id == "node-1", f"IP {ip} bị đổi từ node-1 sang {new_node_id} (vi phạm minimal disruption)"
        elif old_node_id == "node-3":
            # Phải 100% giữ nguyên ở node-3
            assert new_node_id == "node-3", f"IP {ip} bị đổi từ node-3 sang {new_node_id} (vi phạm minimal disruption)"
        elif old_node_id == "node-2":
            # Chỉ riêng client của node-2 được chuyển sang node-1 hoặc node-3
            assert new_node_id in ["node-1", "node-3"]

    print("  [PASS] test_minimal_disruption_on_failover")


def test_all_nodes_down():
    """Kiểm tra khi tất cả node đều chết: hàm get_backend trả về None an toàn."""
    backends = [
        Backend(id="node-1", host="127.0.0.1", port=9001, alive=False),
        Backend(id="node-2", host="127.0.0.1", port=9002, alive=False),
    ]
    lb = ConsistentHashBalancer(backends)
    assert lb.get_backend("1.2.3.4") is None
    print("  [PASS] test_all_nodes_down")


def test_x_forwarded_for_parsing():
    """Kiểm tra bóc tách IP đầu tiên từ chuỗi header X-Forwarded-For."""
    backends = [Backend(id="node-1", host="127.0.0.1", port=9001)]
    lb = ConsistentHashBalancer(backends)

    # Chuỗi header chứa danh sách proxy: "client, proxy1, proxy2"
    node1 = lb.get_backend("203.0.113.195, 70.41.3.18, 192.168.1.1")
    node2 = lb.get_backend("203.0.113.195")
    assert node1.id == node2.id
    print("  [PASS] test_x_forwarded_for_parsing")


def test_explain_decision():
    """Kiểm tra explain_decision trả về 5 thành phần khoảng chặn trên vòng băm (prev_vn|prev_h|ip_h|cw_vn|cw_h)."""
    backends = [Backend(id="node-1", host="127.0.0.1", port=9001)]
    lb = ConsistentHashBalancer(backends)
    explanation = lb.explain_decision("192.168.1.10")
    parts = explanation.split("|")
    assert len(parts) == 5, f"Kỳ vọng 5 thành phần prev_vn|prev_h|ip_h|cw_vn|cw_h, nhận: {explanation}"
    prev_vn, prev_h, ip_h, cw_vn, cw_h = parts
    assert prev_vn.startswith("node-1#vn")
    assert prev_h.startswith("0x") and len(prev_h) == 10
    assert ip_h.startswith("0x") and len(ip_h) == 10
    assert cw_vn.startswith("node-1#vn")
    assert cw_h.startswith("0x") and len(cw_h) == 10
    assert lb.explain_decision("") == ""
    print("  [PASS] test_explain_decision")


def test_bisect_left_exact_match():
    """Kiểm chứng bisect_left: Khi hash(key) trùng khít với hash của một vnode, key phải ánh xạ trúng vnode đó."""
    b1 = Backend(id="node-1", host="127.0.0.1", port=9001)
    b2 = Backend(id="node-2", host="127.0.0.1", port=9002)
    lb = ConsistentHashBalancer([b1, b2], vnodes=10)

    # Chọn một vnode bất kỳ trên ring và lấy hash của nó
    target_hash = lb._sorted_keys[5]
    expected_backend = lb._ring[target_hash]

    # Giả lập client_ip có mã băm trùng khít với target_hash
    original_hash = lb._hash
    lb._hash = lambda k: target_hash if k == "exact-match-ip" else original_hash(k)

    chosen = lb.get_backend("exact-match-ip")
    assert chosen.id == expected_backend.id

    # Kiểm tra giải thích thuật toán cũng phải chỉ đúng vào vnode có hash bằng target_hash
    explanation = lb.explain_decision("exact-match-ip")
    parts = explanation.split("|")
    cw_hash = int(parts[4], 16)
    assert cw_hash == target_hash
    print("  [PASS] test_bisect_left_exact_match")


if __name__ == "__main__":
    print(">>> Running Consistent Hashing Tests...")
    test_determinism_sticky_routing()
    test_load_distribution_virtual_nodes()
    test_weighted_virtual_nodes()
    test_minimal_disruption_on_failover()
    test_all_nodes_down()
    test_x_forwarded_for_parsing()
    test_explain_decision()
    test_bisect_left_exact_match()
    print(">>> ALL CONSISTENT HASHING TESTS PASSED [100%]\n")

