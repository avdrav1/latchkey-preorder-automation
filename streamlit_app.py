#!/usr/bin/env python3
"""
Latchkey Records Preorder Generator
Streamlit web interface for processing Alliance catalog files via FTP
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import tempfile
import os
import ftplib
import zipfile
import hashlib

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    ENV_LOADED = True
except ImportError:
    ENV_LOADED = False
    st.warning("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")

# Import your existing transformer class
try:
    from preorder_transformer import PreorderTransformer
except ImportError:
    st.error("Could not import PreorderTransformer. Make sure preorder_transformer.py is in the same directory.")
    st.stop()

# Configure the Streamlit page
st.set_page_config(
    page_title="Latchkey Records Preorder Generator",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f1f1f;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e2e3f3;
        border: 1px solid #b3b7e6;
        color: #383d71;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        margin: 1rem 0;
    }
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

def check_admin_password():
    """Check if admin password is configured"""
    admin_password = None
    
    # Try Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and hasattr(st.secrets, 'admin_password'):
            admin_password = st.secrets.admin_password
    except:
        pass
    
    # Fall back to environment variable
    if not admin_password:
        admin_password = os.getenv('ADMIN_PASSWORD')
    
    return admin_password

def hash_password(password):
    """Hash password for session storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def show_login_form():
    """Display login form"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown("### 🔐 Admin Access Required")
    st.write("Enter the admin password to access the Preorder Generator:")
    
    # Create login form
    with st.form("login_form"):
        password_input = st.text_input("Password", type="password", placeholder="Enter admin password")
        submit_button = st.form_submit_button("Login", type="primary")
        
        if submit_button:
            admin_password = check_admin_password()
            
            if not admin_password:
                st.error("❌ Admin password not configured. Please contact administrator.")
                return False
            
            if password_input == admin_password:
                # Store hashed password in session
                st.session_state.authenticated = True
                st.session_state.auth_hash = hash_password(admin_password)
                st.rerun()
            else:
                st.error("❌ Invalid password. Please try again.")
                return False
    
    st.markdown('</div>', unsafe_allow_html=True)
    return False

def check_authentication():
    """Check if user is authenticated"""
    # Check if user is logged in
    if 'authenticated' not in st.session_state:
        return False
    
    # Verify the stored hash is still valid
    admin_password = check_admin_password()
    if not admin_password:
        return False
    
    expected_hash = hash_password(admin_password)
    stored_hash = st.session_state.get('auth_hash', '')
    
    return st.session_state.authenticated and stored_hash == expected_hash

def show_logout_option():
    """Show logout button in sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.write("**Admin Session Active**")
        if st.button("🚪 Logout", type="secondary"):
            # Clear authentication
            st.session_state.authenticated = False
            if 'auth_hash' in st.session_state:
                del st.session_state.auth_hash
            # Clear URL parameter
            if "auth" in st.query_params:
                del st.query_params["auth"]
            st.rerun()

def get_ftp_credentials():
    """Get FTP credentials from Streamlit secrets, .env file, or environment variables"""
    
    # Check if .env file exists and show debug info
    env_file_path = os.path.join(os.getcwd(), '.env')
    env_file_exists = os.path.exists(env_file_path)
    
    try:
        # Try Streamlit secrets first (for deployment) - but only if they exist
        has_secrets = False
        try:
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'ftp'):
                has_secrets = True
        except Exception:
            # Secrets don't exist or can't be accessed, that's fine
            has_secrets = False
        
        if has_secrets:
            return {
                'host': st.secrets.ftp.host,
                'username': st.secrets.ftp.username,
                'password': st.secrets.ftp.password,
                'remote_directory': st.secrets.ftp.get('remote_directory', '/'),
                'filename': 'dfStdCatalogFull_048943_LatchKey.zip',
                'source': 'Streamlit Secrets'
            }
        else:
            # Try environment variables (loaded from .env or system)
            host = os.getenv('FTP_HOST')
            username = os.getenv('FTP_USERNAME') 
            password = os.getenv('FTP_PASSWORD')
            remote_directory = os.getenv('FTP_REMOTE_DIRECTORY', '/')
            
            if host and username and password:
                source = '.env file' if env_file_exists else 'Environment variables'
                return {
                    'host': host,
                    'username': username,
                    'password': password,
                    'remote_directory': remote_directory,
                    'filename': 'dfStdCatalogFull_048943_LatchKey.zip',
                    'source': source
                }
            else:
                # Return info about what's missing
                missing = []
                if not host: missing.append('FTP_HOST')
                if not username: missing.append('FTP_USERNAME') 
                if not password: missing.append('FTP_PASSWORD')
                
                return {
                    'missing': missing,
                    'env_file_exists': env_file_exists,
                    'env_file_path': env_file_path
                }
                
    except Exception as e:
        return {'error': str(e)}

