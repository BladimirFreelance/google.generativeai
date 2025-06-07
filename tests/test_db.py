import db


def test_load_save_cycle(tmp_path):
    db_path = tmp_path / "keys.db"
    assert db.load_keys(path=str(db_path)) == []

    db.save_key("abc", path=str(db_path))
    assert db.load_keys(path=str(db_path)) == ["abc"]

    db.save_key("abc", path=str(db_path))
    assert db.load_keys(path=str(db_path)) == ["abc"]

    db.save_key("def", path=str(db_path))
    assert set(db.load_keys(path=str(db_path))) == {"abc", "def"}
