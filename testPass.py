import os, json, uuid, io, zipfile, hashlib, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TEAM_ID = os.environ["APPLE_TEAM_ID"]
PASS_TYPE_ID = os.environ["PASS_TYPE_ID"]
P12_PASSWORD = os.environ["PASS_P12_PASSWORD"]
ORG_NAME = os.getenv("ORG_NAME", "Sample Coffee")


CERTS = Path("/Users/josephcybulzebede/Documents/punchcards/certs")
ASSETS = Path("/Users/josephcybulzebede/Documents/punchcards/assets")

P12 = CERTS / "pass.p12"
WWDR = CERTS / "AppleWWDRCA.pem"
def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()

def build_pass_json(serial: str) -> dict:
    return {
        "formatVersion": 1,
        "passTypeIdentifier": PASS_TYPE_ID,
        "teamIdentifier": TEAM_ID,
        "organizationName": ORG_NAME,
        "description": "Punch card test",
        "serialNumber": serial,
        "logoText": ORG_NAME,
        "foregroundColor": "rgb(255,255,255)",
        "backgroundColor": "rgb(40,40,40)",
        "barcode": {
            "format": "PKBarcodeFormatQR",
            "message": serial,
            "messageEncoding": "iso-8859-1"
        },
        "storeCard": {
            "primaryFields": [
                {"key": "punches", "label": "Punches", "value": "3 / 10"}
            ],
            "auxiliaryFields": [
                {"key": "status", "label": "Status", "value": "Active"}
            ]
        }
        # For live updates later, add:
        # "webServiceURL": "https://api.yourdomain.com/wallet",
        # "authenticationToken": "random-per-pass-token"
    }

def make_pkpass(output_path: Path) -> Path:
    # 1) Collect files
    serial = str(uuid.uuid4())
    files = {}
    files["pass.json"] = json.dumps(build_pass_json(serial), separators=(",", ":")).encode("utf-8")

    # required assets
    for name in ("icon.png", "icon@2x.png"):
        p = ASSETS / name
        print(p)
        if not p.exists():
            raise SystemExit(f"Missing required asset: {p}")
        files[name] = p.read_bytes()
    # optional logo
    if (ASSETS / "logo.png").exists():
        files["logo.png"] = (ASSETS / "logo.png").read_bytes()

    # 2) manifest.json (Apple examples use SHA-1)
    manifest = {fname: sha1(data) for fname, data in files.items()}
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    files["manifest.json"] = manifest_bytes

    # 3) signature (PKCS#7 detached over manifest.json)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "manifest.json").write_bytes(manifest_bytes)

        cert_pem = td / "cert.pem"
        key_pem = td / "key.pem"
        # Extract cert (no keys)
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(P12), "-clcerts", "-nokeys",
             "-passin", f"pass:{P12_PASSWORD}", "-out", str(cert_pem)],
            check=True,
            capture_output=True
        )
        # Extract key
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(P12), "-nocerts",
             "-passin", f"pass:{P12_PASSWORD}", "-passout", "pass:tmpkey",
             "-out", str(key_pem)],
            check=True,
            capture_output=True
        )
        # Create signature
        sig_path = td / "signature"
        try:
            subprocess.run(
                ["openssl", "smime", "-binary", "-sign",
                "-signer", str(cert_pem),
                "-inkey", str(key_pem),
                "-certfile", str(WWDR),
                "-in", str(td / "manifest.json"),
                "-out", str(sig_path),
                "-outform", "DER",
                "-passin", "pass:tmpkey"],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print("CMD:", " ".join(e.cmd))
            print("STDOUT:", e.stdout.decode(errors="ignore"))
            print("STDERR:", e.stderr.decode(errors="ignore"))
            raise
        files["signature"] = sig_path.read_bytes()

    # 4) Zip to .pkpass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    print(f"✅ Created: {output_path}  (serial: {serial})")
    return output_path

if __name__ == "__main__":
    out = Path("out") / "test.pkpass"
    make_pkpass(out)
