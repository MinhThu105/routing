####################################################
# LSrouter.py
# Name: Doan Minh Thu
# HUID:24020656
#####################################################

import json
import heapq
from router import Router
from packet import Packet


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # Số thứ tự gói tin Link-State của router này
        self.seq_num = 0
        # Các cổng nối trực tiếp: {port: (neighbor_addr, cost)}
        self.neighbors = {}
        # Trạng thái link của bản thân: {neighbor_addr: cost}
        self.own_links = {}
        # Cơ sở dữ liệu toàn mạng (LSDB): {router_addr: (seq_num, {neighbor_addr: cost})}
        self.lsdb = {self.addr: (0, {})}
        # Bảng chuyển tiếp: {dst_addr: out_port}
        self.forwarding_table = {}

    def rebuild_own_links(self):
        """Cập nhật từ điển các hàng xóm trực tiếp của bản thân."""
        links = {}
        for _, (nbr_addr, cost) in self.neighbors.items():
            if nbr_addr not in links or cost < links[nbr_addr]:
                links[nbr_addr] = cost
        self.own_links = links

    def recompute_forwarding_table(self):
        """Chạy thuật toán Dijkstra để tính đường đi ngắn nhất tới mọi đích."""
        dist = {self.addr: 0}
        first_port = {}
        pq = []

        # Khởi tạo từ các hàng xóm nối trực tiếp
        for port, (nbr_addr, cost) in self.neighbors.items():
            if nbr_addr not in dist or cost < dist[nbr_addr]:
                dist[nbr_addr] = cost
                first_port[nbr_addr] = port
                heapq.heappush(pq, (cost, nbr_addr))

        # Dijkstra trên toàn bộ đồ thị trong LSDB
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, float("inf")):
                continue
            _, links = self.lsdb.get(u, (0, {}))
            for v, w in links.items():
                new_dist = d + w
                if v not in dist or new_dist < dist[v]:
                    dist[v] = new_dist
                    first_port[v] = first_port[u]
                    heapq.heappush(pq, (new_dist, v))

        self.forwarding_table = first_port

    def broadcast_own_lsp(self):
        """Gửi gói Link-State của bản thân tới tất cả hàng xóm trực tiếp."""
        payload = json.dumps({
            "origin": self.addr,
            "seq": self.seq_num,
            "links": self.own_links,
        })
        for port, (nbr_addr, _) in self.neighbors.items():
            pkt = Packet(Packet.ROUTING, self.addr, nbr_addr, payload)
            self.send(port, pkt)

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                self.send(self.forwarding_table[dst], packet)
        else:
            if port not in self.neighbors:
                return
            data = json.loads(packet.content)
            origin = data["origin"]
            seq_num = data["seq"]
            links = data["links"]

            if origin == self.addr:
                return

            # Chỉ cập nhật và lan truyền (flood) nếu nhận được gói tin mới hơn
            if origin not in self.lsdb or seq_num > self.lsdb[origin][0]:
                self.lsdb[origin] = (seq_num, links)
                self.recompute_forwarding_table()

                # Flood gói tin ra tất cả các cổng khác trừ cổng vừa nhận
                for out_port, (nbr_addr, _) in self.neighbors.items():
                    if out_port != port:
                        fwd_pkt = Packet(Packet.ROUTING, origin, nbr_addr, packet.content)
                        self.send(out_port, fwd_pkt)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.neighbors[port] = (endpoint, cost)
        self.rebuild_own_links()
        self.seq_num += 1
        self.lsdb[self.addr] = (self.seq_num, dict(self.own_links))
        self.recompute_forwarding_table()
        self.broadcast_own_lsp()

    def handle_remove_link(self, port):
        """Handle removed link."""
        self.neighbors.pop(port, None)
        self.rebuild_own_links()
        self.seq_num += 1
        self.lsdb[self.addr] = (self.seq_num, dict(self.own_links))
        self.recompute_forwarding_table()
        self.broadcast_own_lsp()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.seq_num += 1
            self.lsdb[self.addr] = (self.seq_num, dict(self.own_links))
            self.broadcast_own_lsp()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"LSrouter(addr={self.addr}, seq={self.seq_num}, ft={self.forwarding_table})"
