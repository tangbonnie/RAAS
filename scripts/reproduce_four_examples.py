#!/usr/bin/env python3
"""Recompute the four supplied examples with the released software itself.

No cached analysis or ground-truth counts are loaded. Figures use the real GUI
result widget. --no-figures avoids importing Qt and runs the same analysis engine.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / "datasets/four_examples/analysis_parameters.json"
SOURCE_FILES = (
    "app_version.py", "calibration.py", "preprocess.py", "root_segmentation.py",
    "root_crown.py", "root_stem.py", "root_topology.py", "root_analysis.py", "root_gui.py",
    "scripts/reproduce_four_examples.py",
)
NAMES = {1: "shared_crown_wire", 2: "overlapping_wire", 3: "dense_wire", 4: "real_roots"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_value(value):
    """JSON has no NaN/Infinity; preserve missing measurements as null."""
    import numpy as np
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def write_json(path, value):
    Path(path).write_text(
        json.dumps(json_value(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def export_points(path, result):
    """Export the exact GUI points. Source coordinates are (row, column)."""
    import numpy as np
    groups = (
        ("B", "base", "_base_coords", "Num_Bases"),
        ("T", "visible_endpoint", "_tip_coords", "Num_Tips"),
        ("F", "fork_candidate", "_fork_coords", "Num_Forks"),
        ("X", "crossing_candidate", "_crossing_coords", "Num_Crossings"),
    )
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "type", "x", "y"])
        writer.writeheader()
        for prefix, kind, key, count_key in groups:
            points = np.asarray(result[key], dtype=float).reshape(-1, 2)
            if len(points) != result[count_key] or not np.isfinite(points).all():
                raise ValueError(f"Invalid point/count correspondence: {key}")
            for index, (row, column) in enumerate(points, 1):
                writer.writerow(dict(id=f"{prefix}{index}", type=kind,
                                     x=float(column), y=float(row)))


def check_unknown_scale(example, result):
    if example["calibration_status"] != "unknown":
        return
    if result["Scale_Source"] != "unknown":
        raise ValueError("Uncalibrated input unexpectedly acquired a physical scale")
    physical_keys = ["DPI"] + [
        key for key in result
        if key.endswith(("_cm", "_cm2", "_cm3", "_mm"))
    ]
    for key in physical_keys:
        if not math.isnan(float(result[key])):
            raise ValueError(f"Uncalibrated input must retain NaN for {key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", nargs="+", type=int, choices=range(1, 5),
                        default=[1, 2, 3, 4], metavar="N", help="Image IDs (1-4); default: all four")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/four_examples",
                        help="Output directory; default: repository results/four_examples")
    parser.add_argument("--no-figures", action="store_true",
                        help="Compute metrics and points without importing Qt")
    args = parser.parse_args()
    selected = list(dict.fromkeys(args.images))
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    examples = {int(example["id"]): example for example in config["examples"]}
    sys.path.insert(0, str(ROOT))

    from PIL import Image
    from app_version import APP_VERSION
    from preprocess import process_single_image
    from root_analysis import analyze_root_image

    # Validate every requested source before starting expensive calculations.
    inputs = {}
    for number in selected:
        example = examples[number]
        source = (PARAMETERS.parent / example["path"]).resolve()
        source.relative_to(PARAMETERS.parent.resolve())
        if sha256(source) != example["sha256"]:
            raise ValueError(f"Input SHA-256 does not match the manifest: {source.name}")
        with Image.open(source) as image:
            if image.size != (example["width"], example["height"]):
                raise ValueError(f"Input dimensions do not match: {source.name}")
            if example["embedded_dpi"] is None and image.info.get("dpi") is not None:
                raise ValueError(f"Unexpected DPI metadata: {source.name}")
        inputs[number] = source

    app = viewer = None
    if not args.no_figures:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        if sys.platform == 'win32' and font_dir.is_dir():
            os.environ.setdefault('QT_QPA_FONTDIR', str(font_dir))
        from root_gui import QApplication, AnalysisResultViewer, LIGHT_QSS
        app = QApplication.instance() or QApplication([])
        app.setStyle("Fusion")
        app.setStyleSheet(LIGHT_QSS)
        viewer = AnalysisResultViewer()
        viewer.resize(1900, 1120)
        viewer.show()
        app.processEvents()

    package_versions = {}
    for package in ("numpy", "scipy", "scikit-image", "skan", "Pillow", "matplotlib", "PyQt5"):
        try:
            package_versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            package_versions[package] = None
    provenance = dict(
        software_version=APP_VERSION,
        started_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(), platform=platform.system(),
        packages=package_versions, images=selected, figures=not args.no_figures,
        parameters_sha256=sha256(PARAMETERS),
        source_sha256={name: sha256(ROOT / name) for name in SOURCE_FILES},
        notes="Recomputed software outputs, not biological ground truth. No physical scale is assumed. "
              "Visible endpoints include suspected cropped endpoints without adding a duplicate count.",
        runs=[],
    )
    rows = []
    try:
        for number in selected:
            started = time.perf_counter()
            example = examples[number]
            print(f"Image {number}: preprocessing and analysing the native input...", flush=True)
            binary, skeleton = process_single_image(
                str(inputs[number]), str(output / f"processed_{number}"), **example["preprocess"])
            # The engine can load an adjacent manual-review JSON. A reproducible
            # fresh run must not silently reuse a previous user's annotation.
            if Path(str(binary) + ".review.json").exists():
                raise ValueError("Output contains an existing review annotation; choose a fresh output directory")
            result = analyze_root_image(binary, skeleton, sample_id=f"{number}_{NAMES[number]}",
                                        **example["analysis"], step_log=lambda message: print(message, flush=True))
            check_unknown_scale(example, result)
            public = json_value({key: value for key, value in result.items() if not key.startswith("_")})
            write_json(output / f"metrics_{number}.json", public)
            export_points(output / f"points_{number}.csv", result)
            if viewer is not None:
                viewer._marker_slider.setValue(12 if number == 1 else (6 if number < 4 else 4))
                viewer.show_result(str(binary), str(skeleton), result)
                app.processEvents()
                if len(viewer.fig.axes) != 3 or viewer._render_cache is None:
                    raise RuntimeError("The actual GUI result viewer did not render three panels")
                if any("Display error" in label.get_text()
                       for axis in viewer.fig.axes for label in axis.texts):
                    raise RuntimeError("The actual GUI result viewer reported a display error")
                viewer.fig.savefig(output / f"figure_{number}.png", dpi=160, facecolor="white")
                if not viewer.grab().save(str(output / f"interface_{number}.png")):
                    raise RuntimeError('Failed to save the actual result widget screenshot')
                stem_roi = json.loads(result.get('Stem_Repair_ROI', 'null'))
                if stem_roi:
                    r0, c0, r1, c1 = stem_roi
                    for axis in viewer.fig.axes[:2]:
                        axis.set_xlim(c0 - 50, c1 + 90)
                        axis.set_ylim(r1 + 120, r0 - 30)
                    viewer.fig.savefig(output / f"stem_detail_{number}.png", dpi=160,
                                       facecolor='white')
            rows.append(public)
            provenance["runs"].append(dict(
                image=number, parameters=example, input_sha256=sha256(inputs[number]),
                binary_sha256=sha256(binary), skeleton_sha256=sha256(skeleton),
                seconds=round(time.perf_counter() - started, 3),
            ))
            print(f"Image {number}: Tips={result['Num_Tips']}, Forks={result['Num_Forks']}, "
                  f"Crossings={result['Num_Crossings']}; {provenance['runs'][-1]['seconds']:.1f}s", flush=True)
    finally:
        if viewer is not None:
            viewer.close()
    with (output / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
        writer.writeheader()
        writer.writerows(rows)
    provenance["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "provenance.json", provenance)
    print(f"Results saved to: {output}", flush=True)


if __name__ == "__main__":
    main()
