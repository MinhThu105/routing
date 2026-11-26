####################################################
# DVrouter.py
# Name: Doan Minh Thu
# HUID:24020656
#####################################################

import json
from router import Router
from packet import Packet


class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.INFINITY = 16

        # Bảng định tuyến: {dst_addr: (cost, out_port)}
        self.dv = {self.addr: (0, None)}
        # Danh sách hàng xóm trực tiếp: {port: (neighbor_addr, cost)}
        self.neighbors = {}
        # Distance vector nhận được từ hàng xóm: {neighbor_addr: {dst_addr: cost}}
        self.neighbor_dvs = {}

    def recompute_dv(self):
        """Tính lại distance vector theo thuật toán Bellman-Ford."""
        new_dv = {self.addr: (0, None)}

        # 1. Xét các đường nối trực tiếp tới hàng xóm
        for port, (nbr_addr, link_cost) in self.neighbors.items():
            if link_cost < self.INFINITY:
                if nbr_addr not in new_dv or link_cost < new_dv[nbr_addr][0]:
                    new_dv[nbr_addr] = (link_cost, port)

        # 2. Xét các đường đi qua hàng xóm
        for port, (nbr_addr, link_cost) in self.neighbors.items():
            nbr_table = self.neighbor_dvs.get(nbr_addr, {})
            for dst, nbr_cost in nbr_table.items():
                if dst == self.addr:
                    continue
                total_cost = link_cost + nbr_cost
                if total_cost >= self.INFINITY:
                    continue
                if dst not in new_dv or total_cost < new_dv[dst][0]:
                    new_dv[dst] = (total_cost, port)

        if new_dv != self.dv:
            self.dv = new_dv
            return True
        return False

    def broadcast_dv(self):
        """Gửi distance vector cho tất cả hàng xóm (kèm Poisoned Reverse)."""
        for port, (nbr_addr, _) in self.neighbors.items():
            msg = {}
            for dst, (cost, out_port) in self.dv.items():
                # Poisoned Reverse: báo vô cực (16) nếu đường tới dst đi qua chính hàng xóm này
                if out_port == port and dst != nbr_addr:
                    msg[dst] = self.INFINITY
                else:
                    msg[dst] = cost
            pkt = Packet(Packet.ROUTING, self.addr, nbr_addr, json.dumps(msg))
            self.send(port, pkt)

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.dv:
                cost, out_port = self.dv[dst]
                if out_port is not None and cost < self.INFINITY:
                    self.send(out_port, packet)
        else:
            if port not in self.neighbors:
                return
            sender = self.neighbors[port][0]
            received_dv = json.loads(packet.content)
            self.neighbor_dvs[sender] = received_dv
            if self.recompute_dv():
                self.broadcast_dv()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.neighbors[port] = (endpoint, cost)
        if self.recompute_dv():
            self.broadcast_dv()

    def handle_remove_link(self, port):
        """Handle removed link."""
        nbr_addr, _ = self.neighbors.pop(port, (None, None))
        if nbr_addr is not None:
            still_connected = any(addr == nbr_addr for addr, _ in self.neighbors.values())
            if not still_connected:
                self.neighbor_dvs.pop(nbr_addr, None)
        if self.recompute_dv():
            self.broadcast_dv()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.broadcast_dv()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"DVrouter(addr={self.addr}, dv={self.dv})"
