#!/usr/bin/env python3
"""Upload release assets via curl (robust for large files)."""
import os, subprocess, json, glob, time, sys

token = os.environ["GH_TOKEN"]
repo = "Nagamot-Byt/AudioClass"
tag = os.environ.get("GITHUB_REF_NAME", "v9.1-final")
headers = f'-H "Authorization: Bearer {token}" -H "Accept: application/vnd.github+json"'

# 1. Get release info
result = subprocess.run(
    f'curl -s {headers} https://api.github.com/repos/{repo}/releases/tags/{tag}',
    shell=True, capture_output=True, text=True
)
release = json.loads(result.stdout)
release_id = release["id"]
upload_url = release["upload_url"].replace("{?name,label}", "")
print(f"Release ID: {release_id}")
print(f"Tag: {tag}")

# 2. Collect files to upload
files_to_upload = []

# Docs legales
for doc in ["EULA.txt", "AVISO_DE_PRIVACIDAD.txt", "TERCEROS_Y_LICENCIAS.md"]:
    if os.path.exists(doc):
        files_to_upload.append(doc)

# Zips de artifacts
for pattern in ["AudioClass_v9.1_COMPLETA.zip", "AudioClass_v9.1_LINUX.zip", "AudioClass_v9.1_MACOS.zip"]:
    matches = glob.glob(f"artifacts/**/{pattern}", recursive=True)
    if matches:
        files_to_upload.append(matches[0])
        print(f"Found: {matches[0]} ({os.path.getsize(matches[0])/(1024*1024):.1f} MB)")
    else:
        print(f"WARN: {pattern} not found in artifacts/")

# 3. Upload each file
failed = []
for filepath in files_to_upload:
    filename = os.path.basename(filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"\nUploading {filename} ({size_mb:.1f} MB)...")
    
    cmd = (
        f'curl -s -w "HTTP_CODE:%{{http_code}}" '
        f'{headers} '
        f'-o /dev/null '
        f'--data-binary @{filepath} '
        f'"{upload_url}?name={filename}"'
    )
    
    for attempt in range(3):
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout
        http_code = output.split("HTTP_CODE:")[-1].strip() if "HTTP_CODE:" in output else "000"
        
        if http_code in ("200", "201"):
            print(f"  OK (HTTP {http_code})")
            break
        else:
            print(f"  Attempt {attempt+1}/3 failed (HTTP {http_code})")
            if result.stderr:
                print(f"  Stderr: {result.stderr[:200]}")
            time.sleep(5)
    else:
        print(f"  FAILED: {filename}")
        failed.append(filename)

if failed:
    print(f"\nFailed uploads: {failed}")
    sys.exit(1)
else:
    print("\nAll assets uploaded successfully")
