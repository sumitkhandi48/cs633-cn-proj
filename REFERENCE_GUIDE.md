# Developer Quick-Reference: Reliable UDP FTP Implementation

This document maps the project features to the specific files and line numbers in the codebase. Use this as a cheat sheet during your demo.

---

### 1. Protocol Structure (The "Rules")
*   **File:** `packet_protocol.py`
*   **Binary Header:** `HEADER_FORMAT = "!IIHHIII"` (Line 11). Defines the 28-byte binary packet structure.
*   **Flags:** `SYN, ACK, FIN, DATA, RESUME` (Lines 4-9). The control signals for the state machine.
*   **Packet Integrity:** `Packet.pack()` and `Packet.unpack()` (Lines 24, 38). Uses CRC32 to verify every packet's header and payload.

### 2. Reliability (Selective Repeat ARQ)
*   **File:** `sender_server.py`
*   **Tracking Unacked Packets:** `self.unacked_packets = {}` (Line 81). Stores sent packets until an ACK is received.
*   **Acknowledgment Logic:** `receive_ack(self, pkt)` (Line 108). Verifies the Session ID and removes the packet from the tracking list.
*   **Retransmission (Timeout):** `if now - time_sent > self.timeout:` (Line 186). Triggers a re-send if a packet is not ACKed within 0.5s.

### 3. Flow Control (Sliding Window & AIMD)
*   **File:** `sender_server.py`
*   **The Window Loop:** `while self.next_seq < self.base + self.window_size` (Line 165). Limits how many packets are "in flight" at once.
*   **Additive Increase:** `self.window_size += 1` (Line 116). Increases speed when the network is stable.
*   **Multiplicative Decrease:** `self.window_size = max(1, self.window_size // 2)` (Line 191). Rapidly slows down when packet loss is detected (Congestion Control).

### 4. Resumability (Manifest & Handshake)
*   **File:** `integrity_manager.py` & `receiver_client.py`
*   **Manifest Manager:** `class Manifest` in `integrity_manager.py`. Loads/saves the `.meta` file to track received chunks.
*   **Resume Detection:** `can_resume = (...)` in `receiver_client.py` (Line 22). Checks if a partial file and meta file exist.
*   **Resume Request:** `payload_str += "|RESUME_FROM:"` (Line 40). Tells the server exactly where to start sending.

### 5. Integrity & Security (Hashing & Sessions)
*   **File:** `receiver_client.py` & `integrity_manager.py`
*   **Session Isolation:** `self.session_id` (Line 16). Prevents "stale" packets from old downloads from corrupting a new one.
*   **Final Verification:** `calculate_sha256(file_path)` (Line 132). Compares the hash of the downloaded file with the hash sent by the server in the `FIN` packet.

### 6. Demo Simulation (Packet Loss)
*   **File:** `sender_server.py`
*   **CLI Parameter:** `--loss` (Line 211). Allows you to set the loss rate without changing code.
*   **Deterministic Loss Logic:** `if self.loss_counter % drop_interval == 0:` (Line 175). Deliberately skips the `sendto` call to force a reliability recovery.

---

### Core Troubleshooting (Windows/Handshake Fixes)
*   **Windows Error:** `except ConnectionResetError:` in `sender_server.py` (Line 45). Prevents the server from crashing if a client closes suddenly.
*   **Handshake Robustness:** `while not handshake_done:` loop in `receiver_client.py` (Line 51). Implements a more robust waiting period for the `SYN|ACK` to arrive.
