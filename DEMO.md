# Demo Guide: Reliable UDP File Transfer Protocol

This guide highlights the key technical aspects of the project to explain during your demo.

## 1. The Core: `packet_protocol.py` (The "Protocol")
**Why it's important:** This is where you define the "language" the sender and receiver use to talk.
- **Explain the Header:** Show the `HEADER_FORMAT` (`!IIHHIII`). Explain that we pack data into binary to minimize overhead (just 28 bytes for the header).
- **Explain the Flags:**
    - `SYN`: Synchronization (Start Connection).
    - `ACK`: Acknowledgment (Confirm Receipt).
    - `RESUME`: Signal a resumable transfer.
    - `DATA`: The actual file chunk.
    - `FIN`: Finish (Signal end of file).
- **Integrity Check:** Point out `calculate_crc32`. Explain that UDP is "unreliable" by default, so we use these checksums to detect and discard corrupted packets.

## 2. The Resumability: `receiver_client.py` & `integrity_manager.py`
**Why it's important:** This is the most unique feature of your project.
- **The Manifest (`.meta`):** Show how the `Manifest` class in `integrity_manager.py` tracks exactly which chunks have been received.
- **The Handshake with Resume:** In `receiver_client.py`, show the logic that checks if a `.meta` file exists. If it does, the client sends a `SYN | RESUME` packet with the `RESUME_FROM` sequence number.
- **Session IDs:** Explain that we use a unique `session_id` (current timestamp) so that if we restart a download, the receiver won't accidentally process "stale" packets from the previous attempt.

## 3. Reliability: `sender_server.py`
**Why it's important:** This handles the actual delivery.
- **Sliding Window:** Explain the `window_size`. We don't send just one packet at a time; we send a "window" of packets to be faster.
- **AIMD logic:** Point out how the window grows (`+1`) on success and shrinks (`// 2`) on timeout (like TCP).
- **Windows-Specific Fix:** Mention how we handle `ConnectionResetError`. This is a professional touch showing you understand OS-level socket behavior (especially on Windows).

## 4. Demo Flow Suggestion
1. **Start Server:** `python sender_server.py`.
2. **First Run:** Start a download with `python receiver_client.py hello.mp4`.
3. **Interrupt:** Close the client (Ctrl+C) halfway through.
4. **Resume:** Run again with `python receiver_client.py hello.mp4 --resume`.
5. **Success:** Show the file in `downloads/` and the "Integrity check PASSED" message.
