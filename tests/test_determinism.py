import sqlite3
import time

from dietdb.__main__ import build_database


def test_fresh_builds_have_stable_hash_and_ids(tmp_path):
    first = tmp_path / "one.db"
    second = tmp_path / "two.db"
    hash_one = build_database(str(first), output_hash=True)
    time.sleep(2)
    hash_two = build_database(str(second), output_hash=True)
    assert hash_one == hash_two
    for path in (first, second):
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT MIN(id), MAX(id), COUNT(*) FROM foods").fetchone() == (1, 542, 542)
        assert conn.execute("SELECT id FROM foods WHERE source_code = 'A015'").fetchone() == (15,)
        conn.close()