def show_credential_debug_info():
    """Show debug information about credential loading"""
    creds = get_ftp_credentials()
    
    if 'error' in creds:
        st.error(f"Error loading credentials: {creds['error']}")
        return False
    
    if 'missing' in creds:
        st.error("❌ Missing FTP credentials:")
        for var in creds['missing']:
            st.write(f"   - {var}")
        
        if creds['env_file_exists']:
            st.info(f"📁 .env file found at: {creds['env_file_path']}")
            st.write("Make sure your .env file contains:")
            st.code("""FTP_HOST=your-alliance-ftp-host.com
FTP_USERNAME=your-username
FTP_PASSWORD=your-password
FTP_REMOTE_DIRECTORY=/path/to/catalog/files
ADMIN_PASSWORD=your-secure-admin-password""")
        else:
            st.warning(f"📁 No .env file found at: {creds['env_file_path']}")
            st.write("Create a .env file with your FTP credentials:")
            st.code("""FTP_HOST=your-alliance-ftp-host.com
FTP_USERNAME=your-username
FTP_PASSWORD=your-password
FTP_REMOTE_DIRECTORY=/path/to/catalog/files
ADMIN_PASSWORD=your-secure-admin-password""")
        
        return False
    
    if 'source' in creds:
        st.success(f"✅ FTP credentials loaded from: **{creds['source']}**")
        st.write(f"   - Host: {creds['host']}")
        st.write(f"   - Username: {creds['username']}")
        st.write(f"   - Directory: {creds['remote_directory']}")
        st.write(f"   - **Target file:** {creds['filename']}")
        return True
    
    return False

def download_alliance_catalog():
    """Download the Alliance catalog file from FTP"""
    credentials = get_ftp_credentials()
    
    if 'missing' in credentials or 'error' in credentials:
        return None, "FTP credentials not properly configured. Please check your .env file."
    
    try:
        filename = credentials['filename']  # dfStdCatalogFull_048943_LatchKey.zip
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            tmp_file_path = tmp_file.name
        
        # Download the specific file
        with ftplib.FTP(credentials['host']) as ftp:
            ftp.login(credentials['username'], credentials['password'])
            
            # Change to the remote directory if specified
            if credentials['remote_directory'] != '/':
                ftp.cwd(credentials['remote_directory'])
            
            # Get file size for progress tracking (optional)
            try:
                file_size = ftp.size(filename)
            except:
                file_size = None
            
            with open(tmp_file_path, 'wb') as f:
                def callback(data):
                    f.write(data)
                
                ftp.retrbinary(f'RETR {filename}', callback)
        
        return tmp_file_path, None
    
    except ftplib.all_errors as e:
        return None, f"FTP Error: {str(e)}"
    except Exception as e:
        return None, f"Download Error: {str(e)}"

def check_ftp_connection():
    """Test FTP connection and return status with catalog file info"""
    credentials = get_ftp_credentials()
    
    if 'missing' in credentials or 'error' in credentials:
        return False, "FTP credentials not properly configured"
    
    try:
        filename = credentials['filename']  # dfStdCatalogFull_048943_LatchKey.zip
        
        # Test connection and get file info
        with ftplib.FTP(credentials['host']) as ftp:
            ftp.login(credentials['username'], credentials['password'])
            
            if credentials['remote_directory'] != '/':
                ftp.cwd(credentials['remote_directory'])
            
            try:
                file_size = ftp.size(filename)
                size_info = f"{file_size:,} bytes"
            except:
                size_info = "size unknown"
            
            try:
                # Get modification time
                mod_time_response = ftp.voidcmd(f"MDTM {filename}")
                mod_time_str = mod_time_response.split()[-1]
                mod_time = datetime.strptime(mod_time_str, "%Y%m%d%H%M%S")
                mod_time_formatted = mod_time.strftime('%Y-%m-%d %H:%M')
                return True, f"File: '{filename}' ({size_info}, modified: {mod_time_formatted})"
            except:
                return True, f"File: '{filename}' ({size_info})"
                
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def calculate_default_friday():
    """Calculate the default target date (4 Fridays from now)"""
    today = datetime.now()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.weekday() == 4:  # If today is Friday
        days_until_friday = 7  # Get next Friday
    next_friday = today + timedelta(days=days_until_friday)
    target_friday = next_friday + timedelta(weeks=3)  # 4 weeks total
    return target_friday.date()

