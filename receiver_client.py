import socket
import os
import time
from packet_protocol import Packet, SYN, ACK, FIN, DATA, RESUME, MAX_PAYLOAD
from integrity_manager import calculate_sha256, Manifest

class ReceiverClient:
    def __init__(self, host="127.0.0.1", port=8001, download_dir="downloads"):
        self.host, self.port = host, port
        self.addr = (self.host, self.port)
        self.download_dir = download_dir
        if not os.path.exists(download_dir): os.makedirs(download_dir)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)
        self.expected_seq, self.buffer = 0, {}
        self.file_handle, self.session_id = None, int(time.time()) & 0xFFFFFFFF
        self.manifest = None

    def download_file(self, filename, resume=False):
        file_path = os.path.join(self.download_dir, filename)
        self.manifest = Manifest(file_path)

        can_resume = (
            resume
            and os.path.exists(file_path)
            and bool(self.manifest.received_chunks)
        )

        if can_resume:
            self.expected_seq = 0
            while self.expected_seq in self.manifest.received_chunks:
                self.expected_seq += 1
            print(f"Downloader: Resuming '{filename}' from chunk {self.expected_seq} "
                  f"({len(self.manifest.received_chunks)} chunks already received)...")
        else:
            if resume and not can_resume:
                print("Downloader: No resume state found, starting fresh.")
            else:
                print(f"Downloader: Requesting '{filename}'...")
            self.expected_seq = 0

        payload_str = filename
        if can_resume:
            payload_str += "|RESUME_FROM:" + str(self.expected_seq)

        req_pkt = Packet(
            flags=SYN | (RESUME if can_resume else 0),
            payload=payload_str.encode("utf-8"),
            session_id=self.session_id
        )

        # Handshake
        handshake_done = False
        while not handshake_done:
            self.sock.sendto(req_pkt.pack(), self.addr)
            start_wait = time.time()
            while time.time() - start_wait < 2.0:
                try:
                    self.sock.settimeout(max(0.1, 2.0 - (time.time() - start_wait)))
                    data, server_addr = self.sock.recvfrom(2048)
                    resp = Packet.unpack(data)
                    if not resp or resp.session_id != self.session_id:
                        continue
                    
                    if resp.flags & (SYN | ACK):
                        print("Downloader: Handshake successful.")
                        handshake_done = True
                        break
                    elif resp.flags & DATA:
                        print("Downloader: Handshake successful (implicit via DATA).")
                        if resp.seq_num not in self.manifest.received_chunks:
                            self.buffer[resp.seq_num] = resp.payload
                        self.sock.sendto(
                            Packet(ack_num=resp.seq_num, flags=ACK, session_id=self.session_id).pack(),
                            server_addr
                        )
                        handshake_done = True
                        break
                except socket.timeout:
                    print("Downloader: Handshake timeout, retrying...")
                    break
                except ConnectionResetError:
                    print("Downloader: Connection reset (Windows ICMP), retrying...")
                    break
            if handshake_done: break

        if can_resume:
            self.file_handle = open(file_path, "r+b")
        else:
            self.file_handle = open(file_path, "wb")
            self.manifest.delete()
            self.manifest = Manifest(file_path)
            self.expected_seq = 0

        self.sock.settimeout(5.0)
        finished = False

        while not finished:
            try:
                data, server_addr = self.sock.recvfrom(2048)
                pkt = Packet.unpack(data)
                if not pkt or pkt.session_id != self.session_id:
                    continue

                if pkt.flags & DATA:
                    # --- SIMULATE ACK LOSS (Commented Out) ---
                    # import random
                    # if random.random() < 0.1: # 10% chance to drop ACK
                    #     print(f"DEBUG: Dropped ACK for packet {pkt.seq_num}")
                    # else:
                    #     self.sock.sendto(
                    #         Packet(ack_num=pkt.seq_num, flags=ACK,
                    #                session_id=self.session_id).pack(),
                    #         server_addr
                    #     )
                    # -----------------------------------------
                    
                    self.sock.sendto(
                        Packet(ack_num=pkt.seq_num, flags=ACK,
                               session_id=self.session_id).pack(),
                        server_addr
                    )
                    if pkt.seq_num >= self.expected_seq:
                        if (pkt.seq_num not in self.buffer
                                and pkt.seq_num not in self.manifest.received_chunks):
                            self.buffer[pkt.seq_num] = pkt.payload
                        while (self.expected_seq in self.buffer
                               or self.expected_seq in self.manifest.received_chunks):
                            if self.expected_seq in self.buffer:
                                self.file_handle.seek(self.expected_seq * MAX_PAYLOAD)
                                self.file_handle.write(self.buffer.pop(self.expected_seq))
                                self.manifest.add_chunk(self.expected_seq)
                            self.expected_seq += 1
                        self.manifest.save()

                elif pkt.flags & FIN:
                    print(f"Downloader: Finished receiving {filename}")
                    self.file_handle.close()
                    self.file_handle = None
                    if calculate_sha256(file_path) == pkt.payload.decode("utf-8"):
                        print("Downloader: Integrity check PASSED. ✓")
                        self.manifest.delete()
                    else:
                        print("Downloader: Integrity check FAILED! ✗")
                    self.sock.sendto(
                        Packet(ack_num=pkt.seq_num, flags=ACK | FIN,
                               session_id=self.session_id).pack(),
                        server_addr
                    )
                    finished = True

            except socket.timeout:
                print("Downloader: Download timed out.")
                break
            except ConnectionResetError:
                print("Downloader: Connection reset (Windows ICMP), retrying...")
                continue


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reliable UDP Downloader")
    parser.add_argument("file", help="Name of the file to download")
    parser.add_argument("--server-ip", default="127.0.0.1", help="IP address of the sender server")
    parser.add_argument("--resume", action="store_true", help="Attempt to resume download")
    args = parser.parse_args()

    ReceiverClient(host=args.server_ip).download_file(args.file, resume=args.resume)