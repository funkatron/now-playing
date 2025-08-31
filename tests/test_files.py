from now_playing.files import write_if_changed, write_artworks_list


def test_write_if_changed_idempotent(tmp_path):
    f = tmp_path / "song.txt"
    content = '"T"\nA\nAl\n2024'

    # First write returns True (changed)
    assert write_if_changed(str(f), content) is True
    assert f.read_text() == content

    # Second write with same content returns False (no change)
    assert write_if_changed(str(f), content) is False
    assert f.read_text() == content


def test_write_artworks_list_creates_and_updates(tmp_path):
    f = tmp_path / "artworks.txt"

    # When list empty, ensure file exists (created empty once)
    write_artworks_list(str(f), [])
    assert f.exists()
    assert f.read_text() == ""

    # Write with one path
    img1 = tmp_path / "cover1.png"
    img1.write_text("dummy")
    write_artworks_list(str(f), [str(img1)])
    assert f.read_text() == f"{img1}\n"


