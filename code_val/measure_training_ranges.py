"""Valide les site_request d'un dataset contre le contrat et y reecrit les plages d'entrainement.

Un dataset peut etre un dossier de scenes, ou le dossier qui contient un sous-dossier par arbre
(dataset_v3/<xml>/) : les plages sont alors mesurees sur l'ensemble des arbres.
"""
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

CODE_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_PATH = CODE_DIRECTORY / "site_request.schema.json"
DEFAULT_DATASET = CODE_DIRECTORY / "dataset_v3"
SITE_REQUEST_SUBDIRECTORY = "site_request"
RANGE_KEY = "x-training-range"
RANGE_PATTERN = re.compile(r'"x-training-range": \[[^\]]*\]')
RANGE_DECIMALS = 3


def list_range_paths(node, path=()) -> list:
    """Dans l'ordre du document, qui est celui des occurrences dans le texte."""
    if not isinstance(node, dict):
        return []
    paths = [path] if RANGE_KEY in node else []
    for key, value in node.items():
        paths += list_range_paths(value, path + (key,))
    return paths


def collect_values(instance, node: dict, path: tuple, schema: dict, buckets: dict) -> None:
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        node, path = schema["$defs"][name], ("$defs", name)
    if RANGE_KEY in node and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        buckets[path].append(instance)
    if isinstance(instance, dict):
        for key, value in instance.items():
            if key in node.get("properties", {}):
                collect_values(value, node["properties"][key], path + ("properties", key), schema, buckets)
    elif isinstance(instance, list) and "items" in node:
        for item in instance:
            collect_values(item, node["items"], path + ("items",), schema, buckets)


def format_range(values: list) -> str:
    scale = 10 ** RANGE_DECIMALS
    low, high = math.floor(min(values) * scale) / scale, math.ceil(max(values) * scale) / scale
    return f'"{RANGE_KEY}": [{low}, {high}]'


def rewrite_ranges(text: str, schema: dict, buckets: dict) -> str:
    replacements = iter([format_range(buckets[path]) if buckets[path] else None
                         for path in list_range_paths(schema)])
    return RANGE_PATTERN.sub(lambda match: next(replacements) or match.group(0), text)


def collect_dataset(paths: list, schema: dict) -> dict:
    validator = Draft202012Validator(schema)
    buckets = defaultdict(list)
    for path in paths:
        request = json.loads(path.read_text(encoding="utf-8"))
        errors = [error.message for error in validator.iter_errors(request)]
        if errors:
            raise SystemExit(f"{path.name} viole le contrat : {errors[:3]}")
        collect_values(request, schema, (), schema, buckets)
    return buckets


def list_site_requests(datasets: list) -> list:
    """Les scenes de chaque dossier, ou de ses sous-dossiers par arbre quand il n'en porte pas lui-meme."""
    paths = []
    for dataset in datasets:
        direct = sorted((dataset / SITE_REQUEST_SUBDIRECTORY).glob("scene_*.json"))
        paths += direct or sorted(dataset.glob(f"*/{SITE_REQUEST_SUBDIRECTORY}/scene_*.json"))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, nargs="+", default=[DEFAULT_DATASET])
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    arguments = parser.parse_args()

    # En octets, pour rendre les fins de ligne telles quelles sous Windows comme sous Linux.
    text = arguments.schema.read_bytes().decode("utf-8")
    schema = json.loads(text)
    paths = list_site_requests(arguments.dataset)
    buckets = collect_dataset(paths, schema)
    for path in list_range_paths(schema):
        if not buckets[path]:
            print(f"aucune valeur pour {'.'.join(path)} : plage conservee")

    arguments.schema.write_bytes(rewrite_ranges(text, schema, buckets).encode("utf-8"))
    print(f"{len(paths)} site_request valides, plages reecrites dans {arguments.schema.name}")


if __name__ == "__main__":
    main()