def validate_date(selected_date):
    """Validate that the selected date is reasonable"""
    warnings = []
    
    # Check if it's a Friday
    if selected_date.weekday() != 4:
        day_name = selected_date.strftime('%A')
        warnings.append(f"⚠️ {selected_date} is a {day_name}, not a Friday")
    
    # Check if it's in the past
    if selected_date <= datetime.now().date():
        warnings.append(f"⚠️ {selected_date} is in the past")
    
    # Check if it's too far in the future (more than 3 months)
    three_months = datetime.now().date() + timedelta(days=90)
    if selected_date > three_months:
        warnings.append(f"⚠️ {selected_date} is more than 3 months away")
    
    return warnings

def process_alliance_catalog(target_date):
    """Download and process the Alliance catalog file with detailed progress tracking"""
    try:
        # Store authentication before processing (in case of restart)
        auth_backup = {
            'authenticated': st.session_state.get('authenticated', False),
            'auth_hash': st.session_state.get('auth_hash', '')
        }
        
        # Initialize the transformer
        transformer = PreorderTransformer()
        
        # Create progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        debug_expander = st.expander("🔍 Detailed Processing Log", expanded=False)  # Changed to collapsed
        
        # Step 1: Download from FTP
        status_text.text("📥 Downloading Alliance catalog from FTP...")
        progress_bar.progress(20)
        
        with debug_expander:
            st.write("**Step 1: FTP Download**")
            credentials = get_ftp_credentials()
            st.write(f"Target filename: **{credentials['filename']}**")
            
        tmp_file_path, error = download_alliance_catalog()
        if error:
            with debug_expander:
                st.error(f"FTP Download failed: {error}")
            return None, error
        
        with debug_expander:
            file_size = os.path.getsize(tmp_file_path)
            st.success(f"✅ Downloaded file: {file_size:,} bytes")
        
        # Step 2: Load and analyze the file
        status_text.text("📊 Loading and analyzing catalog file...")
        progress_bar.progress(40)
        
        with debug_expander:
            st.write("**Step 2: File Analysis**")
            
            # Check if it's a ZIP file
            if tmp_file_path.lower().endswith('.zip') or zipfile.is_zipfile(tmp_file_path):
                st.write("📦 File is a ZIP archive, extracting...")
                
                try:
                    with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                        st.write(f"ZIP contains {len(file_list)} files:")
                        for filename in file_list:
                            if not filename.endswith('/'):
                                file_info = zip_ref.getinfo(filename)
                                st.write(f"  - {filename}: {file_info.file_size:,} bytes")
                        
                        # Find target file
                        target_file = None
                        largest_size = 0
                        
                        for filename in file_list:
                            if filename.endswith('/'):
                                continue
                            file_info = zip_ref.getinfo(filename)
                            if filename.lower().endswith('.txt'):
                                target_file = filename
                                st.write(f"🎯 Found .txt file: {filename}")
                                break
                            elif file_info.file_size > largest_size:
                                largest_size = file_info.file_size
                                target_file = filename
                        
                        if not target_file:
                            st.error("❌ No suitable file found in ZIP")
                            return None, "No suitable file found in ZIP archive"
                        
                        st.write(f"📤 Extracting: {target_file}")
                        
                        # Extract file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_txt:
                            tmp_txt.write(zip_ref.read(target_file))
                            extracted_file_path = tmp_txt.name
                        
                        extracted_size = os.path.getsize(extracted_file_path)
                        st.write(f"✅ Extracted {extracted_size:,} bytes")
                        
                        # Use extracted file
                        analysis_file_path = extracted_file_path
                        
                except Exception as e:
                    st.error(f"❌ ZIP extraction failed: {e}")
                    return None, f"ZIP extraction failed: {e}"
            else:
                st.write("📄 File is already a text file")
                analysis_file_path = tmp_file_path
            
            # Analyze file format
            st.write("**Step 3: Format Detection**")
            
            # Read first bytes
            with open(analysis_file_path, 'rb') as f:
                first_bytes = f.read(100)
                st.write(f"First 20 bytes: `{first_bytes[:20]}`")
                st.write(f"Hex: `{first_bytes[:20].hex()}`")
            
            # Try different encodings
            success = False
            final_encoding = None
            final_separator = None
            
            encodings_to_try = ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'latin-1']
            separators_to_try = ['|', ',', '\t']
            
            for encoding in encodings_to_try:
                for separator in separators_to_try:
                    try:
                        df_test = pd.read_csv(analysis_file_path, dtype=str, encoding=encoding, sep=separator, nrows=5)
                        if len(df_test.columns) > 5:  # Should have many columns
                            st.success(f"✅ Format detected: {encoding} encoding, '{separator}' separator")
                            st.write(f"Found {len(df_test.columns)} columns in sample")
                            st.write("Sample columns:", list(df_test.columns[:10]))
                            final_encoding = encoding
                            final_separator = separator
                            success = True
                            break
                    except Exception as e:
                        st.write(f"❌ Failed {encoding}/{separator}: {str(e)[:50]}...")
                
                if success:
                    break
            
            if not success:
                st.error("❌ Could not detect file format")
                return None, "Could not detect file format"
        
        # Step 3: Load data in chunks to save memory
        status_text.text("📚 Processing catalog data...")
        progress_bar.progress(60)
        
        # MEMORY OPTIMIZATION: Process in chunks instead of loading everything
        target_datetime = datetime.combine(target_date, datetime.min.time())
        target_date_only = target_datetime.date()
        vinyl_formats = ['12-INCH SINGLE', '7-INCH SINGLE', 'VINYL LP']
        
        matched_records = []
        total_processed = 0
        date_matches = 0
        vinyl_matches = 0
        
        with debug_expander:
            st.write("**Step 4: Chunked Processing (Memory Optimized)**")
            st.write(f"Target date: {target_datetime.strftime('%Y-%m-%d')}")
        
        # Process file in chunks of 10,000 rows
        chunk_size = 10000
        chunk_progress = st.empty()
        
        try:
            for chunk_num, df_chunk in enumerate(pd.read_csv(
                analysis_file_path, 
                dtype=str, 
                encoding=final_encoding, 
                sep=final_separator,
                chunksize=chunk_size
            )):
                # Update progress
                chunk_progress.text(f"Processing chunk {chunk_num + 1}...")
                
                # Restore session state in case it was lost
                st.session_state.authenticated = auth_backup['authenticated']
                st.session_state.auth_hash = auth_backup['auth_hash']
                
                for idx, row in df_chunk.iterrows():
                    total_processed += 1
                    
                    # Get basic fields
                    artist = str(row.get('Artist', '')).strip() if pd.notna(row.get('Artist')) else ''
                    album = str(row.get('ItemName', '')).strip() if pd.notna(row.get('ItemName')) else ''
                    format_desc = str(row.get('FormatDesc', '')).strip() if pd.notna(row.get('FormatDesc')) else ''
                    avail_dt_raw = str(row.get('AvailDt', '')).strip() if pd.notna(row.get('AvailDt')) else ''
                    
                    # Skip if missing basic info
                    if not artist or not album:
                        continue
                    
                    # Check date
                    avail_date = transformer.parse_avail_date(avail_dt_raw)
                    if avail_date and avail_date.date() == target_date_only:
                        date_matches += 1
                        
                        # Check format
                        if format_desc in vinyl_formats:
                            vinyl_matches += 1
                            matched_records.append(row)
                
                # Force garbage collection to free memory
                import gc
                del df_chunk
                gc.collect()
        
        except Exception as e:
            return None, f"Error processing data: {e}"
        
        status_text.text("🔄 Generating Shopify CSV...")
        progress_bar.progress(80)
        
        with debug_expander:
            st.write("**Step 5: Final Results**")
            st.write(f"📊 Total records processed: {total_processed:,}")
            st.write(f"📅 Records matching target date: {date_matches}")
            st.write(f"🎵 Vinyl records found: {vinyl_matches}")
        
        if not matched_records:
            return pd.DataFrame(), None
        
        # Convert matched records to DataFrame and transform
        matched_df = pd.DataFrame(matched_records)
        shopify_data = transformer.transform_to_shopify(matched_df, target_datetime)
        
        # Step 5: Complete
        status_text.text("✅ Processing complete!")
        progress_bar.progress(100)
        chunk_progress.empty()
        
        # Clean up temporary files
        try:
            os.unlink(tmp_file_path)
            if 'extracted_file_path' in locals():
                os.unlink(extracted_file_path)
        except:
            pass
        
        # Ensure session state is restored
        st.session_state.authenticated = auth_backup['authenticated']
        st.session_state.auth_hash = auth_backup['auth_hash']
        
        return shopify_data, None
    
    except Exception as e:
        return None, f"Error processing catalog: {str(e)}"

