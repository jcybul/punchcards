#!/usr/bin/env python3
"""
Create a new punch program for a merchant
"""
import os
import sys
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add the parent directory to the path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import PunchProgram, Merchant
from app.db import SessionLocal


def create_program(
    merchant_id: str,
    name: str,
    punches_required: int,
    expires_after_days: int = None,
    active: bool = True,
    wallet_filled_icon_url: str = None,
    wallet_empty_icon_url: str = None
):
    """Create a new punch program"""
    with SessionLocal() as db:
        program = PunchProgram(
            merchant_id=merchant_id,
            name=name,
            punches_required=punches_required,
            expires_after_days=expires_after_days,
            active=active,
            wallet_filled_icon_url=wallet_filled_icon_url,
            wallet_empty_icon_url=wallet_empty_icon_url
        )
        
        
        db.add(program)
        db.commit()
        db.refresh(program)
        
        return program


def interactive_create():
    """Interactive program creation"""
    print("\n=== Create New Punch Program ===\n")
    
    # Get merchant ID
    with SessionLocal() as session:
        merchant_id = input("Merchant ID: ").strip()
        if not merchant_id:
            print("ERROR: Merchant ID is required")
            return
        
        # Verify merchant exists
        try:
            merchant = session.query(Merchant).filter(Merchant.id == merchant_id).first()
            if not merchant:
                print(f"ERROR: Merchant with ID {merchant_id} not found")
                return
            merchant_name = merchant.name
            print(f"Creating program for: {merchant_name}\n")
        except Exception as e:
            print(f"ERROR: Could not verify merchant: {e}")
            return
        
        # Get program details
        name = input("Program name (e.g., 'Free Coffee Card'): ").strip()
        if not name:
            print("ERROR: Program name is required")
            return
        
        # Get punches required
        while True:
            try:
                punches_str = input("Number of punches required (e.g., 10): ").strip()
                punches_required = int(punches_str)
                if punches_required < 1:
                    print("ERROR: Must require at least 1 punch")
                    continue
                break
            except ValueError:
                print("ERROR: Please enter a valid number")
        
        # Get expiration days (optional)
        expires_after_days = None
        expires_input = input("Expires after days (optional, press Enter to skip): ").strip()
        if expires_input:
            try:
                expires_after_days = int(expires_input)
            except ValueError:
                print("WARNING: Invalid number, skipping expiration")
        
        # Get icon URLs (optional)
        wallet_filled_icon_url = input("Filled icon URL (optional): ").strip() or None
        wallet_empty_icon_url = input("Empty icon URL (optional): ").strip() or None
        
        active_input = input("Active? (y/n) [y]: ").strip().lower()
        active = active_input != 'n'
        
        # Summary
        print("\n--- Program Summary ---")
        print(f"Merchant: {merchant_name}")
        print(f"Name: {name}")
        print(f"Punches Required: {punches_required}")
        print(f"Expires After: {expires_after_days or 'Never'} days")
        print(f"Filled Icon URL: {wallet_filled_icon_url or 'Not set'}")
        print(f"Empty Icon URL: {wallet_empty_icon_url or 'Not set'}")
        print(f"Active: {'Yes' if active else 'No'}")
        
        confirm = input("\nCreate program? (y/n): ").lower()
        if confirm != 'y':
            print("Cancelled")
            return
        
        # Create program
        try:
            program = create_program(
                merchant_id=merchant_id,
                name=name,
                punches_required=punches_required,
                expires_after_days=expires_after_days,
                active=active,
                wallet_filled_icon_url=wallet_filled_icon_url,
                wallet_empty_icon_url=wallet_empty_icon_url
            )
            
            print(f"\n[SUCCESS] Program created successfully!")
            print(f"ID: {program.id}")
            print(f"Name: {program.name}")
            print(f"\nNext steps:")
            print(f"1. Create staff access: python scripts/add_staff.py <user_id> {merchant_id} staff")
            
        except Exception as e:
            session.rollback()
            print(f"ERROR: Error creating program: {e}")
        finally:
            session.close()


def main():
    with SessionLocal() as session:
        parser = argparse.ArgumentParser(description="Create a new punch program")
        parser.add_argument("--merchant-id", help="Merchant ID")
        parser.add_argument("--name", help="Program name")
        parser.add_argument("--punches", type=int, help="Number of punches required")
        parser.add_argument("--expires-days", type=int, help="Expires after X days")
        parser.add_argument("--filled-icon", help="Filled icon URL")
        parser.add_argument("--empty-icon", help="Empty icon URL")
        parser.add_argument("--inactive", action="store_true", help="Create as inactive")
        
        args = parser.parse_args()
        
        if args.merchant_id and args.name and args.punches:
            try:
                program = create_program(
                    merchant_id=args.merchant_id,
                    name=args.name,
                    punches_required=args.punches,
                    expires_after_days=args.expires_days,
                    active=not args.inactive,
                    wallet_filled_icon_url=args.filled_icon,
                    wallet_empty_icon_url=args.empty_icon
                )
                
                print(f"[SUCCESS] Program created: {program.name} (ID: {program.id})")
                
            except Exception as e:
                session.rollback()
                print(f"ERROR: {e}")
            finally:
                session.close()
        else:
            # Interactive mode
            interactive_create()


if __name__ == "__main__":
    load_dotenv()
    main()