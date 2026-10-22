"""The shared-password gate in front of the desk's API.

    python -m unittest discover tests
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["TIPOFF_DB"] = str(Path(_tmp.name) / "auth.db")
os.environ.setdefault("TIPOFF_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from tipoff import api, auth  # noqa: E402

REMOTE = ("203.0.113.9", 5000)   # another device
LOCAL = ("127.0.0.1", 5000)      # this computer


class AuthTest(unittest.TestCase):
    def setUp(self):
        auth._fails.clear()

    def client(self, where=REMOTE, **env):
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        if "TIPOFF_PASSWORD" not in env:
            os.environ.pop("TIPOFF_PASSWORD", None)
        return TestClient(api.app, client=where)

    def test_no_password_refuses_other_devices(self):
        r = self.client(REMOTE).get("/api/meta")
        self.assertEqual(r.status_code, 403)
        self.assertIn("TIPOFF_PASSWORD", r.json()["detail"])

    def test_no_password_still_works_on_this_computer(self):
        self.assertEqual(self.client(LOCAL).get("/api/meta").status_code, 200)

    def test_tunnel_traffic_is_not_local(self):
        c = self.client(LOCAL)
        self.assertEqual(c.get("/api/meta", headers={"X-Forwarded-For": "198.51.100.4"}).status_code, 403)

    def test_password_gate(self):
        c = self.client(REMOTE, TIPOFF_PASSWORD="hunter22")
        self.assertEqual(c.get("/api/meta").status_code, 401)
        self.assertEqual(c.get("/api/session").json(), {"required": True, "signed_in": False})
        self.assertEqual(c.post("/api/login", json={"password": "nope"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={"password": "hunter22"}).status_code, 200)
        self.assertEqual(c.get("/api/meta").status_code, 200)
        self.assertTrue(c.get("/api/session").json()["signed_in"])
        c.post("/api/logout")
        self.assertEqual(c.get("/api/meta").status_code, 401)

    def test_guessing_is_throttled(self):
        c = self.client(REMOTE, TIPOFF_PASSWORD="hunter22")
        for _ in range(auth.FAILS_PER_CLIENT):
            c.post("/api/login", json={"password": "wrong"})
        r = c.post("/api/login", json={"password": "hunter22"})
        self.assertEqual(r.status_code, 429, "even the right password waits once a device is locked out")

    def test_changing_password_signs_everyone_out(self):
        c = self.client(REMOTE, TIPOFF_PASSWORD="first-pass")
        c.post("/api/login", json={"password": "first-pass"})
        self.assertEqual(c.get("/api/meta").status_code, 200)
        os.environ["TIPOFF_PASSWORD"] = "second-pass"
        self.assertEqual(c.get("/api/meta").status_code, 401)

    def test_forged_cookie_is_rejected(self):
        c = self.client(REMOTE, TIPOFF_PASSWORD="hunter22")
        c.cookies.set(auth.COOKIE, "9999999999.deadbeef")
        self.assertEqual(c.get("/api/meta").status_code, 401)


def tearDownModule():
    if "con" in api._state:
        api._state.pop("con").close()
    _tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
