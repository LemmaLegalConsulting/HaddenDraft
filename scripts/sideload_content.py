import os
import sys
import argparse
import io
import zipfile
import tarfile
from urllib.parse import urlparse
from pathlib import Path
import requests

def download_and_extract(url, target_dir):
    print(f"Downloading from {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        sys.exit(1)
    
    path = urlparse(url).path
    if path.endswith('.zip') or url.endswith('.zip'):
        print(f"Extracting zip to {target_dir}...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(target_dir)
    elif path.endswith('.tar.gz') or path.endswith('.tgz') or url.endswith('.tar.gz'):
        print(f"Extracting tar to {target_dir}...")
        with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as t:
            t.extractall(target_dir)
    else:
        print("Could not determine format from URL. Assuming zip format...")
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(target_dir)
        except zipfile.BadZipFile:
            print("Failed to extract as zip. Please ensure the URL points to a .zip or .tar.gz archive.")
            sys.exit(1)
            
    print(f"Successfully sideloaded content into {target_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sideload treatises or other content from an archive URL.")
    parser.add_argument("--url", help="URL of the zip or tar.gz archive to sideload", required=True)
    parser.add_argument("--target", help="Target directory (defaults to CONTENT_LIBRARY_DIR or content/)", default="")
    args = parser.parse_args()
    
    target = args.target
    if not target:
        # fallback to CONTENT_LIBRARY_DIR env var or default content/
        target = os.environ.get("CONTENT_LIBRARY_DIR", "content")
        
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)
    
    download_and_extract(args.url, target_path)
