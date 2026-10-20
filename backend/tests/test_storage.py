"""File storage: local disk by default, S3 when STORAGE_BACKEND=s3 (checked with a fake client, never real AWS)."""
import pytest

from services import storage
from services.errors import NotFound


class FakeS3:
    class exceptions:
        pass

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.uploads: list[tuple[str, str, dict]] = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        with open(filename, "rb") as handle:
            self.objects[(bucket, key)] = handle.read()
        self.uploads.append((bucket, key, ExtraArgs or {}))

    def download_file(self, bucket, key, filename):
        if (bucket, key) not in self.objects:
            error = Exception("missing")
            error.response = {"Error": {"Code": "404"}}
            raise error
        with open(filename, "wb") as handle:
            handle.write(self.objects[(bucket, key)])

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


@pytest.fixture
def s3(app, tmp_path, monkeypatch):
    fake = FakeS3()
    monkeypatch.setitem(app.config, "STORAGE_BACKEND", "s3")
    monkeypatch.setitem(app.config, "S3_BUCKET", "unit-test-bucket")
    monkeypatch.setitem(app.config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(storage, "_client", fake)
    monkeypatch.setattr(storage.tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    return fake


def test_local_is_the_default_in_tests(app):
    assert app.config["STORAGE_BACKEND"] == "local"


def test_local_round_trip(app, tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "UPLOAD_DIR", tmp_path)
    with app.app_context():
        storage.put_bytes("cv/1/a.pdf", b"hello")
        assert storage.resolve("cv/1/a.pdf").read_bytes() == b"hello"
        storage.delete("cv/1/a.pdf")
        with pytest.raises(NotFound):
            storage.resolve("cv/1/a.pdf")


def test_s3_put_uploads_to_the_bucket_and_clears_the_staged_copy(app, s3, tmp_path):
    with app.app_context():
        storage.put_bytes("cv/1/a.pdf", b"hello")
    assert s3.objects == {("unit-test-bucket", "cv/1/a.pdf"): b"hello"}
    assert s3.uploads[0][2]["ContentType"] == "application/pdf"
    assert not (tmp_path / "uploads" / "cv" / "1" / "a.pdf").exists()


def test_s3_resolve_fetches_once_then_serves_the_cache(app, s3):
    s3.objects[("unit-test-bucket", "content/x.txt")] = b"data"
    with app.app_context():
        first = storage.resolve("content/x.txt")
        assert first.read_bytes() == b"data"
        s3.objects.clear()  # a second call must not need the bucket
        assert storage.resolve("content/x.txt") == first


def test_s3_delete_removes_the_object_and_the_cached_copy(app, s3):
    s3.objects[("unit-test-bucket", "content/x.txt")] = b"data"
    with app.app_context():
        cached = storage.resolve("content/x.txt")
        storage.delete("content/x.txt")
        assert not s3.objects and not cached.exists()
        with pytest.raises(NotFound):
            storage.resolve("content/x.txt")


def test_s3_falls_back_to_a_file_still_on_local_disk(app, s3, tmp_path):
    legacy = tmp_path / "uploads" / "content" / "old.pdf"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"old")
    with app.app_context():
        assert storage.resolve("content/old.pdf").read_bytes() == b"old"


def test_a_key_outside_the_upload_folder_is_never_served(app, s3, tmp_path):
    (tmp_path / "secret.txt").write_text("no")
    (tmp_path / "uploads").mkdir()
    with app.app_context(), pytest.raises(NotFound):
        storage.resolve("../secret.txt")


def test_uploads_migrate_copies_only_what_is_missing_and_keeps_local_files(app, s3, tmp_path):
    root = tmp_path / "uploads"
    for key in ("content/a.pdf", "cv/1/b.pdf"):
        (root / key).parent.mkdir(parents=True, exist_ok=True)
        (root / key).write_bytes(b"x")
    s3.objects[("unit-test-bucket", "content/a.pdf")] = b"x"  # already there
    s3.head_object = lambda Bucket, Key: None if (Bucket, Key) in s3.objects else (_ for _ in ()).throw(_missing())
    runner = app.test_cli_runner()

    dry = runner.invoke(args=["uploads", "migrate"])
    assert "would copy 1, already in the bucket 1" in dry.output and ("unit-test-bucket", "cv/1/b.pdf") not in s3.objects

    done = runner.invoke(args=["uploads", "migrate", "--apply"])
    assert "copied 1, already in the bucket 1" in done.output
    assert ("unit-test-bucket", "cv/1/b.pdf") in s3.objects and (root / "cv/1/b.pdf").exists()


def _missing():
    error = Exception("missing")
    error.response = {"Error": {"Code": "404"}}
    return error
