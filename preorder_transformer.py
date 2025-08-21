#!/usr/bin/env python3
"""
Preorder Club Data Transformer
Automates the conversion from Alliance catalog to Shopify CSV
Usage: python preorder_transformer.py --date 2025-09-19
"""

import pandas as pd
import ftplib
import os
from datetime import datetime, timedelta
import re
import math
import argparse

class PreorderTransformer:
    def __init__(self):
        self.cost_multiplier = 0.77  # 77% of MSRP
        self.base_markup = 6
        self.msrp_minimum_markup = 7
        self.club_base_markup = 6
        self.club_tier1_threshold = 14
        self.club_tier1_addition = 4
        self.club_tier2_threshold = 20
        self.club_tier2_addition = 9
        
    def download_catalog_ftp(self, ftp_host, username, password, remote_path, local_path):
        """Download catalog file from Alliance FTP"""
        try:
            with ftplib.FTP(ftp_host) as ftp:
                ftp.login(username, password)
                with open(local_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {remote_path}', f.write)
            print(f"Downloaded catalog to {local_path}")
            return True
        except Exception as e:
            print(f"FTP download failed: {e}")
            return False
    
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
            
            # Show first few column names to help with mapping
            print(f"First 10 columns: {list(df.columns[:10])}")
            
            # Clean barcode field (remove exponential notation issues)
            if 'Barcode' in df.columns:
                df['Barcode'] = df['Barcode'].astype(str).str.replace('.0', '', regex=False)
            
            # Show a sample row to help with field mapping
            if len(df) > 0:
                print("\nSample data from first row:")
                for col in df.columns[:10]:  # Show first 10 columns
                    print(f"  {col}: {df.iloc[0][col]}")
            
            return df
            
        except Exception as e:
            print(f"Error loading Alliance data: {e}")
            print("If this fails, please share the column names so I can help map them properly.")
            return None
    
    def calculate_next_four_fridays(self):
        """Calculate the next 4 Friday release dates - DEPRECATED"""
        # Kept for backwards compatibility but not used anymore
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.weekday() == 4:  # If today is Friday
            days_until_friday = 7  # Get next Friday
        
        next_friday = today + timedelta(days=days_until_friday)
        
        # Get the next 4 Fridays
        fridays = []
        for i in range(4):
            friday = next_friday + timedelta(weeks=i)
            fridays.append(friday)
        
        return fridays
    
    def parse_target_date(self, date_string):
        """Parse target date from string in various formats"""
        if not date_string:
            return None
            
        # Try different date formats for input
        date_formats = [
            '%Y-%m-%d',     # 2025-09-19
            '%m/%d/%Y',     # 09/19/2025
            '%m-%d-%Y',     # 09-19-2025
            '%Y%m%d',       # 20250919
            '%m/%d/%y',     # 09/19/25
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_string}. Use format: YYYY-MM-DD (e.g., 2025-09-19)")
    
    def validate_target_date(self, target_date):
        """Validate that the target date is a Friday and in the future"""
        if target_date.weekday() != 4:  # 4 = Friday
            print(f"WARNING: {target_date.strftime('%Y-%m-%d')} is a {target_date.strftime('%A')}, not a Friday")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                return False
        
        if target_date.date() <= datetime.now().date():
            print(f"WARNING: {target_date.strftime('%Y-%m-%d')} is in the past")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                return False
        
        return True
    
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
        
        return None
    
    def create_handle(self, artist, title, details, release_date):
        """Create unique URL handle"""
        # Convert all inputs to strings and handle NaN/None values
        def safe_str(value):
            if pd.isna(value) or value is None:
                return ''
            return str(value).strip()
        
        # Clean and combine elements
        handle_parts = [
            safe_str(artist), 
            safe_str(title), 
            safe_str(details), 
            release_date.strftime('%Y%m%d')
        ]
        handle = '-'.join([part for part in handle_parts if part])
        
        # Clean for URL (remove special chars, spaces, etc.)
        handle = re.sub(r'[^a-zA-Z0-9-]', '-', handle.lower())
        handle = re.sub(r'-+', '-', handle)  # Remove multiple dashes
        handle = handle.strip('-')
        
        return handle
    
    def format_vinyl_details(self, details_string):
        """Convert vinyl details from ALL CAPS^SEPARATED to Mixed Case, Separated"""
        if not details_string or str(details_string).strip().lower() == 'nan':
            return ''
        
        details = str(details_string).strip()
        if not details:
            return ''
        
        # Split by carats and clean up each part
        parts = [part.strip() for part in details.split('^') if part.strip()]
        
        # Convert each part to title case with some special handling
        formatted_parts = []
        for part in parts:
            # Convert to title case
            formatted = part.title()
            
            # Handle some common vinyl terminology that should stay specific ways
            replacements = {
                'Lp': 'LP',
                'Ep': 'EP',
                'Cd': 'CD',
                'Rsd': 'RSD',
                'Vinyl': 'Vinyl',
                'Ltd': 'Ltd',
                'Limited': 'Limited',
                'Edition': 'Edition',
                'Exclusive': 'Exclusive',
                'Indie': 'Indie',
                'Signed': 'Signed',
                'Autographed': 'Autographed',
                'Colored': 'Colored',
                'Picture': 'Picture',
                'Disc': 'Disc',
                'Gatefold': 'Gatefold',
                'Explicit': 'Explicit',
                'Lyrics': 'Lyrics'
            }
            
            # Apply replacements for better formatting
            for old, new in replacements.items():
                formatted = formatted.replace(old, new)
            
            # Handle slashes (like "AUTOGRAPHED / STAR SIGNED" -> "Autographed/Star Signed")
            if '/' in formatted:
                slash_parts = [p.strip() for p in formatted.split('/')]
                formatted = '/'.join(slash_parts)
            
            formatted_parts.append(formatted)
        
        # Join with commas and spaces
        return ', '.join(formatted_parts)

    def create_title(self, artist, album, color_details):
        """Create product title: [Artist] - [Album] LP ([Formatted details])"""
        # Convert all inputs to strings and handle NaN/None values
        def safe_str(value):
            if pd.isna(value) or value is None:
                return ''
            return str(value).strip()
        
        artist = safe_str(artist)
        album = safe_str(album)
        color_details = safe_str(color_details)
        
        title = f"{artist} - {album} LP"
        
        if color_details:
            # Format the vinyl details
            formatted_details = self.format_vinyl_details(color_details)
            if formatted_details:
                title += f" ({formatted_details})"
        
        return title
    
    def calculate_pricing(self, msrp):
        """Calculate all pricing based on MSRP"""
        try:
            msrp = float(msrp)
        except (ValueError, TypeError):
            return None, None, None
        
        # Estimate cost at 77% of MSRP
        estimated_cost = msrp * self.cost_multiplier
        
        # Adjust MSRP if too close to cost
        my_price = estimated_cost + self.base_markup
        if msrp < my_price + 6:
            adjusted_msrp = my_price + self.msrp_minimum_markup
        else:
            adjusted_msrp = msrp
        
        # Calculate club price
        club_price = estimated_cost + self.club_base_markup
        cost_diff = club_price - estimated_cost
        
        if cost_diff > self.club_tier1_threshold:
            club_price += self.club_tier1_addition
            cost_diff = club_price - estimated_cost
            
            if cost_diff > self.club_tier2_threshold:
                club_price += self.club_tier2_addition
        
        return estimated_cost, adjusted_msrp, club_price
    
    def calculate_weight_grams(self, format_type):
        """Calculate weight in grams based on format"""
        weight_map = {
            'VINYL LP': 180,  # grams
            '12-INCH SINGLE': 140,
            '7-INCH SINGLE': 40
        }
        return weight_map.get(format_type, 180)  # Default to LP weight
    
    def transform_to_shopify(self, alliance_df, target_date):
        """Transform Alliance data to Shopify format for a specific target date"""
        target_date_only = target_date.date()
        
        print(f"Processing {len(alliance_df)} records...")
        print(f"Target release date: {target_date.strftime('%Y-%m-%d (%A, %B %d, %Y)')}")
        
        # First, let's analyze what format codes we have
        format_counts = alliance_df['FormatDesc'].value_counts()
        print(f"\nTop FormatDesc values in dataset:")
        print(format_counts.head(10))
        
        vinyl_count = 0
        skipped_count = 0
        date_matches = 0
        shopify_data = []
        
        for idx, row in alliance_df.iterrows():
            try:
                # Helper function to safely get string values
                def safe_get(column_name, default=''):
                    value = row.get(column_name, default)
                    if pd.isna(value) or value is None:
                        return default
                    return str(value).strip()
                
                # Extract key fields (using actual column names from Alliance)
                artist = safe_get('Artist')
                album = safe_get('ItemName')  # This is the album/title field
                format_desc = safe_get('FormatDesc')  # This should contain the format descriptions
                item_format = safe_get('ItemFormat')  # This might help us filter for vinyl
                barcode = safe_get('Barcode')
                msrp_raw = row.get('MSRP', 0)
                color_details = safe_get('DelimMisc')
                item_notes = safe_get('ItemNotes')
                image_url = safe_get('ImgHttpPath')
                avail_dt_raw = safe_get('AvailDt')
                
                # Debug: Print first few records to see what we're working with
                if idx < 5:
                    print(f"\nRecord {idx + 1}:")
                    print(f"  Artist: '{artist}'")
                    print(f"  Album: '{album}'")
                    print(f"  ItemFormat: '{item_format}'")
                    print(f"  FormatDesc: '{format_desc}'")
                    print(f"  AvailDt: '{avail_dt_raw}'")
                    print(f"  MSRP: '{msrp_raw}'")
                
                # Skip if we don't have basic required info
                if not artist or not album:
                    skipped_count += 1
                    continue
                
                # FIRST FILTER: Check date - must match the target date
                avail_date = self.parse_avail_date(avail_dt_raw)
                if not avail_date or avail_date.date() != target_date_only:
                    skipped_count += 1
                    continue
                
                date_matches += 1
                
                # SECOND FILTER: Must be one of the target vinyl formats
                vinyl_formats = ['12-INCH SINGLE', '7-INCH SINGLE', 'VINYL LP']
                if format_desc not in vinyl_formats:
                    skipped_count += 1
                    continue
                
                vinyl_count += 1
                
                # Show some vinyl records we're processing
                if vinyl_count <= 10:
                    print(f"  -> MATCH #{vinyl_count}: {artist} - {album} (Format: {format_desc}, Date: {avail_date.strftime('%Y-%m-%d')})")
                
                # Set the format type for weight calculation
                format_type = format_desc  # Use the actual format description
                
                # Calculate pricing
                cost, adjusted_msrp, club_price = self.calculate_pricing(msrp_raw)
                if not cost:
                    print(f"  -> Skipping due to pricing issue: {msrp_raw}")
                    continue  # Skip if pricing calculation failed
                
                # Create fields
                handle = self.create_handle(artist, album, color_details, target_date)
                title = self.create_title(artist, album, color_details)
                weight_grams = self.calculate_weight_grams(format_type)
                
                # Create description with preamble and ItemNotes
                body_content = self.create_description(item_notes, target_date)
                
                # Create tags
                tags = f"preorder club,preorder{target_date.strftime('%Y%m%d')}"
                
                # Build Shopify row
                shopify_row = {
                    'Handle': handle,
                    'Variant Barcode': barcode,
                    'Title': title,
                    'Body (HTML)': body_content,
                    'Vendor': 'Alliance Entertainment',
                    'Product Category': 'Media > Music & Sound Recordings > Records & LPs',
                    'Type': 'Records & LPs',
                    'Tags': tags,
                    'Option1 Name': 'Title',
                    'Option1 Value': 'Default Title',
                    'Variant Grams': weight_grams,
                    'Variant Inventory Tracker': 'shopify',
                    'Variant Inventory Policy': 'continue',
                    'Variant Fulfillment Service': 'manual',
                    'Variant Price': club_price,
                    'Variant Compare At Price': adjusted_msrp,
                    'Variant Requires Shipping': 'TRUE',
                    'Variant Taxable': 'TRUE',
                    'Image Src': image_url,
                    'Gift Card': 'FALSE',
                    'Variant Weight Unit': 'lb',
                    'Cost per item': cost,
                    'Included / United States': 'TRUE',
                    'Included / International': 'TRUE',
                    'Status': 'draft'
                }
                
                shopify_data.append(shopify_row)
                
                # Progress indicator for vinyl records
                if vinyl_count % 50 == 0:
                    print(f"Found {vinyl_count} vinyl records so far...")
                
            except Exception as e:
                print(f"Error processing row {idx}: {e}")
                continue
        
        print(f"\nFiltering complete:")
        print(f"  Total records processed: {len(alliance_df)}")
        print(f"  Records matching target date: {date_matches}")
        print(f"  Vinyl records found: {vinyl_count}")
        print(f"  Records skipped: {skipped_count}")
        print(f"  Final products for Shopify: {len(shopify_data)}")
        
        return pd.DataFrame(shopify_data)
    
    def create_description(self, item_notes, release_date):
        """Create product description with preamble and ItemNotes"""
        # Create the preamble with dynamic date
        preamble = f"""<p>This is a preorder for {release_date.strftime('%m/%d/%Y')}! We will ship as soon as your full order arrives, which will usually be that day or the following day. Occasionally, it may be up to a week later. See the full list of the week for more details, and email info@latchkeyrecords.com with any questions!</p>"""
        
        # Clean up item notes and wrap in paragraph tags if content exists
        description = preamble
        if item_notes and str(item_notes).strip() and str(item_notes).strip().lower() != 'nan':
            cleaned_notes = str(item_notes).strip()
            # Wrap in paragraph tags if not already HTML
            if not cleaned_notes.startswith('<'):
                cleaned_notes = f"<p>{cleaned_notes}</p>"
            description += cleaned_notes
            
        return description
    
    def save_csv(self, df, target_date):
        """Save the transformed data as CSV"""
        filename = f"{target_date.strftime('%Y%m%d')}_to_upload.csv"
        df.to_csv(filename, index=False)
        print(f"Saved {len(df)} products to {filename}")
        return filename

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description='Transform Alliance catalog to Shopify CSV for a specific release date',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python preorder_transformer.py --date 2025-09-19
  python preorder_transformer.py --date 09/19/2025
  python preorder_transformer.py --date 20250919
        """
    )
    parser.add_argument(
        '--date', 
        required=True,
        help='Target release date (formats: YYYY-MM-DD, MM/DD/YYYY, YYYYMMDD, etc.)'
    )
    parser.add_argument(
        '--file',
        default='alliance_catalog.txt',
        help='Alliance catalog file path (default: alliance_catalog.txt)'
    )
    
    args = parser.parse_args()
    
    transformer = PreorderTransformer()
    
    print("Starting preorder transformation...")
    print(f"Alliance file: {args.file}")
    
    # Parse and validate the target date
    try:
        target_date = transformer.parse_target_date(args.date)
        print(f"Parsed target date: {target_date.strftime('%Y-%m-%d (%A)')}")
        
        # Validate the date (Friday check, future date check)
        if not transformer.validate_target_date(target_date):
            print("Exiting due to date validation.")
            return
            
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    # Step 1: Load Alliance data
    alliance_data = transformer.load_alliance_data(args.file)
    if alliance_data is None:
        return
    
    # Step 2: Transform to Shopify format
    shopify_data = transformer.transform_to_shopify(alliance_data, target_date)
    
    # Step 3: Save CSV
    filename = transformer.save_csv(shopify_data, target_date)
    
    print(f"\nTransformation complete! Upload {filename} to Shopify.")
    print(f"Release date: {target_date.strftime('%B %d, %Y (%A)')}")
    print(f"Collection tag: preorder{target_date.strftime('%Y%m%d')}")

if __name__ == "__main__":
    main()