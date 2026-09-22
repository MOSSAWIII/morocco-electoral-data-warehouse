from hashlib import sha256

from morocco_elections.provenance import sha256_file


def test_sha256_file_reads_binary_content(tmp_path) -> None:
    path = tmp_path / "source.bin"
    content = b"warehouse-electoral\x00\xff"
    path.write_bytes(content)

    assert sha256_file(path) == sha256(content).hexdigest()
