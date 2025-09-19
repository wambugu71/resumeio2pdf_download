import os
import io
import time
import hashlib
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

# (Removed background task registry – synchronous flow only)

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

# (Removed background execution; generation now runs inline with progress bar)

# -----------------------------
# Session State Initialization
# -----------------------------
if 'run_history' not in st.session_state:
    st.session_state.run_history = []  # list[RunResult]
if 'last_generated' not in st.session_state:
    st.session_state.last_generated = None  # (hash, bytes, RunResult)

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
    # No running background tasks in synchronous mode

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

pdf_bytes = None
run_result = None

if submitted:
    if not token.strip():
        st.error("Token cannot be empty.")
    else:
        param_hash = token_fingerprint(token)
        start = time.time()
        progress_bar = st.progress(0.0)
        status_line = st.empty()
        def cb(p, msg):
            progress_bar.progress(min(max(p, 0.0), 1.0))
            status_line.write(msg)
        try:
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_with_progress(token, resolution, output_format, enable_ocr, preserve_links, cb)
            duration = time.time() - start
            run_result = RunResult(
                token_display=anonymize(token),
                token_hash=param_hash,
                duration_s=duration,
                size_bytes=len(pdf_bytes),
                success=True
            )
            st.session_state.run_history.insert(0, run_result)
            st.success(f"✅ PDF generated in {duration:.2f}s — {humanize.naturalsize(len(pdf_bytes))}")
            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name=f"resume_{param_hash}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"❌ Generation failed: {e}")
            pdf_bytes = None

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
