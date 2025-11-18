"""
Simple service for downloading assets from public URLs.
"""
import requests
from pathlib import Path
import os
import time
import logging


logger = logging.getLogger(__name__)

LOCAL_ASSETS = Path(os.getenv("WALLET_ASSETS_DIR", "/Users/josephcybulzebede/Documents/punchcards/assets"))

def download_from_url(url: str) -> bytes | None:
    """
    Download an asset from a public URL.
    
    Args:
        url: Public URL to the asset
        
    Returns:
        bytes of the file, or None if failed
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


def get_program_icon(icon_url: str | None, icon_type: str) -> bytes | None:
    """
    Get program icon from URL or local fallback.
    
    Args:
        icon_url: URL to the icon (from database)
        icon_type: "filled" or "empty" (for fallback filename)
        
    Returns:
        bytes of icon image
    """
    if icon_url:
        icon = download_from_url(icon_url)
        if icon:
            return icon
        
    
    filename = f"mug_{icon_type}.png"
    local_path = LOCAL_ASSETS / filename
    
    if local_path.exists():
        return local_path.read_bytes()
    
    print(f"Warning: Icon {filename} not found")
    return None

def get_merchant_logo(logo_url: str ) -> bytes | None:
    """
    Get program icon from URL or local fallback.
    
    Args:
        icon_url: URL to the icon (from database)
        icon_type: "filled" or "empty" (for fallback filename)
        
    Returns:
        bytes of icon image
    """
    if logo_url:
        logo = download_from_url(logo_url)
        if logo:
            return logo
        else:
            raise FileNotFoundError
    return None


def get_default_asset(filename: str) -> bytes | None:
    """
    Get default asset from local filesystem.
    
    Args:
        filename: e.g., "icon.png", "logo.png"
        
    Returns:
        bytes of the asset
    """    
    start = time.time()

    local_path = LOCAL_ASSETS / filename
    
    if local_path.exists():
        elapsed_ms = (time.time() - start) * 1000
        logger.debug(f"📦 {filename}: {elapsed_ms:.0f}ms")
        return local_path.read_bytes()
    
    print(f"Warning: Asset {filename} not found")
    
    return None