def main():
    # Check authentication first
    if not check_authentication():
        show_login_form()
        return
    
    # Show logout option in sidebar
    show_logout_option()
    
    # Header
    st.markdown('<h1 class="main-header">🎵 Latchkey Records Preorder Generator</h1>', unsafe_allow_html=True)
    
    # Subtitle
    st.markdown("""
    <div class="info-box">
    Select a target release date and generate a Shopify-ready CSV with vinyl preorders 
    (12-inch singles, 7-inch singles, and vinyl LPs) from the latest Alliance catalog.
    </div>
    """, unsafe_allow_html=True)
    
    # Check FTP connection status and show credential info
    with st.expander("🔧 FTP Configuration & Status", expanded=False):
        creds_loaded = show_credential_debug_info()
        
        if creds_loaded:
            with st.spinner("Testing FTP connection..."):
                ftp_connected, ftp_status = check_ftp_connection()
            
            if ftp_connected:
                st.success(f"✅ FTP Connection: {ftp_status}")
            else:
                st.error(f"❌ FTP Connection: {ftp_status}")
        else:
            ftp_connected = False
    
    if not ftp_connected:
        st.stop()
    
    # Create two columns for better layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📅 Select Release Date")
        
        # Date input with default value
        default_date = calculate_default_friday()
        
        # Show the default date calculation
        st.info(f"Default target date: **{default_date.strftime('%A, %B %d, %Y')}** (4 Fridays from today)")
        
        # Date picker
        target_date = st.date_input(
            "Target release date:",
            value=default_date,
            help="Select the Friday when these preorders should release"
        )
        
        # Validate the selected date
        date_warnings = validate_date(target_date)
        for warning in date_warnings:
            st.warning(warning)
    
    with col2:
        st.subheader("ℹ️ Information")
        
        st.markdown("""
        **What this tool does:**
        - Downloads latest Alliance catalog via FTP
        - Filters for vinyl records only
        - Matches your target release date
        - Calculates pricing based on your rules
        - Formats product titles properly
        - Creates Shopify-ready CSV
        
        **Vinyl formats included:**
        - 12-INCH SINGLE
        - 7-INCH SINGLE  
        - VINYL LP
        
        **Data source:**
        - Alliance Entertainment FTP
        - Specific catalog file: dfStdCatalogFull_048943_LatchKey.zip
        - No file size limitations
        - Full catalog data
        """)
    
    # Processing section
    st.subheader("🚀 Generate Preorder CSV")
    
    # Show file info
    st.markdown("""
    <div class="info-box">
    📊 <strong>Note:</strong> The app downloads the main Alliance catalog file: dfStdCatalogFull_048943_LatchKey.zip. 
    This is the complete catalog updated regularly by Alliance Entertainment.
    </div>
    """, unsafe_allow_html=True)
    
    # Process button
    if st.button("Download & Process Alliance Catalog", type="primary", disabled=(not ftp_connected)):
        # Show processing message
        with st.container():
            # Process the catalog
            result_df, error = process_alliance_catalog(target_date)
        
        if error:
            st.error(f"❌ {error}")
        elif result_df is not None and len(result_df) > 0:
            # Success! Show results
            st.markdown(f"""
            <div class="success-box">
            ✅ <strong>Processing Complete!</strong><br>
            Found <strong>{len(result_df)}</strong> vinyl records for {target_date.strftime('%B %d, %Y')}
            </div>
            """, unsafe_allow_html=True)
            
            # Show summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(result_df))
            with col2:
                if 'Variant Price' in result_df.columns:
                    avg_price = result_df['Variant Price'].mean()
                    st.metric("Avg Price", f"${avg_price:.2f}")
            with col3:
                st.metric("Release Date", target_date.strftime('%m/%d/%Y'))
            
            # Convert DataFrame to CSV
            csv_buffer = io.StringIO()
            result_df.to_csv(csv_buffer, index=False)
            csv_string = csv_buffer.getvalue()
            
            # Generate filename
            filename = f"{target_date.strftime('%Y%m%d')}_to_upload.csv"
            
            # Download button
            st.download_button(
                label="📥 Download Shopify CSV",
                data=csv_string,
                file_name=filename,
                mime="text/csv",
                type="primary"
            )
            
            # Show preview of the data
            with st.expander("🔍 Preview Generated Data"):
                st.dataframe(result_df.head(10))
            
            # Show next steps
            st.markdown("""
            ### 📋 Next Steps:
            1. **Download the CSV** using the button above
            2. **Upload to Shopify** via Products → Import
            3. **Update collection settings** with tag: `preorder{}`
            4. **Set passwords** in Locksmith app
            """.format(target_date.strftime('%Y%m%d')))
            
        else:
            st.warning("⚠️ No vinyl records found for the selected date. This could mean:")
            st.markdown("""
            - No records are releasing on that specific date
            - The date format in the Alliance file doesn't match the target date
            - All records for that date were filtered out (missing artist/album info, pricing issues, etc.)
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
    Latchkey Records Preorder Generator | Built with Streamlit | Data via Alliance Entertainment FTP
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()