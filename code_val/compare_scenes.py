"""Compare two directories of generated scenes, array by array.

    python3 code_val/compare_scenes.py code_val/pilot_v3 code_val/tmp/v3_before

Timings, the commit stamp and the request id (it carries the directory name) are left out.
"""
import argparse
import json
from pathlib import Path

import numpy as np

DESCRIPTOR_PATTERN = "scene_*.json"
SITE_REQUEST_SUBDIRECTORY = "site_request"
TIMING_KEYS = ("runtime_seconds", "soil_seconds", "growth_seconds")
VERSION_KEY = "versions"
REQUEST_KEY = "request_id"


def read_descriptor(path: Path) -> dict:
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    descriptor.pop(VERSION_KEY)
    for key in TIMING_KEYS:
        descriptor["diagnostics"].pop(key)
    return descriptor


def read_site_request(path: Path) -> dict:
    request = json.loads(path.read_text(encoding="utf-8"))
    request.pop(REQUEST_KEY)
    return request


def find_array_differences(reference: Path, candidate: Path) -> list:
    with np.load(reference) as expected, np.load(candidate) as produced:
        if set(expected.files) != set(produced.files):
            return ["npz keys"]
        return [key for key in expected.files if not np.array_equal(expected[key], produced[key])]


def find_scene_differences(stem: str, reference: Path, candidate: Path) -> list:
    differences = find_array_differences(reference / f"{stem}.npz", candidate / f"{stem}.npz")
    if (reference / f"{stem}.vti").read_bytes() != (candidate / f"{stem}.vti").read_bytes():
        differences.append("vti")
    if read_descriptor(reference / f"{stem}.json") != read_descriptor(candidate / f"{stem}.json"):
        differences.append("descriptor")
    request = Path(SITE_REQUEST_SUBDIRECTORY) / f"{stem}.json"
    if read_site_request(reference / request) != read_site_request(candidate / request):
        differences.append("site_request")
    return differences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    arguments = parser.parse_args()

    stems = sorted(path.stem for path in arguments.candidate.glob(DESCRIPTOR_PATTERN))
    different = 0
    for stem in stems:
        differences = find_scene_differences(stem, arguments.reference, arguments.candidate)
        different += bool(differences)
        print(f"{stem}  {'identical' if not differences else 'DIFFERENT: ' + ', '.join(differences)}")
    print(f"{len(stems) - different}/{len(stems)} scenes identical")
    raise SystemExit(1 if different else 0)


if __name__ == "__main__":
    main()
