import struct
from integrity_manager import calculate_crc32, verify_crc32

# Protocol Flags
SYN = 0x01
ACK = 0x02
FIN = 0x04
DATA = 0x08
RESUME = 0x10

# Binary Format (Network Byte Order): 4I (uint32) 2H (uint16) 3I (uint32)
HEADER_FORMAT = "!IIHHIII"  # seq, ack, flags, len, h_crc, p_crc, session
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD = 1024

class Packet:
    """The 'Rules' of communication: how data is structured for the network."""
    def __init__(self, seq_num=0, ack_num=0, flags=0, payload=b"", session_id=0):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.payload = payload
        self.payload_len = len(payload)
        self.session_id = session_id
        self.payload_checksum = calculate_crc32(payload)
        self.header_checksum = 0

    def pack(self) -> bytes:
        """Serialize into binary for transmission."""
        temp_header = struct.pack(
            HEADER_FORMAT, self.seq_num, self.ack_num, self.flags,
            self.payload_len, 0, self.payload_checksum, self.session_id
        )
        self.header_checksum = calculate_crc32(temp_header)
        
        final_header = struct.pack(
            HEADER_FORMAT, self.seq_num, self.ack_num, self.flags,
            self.payload_len, self.header_checksum, self.payload_checksum, self.session_id
        )
        return final_header + self.payload

    @staticmethod
    def unpack(data: bytes):
        """Deserialize from network bytes with checksum verification."""
        if len(data) < HEADER_SIZE: return None
        
        header_data = data[:HEADER_SIZE]
        payload = data[HEADER_SIZE:]
        (seq_num, ack_num, flags, p_len, h_crc, p_crc, session_id) = struct.unpack(HEADER_FORMAT, header_data)
        
        # Verify Integrity
        temp_header = struct.pack(HEADER_FORMAT, seq_num, ack_num, flags, p_len, 0, p_crc, session_id)
        if not verify_crc32(temp_header, h_crc) or len(payload) != p_len or not verify_crc32(payload, p_crc):
            return None
            
        return Packet(seq_num, ack_num, flags, payload, session_id)
