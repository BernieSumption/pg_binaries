import os
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import unittest
import io


ROOT = Path(__file__).resolve().parents[1]


class LinuxCoreResolverTests(unittest.TestCase):
    def run_resolver(self, architecture="x86_64", pin_state=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindir = root / "bin"
        out = root / "core"
        bindir.mkdir()
        real_python = shutil.which("python3")
        pin_archive = root / "pinned-core.tar.gz"
        if pin_state:
            manifest = json.dumps({"component": "postgresql", "version": "18.6", "platform": "linux",
                                   "architecture": architecture, "source_revision": "a" * 40,
                                   "build_id": "candidate-1",
                                   "builder_inputs": {"base_image": "ubuntu:22.04",
                                                      "base_image_digest": "sha256:" + "a" * 64,
                                                      "packages_sha256": "b" * 64}}).encode()
            with tarfile.open(pin_archive, "w:gz") as archive:
                info = tarfile.TarInfo("postgresql/manifest.json")
                info.size = len(manifest)
                archive.addfile(info, io.BytesIO(manifest))
        pin_sha = hashlib.sha256(pin_archive.read_bytes()).hexdigest() if pin_state else ""
        (bindir / "python3").write_text(f'''#!{real_python}
import hashlib, json, os, pathlib, sys
args = sys.argv[1:]
if args and args[0].endswith("plan_work.py"):
    sys.exit(0)
if args and args[0].endswith("linux_core_pin.py") and os.environ.get("PIN_STATE"):
    print(json.dumps({{"schema_version":1, "workflow":"postgresql-linux-selected-publication.yml",
        "run_id":123, "artifact_name":"postgresql-linux-core-123",
        "archive_name":"postgresql-18.6-linux-x86_64.tar.gz", "sha256":os.environ["PIN_SHA"]}}))
    sys.exit(0)
if args and args[0].endswith("linux_core_candidate.py"):
    if os.environ["PIN_STATE"] == "stale":
        sys.exit(1)
    archive = pathlib.Path(args[args.index("--archive") + 1])
    print(json.dumps({{"run_id":"123", "run_attempt":2, "source_revision":"a"*40,
        "artifact_revision":"a"*40, "artifact_name":"postgresql-linux-core-123",
        "sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}}))
    sys.exit(0)
os.execv({real_python!r}, [{real_python!r}, *args])
''')
        (bindir / "docker").write_text(f'''#!{real_python}
import pathlib, sys, tarfile, json, io
a = sys.argv[1:]
if a[:2] == ["image", "inspect"]:
    print("ubuntu@sha256:" + "a" * 64 if a[2] == "ubuntu:22.04" else "sha256:" + "b" * 64)
elif a and a[0] == "run" and "--entrypoint" in a:
    print("dpkg-query\t1\tall\tii")
elif a and a[0] == "run":
    values = [a[i + 1] for i, x in enumerate(a[:-1]) if x in ("-e", "-v")]
    version = next((x.split("=", 1)[1] for x in values if x.startswith("PG_VERSION=")), "18.6")
    arch = next((x.split("=", 1)[1] for x in values if x.startswith("PG_ARCHITECTURE=")), "x86_64")
    mode = next((x.split("=", 1)[1] for x in values if x.startswith("CORE_ONLY=")), "")
    mount = next(x.split(":", 1)[0] for x in values if x.endswith(":/out"))
    (pathlib.Path(mount) / "build-mode.txt").write_text(mode)
    target = pathlib.Path(mount) / f"postgresql-{{version}}-linux-{{arch}}.tar.gz"
    with tarfile.open(target, "w:gz") as tar:
        data = __import__("json").dumps({{"component":"postgresql", "version":version, "platform":"linux",
            "architecture":arch, "source_revision":"a"*40, "build_id":"github-123-1",
            "builder_inputs":{{"base_image":"ubuntu:22.04", "base_image_digest":"sha256:"+"a"*64,
            "packages_sha256":"b"*64}}}}).encode()
        info = tarfile.TarInfo("postgresql/manifest.json"); info.size = len(data); tar.addfile(info, __import__("io").BytesIO(data))
    target.with_name(target.name + ".sha256").write_text("built\\n")
''')
        (bindir / "gh").write_text(f'''#!{real_python}
import json, os, pathlib, shutil, sys
a = sys.argv[1:]
if a[:2] == ["run", "download"]:
    if os.environ["PIN_STATE"] == "unavailable":
        raise SystemExit(1)
    out = pathlib.Path(a[a.index("--dir") + 1])
    shutil.copyfile(os.environ["PIN_ARCHIVE"], out / "postgresql-18.6-linux-x86_64.tar.gz")
elif a[:1] == ["api"]:
    print(json.dumps({{"id":123, "run_attempt":2, "repository":{{"full_name":"owner/repo"}},
        "head_repository":{{"full_name":"owner/repo"}}, "head_sha":"a"*40,
        "path":".github/workflows/postgresql-linux-selected-publication.yml",
        "head_branch":"spike", "event":"push", "status":"completed", "conclusion":"success"}}))
''')
        for executable in (bindir / "python3", bindir / "docker", bindir / "gh"):
            executable.chmod(0o755)
        env = os.environ | {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "GH_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_REF_NAME": "spike", "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/build.yml@refs/heads/spike",
            "GITHUB_SHA": "a" * 40,
        }
        if pin_state:
            env.update({"PIN_STATE": pin_state, "PIN_SHA": pin_sha, "PIN_ARCHIVE": str(pin_archive)})
        result = subprocess.run(
            [str(ROOT / "scripts/linux/resolve-core.sh"), "18.6", architecture, str(out)], cwd=ROOT, env=env,
            text=True, capture_output=True)
        return result, out

    def test_missing_pin_builds_core_in_docker(self):
        result, out = self.run_resolver()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No usable unpublished Linux core pin exists", result.stdout)
        record = __import__("json").loads((out / "core-resolution.json").read_text())
        self.assertEqual(record["origin"], "built")
        self.assertEqual((out / "build-mode.txt").read_text(), "1")

    def test_arm64_fallback_uses_arm64_archive_name(self):
        result, out = self.run_resolver(architecture="arm64")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "postgresql-18.6-linux-arm64.tar.gz").is_file())

    def test_valid_exact_pin_is_reused(self):
        result, out = self.run_resolver(pin_state="valid")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((out / "core-resolution.json").read_text())
        self.assertEqual(record["origin"], "reused")
        self.assertEqual(record["provenance"]["run_id"], "123")
        self.assertEqual(record["provenance"]["run_attempt"], 2)
        self.assertEqual(record["provenance"]["artifact_name"], "postgresql-linux-core-123")
        self.assertFalse((out / "build-mode.txt").exists())

    def test_unavailable_or_stale_exact_pin_builds_in_docker(self):
        for state in ("unavailable", "stale"):
            with self.subTest(state=state):
                result, out = self.run_resolver(pin_state=state)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads((out / "core-resolution.json").read_text())
                self.assertEqual(record["origin"], "built")
                self.assertEqual((out / "build-mode.txt").read_text(), "1")


if __name__ == "__main__":
    unittest.main()
