#!/usr/bin/env python3
"""
build.py — Builds the 'NCAAF Scores.alfredworkflow' archive.
Ensures all 138 FBS logos are downloaded and packages all workflow files into a zip.
"""
import os
import zipfile

WORKFLOW_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE  = os.path.join(WORKFLOW_DIR, "NCAAF Scores.alfredworkflow")


def ensure_logos():
    logos_dir = os.path.join(WORKFLOW_DIR, "cfb_logos")
    if not os.path.exists(logos_dir) or len(os.listdir(logos_dir)) < 130:
        print("Missing logos, downloading now...")
        import download_logos
        download_logos.download_all_logos()


def build_workflow():
    ensure_logos()

    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    top_level_files = [
        "cfb.py",
        "cfb_standings.py",
        "cfb_rankings.py",
        "cfb_team.py",
        "utils.py",
        "image_utils.py",
        "info.plist",
        "icon.png",
        "README.md",
        "requirements.txt",
    ]

    with zipfile.ZipFile(OUTPUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in top_level_files:
            fpath = os.path.join(WORKFLOW_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
                print(f"  + Added {fname}")

        # Add data/
        data_dir = os.path.join(WORKFLOW_DIR, "data")
        for root, _, files in os.walk(data_dir):
            for file in files:
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, WORKFLOW_DIR)
                zf.write(fpath, arcname=rel_path)
                print(f"  + Added {rel_path}")

        # Add cfb_logos/
        logos_dir = os.path.join(WORKFLOW_DIR, "cfb_logos")
        for root, _, files in os.walk(logos_dir):
            for file in files:
                if file.startswith("."):
                    continue
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, WORKFLOW_DIR)
                zf.write(fpath, arcname=rel_path)
        print(f"  + Added {len(os.listdir(logos_dir))} team logos from cfb_logos/")

        # Add bundled lib/
        lib_dir = os.path.join(WORKFLOW_DIR, "lib")
        lib_count = 0
        for root, _, files in os.walk(lib_dir):
            for file in files:
                if file.endswith(".pyc") or "__pycache__" in root:
                    continue
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, WORKFLOW_DIR)
                zf.write(fpath, arcname=rel_path)
                lib_count += 1
        print(f"  + Added {lib_count} bundled library files from lib/")

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\n🎉 Successfully created: {OUTPUT_FILE} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build_workflow()
