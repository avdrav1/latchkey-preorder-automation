#!/usr/bin/env python3
"""
DEBUG VERSION: Preorder Club Data Transformer
Only processes first 10 records to see what we're working with
"""

import pandas as pd
import ftplib
import os
from datetime import datetime, timedelta
import re
import math

class DebugPreorderTransformer:
    def __init__(self):
        self.cost_multiplier = 0.77  # 77% of MSRP
        
    def load_alliance_data(self, file_path):
        """Load and clean Alliance catalog data"""
        print(f"Attempting to load file: {file_path}")
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return None
            
            # Based on diagnosis, this is UTF-16 encoded, pipe-delimited
            print("Loading UTF-16 pipe-delimited file...")
            df = pd.read_csv(file_path, dtype=str, encoding='utf-16', sep='|')
            
            print(f"Success! Loaded {len(df)} records from Alliance catalog")
            print(f"Columns found: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            print(f"Error loading Alliance data: {e}")
            return None
    
    def calculate_target_release_date(self):
        """Calculate the target release date (4 Fridays ahead)"""
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.weekday() == 4:  # If today is Friday
            days_until_friday = 7  # Get next Friday
        next_friday = today + timedelta(days=days_until_friday)
        target_release = next_friday + timedelta(weeks=3)  # 4 Fridays total (next + 3 more)
        return target_release
    
    def parse_avail_date(self, avail_dt_str):
        """Try to parse the AvailDt field in various formats"""
        if not avail_dt_str or pd.isna(avail_dt_str):
            return None
            
        avail_dt_str = str(avail_dt_str).strip()
        if not avail_dt_str or avail_dt_str.lower() == 'nan':
            return None
        
        # Try different date formats (including timestamp formats)
        date_formats = [
            '%Y-%m-%d %H:%M:%S',  # 2016-01-29 00:00:00
            '%Y-%m-%d',           # 2025-09-19
            '%m/%d/%Y %H:%M:%S',  # 09/19/2025 00:00:00
            '%m/%d/%Y',           # 09/19/2025
            '%m-%d-%Y',           # 09-19-2025
            '%Y%m%d',             # 20250919
            '%m/%d/%y',           # 09/19/25
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(avail_dt_str, fmt)
            except ValueError:
                continue
        
        print(f"  WARNING: Could not parse date format: '{avail_dt_str}'")
        return None
    
    def analyze_first_records(self, alliance_df, num_records=10):
        """Analyze the first N records in detail"""
        print(f"\n=== ANALYZING FIRST {num_records} RECORDS ===")
        
        target_release_date = self.calculate_target_release_date()
        print(f"TARGET RELEASE DATE: {target_release_date.strftime('%Y-%m-%d (%A)')}")
        
        # Helper function to safely get string values
        def safe_get(row, column_name, default=''):
            value = row.get(column_name, default)
            if pd.isna(value) or value is None:
                return default
            return str(value).strip()
        
        vinyl_target_formats = ['12-INCH SINGLE', '7-INCH SINGLE', 'VINYL LP']
        vinyl_found = 0
        date_matched = 0
        both_matched = 0
        
        for idx in range(min(num_records, len(alliance_df))):
            row = alliance_df.iloc[idx]
            
            print(f"\n--- RECORD {idx + 1} ---")
            
            # Show all key fields
            artist = safe_get(row, 'Artist')
            album = safe_get(row, 'ItemName')
            format_desc = safe_get(row, 'FormatDesc')
            item_format = safe_get(row, 'ItemFormat')
            barcode = safe_get(row, 'Barcode')
            msrp = row.get('MSRP', 'N/A')
            avail_dt_raw = safe_get(row, 'AvailDt')
            color_details = safe_get(row, 'DelimMisc')
            
            print(f"Artist: '{artist}'")
            print(f"ItemName: '{album}'")
            print(f"FormatDesc: '{format_desc}'")
            print(f"ItemFormat: '{item_format}'")
            print(f"MSRP: '{msrp}'")
            print(f"AvailDt (raw): '{avail_dt_raw}'")
            
            # Check if this would be considered vinyl
            is_target_vinyl = format_desc in vinyl_target_formats
            print(f"IS TARGET VINYL FORMAT? {is_target_vinyl}")
            
            # Check the date
            avail_date = self.parse_avail_date(avail_dt_raw)
            is_target_date = False
            
            if avail_date:
                print(f"AvailDt (parsed): {avail_date.strftime('%Y-%m-%d (%A)')}")
                is_target_date = avail_date.date() == target_release_date.date()
                print(f"IS TARGET DATE? {is_target_date}")
                
                if avail_date.date() < datetime.now().date():
                    print("  -> PAST DATE (would be excluded)")
                elif avail_date.date() > target_release_date.date():
                    print("  -> FUTURE DATE (beyond target, would be excluded)")
            else:
                print("AvailDt (parsed): FAILED TO PARSE")
                print("IS TARGET DATE? UNKNOWN")
            
            # Summary for this record
            if is_target_vinyl:
                vinyl_found += 1
            if is_target_date:
                date_matched += 1
            if is_target_vinyl and is_target_date:
                both_matched += 1
                print(f"*** PERFECT MATCH #{both_matched} ***")
            
            print("-" * 60)
        
        print(f"\nSUMMARY OF FIRST {num_records} RECORDS:")
        print(f"  Target vinyl format matches: {vinyl_found}")
        print(f"  Target date matches: {date_matched}")
        print(f"  BOTH vinyl AND date matches: {both_matched}")
        
        # Now let's see what AvailDt values exist for our target date
        print(f"\n=== CHECKING ENTIRE DATASET FOR TARGET DATE ===")
        print(f"Looking for records with AvailDt = {target_release_date.strftime('%Y-%m-%d')}")
        
        target_date_count = 0
        vinyl_and_date_count = 0
        
        for idx, row in alliance_df.iterrows():
            avail_dt_raw = safe_get(row, 'AvailDt')
            format_desc = safe_get(row, 'FormatDesc')
            
            avail_date = self.parse_avail_date(avail_dt_raw)
            if avail_date and avail_date.date() == target_release_date.date():
                target_date_count += 1
                
                if format_desc in vinyl_target_formats:
                    vinyl_and_date_count += 1
                    if vinyl_and_date_count <= 5:  # Show first 5 matches
                        artist = safe_get(row, 'Artist')
                        album = safe_get(row, 'ItemName')
                        print(f"  MATCH: {artist} - {album} ({format_desc})")
        
        print(f"\nFINAL DATASET SUMMARY:")
        print(f"  Total records with target date ({target_release_date.strftime('%Y-%m-%d')}): {target_date_count}")
        print(f"  Vinyl records with target date: {vinyl_and_date_count}")
        print(f"  ^ This should be around 320 records for your preorder club!")
        
        return vinyl_and_date_count

def main():
    transformer = DebugPreorderTransformer()
    
    print("Starting DEBUG preorder analysis...")
    print("This will only look at the first 10 records in detail")
    
    # Load Alliance data
    alliance_data = transformer.load_alliance_data("alliance_catalog.txt")
    if alliance_data is None:
        return
    
    # Analyze first 10 records
    vinyl_count = transformer.analyze_first_records(alliance_data, 10)
    
    print(f"\nDEBUG COMPLETE!")
    print(f"Found {vinyl_count} vinyl records in first 10 records")
    print("Check the FormatDesc values above to see what we should filter for")

if __name__ == "__main__":
    main()