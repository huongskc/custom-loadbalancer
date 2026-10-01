"""
Consistent Hashing with Virtual Nodes (Karger et al. 1997)
Ánh xạ các server và client IP lên vòng tròn băm 32-bit với Virtual Nodes.
Tìm kiếm nhị phân O(log(N * V)) sử dụng bisect.
"""

import bisect
import hashlib
from typing import Dict, List, Optional
from .base import Backend, BaseBalancer


class ConsistentHashBalancer(BaseBalancer):
    """
    Thuật toán Cân bằng tải Consistent Hashing hỗ trợ Virtual Nodes.
    """

    def __init__(self, backends: List[Backend], vnodes: int = 100):
        super().__init__(backends, name="consistent_hash")
        self.vnodes = vnodes
        self._ring: Dict[int, Backend] = {}
        self._sorted_keys: List[int] = []
        self._build_ring()

    def _hash(self, key: str) -> int:
        """Băm chuỗi sang số nguyên 32-bit trên vòng tròn [0, 2^32 - 1]."""
        return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)

    def _build_ring(self):
        """Xây dựng lại vòng tròn băm từ danh sách các node đang hoạt động (alive = True)."""
        self._ring.clear()
        for backend in self.get_alive_backends():
            # Số virtual nodes tỷ lệ thuận với trọng số của backend (mặc định weight=1 -> 100 vnodes)
            num_vnodes = self.vnodes * max(1, backend.weight)
            for i in range(num_vnodes):
                vnode_key = f"{backend.id}#vn{i}"
                h = self._hash(vnode_key)
                self._ring[h] = backend

        self._sorted_keys = sorted(self._ring.keys())

    def on_backends_updated(self):
        """Hook tự động kích hoạt khi có node thay đổi trạng thái (sập hoặc hồi phục)."""
        self._build_ring()

    def get_backend(self, client_ip: str = "") -> Optional[Backend]:
        """
        Tìm backend đầu tiên theo chiều kim đồng hồ có giá trị băm >= hash(client_ip).
        Độ phức tạp thời gian: O(log(N * V)).
        """
        if not self._sorted_keys:
            return None

        # Bóc tách IP đầu tiên nếu client_ip là chuỗi danh sách proxy từ X-Forwarded-For
        clean_ip = client_ip.split(",")[0].strip() if client_ip else "127.0.0.1"
        h = self._hash(clean_ip)

        # Tìm kiếm nhị phân vị trí khóa trên vòng tròn
        idx = bisect.bisect_right(self._sorted_keys, h)
        if idx == len(self._sorted_keys):
            idx = 0  # Quay tròn về điểm đầu tiên của ring (vòng tròn khép kín)

        return self._ring[self._sorted_keys[idx]]
