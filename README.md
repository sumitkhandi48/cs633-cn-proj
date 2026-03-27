# Reliable UDP File Transfer Protocol (Custom FTP)

A custom, reliable file transfer protocol built over UDP using Python. This project implements reliability on top of the connectionless UDP protocol, featuring session management, sliding window flow control, and resumable transfers.

## Key Features
- **Reliable Transfer:** Implements a custom ARQ (Automatic Repeat Request) mechanism for guaranteed delivery.
- **Sliding Window:** Dynamic window scaling using AIMD (Additive Increase, Multiplicative Decrease) for optimized throughput.
- **Resumable Downloads:** Tracks received chunks via a manifest (`.meta`) file, allowing interrupted transfers to resume from where they left off.
- **Session Management:** Uses unique Session IDs to prevent interference from stale packets or previous sessions.
- **Integrity Checking:** 
  - **CRC32 Checksums:** Per-packet verification for both header and payload.
  - **SHA256 Hashing:** Full-file integrity verification after the transfer is complete.
- **Binary Protocol:** Custom-packed binary header for low overhead and efficiency.

## Project Structure
- `packet_protocol.py`: Defines the **"Rules of the Road."** Contains the binary packet structure, flags (SYN, ACK, DATA, FIN, RESUME), and checksum logic.
- `sender_server.py`: The **File Provider.** Listens for requests, manages multiple client sessions, and handles the sliding window transmission.
- `receiver_client.py`: The **Downloader.** Initiates transfers, handles the handshake, manages the receive buffer, and maintains the resume manifest.
- `integrity_manager.py`: Helper utilities for CRC32 calculation, SHA256 hashing, and manifest (`.meta`) file management.

## Usage

### 1. Start the Server (The Provider)
The server serves files from the `shared/` directory.
```bash
python sender_server.py
```

### 2. Run the Client (The Downloader)
Download a file from the server into the `downloads/` directory.
```bash
python receiver_client.py <filename> --server-ip <IP_ADDRESS>
```
*Note: Replace `<filename>` with a file existing in the server's `shared/` folder.*

### 3. Resuming a Download
If a download is interrupted, run the client again with the `--resume` flag:
```bash
python receiver_client.py <filename> --server-ip <IP_ADDRESS> --resume
```

## Protocol Details
- **Payload Size:** 1024 bytes (MAX_PAYLOAD).
- **Header Format:** `!IIHHIII` (Sequence, Ack, Flags, Length, Header CRC, Payload CRC, Session ID).
- **Handshake:** A SYN/ACK-based handshake ensures both parties are ready before data flows.
- **Error Handling:** Robustly handles `ConnectionResetError` on Windows and ignores stale session packets.
