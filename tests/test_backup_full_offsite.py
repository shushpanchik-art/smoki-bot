"""Run the actual backup script with local files and no external services.

The command shims exercise real tar/gzip output while injecting exit statuses.
Every rclone and notification invocation is replaced with a local fake; no
credentials, production paths, Telegram calls, or remote backups are used.
Run independently of bot dependencies with:
    python -m unittest tests.test_backup_full_offsite -v
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/backup_full_offsite.sh"


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux backup utilities required")
class FullOffsiteBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smoki-backup-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.source = self.root / "SMOKI"
        self.staging = self.root / "staging"
        self.remote = self.root / "fake-remote"
        for folder in (self.bin, self.source, self.staging, self.remote):
            folder.mkdir()
        self.payload = os.urandom(4096)
        (self.source / "payload.bin").write_bytes(self.payload)
        config = self.root / "dummy-rclone.conf"
        config.write_text("# Fake rclone does not read credentials.\n")

        # Do not inherit production secrets or RCLONE_* settings from the caller.
        self.env = {
            "PATH": f"{self.bin}{os.pathsep}{os.defpath}",
            "HOME": str(self.root),
            "LANG": "C.UTF-8",
            "BOT_DIR": str(self.root / "bot"),
            "SOURCE_DIR": str(self.source),
            "STAGING_DIR": str(self.staging),
            "RCLONE_CONFIG": str(config),
            "RCLONE_REMOTE": "fake:backups",
            "NOTIFY_SCRIPT": str(self.bin / "notify"),
            "FAKE_REMOTE_DIR": str(self.remote),
            "FAKE_CALLS": str(self.root / "calls.jsonl"),
            "FAKE_NOTIFICATIONS": str(self.root / "notifications"),
        }
        for command in ("tar", "gzip", "sha256sum"):
            executable = shutil.which(command, path=os.defpath)
            self.assertIsNotNone(executable, f"Missing {command}")
            self.env[f"REAL_{command.upper()}"] = executable
            self.write_command(command, """
                import os
                from pathlib import Path
                import subprocess
                import sys

                name = Path(sys.argv[0]).name.upper()
                status = subprocess.run(
                    [os.environ['REAL_' + name], *sys.argv[1:]], check=False
                ).returncode
                forced = int(os.environ.get('FAKE_' + name + '_RC', '0'))
                if forced:
                    print('injected ' + name + ' failure', file=sys.stderr)
                sys.exit(status or forced)
            """)
        self.write_command("notify", """
            import os
            import sys
            with open(os.environ['FAKE_NOTIFICATIONS'], 'a') as output:
                output.write(sys.argv[1] + '\\n')
        """)
        self.write_command("rclone", """
            import hashlib
            import json
            import os
            from pathlib import Path
            import shutil
            import sys

            args = sys.argv[1:]
            commands = {'copyto', 'hashsum', 'delete', 'lsf'}
            index = next(i for i, arg in enumerate(args) if arg in commands)
            operation, *rest = args[index:]
            with open(os.environ['FAKE_CALLS'], 'a') as output:
                output.write(json.dumps([operation, *rest]) + '\\n')
            remote = Path(os.environ['FAKE_REMOTE_DIR'])

            def resolve(value):
                if value.startswith('fake:backups/'):
                    return remote / value.rsplit('/', 1)[1]
                if value.startswith('fake:'):
                    raise AssertionError('Unexpected fake remote: ' + value)
                return Path(value)

            if operation == 'copyto':
                stage = 'latest' if rest[0].startswith('fake:') else 'history'
                if os.environ.get('FAKE_COPY_FAIL') == stage:
                    print('injected copy failure: ' + stage, file=sys.stderr)
                    sys.exit(5)
                shutil.copyfile(resolve(rest[0]), resolve(rest[1]))
            elif operation == 'hashsum':
                assert rest[0] == 'sha256'
                digest = hashlib.sha256(resolve(rest[1]).read_bytes()).hexdigest()
                if os.environ.get('FAKE_BAD_HASH'):
                    digest = '0' * 64
                print(digest + '  archive.tar.gz')
            elif operation == 'lsf':
                for item in sorted(remote.glob('smoki-full_*.tar.gz')):
                    print(item.name)
            # Retention is recorded but never deletes anything in this fake.
        """)

    def write_command(self, name, source):
        command = self.bin / name
        command.write_text(f"#!{sys.executable}\n" + textwrap.dedent(source))
        command.chmod(0o755)

    def run_backup(self, **overrides):
        result = subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=self.root,
            env={**self.env, **{key: str(value) for key, value in overrides.items()}},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        calls_path = self.root / "calls.jsonl"
        self.calls = (
            [json.loads(line) for line in calls_path.read_text().splitlines()]
            if calls_path.exists() else []
        )
        notify_path = self.root / "notifications"
        self.notifications = notify_path.read_text().splitlines() if notify_path.exists() else []
        # Cleanup must run on success and on every tested failure.
        self.assertEqual(list(self.staging.glob("*.tmp")), [])
        self.assertEqual(list(self.staging.glob("*.tar.gz")), [])
        self.assertEqual(list(self.staging.glob("*.tar.stderr")), [])
        return result

    def assert_success(self, result, tar_rc):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"tar_rc={tar_rc}", result.stdout)
        self.assertIn("OK: full-offsite backup complete", result.stdout)
        self.assertEqual(self.notifications, ["offsite-full-recovered"])
        self.assertEqual(
            [call[0] for call in self.calls],
            ["copyto", "copyto", "hashsum", "delete", "lsf"],
        )
        history = list(self.remote.glob("smoki-full_*.tar.gz"))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].read_bytes(), (self.remote / "smoki-full-latest.tar.gz").read_bytes())
        with tarfile.open(history[0], "r:gz") as archive:
            member = archive.extractfile("SMOKI/payload.bin")
            self.assertIsNotNone(member)
            self.assertEqual(member.read(), self.payload)

    def assert_failure(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("OK: full-offsite backup complete", result.stdout)
        self.assertEqual(self.notifications, ["offsite-full-failed"])
        self.assertNotIn("delete", [call[0] for call in self.calls])

    def test_success_uploads_valid_history_and_latest(self):
        self.assert_success(self.run_backup(), tar_rc=0)

    def test_tar_changed_file_status_does_not_trigger_err_trap(self):
        self.assert_success(self.run_backup(FAKE_TAR_RC=1), tar_rc=1)

    def test_fatal_tar_error_is_reported_before_any_upload(self):
        result = self.run_backup(FAKE_TAR_RC=2)
        self.assert_failure(result)
        self.assertIn("tar упал (rc=2)", result.stdout)
        self.assertIn("injected TAR failure", result.stdout)
        self.assertEqual(self.calls, [])

    def test_gzip_error_is_reported_before_any_upload(self):
        result = self.run_backup(FAKE_GZIP_RC=1)
        self.assert_failure(result)
        self.assertIn("gzip упал (rc=1)", result.stdout)
        self.assertEqual(self.calls, [])

    def test_tar_warning_does_not_hide_gzip_error(self):
        result = self.run_backup(FAKE_TAR_RC=1, FAKE_GZIP_RC=1)
        self.assert_failure(result)
        self.assertIn("gzip упал (rc=1)", result.stdout)
        self.assertEqual(self.calls, [])

    def test_unrelated_failure_still_triggers_err_trap(self):
        result = self.run_backup(FAKE_SHA256SUM_RC=7)
        self.assert_failure(result)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.calls, [])

    def test_history_upload_failure_does_not_copy_latest(self):
        result = self.run_backup(FAKE_COPY_FAIL="history")
        self.assert_failure(result)
        self.assertEqual([call[0] for call in self.calls], ["copyto"])
        self.assertEqual(list(self.remote.iterdir()), [])

    def test_latest_copy_failure_is_not_reported_as_success(self):
        result = self.run_backup(FAKE_COPY_FAIL="latest")
        self.assert_failure(result)
        self.assertEqual([call[0] for call in self.calls], ["copyto", "copyto"])
        self.assertEqual(len(list(self.remote.glob("smoki-full_*.tar.gz"))), 1)
        self.assertFalse((self.remote / "smoki-full-latest.tar.gz").exists())

    def test_checksum_mismatch_is_not_reported_as_success(self):
        result = self.run_backup(FAKE_BAD_HASH=1)
        self.assert_failure(result)
        self.assertIn("integrity FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
