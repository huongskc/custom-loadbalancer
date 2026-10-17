from typing import List, Optional
from .base import Backend, BaseBalancer


class RoundRobinBalancer(BaseBalancer):
    def __init__(self, backends: Optional[List[Backend]] = None):
        super().__init__(backends or [], name="round_robin")
        self.current_index = 0

    def get_backend(self, client_ip: str = "") -> Optional[Backend]:
        """
        Trả về backend tiếp theo trong danh sách các node đang hoạt động (alive = True) một cách tuần tự.
        """
        alive_backends = self.get_alive_backends()
        if not alive_backends:
            return None

        # Lấy backend hiện tại theo modulo số lượng backend đang sống
        backend = alive_backends[self.current_index % len(alive_backends)]

        # Cập nhật con trỏ index để vòng lại từ đầu nếu đã đến cuối danh sách
        self.current_index = (self.current_index + 1) % len(alive_backends)

        return backend

    def explain_decision(self, client_ip: str = "", chosen: Optional[Backend] = None) -> str:
        """Giải trình bước xoay vòng phục vụ Dashboard và Header X-Balancer-Decision."""
        alive = self.get_alive_backends()
        if not chosen or not alive:
            return "ROUND_ROBIN[no_alive_backend]"
        pos = alive.index(chosen) + 1 if chosen in alive else "?"
        return f"ROUND_ROBIN[step={pos}/{len(alive)}->{chosen.id}]"

    def get_visualizer_state(self) -> dict:
        alive = self.get_alive_backends()
        steps = []
        for idx, b in enumerate(alive):
            steps.append({
                "id": b.id,
                "port": b.port,
                "weight": b.weight,
                "step": idx + 1,
                "is_current": (idx == (self.current_index % len(alive))) if alive else False,
            })
        return {
            "type": "round_robin",
            "total_alive": len(alive),
            "current_index": self.current_index,
            "steps": steps,
        }