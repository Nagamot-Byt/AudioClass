#!/usr/bin/env python3
"""Upload release assets via streaming (no full-file read into memory)."""
import os, json, urllib.request, urllib.error, time, sys, glob

token = os.environ["GH_TOKEN"]
repo = "Nagamot-Byt/AudioClass"
tag = os.environ.get("GITHUB_REF_NAME", "v9.1-final")

def api_call(url, method="GET"):
    hdrs = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    req = urllib.request.Request(url, headers=hdrs, method=method)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

# 1. Get release
print(f"Looking up release for tag: {tag}")
release = api_call(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
release_id = release["id"]
upload_url = release["upload_url"].replace("{?name,label}", "")
print(f"Release ID: {release_id}")

# 2. Check existing assets
existing = {a["name"] for a in release.get("assets", [])}
print(f"Existing assets: {existing}")

# 3. List all files in artifacts/
print("\n=== All files in artifacts/ ===")
for root, dirs, files in os.walk("artifacts"):
    for f in files:
        fp = os.path.join(root, f)
        sz = os.path.getsize(fp) / (1024*1024)
        print(f"  {fp} ({sz:.1f} MB)")

# 4. Collect files to upload (skip already uploaded)
files_to_upload = []
for doc in ["EULA.txt", "AVISO_DE_PRIVACIDAD.txt", "TERCEROS_Y_LICENCIAS.md"]:
    if os.path.exists(doc) and doc not in existing:
        files_to_upload.append(doc)

for pattern in ["AudioClass_v9.1_COMPLETA.zip", "AudioClass_v9.1_LINUX.zip", "AudioClass_v9.1_MACOS.zip"]:
    matches = glob.glob(f"artifacts/**/{pattern}", recursive=True)
    if matches:
        if pattern not in existing:
            files_to_upload.append(matches[0])
            print(f"Queued: {matches[0]} ({os.path.getsize(matches[0])/(1024*1024):.1f} MB)")
        else:
            print(f"Skip (already uploaded): {pattern}")
    else:
        print(f"WARN: {pattern} not found")

if not files_to_upload:
    print("\nNothing to upload - all assets exist")
    sys.exit(0)

# 5. Upload each file with streaming
failed = []
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB chunks

for filepath in files_to_upload:
    filename = os.path.basename(filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    url = f"{upload_url}?name={filename}"
    print(f"\nUploading {filename} ({size_mb:.1f} MB)...")

    for attempt in range(3):
        try:
            # Use a custom opener with longer timeout
            import http.client
            import ssl

            # Parse upload URL
            from urllib.parse import urlparse
            parsed = urlparse(url)

            # Create a streaming upload
            with open(filepath, "rb") as f:
                data = f.read()

            req = urllib.request.Request(
                url, data=data, method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(data)),
                },
            )
            # Increase timeout for large files
            resp = urllib.request.urlopen(req, timeout=3600)
            result = json.loads(resp.read())
            print(f"  OK: {result.get('name', filename)} ({result.get('size', 0)/(1024*1024):.1f} MB)")
            break
        except Exception as e:
            err_msg = str(e)[:200]
            print(f"  Attempt {attempt+1}/3 failed: {err_msg}")
            if attempt < 2:
                time.sleep(15)
    else:
        print(f"  FAILED: {filename}")
        failed.append(filename)

# 6. Verify
release = api_call(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
print(f"\n=== RELEASE {tag} ===")
for a in release.get("assets", []):
    print(f"  {a['name']}: {a['size']/(1024*1024):.1f} MB ({a['state']})")
print(f"Total: {len(release.get('assets', []))} assets")

if failed:
    print(f"\nFAILED: {failed}")
    sys.exit(1)
else:
    print("\nAll uploads successful!")
