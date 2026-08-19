#!/usr/bin/env python3
"""Upload release assets via Python urllib (no curl dependency)."""
import os, json, urllib.request, urllib.error, time, sys, glob

token = os.environ["GH_TOKEN"]
repo = "Nagamot-Byt/AudioClass"
tag = os.environ.get("GITHUB_REF_NAME", "v9.1-final")

def api_call(url, method="GET", data=None, headers_extra=None):
    """Make a GitHub API call."""
    hdrs = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-uploader",
    }
    if headers_extra:
        hdrs.update(headers_extra)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=300)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {body[:500]}")
        raise

# 1. Get release
print(f"Looking up release for tag: {tag}")
release = api_call(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
release_id = release["id"]
upload_url_template = release["upload_url"]
print(f"Release ID: {release_id}, URL: {upload_url_template[:80]}...")

# 2. Delete existing assets (if any)
for asset in release.get("assets", []):
    print(f"Deleting existing asset: {asset['name']}")
    api_call(asset["url"], method="DELETE")

# 3. Collect files
files = []
for doc in ["EULA.txt", "AVISO_DE_PRIVACIDAD.txt", "TERCEROS_Y_LICENCIAS.md"]:
    if os.path.exists(doc):
        files.append(doc)

for pattern in ["AudioClass_v9.1_COMPLETA.zip", "AudioClass_v9.1_LINUX.zip", "AudioClass_v9.1_MACOS.zip"]:
    matches = glob.glob(f"artifacts/**/{pattern}", recursive=True)
    if matches:
        files.append(matches[0])
        print(f"Found: {matches[0]} ({os.path.getsize(matches[0])/(1024*1024):.1f} MB)")
    else:
        print(f"WARN: {pattern} not found")

# 4. Upload each file
failed = []
for filepath in files:
    filename = os.path.basename(filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    url = upload_url_template.replace("{?name,label}", f"?name={filename}")
    print(f"\nUploading {filename} ({size_mb:.1f} MB)...")

    for attempt in range(3):
        try:
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
            resp = urllib.request.urlopen(req, timeout=1800)
            result = json.loads(resp.read())
            print(f"  OK: {result.get('name', filename)} ({result.get('size', 0)/(1024*1024):.1f} MB)")
            break
        except Exception as e:
            print(f"  Attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(10)
    else:
        print(f"  FAILED: {filename}")
        failed.append(filename)

# 5. Summary
release = api_call(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
print(f"\n=== RELEASE {tag} ===")
for a in release.get("assets", []):
    print(f"  {a['name']}: {a['size']/(1024*1024):.1f} MB")
print(f"Total: {len(release.get('assets', []))} assets")

if failed:
    print(f"\nFAILED: {failed}")
    sys.exit(1)
else:
    print("\nAll uploads successful!")
