import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LinuxCoreResolverTests(unittest.TestCase):
    def run_resolver(self, validation_status="0", architecture="x86_64"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindir = root / "bin"
        out = root / "core"
        bindir.mkdir()
        real_python = shutil.which("python3")
        (bindir / "python3").write_text(f'''#!{real_python}
import hashlib, os, pathlib, subprocess, sys
args = sys.argv[1:]
if args and args[0].endswith("actions_candidate_discovery.py"):
    output = pathlib.Path(args[args.index("--output-directory") + 1])
    name = args[args.index("--archive-basename") + 1]
    archive = output / name
    archive.write_bytes(b"candidate")
    (output / (name + ".sha256")).write_text(hashlib.sha256(b"candidate").hexdigest() + "  " + name + "\\n")
    pathlib.Path(args[args.index("--manifest-path") + 1]).write_text("{{}}")
    sys.exit(0)
if args and args[0].endswith("linux_core_candidate.py"):
    sys.exit(int(os.environ["VALIDATE_STATUS"]))
os.execv({real_python!r}, [{real_python!r}, *args])
''')
        (bindir / "docker").write_text(f'''#!{real_python}
import pathlib, sys
a = sys.argv[1:]
if a[:2] == ["image", "inspect"]:
    print("ubuntu@sha256:" + "a" * 64 if a[2] == "ubuntu:22.04" else "sha256:" + "b" * 64)
elif a and a[0] == "run" and "--entrypoint" in a:
    print("dpkg-query\t1\tall\tii")
elif a and a[0] == "run":
    values = [a[i + 1] for i, x in enumerate(a[:-1]) if x in ("-e", "-v")]
    version = next((x.split("=", 1)[1] for x in values if x.startswith("PG_VERSION=")), "18.6")
    arch = next((x.split("=", 1)[1] for x in values if x.startswith("PG_ARCHITECTURE=")), "x86_64")
    mount = next(x.split(":", 1)[0] for x in values if x.endswith(":/out"))
    target = pathlib.Path(mount) / f"postgresql-{{version}}-linux-{{arch}}.tar.gz"
    target.write_bytes(b"built")
    target.with_name(target.name + ".sha256").write_text("built\\n")
''')
        for executable in (bindir / "python3", bindir / "docker"):
            executable.chmod(0o755)
        env = os.environ | {
            "PATH": f"{bindir}:{os.environ['PATH']}", "VALIDATE_STATUS": validation_status,
            "GH_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_REF_NAME": "spike", "GITHUB_RUN_ID": "123",
            "GITHUB_SHA": "a" * 40,
        }
        result = subprocess.run(
            [str(ROOT / "scripts/linux/resolve-core.sh"), "18.6", architecture, str(out),
             "workflow.yml", "artifact-{run_id}"], cwd=ROOT, env=env,
            text=True, capture_output=True)
        return result, out

    def test_uses_accepted_candidate(self):
        result, out = self.run_resolver()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using a checksum-verified core candidate", result.stdout)
        self.assertEqual((out / "postgresql-18.6-linux-x86_64.tar.gz").read_bytes(), b"candidate")

    def test_rejected_candidate_falls_back_to_docker_build(self):
        result, out = self.run_resolver(validation_status="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("building the selected PostgreSQL core in Docker", result.stdout)
        self.assertEqual((out / "postgresql-18.6-linux-x86_64.tar.gz").read_bytes(), b"built")

    def test_arm64_candidate_uses_arm64_archive_name(self):
        result, out = self.run_resolver(architecture="arm64")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "postgresql-18.6-linux-arm64.tar.gz").is_file())


if __name__ == "__main__":
    unittest.main()
