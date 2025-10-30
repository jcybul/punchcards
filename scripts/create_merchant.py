#!/usr/bin/env python3
"""
Create a new merchant with colors and branding.

Usage:
    python scripts/create_merchant.py
    
    Or with arguments:
    python scripts/create_merchant.py --name "Joe's Coffee" --email "joe@coffee.com"
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Merchant


def create_merchant(
    name: str,
    contact_email: str,
    wallet_brand_color: str = "#111111",
    wallet_strip_color: str = "#6E463A",
    wallet_foreground_color: str = "#FFFFFF",
    wallet_logo_url: str = None
) -> Merchant:
    """
    Create a new merchant.
    
    Args:
        name: Business name
        contact_email: Contact email
        wallet_brand_color: Hex color for card background (default: black)
        wallet_strip_color: Hex color for strip background (default: brown)
        wallet_foreground_color: Hex color for text (default: white)
        wallet_logo_url: Optional URL to logo
        
    Returns:
        Created Merchant object
    """
    with SessionLocal() as db:
        merchant = Merchant(
            name=name,
            contact_email=contact_email,
            wallet_brand_color=wallet_brand_color,
            wallet_strip_color=wallet_strip_color,
            wallet_foreground_color=wallet_foreground_color,
            wallet_logo_url=wallet_logo_url
        )
        
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
        
        return merchant


def interactive_create():
    """Interactive prompt to create a merchant."""
    print("\n=== Create New Merchant ===\n")
    
    name = input("Business name: ").strip()
    if not name:
        print("ERROR: Name is required")
        return
    
    email = input("Contact email: ").strip()
    if not email:
        print("ERROR: Email is required")
        return
    
    print("\n--- Brand Colors (press Enter for defaults) ---")
    
    brand_color = input("Card background color [#111111]: ").strip() or "#111111"
    strip_color = input("Strip background color [#6E463A]: ").strip() or "#6E463A"
    foreground_color = input("Text color [#FFFFFF]: ").strip() or "#FFFFFF"
    
    logo_url = input("Logo URL (optional): ").strip() or None
    
    # Validate hex colors
    for color, name_str in [(brand_color, "brand"), (strip_color, "strip"), (foreground_color, "text")]:
        if not color.startswith("#") or len(color) != 7:
            print(f"ERROR: Invalid {name_str} color. Must be hex format like #RRGGBB")
            return
    
    print("\n--- Preview ---")
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Brand color: {brand_color}")
    print(f"Strip color: {strip_color}")
    print(f"Text color: {foreground_color}")
    if logo_url:
        print(f"Logo URL: {logo_url}")
    
    confirm = input("\nCreate merchant? (y/n): ").lower()
    if confirm != 'y':
        print("Cancelled")
        return
    
    try:
        merchant = create_merchant(
            name=name,
            contact_email=email,
            wallet_brand_color=brand_color,
            wallet_strip_color=strip_color,
            wallet_foreground_color=foreground_color,
            wallet_logo_url=logo_url
        )
        
        print(f"\n[SUCCESS] Merchant created successfully!")
        print(f"ID: {merchant.id}")
        print(f"Name: {merchant.name}")
        print(f"\nNext steps:")
        print(f"1. Upload assets to GCS: gs://punchcards-assets/merchants/{merchant.id}/")
        print(f"2. Create punch programs: python scripts/create_program.py")
        print(f"3. Add staff members: python scripts/add_staff.py <user_id> {merchant.id} owner")
        
    except Exception as e:
        print(f"ERROR: Error creating merchant: {e}")


def main():
    parser = argparse.ArgumentParser(description="Create a new merchant")
    parser.add_argument("--name", help="Business name")
    parser.add_argument("--email", help="Contact email")
    parser.add_argument("--brand-color", default="#111111", help="Card background color (hex)")
    parser.add_argument("--strip-color", default="#6E463A", help="Strip background color (hex)")
    parser.add_argument("--text-color", default="#FFFFFF", help="Text color (hex)")
    parser.add_argument("--logo-url", help="Logo URL")
    
    args = parser.parse_args()
    
    # If name and email provided via args, use them
    if args.name and args.email:
        try:
            merchant = create_merchant(
                name=args.name,
                contact_email=args.email,
                wallet_brand_color=args.brand_color,
                wallet_strip_color=args.strip_color,
                wallet_foreground_color=args.text_color,
                wallet_logo_url=args.logo_url
            )
            
            print(f"[SUCCESS] Merchant created: {merchant.name} (ID: {merchant.id})")
            
        except Exception as e:
            print(f"ERROR: {e}")
    else:
        # Interactive mode
        interactive_create()


if __name__ == "__main__":
    main()