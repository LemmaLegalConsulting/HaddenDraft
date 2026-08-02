import os
import glob
import hashlib
import json
import shutil
import argparse

def get_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    parser = argparse.ArgumentParser(
        description="Copy verified local case-law sidecars into private artifact storage."
    )
    parser.add_argument(
        "--source-dir",
        default=os.environ.get("CASELAW_DOWNLOAD_DIR", "downloaded_cases"),
        help="Directory containing PDF, .txt, .json, and .verified.json sidecars.",
    )
    parser.add_argument(
        "--target-dir",
        default="private-content/caselaw-artifacts/caselaw",
        help="Private case-law artifact directory to populate.",
    )
    args = parser.parse_args()

    source_dir = args.source_dir
    target_base = args.target_dir

    originals_dir = os.path.join(target_base, "originals")
    ocr_dir = os.path.join(target_base, "ocr-text")
    metadata_dir = os.path.join(target_base, "metadata")

    os.makedirs(originals_dir, exist_ok=True)
    os.makedirs(ocr_dir, exist_ok=True)
    os.makedirs(metadata_dir, exist_ok=True)

    pdf_files = sorted(glob.glob(os.path.join(source_dir, "*.pdf")))
    count = 0
    for pdf_path in pdf_files:
        verified_path = pdf_path.replace(".pdf", ".verified.json")
        json_path = pdf_path + ".json"
        txt_path = pdf_path + ".txt"

        if not os.path.exists(verified_path) or not os.path.exists(json_path) or not os.path.exists(txt_path):
            continue

        pdf_sha = get_sha256(pdf_path)
        file_size = os.path.getsize(pdf_path)

        target_pdf = os.path.join(originals_dir, f"{pdf_sha}.pdf")
        target_txt = os.path.join(ocr_dir, f"{pdf_sha}.txt")
        target_json = os.path.join(metadata_dir, f"{pdf_sha}.json")
        target_verified = os.path.join(metadata_dir, f"{pdf_sha}.verified.json")

        # copy pdf and txt
        shutil.copy2(pdf_path, target_pdf)
        shutil.copy2(txt_path, target_txt)
        shutil.copy2(verified_path, target_verified)

        # update and copy metadata
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                continue

        metadata["source_sha256"] = pdf_sha
        metadata["file_size_bytes"] = file_size

        with open(target_json, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        count += 1

    print(f"Successfully ingested {count} cases into {target_base}")

if __name__ == "__main__":
    main()
