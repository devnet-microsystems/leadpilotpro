from db_connector import PGCursor


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = [(7,)]

    def execute(self, sql, params=()):
        self.executed.append(sql)

    def executemany(self, sql, params):
        self.executed.append(sql)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def close(self):
        pass


def test_returning_id_preserves_row_for_fetchone():
    raw = FakeCursor()
    cursor = PGCursor(raw)

    cursor.execute("INSERT INTO demo (name) VALUES (?)", ("alpha",))

    assert cursor.lastrowid == 7
    assert cursor.fetchone()[0] == 7
    assert "RETURNING id" in raw.executed[0].upper()


def test_executemany_never_adds_returning_id():
    raw = FakeCursor()
    cursor = PGCursor(raw)

    cursor.executemany(
        "INSERT INTO demo (name) VALUES (?)",
        [("alpha",), ("beta",)],
    )

    assert "RETURNING id" not in raw.executed[0].upper()
