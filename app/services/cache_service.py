# app/services/image_cache.py
import os
import time
import hashlib
import requests
from pathlib import Path
import logging

logger = logging.getLogger(__name__)



CACHE_DIR = Path('/tmp/wallet_image_cache')
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TIMEOUT = 86400  # 24 hours

def get_image_cache_key(url):
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()


def get_cached_image(url):
    """Get image from cache if fresh"""
    if not url:
        return None
    
    cache_key = get_image_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.img"
    
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < CACHE_TIMEOUT:
            logger.info(f"Using cached image: {url}")
            return cache_file.read_bytes()
        else:
            # Cache expired, remove it
            cache_file.unlink()
    
    return None


def save_image_to_cache(url, image_data):
    """Save image to cache"""
    if not image_data:
        return
    
    cache_key = get_image_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.img"
    cache_file.write_bytes(image_data)
    logger.info(f"Cached image: {url}")


def fetch_and_cache_image(url, timeout=10):
    """Fetch image with caching"""
    if not url:
        return None
    
    # Check cache first
    cached = get_cached_image(url)
    if cached:
        return cached
    
    # Fetch from URL
    try:
        logger.info(f"Fetching image: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        image_data = response.content
        save_image_to_cache(url, image_data)
        
        return image_data
    
    except Exception as e:
        logger.error(f"Failed to fetch image {url}: {e}")
        return None


def clear_image_cache():
    """Clear all cached images"""
    for file in CACHE_DIR.glob('*.img'):
        file.unlink()
    logger.info("Cleared image cache")
    
    
def get_cache_stats():
    """Get cache statistics"""
    files = list(CACHE_DIR.glob('*.img'))
    total_size = sum(f.stat().st_size for f in files)
    
    return {
        'cached_images': len(files),
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'cache_dir': str(CACHE_DIR),
        'timeout_hours': CACHE_TIMEOUT / 3600
    }