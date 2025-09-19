import os
import io
import time
import hashlib
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any

import streamlit as st
import humanize

try:
    from pdfengine.pdfgenerator import (
        ApplicationRunner,
        SupportedImageFormats,
        DocumentValidationError,
        ProcessingError,
        NetworkError,
        ServiceConfiguration,
        DocumentSpecification,
        TimestampGenerator,
        HttpRequestExecutor,
        UrlBuilder,
        DocumentMetadataProcessor,
        RemoteDocumentFetcher,
        ImageToPdfConverter,
        LinkAnnotationBuilder,
        PdfDocumentAssembler
    )
except Exception as import_error:  # surface nicely in UI
    ApplicationRunner = None  # type: ignore
    SupportedImageFormats = None  # type: ignore
    DocumentValidationError = Exception  # fallback
    ProcessingError = Exception  # fallback
    NetworkError = Exception  # fallback
    ServiceConfiguration = None  # type: ignore
    DocumentSpecification = None  # type: ignore
    _PDFENGINE_IMPORT_ERROR = import_error
else:
    _PDFENGINE_IMPORT_ERROR = None

# -----------------------------
# Capability / Environment Detection
# -----------------------------

def ocr_available() -> bool:
    import shutil
    return shutil.which("tesseract") is not None

OCR_AVAILABLE = ocr_available()

# -----------------------------
# Global task registry (thread-safe)
# -----------------------------
TASKS: Dict[str, Dict[str, Any]] = {}
TASKS_LOCK = threading.Lock()

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
# Progress-enabled generation (page-level updates)
# -----------------------------

def generate_with_progress(token: str, resolution: int, fmt: str, enable_ocr: bool, preserve_links: bool, progress_cb):
    if ServiceConfiguration is None:
        raise ProcessingError("ServiceConfiguration unavailable (import failed)")
    spec = DocumentSpecification(
        access_token=token,
        output_format=SupportedImageFormats(fmt),
        image_resolution=resolution,
        enable_ocr=enable_ocr,
        preserve_links=preserve_links
    )
    service_conf = ServiceConfiguration()
    timestamp_gen = TimestampGenerator()
    http_client = HttpRequestExecutor(service_conf)
    url_builder = UrlBuilder(service_conf)
    metadata_proc = DocumentMetadataProcessor()
    image_converter = ImageToPdfConverter(enable_ocr=enable_ocr)
    link_builder = LinkAnnotationBuilder()
    fetcher = RemoteDocumentFetcher(http_client, url_builder, service_conf)
    assembler = PdfDocumentAssembler(image_converter, link_builder)
    try:
        progress_cb(0.01, "Fetching metadata…")
        ts = timestamp_gen.get_current_utc_timestamp()
        raw_metadata = fetcher.fetch_document_metadata(spec, ts)
        page_info = metadata_proc.extract_page_info(raw_metadata)
        total_pages = len(page_info)
        if total_pages == 0:
            raise DocumentValidationError("No pages found")
        images = []
        for idx in range(1, total_pages + 1):
            progress_cb(0.05 + 0.80 * ((idx - 1) / total_pages), f"Fetching page {idx}/{total_pages}…")
            img_buf = fetcher.fetch_page_image(spec, idx, ts)
            images.append(img_buf)
        progress_cb(0.90, "Assembling PDF…")
        pdf_bytes = assembler.assemble_document(images, page_info)
        progress_cb(1.0, "Done")
        return pdf_bytes
    except Exception:
        progress_cb(1.0, "Failed")
        raise

# -----------------------------
# Background execution handling
# -----------------------------

def launch_background_task(key: str, func, *args, **kwargs):
    """Run a function in a thread and store status in module-level TASKS dict."""
    with TASKS_LOCK:
        TASKS[key] = {"status": "running", "start": time.time(), "progress": 0.0, "message": "Queued"}

    def _target():
        try:
            pdf_bytes = func(*args, **kwargs)
            with TASKS_LOCK:
                TASKS[key].update({
                    "status": "done",
                    "bytes": pdf_bytes,
                    "end": time.time(),
                    "progress": 1.0,
                    "message": "Completed"
                })
        except Exception as e:  # broad capture, store error
            with TASKS_LOCK:
                TASKS[key].update({
                    "status": "error",
                    "error": str(e),
                    "end": time.time(),
                    "progress": 1.0,
                    "message": "Error"
                })
    threading.Thread(target=_target, daemon=True).start()

# -----------------------------
# Session State Initialization
# -----------------------------
if 'run_history' not in st.session_state:
    st.session_state.run_history = []  # list[RunResult]
if 'active_token_key' not in st.session_state:
    st.session_state.active_token_key = None
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True  # force enabled (legacy key kept for compatibility)
if 'last_auto_tick' not in st.session_state:
    st.session_state.last_auto_tick = 0.0

# -----------------------------
# Layout / UI
# -----------------------------

st.set_page_config(page_title="Resume PDF Generator", page_icon="📄", layout="wide")

if _PDFENGINE_IMPORT_ERROR:
    st.error("Failed to import pdfengine module. Ensure repository structure is intact.")
    with st.expander("Import Error Details"):
        st.exception(_PDFENGINE_IMPORT_ERROR)
    st.stop()

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
    # Auto refresh always on now; toggle removed per user request.
    st.markdown("---")
    st.write("Cache Controls")
    if st.button("Clear Cached PDFs"):
        cached_generate_pdf.clear()
        st.success("Cache cleared.")
    if st.session_state.active_token_key:
        with TASKS_LOCK:
            ti = TASKS.get(st.session_state.active_token_key)
        if ti and ti.get('status') == 'running':
            st.caption("Auto-updating while generation runs… (no manual refresh needed)")

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
        with TASKS_LOCK:
            existing = TASKS.get(task_key)
        if existing and existing.get('status') in ("running", "done"):
            st.info("This exact request was already started. Showing status below.")
        else:
            # Launch progress-enabled generation
            def progress_wrapper():
                def cb(p, msg):
                    with TASKS_LOCK:
                        if task_key in TASKS and TASKS[task_key]['status'] == 'running':
                            TASKS[task_key]['progress'] = max(0.0, min(1.0, p))
                            TASKS[task_key]['message'] = msg
                return generate_with_progress(token, resolution, output_format, enable_ocr, preserve_links, cb)
            launch_background_task(task_key, progress_wrapper)
            st.success("Generation started.")

# Display active task status
active_key = st.session_state.active_token_key
if active_key:
    with TASKS_LOCK:
        task_info: Dict[str, Any] = TASKS.get(active_key, {}).copy()
    if task_info:
        placeholder = st.empty()
        status = task_info.get('status')
        if status == 'running':
            elapsed = time.time() - task_info['start']
            prog = task_info.get('progress', 0.0)
            msg = task_info.get('message', 'Working…')
            with placeholder.container():
                st.write(f"⏳ <strong>Generating PDF</strong> – {msg} (elapsed {elapsed:.1f}s)", unsafe_allow_html=True)
                st.progress(prog)
            # Throttled auto-rerun loop (approx every 1s) for live updates
            now = time.time()
            if now - st.session_state.last_auto_tick > 1.0 and prog < 1.0:
                st.session_state.last_auto_tick = now
                if hasattr(st, 'rerun'):
                    st.rerun()
        elif status == 'done':
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
        elif status == 'error':
            duration = task_info['end'] - task_info['start']
            err = task_info.get('error', 'Unknown error')
            with placeholder.container():
                st.error(f"❌ Failed after {duration:.2f}s: {err}")

        # Manual refresh button
        # Manual refresh button removed per request.

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
