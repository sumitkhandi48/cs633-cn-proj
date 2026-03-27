import socket
import os
import time
import threading
from packet_protocol import Packet, SYN, ACK, FIN, DATA, RESUME, MAX_PAYLOAD
from integrity_manager import calculate_sha256

class SenderServer:
    def __init__(self, host="0.0.0.0", port=8001, shared_dir="shared", loss_rate=0):
        self.host = host
        self.port = port
        self.shared_dir = shared_dir
        self.loss_rate = loss_rate # Percentage (0-100)
        if not os.path.exists(shared_dir): os.makedirs(shared_dir)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.5)
        self.sessions = {}
        self.session_lock = threading.Lock()

    def start(self):
        print(f"Provider: Listening on {self.host}:{self.port} (Serving from '{self.shared_dir}/')")
        if self.loss_rate > 0:
            print(f"DEBUG: Packet loss simulation ENABLED ({self.loss_rate}%)")
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
                pkt = Packet.unpack(data)
                if not pkt: continue
                
                if pkt.flags & SYN:
                    self.handle_syn(pkt, addr)
                elif pkt.flags & ACK:
                    with self.session_lock:
                        session = self.sessions.get(addr)
                    if session:
                        session.receive_ack(pkt)
            except socket.timeout: continue
            except ConnectionResetError:
                # Windows-specific: occurs if a previous sendto failed (e.g., client closed port)
                continue
            except Exception as e:
                print(f"Provider: Error in main loop: {e}")
                continue

    def handle_syn(self, pkt, addr):
        try:
            payload_data = pkt.payload.decode("utf-8").split("|")
            filename = payload_data[0]
            file_path = os.path.join(self.shared_dir, filename)
            
            if not os.path.exists(file_path):
                print(f"Provider: File {filename} requested by {addr} not found.")
                return

            print(f"Provider: Sending '{filename}' to {addr}")

            with self.session_lock:
                old_session = self.sessions.pop(addr, None)

            if old_session:
                old_session.stop()

            client_received = set()
            if pkt.flags & RESUME and len(payload_data) > 1:
                res_part = payload_data[1]
                if res_part.startswith("RESUME_FROM:"):
                    start_seq = int(res_part.split(":")[1])
                    client_received = set(range(start_seq))
                else:
                    try:
                        client_received = set(map(int, res_part.split(",")))
                    except ValueError: pass

            session = SenderSession(self.sock, addr, file_path, client_received, pkt.session_id, self.loss_rate)
            with self.session_lock:
                self.sessions[addr] = session
            session.start()
        except Exception as e:
            print(f"Provider: Error handling SYN from {addr}: {e}")


class SenderSession:
    def __init__(self, sock, addr, file_path, received_chunks, session_id, loss_rate=0):
        self.sock, self.addr, self.file_path = sock, addr, file_path
        self.base, self.next_seq, self.window_size = 0, 0, 10
        self.timeout = 0.5
        self.unacked_packets, self.client_received = {}, received_chunks
        self.session_id = session_id
        self.loss_rate = loss_rate
        self.loss_counter = 0
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self.finished = False
        self.acked_this_window = 0
        self._thread = None

        file_size = os.path.getsize(file_path)
        self.total_chunks = (file_size + MAX_PAYLOAD - 1) // MAX_PAYLOAD
        self.sha256_hash = calculate_sha256(file_path)

    def start(self):
        syn_ack = Packet(flags=SYN | ACK, session_id=self.session_id)
        self.sock.sendto(syn_ack.pack(), self.addr)
        def delayed_run():
            time.sleep(0.05)
            self.run()
        self._thread = threading.Thread(target=delayed_run, daemon=True)
        self._thread.start()

    def join(self, timeout=3.0):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def receive_ack(self, pkt):
        if self._stop_event.is_set():
            return
        if pkt.session_id != self.session_id:
            return
        seq = pkt.ack_num
        with self.lock:
            if seq in self.unacked_packets:
                del self.unacked_packets[seq]
                self.acked_this_window += 1
                if self.acked_this_window >= self.window_size:
                    self.window_size += 1
                    self.acked_this_window = 0
            while self.base not in self.unacked_packets and self.base < self.next_seq:
                self.base += 1

    def run(self):
        with open(self.file_path, "rb") as f:
            while self.base < self.total_chunks and not self._stop_event.is_set():
                with self.lock:
                    while self.base in self.client_received and self.base < self.total_chunks:
                        self.base += 1
                    if self.next_seq < self.base: self.next_seq = self.base

                    while self.next_seq < self.base + self.window_size and self.next_seq < self.total_chunks:
                        if self.next_seq not in self.client_received:
                            f.seek(self.next_seq * MAX_PAYLOAD)
                            payload = f.read(MAX_PAYLOAD)
                            pkt = Packet(seq_num=self.next_seq, flags=DATA, payload=payload, session_id=self.session_id)
                            
                            # --- CONTROLLED PACKET LOSS ---
                            if self.loss_rate > 0:
                                self.loss_counter += 1
                                # Drop every Nth packet (e.g. if loss is 10%, drop every 10th)
                                drop_interval = 100 // self.loss_rate
                                if self.loss_counter % drop_interval == 0:
                                    print(f" [!] SIMULATED LOSS: Dropped packet #{self.next_seq}")
                                    self.unacked_packets[self.next_seq] = (pkt, time.time())
                                    self.next_seq += 1
                                    continue
                            # ------------------------------
                            
                            self.sock.sendto(pkt.pack(), self.addr)
                            self.unacked_packets[self.next_seq] = (pkt, time.time())
                        self.next_seq += 1

                    now = time.time()
                    timeout_hit = False
                    for seq, (pkt, time_sent) in list(self.unacked_packets.items()):
                        if now - time_sent > self.timeout:
                            if not self._stop_event.is_set():
                                self.sock.sendto(pkt.pack(), self.addr)
                            self.unacked_packets[seq] = (pkt, now)
                            timeout_hit = True
                    if timeout_hit: self.window_size = max(1, self.window_size // 2)
                time.sleep(0.01)

        if not self._stop_event.is_set():
            fin_pkt = Packet(seq_num=self.total_chunks, flags=FIN,
                             payload=self.sha256_hash.encode("utf-8"),
                             session_id=self.session_id)
            for _ in range(5):
                self.sock.sendto(fin_pkt.pack(), self.addr)
                time.sleep(0.1)

        self.finished = True

    def stop(self):
        self._stop_event.set()


if __name__ == "__main__":
    import argparse
    import sys
    
    try:
        parser = argparse.ArgumentParser(description="Reliable UDP Sender")
        parser.add_argument("--loss", type=int, default=0, help="Simulate packet loss percentage (0-100)")
        args = parser.parse_args()
        
        server = SenderServer(loss_rate=args.loss)
        server.start()
    except KeyboardInterrupt:
        print("\nProvider: Shutting down.")
        sys.exit(0)
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        input("Press Enter to exit...") # Keep window open on Windows
        sys.exit(1)
