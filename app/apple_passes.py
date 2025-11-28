# app/apple_passes.py
from __future__ import annotations
from datetime import datetime
import os, json, uuid, io, zipfile, hashlib, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv
from app.services.asset_service import get_program_icon, get_default_asset, get_merchant_logo
from app.services.strip_generator import generate_strip_with_punches
from app.services.utils_functions_service import ensure_naive_utc

import time
import logging

logger = logging.getLogger(__name__)

load_dotenv()

TEAM_ID = os.environ["APPLE_TEAM_ID"]
PASS_TYPE_ID = os.environ["PASS_TYPE_ID"]
P12_PASSWORD = os.environ["PASS_P12_PASSWORD"]
ORG_NAME = os.getenv("ORG_NAME", "Froyo ltda")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")  

if os.getenv("WALLET_CERTS_DIR") == "/apple-certs":
    # Cloud Run paths
    P12 = Path("/apple-certs/pass/secrets/certs/pass.p12")
    WWDR = Path("/apple-certs/wwdr/secrets/certs/AppleWWDRCA.pem")
    ASSETS = Path("/app/assets")
else:
    # Local development paths
    CERTS = Path(os.getenv("WALLET_CERTS_DIR", "/Users/josephcybulzebede/Documents/punchcards/certs"))
    P12 = CERTS / "pass.p12"
    WWDR = CERTS / "AppleWWDRCA.pem"
    ASSETS = Path(os.getenv("WALLET_ASSETS_DIR", "/Users/josephcybulzebede/Documents/punchcards/assets"))
    
def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()

def hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to R,G,B format for Apple Wallet."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{r},{g},{b}"



def _build_pass_json(
    serial: str, 
    auth_token: str,
    card,
    *, 
    punches: int, 
    org: str,
    group: str,
    punches_required: int,
    reward_credits: int,
    status: str, 
    logo_text: str | None = None,
    background_color: str = "#111111",
    foreground_color: str = "#FFFFFF",
    terms_and_conditions: str
) -> dict:
    
    card_code = serial.split('-')[0].upper()
    if reward_credits > 0:
        secondary_fields =[
            {
                "key": "rewards",
                "label": "REWARDS AVAILABLE",
                "value": str(reward_credits)
            },
            {
                    "key": "progress",
                    "label": "PROGRESS",
                    "value": f"{punches} of {punches_required}"
            }
        ]
    else:
         secondary_fields =[
            {
                    "key": "progress",
                    "label": "PROGRESS",
                    "value": f"{punches} of {punches_required}"
            }
        ]
        
    
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": PASS_TYPE_ID,
        "teamIdentifier": TEAM_ID,
        "organizationName": org,               
        "description": f"{org} Punch Card", 
        #"logoText": logo_text or org, 
        "serialNumber": serial,
        "foregroundColor": f"rgb({hex_to_rgb(foreground_color)})",
        "backgroundColor": f"rgb({hex_to_rgb(background_color)})",
       "groupingIdentifier": group,
        "barcode": {
            "format": "PKBarcodeFormatQR",
            "message": serial,
            "messageEncoding": "iso-8859-1",
             "altText": card_code
        },
        "storeCard": {
            
            "secondaryFields": secondary_fields,
            
            "auxiliaryFields": [],
            "backFields": [
        {
            "key": "terms",
            "label": "Terms & Conditions",
            "value": terms_and_conditions or "Valid at participating locations. Not transferable."
        },
        {
            "key": "contact",
            "label": "Contact Info",
            "value": "Support@cashbackpanama.com"
        }
        
        ]
        }
    }
    
    if card.expires_at:
        now = datetime.utcnow()
        if hasattr(card.expires_at, 'isoformat'):
            expiration_iso = card.expires_at.isoformat()
            if 'T' in expiration_iso and not expiration_iso.endswith('Z') and '+' not in expiration_iso:
                # Naive datetime - add Z for UTC
                expiration_iso = expiration_iso + 'Z'
        else:
            expiration_iso = str(card.expires_at)
        
        
        pass_json["expirationDate"] = expiration_iso
        
        
        expires_at = card.expires_at
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
            
        logger.debug(f"now: {now}, tzinfo: {now.tzinfo}")
        logger.debug(f"expires_at: {card.expires_at}, tzinfo: {card.expires_at.tzinfo}")
        logger.debug(f"Type: {type(card.expires_at)}")
                
        if card.expires_at < now:
            pass_json["voided"] = True
        
        # Calculate days remaining
        days_remaining = (expires_at - now).days
        
        # Format expiration text
        if days_remaining <= 0:
            expiration_text = "EXPIRED"
            expiration_label = "STATUS"
        elif days_remaining <= 7:
            expiration_text = f"Expires in {days_remaining} day{'s' if days_remaining != 1 else ''}"
            expiration_label = "STATUS"
        else:
            expiration_text = expires_at.strftime("%b %d, %Y")
            expiration_label = "VALID UNTIL"
        
        
        pass_json["storeCard"]["auxiliaryFields"].append({
            "key": "expiration",
            "label": expiration_label,
            "value": expiration_text
        })
    
    
    if BASE_URL and BASE_URL != "http://localhost:8080":
        pass_json["webServiceURL"] = BASE_URL
        pass_json["authenticationToken"] = auth_token
    
    return pass_json

