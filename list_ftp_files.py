#!/usr/bin/env python3
"""
Quick script to list all files on Alliance FTP server
"""

import ftplib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_ftp_files():
    """List all files on the FTP server"""
    
    # Get credentials
    host = os.getenv('FTP_HOST')
    username = os.getenv('FTP_USERNAME')
    password = os.getenv('FTP_PASSWORD')
    remote_directory = os.getenv('FTP_REMOTE_DIRECTORY', '/')
    
    if not all([host, username, password]):
        print("Missing FTP credentials in .env file")
        return
    
    try:
        print(f"Connecting to {host}...")
        
        with ftplib.FTP(host) as ftp:
            ftp.login(username, password)
            
            if remote_directory != '/':
                print(f"Changing to directory: {remote_directory}")
                ftp.cwd(remote_directory)
            
            print("\n=== FILES ON FTP SERVER ===")
            
            # Get file list
            files_list = []
            ftp.retrlines('LIST', files_list.append)
            
            for line in files_list:
                parts = line.split()
                if len(parts) >= 9 and parts[0].startswith('-'):
                    filename = parts[-1]
                    file_size = parts[4]
                    
                    # Try to get modification time
                    try:
                        mod_response = ftp.voidcmd(f"MDTM {filename}")
                        mod_time = mod_response.split()[-1]
                        print(f"📄 {filename} ({file_size} bytes, modified: {mod_time})")
                    except:
                        print(f"📄 {filename} ({file_size} bytes)")
            
            print("\n=== LOOKING FOR CATALOG FILES ===")
            catalog_files = [line for line in files_list 
                           if 'catalog' in line.lower() or 'latchkey' in line.lower()]
            
            if catalog_files:
                for line in catalog_files:
                    print(f"🎯 {line}")
            else:
                print("No obvious catalog files found")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_ftp_files()