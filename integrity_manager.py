import zlib
import hashlib
import os

def calculate_crc32(data: bytes) -> int:
    """Error Detection: Calculate CRC32 checksum for a chunk."""
    return zlib.crc32(data) & 0xFFFFFFFF

def verify_crc32(data: bytes, expected_checksum: int) -> bool:
    """Error Detection: Verify if a chunk is corrupted."""
    return calculate_crc32(data) == expected_checksum

def calculate_sha256(file_path: str) -> str:
    """Full File Integrity: Calculate hash for final verification."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

class Manifest:
    """Resumability Manager: Tracks which chunks are already downloaded."""
    def __init__(self, file_path):
        self.meta_path = file_path + ".meta"
        self.received_chunks = set()
        self.load()

    def load(self):
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r") as f:
                content = f.read()
                if content:
                    try:
                        self.received_chunks = set(map(int, content.split(",")))
                    except ValueError:
                        self.received_chunks = set()

    def save(self):
        with open(self.meta_path, "w") as f:
            f.write(",".join(map(str, sorted(list(self.received_chunks)))))

    def add_chunk(self, seq_num):
        self.received_chunks.add(seq_num)

    def delete(self):
        if os.path.exists(self.meta_path):
            os.remove(self.meta_path)