def _sign_manifest_and_collect(files: dict[str, bytes]) -> dict[str, bytes]:
    """
    Given pass files (including pass.json), compute manifest.json, sign it with your p12 + WWDR,
    and return the updated files dict with 'manifest.json' and 'signature' entries.
    """
    # 1) manifest.json (Apple examples use SHA-1)
    manifest = {fname: _sha1(data) for fname, data in files.items()}
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    files["manifest.json"] = manifest_bytes
    
    # 2) signature (PKCS#7 detached over manifest.json)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "manifest.json").write_bytes(manifest_bytes)

        cert_pem = tdp / "cert.pem"
        key_pem = tdp / "key.pem"

        # # Extract cert (no keys)
        # try:
        #     subprocess.run(
        #         ["openssl", "pkcs12", "-in", str(P12), "-clcerts", "-nokeys",
        #         "-passin", f"pass:{P12_PASSWORD}", "-out", str(cert_pem),"-legacy"],
        #         check=True, capture_output=True
        #     )
        # except subprocess.CalledProcessError as e:
        #     # Helpful debug on cert/WWDR issues
        #     print("CMD:", " ".join(e.cmd))
        #     print("STDOUT:", e.stdout.decode(errors="ignore"))
        #     print("STDERR:", e.stderr.decode(errors="ignore"))
        #     raise
        # # Extract private key (password-protected temp key)
        
        # try:
        #     subprocess.run(
        #         ["openssl", "pkcs12", "-in", str(P12), "-nocerts",
        #         "-passin", f"pass:{P12_PASSWORD}", "-passout", "pass:tmpkey",
        #         "-out", str(key_pem),"-legacy"],
        #         check=True, capture_output=True
        #     )
        # except subprocess.CalledProcessError as e:
        #     # Helpful debug on cert/WWDR issues
        #     print("CMD:", " ".join(e.cmd))
        #     print("STDOUT:", e.stdout.decode(errors="ignore"))
        #     print("STDERR:", e.stderr.decode(errors="ignore"))
        #     raise

        _extract_p12_cert(P12, P12_PASSWORD, cert_pem)
        _extract_p12_key(P12, P12_PASSWORD, key_pem, temp_password="tmpkey")

        sig_path = tdp / "signature"
        try:
            subprocess.run(
                ["openssl", "smime", "-binary", "-sign",
                 "-signer", str(cert_pem),
                 "-inkey", str(key_pem),
                 "-certfile", str(WWDR),
                 "-in", str(tdp / "manifest.json"),
                 "-out", str(sig_path),
                 "-outform", "DER",
                 "-passin", "pass:tmpkey"],
                check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print("CMD:", " ".join(e.cmd))
            print("STDOUT:", e.stdout.decode(errors="ignore"))
            print("STDERR:", e.stderr.decode(errors="ignore"))
            raise

        files["signature"] = sig_path.read_bytes()

    return files

def _extract_p12_cert(p12_path, password, output_path):
    """Extract certificate from P12. Try modern first, fallback to legacy."""
    try:
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(p12_path), "-clcerts", "-nokeys",
             "-passin", f"pass:{password}", "-out", str(output_path), "-legacy"],
            check=True,
            capture_output=True
        )
        return
    except subprocess.CalledProcessError:
        pass  
        print("Fall back to no legacy")

    try:
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(p12_path), "-clcerts", "-nokeys",
             "-passin", f"pass:{password}", "-out", str(output_path)],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract certificate from P12: {e.stderr.decode()}")


