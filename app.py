import streamlit as st
import pandas as pd
import requests
import os
import zipfile
import shutil
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import io

# Set up page configurations
st.set_page_config(
    page_title="POC Reporter - Digital Drop Packager",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium UI Styling
st.markdown("""
<style>
    /* Import modern typography */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Space+Grotesk:wght@400;500;700&display=swap');
    
    /* Main container styling */
    .main .block-container {
        font-family: 'Outfit', sans-serif;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Custom Headers */
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    /* Custom Gradient Title */
    .title-gradient {
        background: linear-gradient(135deg, #FF4B4B 0%, #852DF4 50%, #2979FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    .subtitle-text {
        color: #7f8c8d;
        font-size: 1.15rem;
        margin-bottom: 2.5rem;
    }
    
    /* Cards and Glassmorphism */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255, 4B, 4B, 0.4);
        box-shadow: 0 12px 40px 0 rgba(133, 45, 244, 0.25);
    }
    
    .metric-num {
        font-size: 2.5rem;
        font-weight: 700;
        color: #FF4B4B;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    .metric-label {
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #b2bec3;
        margin-top: 0.25rem;
    }
    
    /* Log console styling */
    .log-container {
        font-family: 'Space Grotesk', monospace;
        background-color: #0d1117;
        color: #58a6ff;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #30363d;
        height: 250px;
        overflow-y: auto;
        font-size: 0.85rem;
        line-height: 1.4;
    }
    
    .log-entry-info {
        color: #c9d1d9;
    }
    
    .log-entry-success {
        color: #56e39f;
        font-weight: 600;
    }
    
    .log-entry-warn {
        color: #ffb703;
    }
    
    .log-entry-error {
        color: #ff4b4b;
        font-weight: 600;
    }
    
    /* Buttons and controls */
    div.stButton > button {
        background: linear-gradient(135deg, #FF4B4B 0%, #852DF4 100%);
        color: white;
        border: none;
        padding: 0.6rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
        transition: all 0.3s ease;
        width: 100%;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, #852DF4 0%, #2979FF 100%);
        box-shadow: 0 6px 20px rgba(133, 45, 244, 0.4);
        transform: translateY(-2px);
        color: white;
    }
    
    div.stDownloadButton > button {
        background: linear-gradient(135deg, #56e39f 0%, #00b894 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        font-weight: 700;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 184, 148, 0.3);
        transition: all 0.3s ease;
        width: 100%;
        margin-top: 1rem;
    }
    
    div.stDownloadButton > button:hover {
        background: linear-gradient(135deg, #00b894 0%, #0984e3 100%);
        box-shadow: 0 6px 20px rgba(9, 132, 227, 0.4);
        transform: translateY(-2px);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Main App Header
st.markdown("<div class='title-gradient'>Digital Drop Packager</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-text'>Upload a call reports CSV to automatically download, de-duplicate, rename, and zip all recordings sorted by Policy Number.</div>", unsafe_allow_html=True)

# Sidebar with guidelines
with st.sidebar:
    st.markdown("### 🎙️ About Digital Drop Packager")
    st.write(
        "This tool automates the process of retrieving recording links from customer interaction logs, "
        "renaming them intelligently according to policy numbers, resolving duplicate naming collisions, "
        "and assembling them into a single zip file download."
    )
    
    st.markdown("---")
    st.markdown("### 💡 How Collision Handling Works")
    st.write(
        "If a policy number appears multiple times with recordings:\n"
        "1. First recording $\\rightarrow$ `[policy_number].mp3`\n"
        "2. Second recording $\\rightarrow$ `[policy_number]-1.mp3`\n"
        "3. Third recording $\\rightarrow$ `[policy_number]-2.mp3`\n"
        "and so on."
    )
    
    st.markdown("---")
    st.markdown("### 🛠️ Configuration")
    max_workers = st.slider("Download Concurrency (Threads)", min_value=1, max_value=10, value=5, help="Speed up downloads by running multiple requests concurrently.")
    timeout_sec = st.slider("Request Timeout (Seconds)", min_value=5, max_value=60, value=15, help="How long to wait for each download request to respond.")

# Initialize session state for downloaded zip file
if 'zip_path' not in st.session_state:
    st.session_state.zip_path = None
if 'zip_name' not in st.session_state:
    st.session_state.zip_name = None
if 'download_logs' not in st.session_state:
    st.session_state.download_logs = []
if 'excel_bytes' not in st.session_state:
    st.session_state.excel_bytes = None
if 'excel_name' not in st.session_state:
    st.session_state.excel_name = None
if 'success_count' not in st.session_state:
    st.session_state.success_count = None

# Directory configurations
TEMP_DIR = os.path.join(os.getcwd(), "temp_recordings")

def clean_temp_directories():
    """Clean up temp folders and zip files on code startup or re-upload."""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    
    # Also look for any zip files in the current folder that might have been left over
    for f in os.listdir(os.getcwd()):
        if f.endswith("_recordings.zip"):
            try:
                os.remove(f)
            except Exception:
                pass

def clean_value(val):
    """Clean string values from CSV, handling NULL strings."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s.upper() in ["NULL", "NAN", ""]:
        return None
    return s

def extract_file_extension(url):
    """Extract extension from URL, defaulting to .mp3."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        ext = os.path.splitext(path)[1]
        if ext and len(ext) <= 5:  # ensure it looks like a valid extension (e.g. .mp3, .wav)
            return ext.lower()
    except Exception:
        pass
    return ".mp3"

# File Uploader component
uploaded_file = st.file_uploader("Upload call logs CSV file", type=["csv"], help="Make sure your CSV contains policy_number and recording_url columns.")

if uploaded_file is not None:
    # If a new file is uploaded, clear any previous downloads
    if 'last_uploaded_name' not in st.session_state or st.session_state.last_uploaded_name != uploaded_file.name:
        st.session_state.last_uploaded_name = uploaded_file.name
        st.session_state.zip_path = None
        st.session_state.zip_name = None
        st.session_state.download_logs = []
        st.session_state.excel_bytes = None
        st.session_state.excel_name = None
        st.session_state.success_count = None
        clean_temp_directories()

    try:
        # Auto-detect delimiter by reading a sample of the file
        sample_bytes = uploaded_file.read(2048)
        uploaded_file.seek(0)
        
        try:
            sample_str = sample_bytes.decode('utf-8', errors='ignore')
        except Exception:
            sample_str = ""
            
        sep = ','
        # Count occurrences of standard delimiters
        tab_count = sample_str.count('\t')
        comma_count = sample_str.count(',')
        semi_count = sample_str.count(';')
        
        if tab_count > comma_count and tab_count > semi_count:
            sep = '\t'
        elif semi_count > comma_count and semi_count > tab_count:
            sep = ';'
            
        # Load CSV with detected separator
        df = pd.read_csv(uploaded_file, sep=sep)
        
        # Verify required columns
        required_cols = ['policy_number', 'recording_url']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ The uploaded CSV is missing required columns: **{', '.join(missing_cols)}**.")
            st.info("Ensure the CSV contains at least `policy_number` and `recording_url` headers.")
        else:
            # Clean and analyze the columns
            df['cleaned_policy'] = df['policy_number'].apply(clean_value)
            df['cleaned_url'] = df['recording_url'].apply(clean_value)
            
            # Calculate duration > 0 calls count
            if 'duration_seconds' in df.columns:
                try:
                    durations = pd.to_numeric(df['duration_seconds'], errors='coerce').fillna(0)
                    duration_gt_0_count = int((durations > 0).sum())
                except Exception:
                    duration_gt_0_count = 0
            else:
                duration_gt_0_count = 0
                
            # Generate the Excel report in memory if not already cached
            if st.session_state.excel_bytes is None:
                try:
                    excel_df = df.copy()
                    
                    # Format call_date
                    if 'call_date' in excel_df.columns:
                        try:
                            excel_df['call_date'] = pd.to_datetime(excel_df['call_date'], errors='coerce')
                            excel_df['call_date'] = excel_df['call_date'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
                        except Exception:
                            pass
                    
                    # Exclude the unwanted columns
                    cols_to_remove = ['call_id', 'call_detail_id', 'telephony_status', 'recording_url', 'telephony_sid', 'scheduled_at', 'mobile_number']
                    cols_to_drop = [c for c in cols_to_remove if c in excel_df.columns]
                    excel_df = excel_df.drop(columns=cols_to_drop)
                    
                    # Exclude temporary columns
                    temp_cols_to_drop = [c for c in ['cleaned_policy', 'cleaned_url'] if c in excel_df.columns]
                    excel_df = excel_df.drop(columns=temp_cols_to_drop)
                    
                    # Write to Excel in memory using openpyxl
                    excel_output = io.BytesIO()
                    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                        excel_df.to_excel(writer, index=False, sheet_name='Call Report')
                    
                    st.session_state.excel_bytes = excel_output.getvalue()
                    st.session_state.excel_name = f"{os.path.splitext(uploaded_file.name)[0]}_report.xlsx"
                except Exception as exc:
                    st.error(f"Failed to generate Excel report: {str(exc)}")
            
            # Filter rows that have valid URLs and policy numbers
            valid_rows = df[df['cleaned_url'].notna() & df['cleaned_policy'].notna()]
            skipped_rows = df[df['cleaned_url'].isna() | df['cleaned_policy'].isna()]
            
            # Metrics Display
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-num'>{len(df)}</div>
                    <div class='metric-label'>Total CSV Rows</div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-num'>{len(valid_rows)}</div>
                    <div class='metric-label'>With Recordings</div>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-num'>{len(skipped_rows)}</div>
                    <div class='metric-label'>Skipped / No Audio</div>
                </div>
                """, unsafe_allow_html=True)
            with m4:
                # Count unique policy numbers in valid rows
                unique_policies = valid_rows['cleaned_policy'].nunique() if len(valid_rows) > 0 else 0
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-num'>{unique_policies}</div>
                    <div class='metric-label'>Unique Policies</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
            
            # Split page into CSV Preview and Actions
            col_left, col_right = st.columns([3, 2])
            
            with col_left:
                st.subheader("📊 Data Preview & Status")
                
                # Create a neat display dataframe
                preview_df = df.copy()
                # Flag if it will be downloaded
                preview_df['Action Status'] = '⚠️ Skipped (No Recording URL)'
                preview_df.loc[valid_rows.index, 'Action Status'] = '📥 Queued for Download'
                
                # Show columns of interest primarily
                cols_to_show = ['policy_number', 'mobile_number', 'telephony_status', 'outcome', 'recording_url', 'Action Status']
                cols_to_show = [c for c in cols_to_show if c in preview_df.columns]
                
                st.dataframe(
                    preview_df[cols_to_show],
                    use_container_width=True,
                    height=300
                )
                
            with col_right:
                st.subheader("⚙️ Pack & Download Action Panel")
                
                # Excel report download section
                if st.session_state.excel_bytes is not None:
                    st.markdown("### 📄 Sanitized Excel Report")
                    st.write("Download the sanitized report containing only essential columns and formatted timestamps.")
                    st.download_button(
                        label=f"📥 Download Excel Report (.xlsx)",
                        data=st.session_state.excel_bytes,
                        file_name=st.session_state.excel_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="excel_report_download"
                    )
                    st.markdown("<hr style='margin: 1.5rem 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);'/>", unsafe_allow_html=True)
                
                st.markdown("### 🎙️ Download & Package Audio")
                if len(valid_rows) == 0:
                    st.warning("⚠️ No valid recording URLs found in this CSV to download.")
                else:
                    st.info(f"Ready to download **{len(valid_rows)}** recording files, rename them by policy number (handling duplicates), and bundle them in a single ZIP folder.")
                    
                    # Start Button
                    start_btn = st.button("🚀 Start Downloading & Packaging")
                    
                    if start_btn:
                        st.session_state.download_logs = []
                        st.session_state.zip_path = None
                        st.session_state.zip_name = None
                        
                        # Create fresh temporary directories
                        clean_temp_directories()
                        os.makedirs(TEMP_DIR, exist_ok=True)
                        
                        # Keep track of file occurrences for duplicate handling
                        filename_counts = {}
                        
                        # Prepare download tasks
                        download_queue = []
                        for idx, row in valid_rows.iterrows():
                            policy = str(row['cleaned_policy'])
                            url = row['cleaned_url']
                            ext = extract_file_extension(url)
                            
                            # Deduplicate naming logic
                            count = filename_counts.get(policy, 0)
                            if count == 0:
                                target_name = f"{policy}{ext}"
                            else:
                                target_name = f"{policy}-{count}{ext}"
                            filename_counts[policy] = count + 1
                            
                            download_queue.append({
                                'url': url,
                                'target_name': target_name,
                                'policy': policy
                            })
                        
                        # Progress reporting widgets
                        progress_bar = st.progress(0.0)
                        status_text = st.empty()
                        
                        log_container_header = st.markdown("**Live Action Logs:**")
                        log_placeholder = st.empty()
                        
                        success_count = 0
                        fail_count = 0
                        total_tasks = len(download_queue)
                        
                        logs = []
                        
                        def update_log_display():
                            html_content = "<div class='log-container'>"
                            for entry_type, text in logs[-12:]: # Display last 12 log lines for readability
                                if entry_type == 'success':
                                    html_content += f"<div class='log-entry-success'>✓ {text}</div>"
                                elif entry_type == 'error':
                                    html_content += f"<div class='log-entry-error'>✗ {text}</div>"
                                elif entry_type == 'warn':
                                    html_content += f"<div class='log-entry-warn'>⚠ {text}</div>"
                                else:
                                    html_content += f"<div class='log-entry-info'>ℹ {text}</div>"
                            html_content += "</div>"
                            log_placeholder.markdown(html_content, unsafe_allow_html=True)
                        
                        # Define target download logic
                        def download_single_file(task):
                            url = task['url']
                            target_name = task['target_name']
                            dest_path = os.path.join(TEMP_DIR, target_name)
                            
                            try:
                                response = requests.get(url, timeout=timeout_sec, stream=True)
                                if response.status_code == 200:
                                    with open(dest_path, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=16384):
                                            if chunk:
                                                f.write(chunk)
                                    return True, task, None
                                else:
                                    return False, task, f"HTTP status {response.status_code}"
                            except Exception as e:
                                return False, task, str(e)

                        logs.append(('info', f"Initialized download queue with {total_tasks} files."))
                        update_log_display()
                        
                        # Execute downloads concurrently using ThreadPoolExecutor
                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            future_to_task = {executor.submit(download_single_file, task): task for task in download_queue}
                            
                            for i, future in enumerate(as_completed(future_to_task)):
                                success, task, err_msg = future.result()
                                current_index = i + 1
                                progress_pct = float(current_index) / total_tasks
                                progress_bar.progress(progress_pct)
                                
                                if success:
                                    success_count += 1
                                    logs.append(('success', f"Saved: {task['target_name']} (Policy {task['policy']})"))
                                else:
                                    fail_count += 1
                                    logs.append(('error', f"Failed: {task['target_name']} -> {err_msg}"))
                                
                                status_text.markdown(f"📥 **Downloading files:** {current_index}/{total_tasks} processed ({success_count} succeeded, {fail_count} failed)")
                                update_log_display()
                                time.sleep(0.05) # Subtle micro-delay for smooth UI rendering
                        
                        # Zip all downloaded files
                        if success_count > 0:
                            logs.append(('info', "Creating ZIP archive..."))
                            update_log_display()
                            
                            zip_filename = f"{os.path.splitext(uploaded_file.name)[0]}_recordings.zip"
                            zip_file_path = os.path.join(os.getcwd(), zip_filename)
                            
                            # Compress all files inside TEMP_DIR
                            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for file in os.listdir(TEMP_DIR):
                                    file_path = os.path.join(TEMP_DIR, file)
                                    if os.path.isfile(file_path):
                                        zip_file.write(file_path, arcname=file)
                            
                            logs.append(('success', f"Successfully packaged {success_count} recordings into {zip_filename}!"))
                            update_log_display()
                            
                            # Clean up downloaded individual files to save disk space
                            shutil.rmtree(TEMP_DIR)
                            
                            st.session_state.zip_path = zip_file_path
                            st.session_state.zip_name = zip_filename
                            st.session_state.download_logs = logs
                            st.session_state.success_count = success_count
                            
                            st.balloons()
                        else:
                            st.error("❌ Failed to download any of the recording files. Please check the network connectivity or recording URLs.")
                            shutil.rmtree(TEMP_DIR)
                    
                    # Display the download button if ZIP file is successfully generated
                    if st.session_state.zip_path and os.path.exists(st.session_state.zip_path):
                        st.success(f"🎉 **Ready!** Packaged files successfully.")
                        
                        # Render Quality Validation Flag
                        if st.session_state.success_count is not None:
                            s_count = st.session_state.success_count
                            if s_count == duration_gt_0_count:
                                st.markdown(f"""
                                <div style="background-color: rgba(86, 227, 159, 0.1); border: 2px solid #56e39f; color: #56e39f; border-radius: 12px; padding: 1.25rem; margin-top: 1rem; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(86, 227, 159, 0.15);">
                                    <div style="display: flex; align-items: center; gap: 12px;">
                                        <span style="font-size: 1.8rem; line-height: 1;">✅</span>
                                        <div>
                                            <strong style="font-size: 1.1rem; font-family: 'Space Grotesk', sans-serif;">VALIDATION PASSED</strong><br/>
                                            <span style="font-size: 0.9rem; color: #c9d1d9;">All active conversations matched! The ZIP package contains exactly <strong>{s_count}</strong> recording files, which matches the <strong>{duration_gt_0_count}</strong> calls with duration > 0 seconds in the Excel report.</span>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div style="background-color: rgba(255, 183, 3, 0.1); border: 2px solid #ffb703; color: #ffb703; border-radius: 12px; padding: 1.25rem; margin-top: 1rem; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(255, 183, 3, 0.15);">
                                    <div style="display: flex; align-items: center; gap: 12px;">
                                        <span style="font-size: 1.8rem; line-height: 1;">⚠️</span>
                                        <div>
                                            <strong style="font-size: 1.1rem; font-family: 'Space Grotesk', sans-serif;">VALIDATION ALERT (MISMATCH)</strong><br/>
                                            <span style="font-size: 0.9rem; color: #c9d1d9;">Count mismatch detected:
                                            The ZIP contains <strong>{s_count}</strong> files, but there are <strong>{duration_gt_0_count}</strong> calls with duration > 0 seconds in the report. Verify if any download failures occurred.</span>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        # Read the zip in binary mode for Streamlit download button
                        with open(st.session_state.zip_path, 'rb') as f:
                            zip_bytes = f.read()
                        
                        st.download_button(
                            label=f"📥 Download {st.session_state.zip_name}",
                            data=zip_bytes,
                            file_name=st.session_state.zip_name,
                            mime="application/zip",
                            help="Click here to save the complete zip package containing all renamed recordings."
                        )
                        
                        # Keep logs persistent after page refreshes
                        if st.session_state.download_logs:
                            st.markdown("**Process Summary & Log:**")
                            html_content = "<div class='log-container'>"
                            for entry_type, text in st.session_state.download_logs:
                                if entry_type == 'success':
                                    html_content += f"<div class='log-entry-success'>✓ {text}</div>"
                                elif entry_type == 'error':
                                    html_content += f"<div class='log-entry-error'>✗ {text}</div>"
                                elif entry_type == 'warn':
                                    html_content += f"<div class='log-entry-warn'>⚠ {text}</div>"
                                else:
                                    html_content += f"<div class='log-entry-info'>ℹ {text}</div>"
                            html_content += "</div>"
                            st.markdown(html_content, unsafe_allow_html=True)
                            
    except Exception as err:
        st.error(f"Error parsing file: {str(err)}")
        st.exception(err)
