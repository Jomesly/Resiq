"""Consistent local-volume backups and an isolated PostgreSQL restoration drill.

Run with Python 3.12+. Never restores over the live database. The backup directory
contains sensitive receipts and credentials; encrypt and copy it off the host.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(env_file, output, *, project="resiq-production"):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if os.name != "nt":
        output.chmod(0o700)
    command = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(env_file.resolve()),
        "-f",
        str(ROOT / "compose.production.yml"),
    ]
    services = ["api", "worker", "maintenance"]
    running = run(
        command + ["ps", "--services", "--status", "running"], capture_output=True, text=True
    ).stdout.splitlines()
    restart = [name for name in services if name in running]
    try:
        # Stop admissions, finish/fence workers, and freeze cleanup before taking both snapshots.
        run(command + ["stop", "--timeout", "110", *services])
        with (output / "database.dump").open("wb") as stream:
            run(
                command
                + [
                    "exec",
                    "-T",
                    "db",
                    "pg_dump",
                    "-U",
                    "resiq",
                    "-d",
                    "resiq",
                    "-Fc",
                    "--no-owner",
                ],
                stdout=stream,
            )
        script = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add('/data',arcname='receipts'); t.close()"
        with (output / "receipts.tar").open("wb") as stream:
            run(
                command + ["run", "--rm", "--no-deps", "-T", "api", "python", "-c", script],
                stdout=stream,
            )
        manifest = {
            "format": 1,
            "created_at_unix": time.time(),
            "files": {name: digest(output / name) for name in ("database.dump", "receipts.tar")},
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("Backup complete. Run restore-check, encrypt it, and copy it off this host.")
    finally:
        if restart:
            run(command + ["start", *restart])


def restore_check(source):
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name in ("database.dump", "receipts.tar"):
        if digest(source / name) != manifest["files"][name]:
            raise ValueError("Backup checksum mismatch: " + name)
    container = "resiq-restore-check-" + uuid4().hex
    env = {**os.environ, "POSTGRES_PASSWORD": secrets.token_urlsafe(32)}
    try:
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container,
                "--network",
                "none",
                "--tmpfs",
                "/var/lib/postgresql/data",
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_USER=resiq",
                "-e",
                "POSTGRES_DB=resiq",
                "postgres:16-alpine",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
        )
        for _ in range(60):
            probe = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "resiq", "-d", "resiq"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError("Restore database did not start.")
        with (source / "database.dump").open("rb") as stream:
            run(
                [
                    "docker",
                    "exec",
                    "-i",
                    container,
                    "pg_restore",
                    "-U",
                    "resiq",
                    "-d",
                    "resiq",
                    "--no-owner",
                    "--exit-on-error",
                ],
                stdin=stream,
            )
        query = "SELECT original_key FROM receipts UNION SELECT processed_key FROM receipts WHERE processed_key IS NOT NULL UNION SELECT value FROM receipts, jsonb_each_text(stage_keys)"
        keys = run(
            ["docker", "exec", container, "psql", "-U", "resiq", "-d", "resiq", "-At", "-c", query],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        with tempfile.TemporaryDirectory(prefix="resiq-restore-") as directory:
            root = Path(directory).resolve()
            with tarfile.open(source / "receipts.tar") as archive:
                for member in archive.getmembers():
                    if not (member.isfile() or member.isdir()) or not (
                        root / member.name
                    ).resolve().is_relative_to(root):
                        raise ValueError("Unsafe backup archive member.")
                archive.extractall(root, filter="data")
            for key in keys:
                target = (root / "receipts" / key).resolve()
                if (
                    not target.is_relative_to(root / "receipts")
                    or not target.is_file()
                    or target.stat().st_size == 0
                ):
                    raise ValueError("A referenced receipt image was not restored.")
        counts = run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "resiq",
                "-d",
                "resiq",
                "-At",
                "-c",
                "SELECT count(*) FROM receipts",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()
        print(
            json.dumps(
                {
                    "restoration_passed": True,
                    "receipts": int(counts),
                    "referenced_images_verified": len(keys),
                }
            )
        )
    finally:
        # The exact newly-created container name is the only deletion target.
        subprocess.run(
            ["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("backup")
    create.add_argument("--env-file", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--project-name", default="resiq-production")
    check = sub.add_parser("restore-check")
    check.add_argument("source", type=Path)
    args = parser.parse_args()
    if args.command == "backup":
        backup(args.env_file, args.output, project=args.project_name)
    else:
        restore_check(args.source)


if __name__ == "__main__":
    main()