def _extract_p12_key(p12_path, password, output_path, temp_password="tmpkey"):
    """Extract private key from P12. Try modern first, fallback to legacy."""
    try:
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(p12_path), "-nocerts",
             "-passin", f"pass:{password}", "-passout", f"pass:{temp_password}",
             "-out", str(output_path), "-legacy"],
            check=True,
            capture_output=True
        )
        return
    except subprocess.CalledProcessError:
        pass 
        print("Fall back to no legacy")
    
    try:
        subprocess.run(
            ["openssl", "pkcs12", "-in", str(p12_path), "-nocerts",
             "-passin", f"pass:{password}", "-passout", f"pass:{temp_password}",
             "-out", str(output_path)],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract private key from P12: {e.stderr.decode()}")


def build_pkpass(card, program,merchant, *, logo_text: str | None = None, use_dynamic_strip: bool = True) -> bytes:
    """
    Build and sign a .pkpass for a given WalletCard + PunchProgram.
    Returns BYTES (ready to send as application/vnd.apple.pkpass).
    NOW WITH LIVE UPDATES via webServiceURL!
    """
    
    overall_start = time.time()
    logger.debug(f"Building pass for card {card.id}")
    
    # serial ties the pass to the card (keep stable per card)
    t1 = time.time()
    serial = str(card.id)
    auth_token = card.auth_token  # Use the card's unique auth token
    
    
    background_color = merchant.wallet_brand_color or "#111111"
    foreground_color = merchant.wallet_foreground_color or "#FFFFFF"
    strip_color = merchant.wallet_strip_color or "#6E463A"


    # 1) Collect files in memory
    pass_json = _build_pass_json(
        serial,
        auth_token,
        card,
        punches=card.current_punches or 0,
        org = program.name,
        group= str(program.id),
        punches_required=program.punches_required,
        reward_credits=card.reward_credits or 0,
        status=card.status or "active",
        logo_text=logo_text or merchant.name,
        background_color=background_color,
        foreground_color=foreground_color,
        terms_and_conditions=program.google_terms_conditions
    )
    
    logger.debug(f"  ├─ JSON built: {(time.time() - t1)*1000:.0f}ms")
    t2 = time.time()
    
    
    files: dict[str, bytes] = {}
    files["pass.json"] = json.dumps(pass_json, separators=(",", ":")).encode("utf-8")
    logger.debug(f"  ├─ Files dict created: {(time.time() - t2)*1000:.0f}ms")
    
    

    # required assets
    t3 = time.time()
    icon = get_default_asset("icon.png")
    icon_2x = get_default_asset("icon@2x.png")
    
    if icon:
        files["icon.png"] = icon
    if icon_2x:
        files["icon@2x.png"] = icon_2x

    # optional static assets
    logo = get_merchant_logo(merchant.wallet_logo_url)
    logo_2x = get_merchant_logo(merchant.wallet_logo_url)
    
    if logo:
        files["logo.png"] = logo
    if logo_2x:
        files["logo@2x.png"] = logo_2x
    logger.debug(f"  ├─ Default assets loaded: {(time.time() - t3)*1000:.0f}ms")
    
    

    # Generate dynamic strip with punch indicators
    t4 = time.time()
    if use_dynamic_strip:
        try:
            
            strip_2x = generate_strip_with_punches(
                punches=card.current_punches or 0,
                punches_required=program.punches_required,
                reward_credits=card.reward_credits or 0,
                strip_color=strip_color,
                filled_icon_url=program.wallet_filled_icon_url,
                empty_icon_url=program.wallet_empty_icon_url
            )
            files["strip@2x.png"] = strip_2x
            files["strip.png"] = strip_2x
            
            
        except Exception as e:
            print(f"Error generating strip: {e}")
            
        except ImportError:
            # Fallback to static strip if generator not available
            for name in ("strip.png", "strip@2x.png"):
                p = ASSETS / name
                if p.exists():
                    files[name] = p.read_bytes()
    else:
        # Use static strip images
        for name in ("strip.png", "strip@2x.png"):
            p = ASSETS / name
            if p.exists():
                files[name] = p.read_bytes()
                
    logger.debug(f"  ├─ Strip generated: {(time.time() - t4)*1000:.0f}ms")

    # 2) Sign manifest and append signature
    t5 = time.time()
    files = _sign_manifest_and_collect(files)
    logger.info(f"  ├─ Manifest signed: {(time.time() - t5)*1000:.0f}ms")

    # 3) Create the pkpass ZIP in memory
    t6 = time.time()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    logger.debug(f"  ├─ ZIP created: {(time.time() - t6)*1000:.0f}ms")
    
    total = (time.time() - overall_start) * 1000
    logger.debug(f"  └─ ✅ Total: {total:.0f}ms")

    return buf.getvalue()