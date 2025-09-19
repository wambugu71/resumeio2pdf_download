import os
import io
import time
import hashlib
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any

import streamlit as st
import humanize

from pdfengine.pdfgenerator import (
    ApplicationRunner,
    SupportedImageFormats,
    DocumentSpecification,
    DocumentValidationError,
    ProcessingError,
    NetworkError
)

# -----------------------------
# Capability / Environment Detection
# -----------------------------

def ocr_available() -> bool:
    import shutil
    return shutil.which("tesseract") is not None

OCR_AVAILABLE = ocr_available()

# -----------------------------
# Helpers
# -----------------------------

def anonymize(token: str) -> str:
    if not token:
        return "";
    t = token.strip()
    if len(t) <= 7:
        return "***"
    return f"{t[:4]}…{t[-2:]}"

def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]

@dataclass
class RunResult:
    token_display: str
    token_hash: str
    duration_s: float
    size_bytes: int
    success: bool
    error: Optional[str] = None

# -----------------------------
# Caching expensive resources
# -----------------------------

@st.cache_resource(show_spinner=False)
def get_runner():
    return ApplicationRunner()

# Final PDF cache keyed by params
@st.cache_data(show_spinner=False)
def cached_generate_pdf(token: str, resolution: int, fmt: str, enable_ocr: bool, preserve_links: bool) -> bytes:
    runner = get_runner()
    # The current engine ignores some params, but we include them for future extension
    pdf_bytes = runner.execute_document_conversion(token)
    if not pdf_bytes:
        raise ProcessingError("Empty PDF result")
    return pdf_bytes

# -----------------------------
# Background execution handling
# -----------------------------

def launch_background_task(key: str, func, *args, **kwargs):
    """Run a function in a thread and store status in session_state."""
    st.session_state.tasks[key] = {"status": "running", "start": time.time()}
    def _target():
        try:
            pdf_bytes = func(*args, **kwargs)
            st.session_state.tasks[key].update({
                "status": "done",
                "bytes": pdf_bytes,
                "end": time.time()
            })
        except Exception as e:  # broad capture, store error
            st.session_state.tasks[key].update({
                "status": "error",
                "error": str(e),
                "end": time.time()
            })
    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

# -----------------------------
# Session State Initialization
# -----------------------------
if 'run_history' not in st.session_state:
    st.session_state.run_history = []  # list[RunResult]
if 'tasks' not in st.session_state:
    st.session_state.tasks = {}
if 'active_token_key' not in st.session_state:
    st.session_state.active_token_key = None

# -----------------------------
# Layout / UI
# -----------------------------

st.set_page_config(page_title="Resume PDF Generator", page_icon="📄", layout="wide")

st.title("📄 Resume PDF Generator (Streamlit UI)")
st.caption("Open-source interface for converting resume tokens to PDFs.")

with st.sidebar:
    st.subheader("Settings")
    default_resolution = int(os.getenv("PDF_DEFAULT_RESOLUTION", "3000"))
    max_resolution_env = int(os.getenv("PDF_MAX_RESOLUTION", "5000"))
    min_resolution_env = int(os.getenv("PDF_MIN_RESOLUTION", "100"))
    hard_cap_resolution = min(max_resolution_env, 5000)  # protective cap for hosted env
    st.write(f"OCR Available: {'✅' if OCR_AVAILABLE else '❌'}")
    if not OCR_AVAILABLE:
        st.info("Tesseract not found. OCR disabled.")
    st.markdown("---")
    st.write("Cache Controls")
    if st.button("Clear Cached PDFs"):
        cached_generate_pdf.clear()
        st.success("Cache cleared.")

# Main input form
with st.form("generate_form", clear_on_submit=False):
    token = st.text_input("Resume Access Token", help="Paste the token used to fetch resume metadata/images.")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        resolution = st.number_input("Resolution", min_value=min_resolution_env, max_value=hard_cap_resolution, value=default_resolution, step=100)
    with col2:
        output_format = st.selectbox("Image Format", options=[f.value for f in SupportedImageFormats], index=0)
    with col3:
        enable_ocr = st.checkbox("Enable OCR", value=True and OCR_AVAILABLE, disabled=not OCR_AVAILABLE)
    with col4:
        preserve_links = st.checkbox("Preserve Links", value=True)
    submitted = st.form_submit_button("Generate PDF", type="primary")

# Validation & launch
if submitted:
    if not token.strip():
        st.error("Token cannot be empty.")
    else:
        # Build task key
        task_key = f"{token_fingerprint(token)}-{resolution}-{output_format}-{int(enable_ocr)}-{int(preserve_links)}"
        st.session_state.active_token_key = task_key
        if task_key in st.session_state.tasks and st.session_state.tasks[task_key]['status'] in ("running", "done"):
            st.info("This exact request was already started. Showing status below.")
        else:
            launch_background_task(task_key, cached_generate_pdf, token, resolution, output_format, enable_ocr, preserve_links)
            st.success("Generation started.")

# Display active task status
active_key = st.session_state.active_token_key
if active_key:
    task_info: Dict[str, Any] = st.session_state.tasks.get(active_key, {})
    if task_info:
        placeholder = st.empty()
        if task_info['status'] == 'running':
            elapsed = time.time() - task_info['start']
            with placeholder.container():
                st.info(f"⏳ Generating PDF... Elapsed {elapsed:.1f}s")
                st.progress(min(0.05 + (elapsed/30.0), 0.95))  # synthetic progress bar
            st.experimental_rerun()
        elif task_info['status'] == 'done':
            duration = task_info['end'] - task_info['start']
            pdf_bytes = task_info['bytes']
            size = len(pdf_bytes)
            run_result = RunResult(
                token_display=anonymize(token),
                token_hash=active_key.split('-')[0],
                duration_s=duration,
                size_bytes=size,
                success=True
            )
            # Append to history if new
            if not any(r.token_hash == run_result.token_hash and r.size_bytes == size for r in st.session_state.run_history):
                st.session_state.run_history.insert(0, run_result)
            with placeholder.container():
                st.success(f"✅ PDF generated in {duration:.2f}s — {humanize.naturalsize(size)}")
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=f"resume_{run_result.token_hash}.pdf",
                    mime="application/pdf"
                )
        elif task_info['status'] == 'error':
            duration = task_info['end'] - task_info['start']
            err = task_info.get('error', 'Unknown error')
            with placeholder.container():
                st.error(f"❌ Failed after {duration:.2f}s: {err}")

st.markdown("---")

# Run History
st.subheader("Recent Runs")
if not st.session_state.run_history:
    st.write("No runs yet.")
else:
    import pandas as pd
    hist_rows = [
        {
            "Token": r.token_display,
            "Hash": r.token_hash,
            "Duration (s)": round(r.duration_s, 2),
            "Size": humanize.naturalsize(r.size_bytes),
            "Status": "Success" if r.success else "Error"
        } for r in st.session_state.run_history
    ]
    df = pd.DataFrame(hist_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption("Tip: identical parameter combinations reuse cached results. Clear cache in the sidebar.")
