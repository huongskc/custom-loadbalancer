"""
Least Connections (Weighted) Load Balancing
Chọn backend có tỷ lệ active_conns / weight nhỏ nhất. Khi hòa, xoay vòng giữa các node hòa
để tránh luôn dồn vào node đầu tiên lúc tải thấp.
"""

from typing import List, Optional
from .base import Backend, BaseBalancer


class LeastConnectionsBalancer(BaseBalancer):
    def __init__(self, backends: List[Backend]):
        super().__init__(backends, name="least_connections")
        self._tie_counter = 0

    @staticmethod
    def _score(b: Backend) -> float:
        return b.active_conns / max(1, b.weight)

    def get_backend(self, client_ip: str = "") -> Optional[Backend]:
        alive = self.get_alive_backends()
        if not alive:
            return None

        min_score = min(self._score(b) for b in alive)
        candidates = [b for b in alive if self._score(b) == min_score]

        chosen = candidates[self._tie_counter % len(candidates)]
        self._tie_counter += 1
        return chosen

    def explain_decision(self, client_ip: str = "", chosen: Optional[Backend] = None) -> str:
        # Không dùng ký tự '|' vì dashboard dành '|' cho định dạng 5 phần của consistent hash
        alive = self.get_alive_backends()
        if not alive:
            return "LEAST_CONN[no_alive_backend]"

        conns_info = ", ".join(f"{b.id}={b.active_conns}/w{b.weight}" for b in alive)
        if chosen:
            score = self._score(chosen)
            return f"LEAST_CONN[{chosen.id} score={score:.2f} ({conns_info})]"
        return "conns: " + conns_info