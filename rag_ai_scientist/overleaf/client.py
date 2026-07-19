from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from rag_ai_scientist.overleaf.config import OverleafProject


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
    )


@dataclass
class OverleafClient:
    project: OverleafProject
    mirror_dir: Path
    author_name: str = "RAG AI Scientist"
    author_email: str = "rag-ai-scientist@local"
    commit_message: str = "auto: sync from rag-ai-scientist ({sha} @ {ts})"
    skip_if_unchanged: bool = True

    @property
    def remote_url(self) -> str:
        token = urllib.parse.quote(self.project.git_token, safe="")
        return f"https://git:{token}@git.overleaf.com/{self.project.project_id}"

    @property
    def masked_remote(self) -> str:
        return f"https://git:***@git.overleaf.com/{self.project.project_id}"

    def ensure_mirror(self) -> Path:
        mirror = self.mirror_dir
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if (mirror / ".git").is_dir():
            _run(["git", "fetch", "origin"], mirror)
            # Overleaf remotes are typically `master`
            try:
                _run(["git", "reset", "--hard", "origin/master"], mirror)
            except subprocess.CalledProcessError:
                _run(["git", "reset", "--hard", "origin/main"], mirror)
            return mirror
        _run(["git", "clone", self.remote_url, str(mirror)])
        return mirror

    def list_files(self, relative: str = "") -> list[str]:
        mirror = self.ensure_mirror()
        root = (mirror / relative).resolve()
        if not str(root).startswith(str(mirror.resolve())):
            raise ValueError("Path escapes mirror root")
        if not root.exists():
            return []
        files: list[str] = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                files.append(str(path.relative_to(mirror)))
        return files

    def read_file(self, relative: str) -> str:
        mirror = self.ensure_mirror()
        path = (mirror / relative).resolve()
        if not str(path).startswith(str(mirror.resolve())):
            raise ValueError("Path escapes mirror root")
        if not path.is_file():
            raise FileNotFoundError(relative)
        return path.read_text(encoding="utf-8")

    def status(self) -> dict:
        mirror = self.ensure_mirror()
        porcelain = _run(["git", "status", "--porcelain"], mirror).stdout
        head = _run(["git", "rev-parse", "--short", "HEAD"], mirror).stdout.strip()
        return {
            "project": self.project.key,
            "name": self.project.name,
            "project_id": self.project.project_id,
            "mirror": str(mirror),
            "head": head,
            "dirty": bool(porcelain.strip()),
            "porcelain": porcelain.strip(),
            "remote": self.masked_remote,
        }

    def sync_bundle(
        self,
        bundle_dir: Path,
        *,
        dry_run: bool = False,
        main_tex_name: str = "main.tex",
    ) -> dict:
        bundle_dir = bundle_dir.resolve()
        if not bundle_dir.is_dir():
            raise FileNotFoundError(f"Bundle dir missing: {bundle_dir}")

        mirror = self.ensure_mirror()
        copied = 0
        for src in bundle_dir.rglob("*"):
            if src.is_dir() or src.name.startswith("."):
                continue
            rel = src.relative_to(bundle_dir)
            dest = mirror / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1

        dirty = _run(["git", "status", "--porcelain"], mirror).stdout.strip()
        if not dirty and self.skip_if_unchanged:
            return {
                "ok": True,
                "pushed": False,
                "reason": "unchanged",
                "copied": copied,
                "remote": self.masked_remote,
            }

        main_tex = mirror / main_tex_name
        sha = _sha256_prefix(main_tex) if main_tex.is_file() else "nomaintex"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        msg = self.commit_message.format(sha=sha, ts=ts)

        _run(["git", "add", "-A"], mirror)
        if dry_run:
            return {
                "ok": True,
                "pushed": False,
                "reason": "dry_run",
                "copied": copied,
                "commit_message": msg,
                "status": _run(["git", "status", "--short"], mirror).stdout,
                "remote": self.masked_remote,
            }

        _run(
            [
                "git",
                "-c",
                f"user.name={self.author_name}",
                "-c",
                f"user.email={self.author_email}",
                "commit",
                "-m",
                msg,
            ],
            mirror,
        )
        try:
            _run(["git", "push", "origin", "HEAD:master"], mirror)
        except subprocess.CalledProcessError:
            _run(["git", "push", "origin", "HEAD:main"], mirror)

        return {
            "ok": True,
            "pushed": True,
            "copied": copied,
            "commit_message": msg,
            "remote": self.masked_remote,
        }


def _sha256_prefix(path: Path, *, n: int = 10) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def client_for_project(
    project: OverleafProject,
    *,
    project_root: Path,
    mirror_subdir: str = ".overleaf_mirror",
) -> OverleafClient:
    mirror = project_root / mirror_subdir / project.key
    return OverleafClient(project=project, mirror_dir=mirror)
