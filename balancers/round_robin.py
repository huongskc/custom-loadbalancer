class RoundRobinBalancer:
    def __init__(self, nodes=None):
        self.nodes = nodes if nodes is not None else []
        self.current_index = 0

    def get_node(self, request_key=None):
        """
        Trả về node tiếp theo trong danh sách một cách tuần tự.
        Tham số request_key giữ nguyên để có cùng interface với Consistent Hashing, 
        dù Round Robin không thực sự dùng đến nó.
        """
        if not self.nodes:
            return None
        
        # Lấy node hiện tại
        node = self.nodes[self.current_index]
        
        # Cập nhật con trỏ index để vòng lại từ đầu nếu đã đến cuối danh sách
        self.current_index = (self.current_index + 1) % len(self.nodes)
        
        return node

    def add_node(self, node):
        """Thêm node mới vào danh sách xoay vòng"""
        if node not in self.nodes:
            self.nodes.append(node)

    def remove_node(self, node):
        """Loại bỏ node khi có sự cố"""
        if node in self.nodes:
            self.nodes.remove(node)
            # Điều chỉnh lại index nếu node bị xóa làm danh sách ngắn đi
            if self.current_index >= len(self.nodes):
                self.current_index = 0