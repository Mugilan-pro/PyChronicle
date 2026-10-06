"""Create the submission ZIP file for Member 3 (Weeks 1 & 2).

Packages only the relevant PyChronicle project files into a clean ZIP archive.
"""

import os
import zipfile


def make_submission_zip():
    archive_name = "PyChronicle_Storage_Engine.zip"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(base_dir, archive_name)

    items_to_include = [
        "pychronicle",
        "tests",
        "example_time_travel.py",
        "example_delta_compression.py",
        "benchmark.py",
        "pyproject.toml",
        "README.md",
        "STORAGE_DOCS.md",
        "TEAM_LEAD_EXPLANATION.txt",
    ]

    print(f"Creating submission package: {archive_name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items_to_include:
            item_path = os.path.join(base_dir, item)
            if not os.path.exists(item_path):
                print(f"  [Skip] {item} not found")
                continue

            if os.path.isdir(item_path):
                for root, dirs, files in os.walk(item_path):
                    # Exclude __pycache__ and .pytest_cache
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache")]
                    for f in files:
                        if f.endswith((".pyc", ".pyo")):
                            continue
                        full_fpath = os.path.join(root, f)
                        rel_path = os.path.relpath(full_fpath, base_dir)
                        zf.write(full_fpath, rel_path)
                        print(f"  [Added] {rel_path}")
            else:
                zf.write(item_path, item)
                print(f"  [Added] {item}")

    file_size_kb = os.path.getsize(zip_path) / 1024.0
    print("=" * 60)
    print(f"SUCCESS! Created: {zip_path}")
    print(f"Archive Size: {file_size_kb:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    make_submission_zip()
