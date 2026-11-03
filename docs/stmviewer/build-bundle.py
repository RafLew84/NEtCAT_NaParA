"""Bundle committed Viewer sources and local model assets; no network or environment changes.

Run with Python >= 3.11. Model input directories are never modified.
The resulting ZIP includes a per-file SHA-256 manifest and is verified before publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

DOCS = (
    "distribution.md", "distribution-start.txt", "installation.md", "user-guide.md",
    "installation-models.md", "installation-validation.md", "guide.html",
    "build-guide.py", "build-bundle.py", "requirements-docs.txt",
)
SOURCE_PATHS = (
    "LICENSE", "stmviewer", "nanotrack/__init__.py", "nanotrack/core",
    "nanotrack/registration", "napara/core", "napara/io",
    "tests/stmviewer/fixtures/registration/cpu.mpp",
    "tests/stmviewer/fixtures/registration/subpixel.mpp",
    "tests/stmviewer/fixtures/asymmetric.stp",
    "tests/stmviewer/fixtures/s94/frame2.s94",
    *(f"docs/stmviewer/{name}" for name in DOCS),
)
MODELS = {
    "loftr": {
        "checkpoint": "outdoor",
        "url": "http://cmp.felk.cvut.cz/~mishkdmy/models/loftr_outdoor.ckpt",
        "implementation": "Kornia (installed using requirements-deep.txt)",
    },
    "efficientloftr": {
        "url": "https://github.com/zju3dv/EfficientLoFTR",
        "commit": "07e9c1401e71e9c556b1fda9d86d060af36ba176",
    },
    "lightglue": {
        "url": "https://github.com/cvg/LightGlue",
        "commit": "5a650c444718caffc2669dc0094cde908f42dd73",
        "weights_release": "v0.1_arxiv",
    },
    "matchanything": {
        "url": "https://huggingface.co/spaces/LittleFrog/MatchAnything",
        "commit": "6a7bcb589ec8da3a9e861e799122beaa5eba2193",
        "source_subdirectory": "imcui/third_party/MatchAnything",
    },
    "romav2": {
        "url": "https://github.com/Parskatt/RoMaV2",
        "package": "romav2==2.0.1",
        "dinov3_url": "https://github.com/facebookresearch/dinov3",
        "dinov3_commit": "adc254450203739c8149213a7a69d8d905b4fcfa",
    },
}
ASSET_PATHS = (
    "efficientloftr/source", "efficientloftr/weights/eloftr_outdoor.ckpt",
    "lightglue/source", "lightglue/weights/superpoint_v1.pth",
    "lightglue/weights/superpoint_lightglue.pth", "lightglue/licenses",
    "matchanything/source", "matchanything/weights/matchanything_eloftr.ckpt",
    "matchanything/licenses", "romav2/dinov3", "romav2/weights/romav2.0.1.pt",
    "romav2/licenses",
)


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE).stdout


def asset_files(root: Path):
    for item in ASSET_PATHS:
        path = root / item
        if not path.exists():
            raise FileNotFoundError(path)
        paths = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in paths:
            relative = file.relative_to(root)
            if {".git", "__pycache__"} & set(relative.parts):
                continue
            if file.is_symlink():
                raise ValueError(f"Symlink is not allowed in bundle inputs: {file}")
            if file.is_file():
                yield "models/" + relative.as_posix(), file


def write_entry(archive: zipfile.ZipFile, name: str, stream, manifest: dict):
    full_name = "NEtCAT/" + name
    if name in manifest["files"]:
        raise ValueError(f"Duplicate entry: {name}")
    digest = hashlib.sha256()
    size = 0
    # ZIP64 also allows future checkpoints larger than 2 GiB.
    info = zipfile.ZipInfo(full_name, date_time=(2026, 11, 3, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with archive.open(info, "w", force_zip64=True) as target:
        while block := stream.read(1024 * 1024):
            target.write(block)
            digest.update(block)
            size += len(block)
    manifest["files"][name] = {"bytes": size, "sha256": digest.hexdigest()}


def verify(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("NEtCAT/manifest.json"))
        expected = {"NEtCAT/manifest.json"} | {"NEtCAT/" + n for n in manifest["files"]}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("ZIP entries differ from manifest")
        for name, record in manifest["files"].items():
            info = archive.getinfo("NEtCAT/" + name)
            with archive.open(info) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != record["sha256"] or info.file_size != record["bytes"]:
                raise ValueError(f"Damaged ZIP entry: {name}")
    return manifest


def build(args) -> None:
    repo = args.repo.resolve()
    commit = git(repo, "rev-parse", "--verify", args.commit + "^{commit}").decode().strip()
    output = args.output.resolve()
    checksum = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or checksum.exists():
        raise FileExistsError(f"Choose a new output path: {output}")
    assets = list(asset_files(args.model_root.resolve()))
    assets.extend([
        ("models/loftr/weights/loftr_outdoor.ckpt", args.loftr_weights),
        ("models/romav2/" + args.roma_wheel.name, args.roma_wheel),
    ])
    for _, path in assets:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Expected a regular file: {path}")
    sources = git(repo, "archive", "--format=tar", commit, "--", *SOURCE_PATHS)
    manifest = {
        "format": "stmviewer-distribution-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "application_commit": commit, "models": MODELS, "files": {},
        "note": "Python environments are not included. See Instrukcja.html.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stmviewer-bundle-", dir=output.parent) as tmp:
        staged = Path(tmp) / output.name
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            with tarfile.open(fileobj=io.BytesIO(sources)) as tar:
                for entry in tar:
                    if entry.isdir():
                        continue
                    if not entry.isfile():
                        raise ValueError(f"Unsupported Git entry: {entry.name}")
                    with tar.extractfile(entry) as stream:
                        payload = stream.read()
                    write_entry(archive, entry.name, io.BytesIO(payload), manifest)
                    alias = {
                        "docs/stmviewer/guide.html": "Instrukcja.html",
                        "docs/stmviewer/distribution-start.txt": "START-TUTAJ.txt",
                    }.get(entry.name)
                    if alias:
                        write_entry(archive, alias, io.BytesIO(payload), manifest)
            for name, path in assets:
                if path.stat().st_size > 1024 * 1024:
                    print(f"Adding {name} ({path.stat().st_size} bytes)", flush=True)
                with path.open("rb") as stream:
                    write_entry(archive, name, stream, manifest)
            archive.writestr("NEtCAT/manifest.json",
                             json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print("Checking every ZIP member: CRC, length and SHA-256...", flush=True)
        verify(staged)
        with staged.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        # Exclusive creation also protects an output created during this build.
        with output.open("xb") as target, staged.open("rb") as source:
            while block := source.read(1024 * 1024):
                target.write(block)
        checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(json.dumps({"path": str(output), "bytes": output.stat().st_size,
                      "sha256": digest, "files": len(manifest["files"]),
                      "application_commit": commit}, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--model-root", type=Path, default=Path.home() / ".cache/stmviewer")
    parser.add_argument("--loftr-weights", type=Path, required=True)
    parser.add_argument("--roma-wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
