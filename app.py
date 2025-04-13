import streamlit as st
from streamlit_navigation_bar import st_navbar
from streamlit_extras.row import row
import io
import json
from dataclasses import dataclass
from datetime import datetime
import pytesseract
import requests
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import AnnotationBuilder
from enum import Enum
import hydralit_components as hc

# Configure page settings
st.set_page_config(
    layout="wide", 
    page_icon="icon.png", 
    page_title="Resume IO",
    initial_sidebar_state="collapsed"
)

# Custom CSS styles
PAGE_STYLE = """
<style>
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        font-family: 'Inter', system-ui, sans-serif;
    }
    
    .stSubheader {
        color: #2a2a72;
        font-size: 2rem;
        margin-bottom: 1.5rem;
    }
    
    .stExpander > details {
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .stButton > button {
        background: linear-gradient(45deg, #2a2a72 0%, #009ffd 100%);
        border: none;
        color: white;
        padding: 0.8rem 2rem;
        border-radius: 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        background: linear-gradient(45deg, #009ffd 0%, #2a2a72 100%);
    }
    
    .stTextInput input {
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput input:focus {
        border-color: #009ffd;
        box-shadow: 0 0 8px rgba(0, 159, 253, 0.3);
    }
    
    .stAlert {
        border-radius: 12px;
        padding: 1rem 1.5rem;
    }
    
    .download-success {
        background: linear-gradient(45deg, #00b09b 0%, #96c93d 100%);
        color: white !important;
        border-radius: 12px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .guide-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 2rem;
    }
</style>
"""
st.markdown(PAGE_STYLE, unsafe_allow_html=True)

class Extension(str, Enum):
    jpeg = "jpeg"
    png = "png"
    webp = "webp"

@dataclass
class ResumeioDownloader:
    rendering_token: str
    extension: Extension = Extension.jpeg
    image_size: int = 3000
    METADATA_URL: str = "https://ssr.resume.tools/meta/{rendering_token}?cache={cache_date}"
    IMAGES_URL: str = (
        "https://ssr.resume.tools/to-image/{rendering_token}-{page_id}.{extension}?cache={cache_date}&size={image_size}"
    )

    def __post_init__(self) -> None:
        self.cache_date = datetime.utcnow().isoformat()[:-4] + "Z"

    def generate_pdf(self) -> bytes:
        self.__get_resume_metadata()
        images = self.__download_images()
        pdf = PdfWriter()
        metadata_w, metadata_h = self.metadata[0].get("viewport").values()
        
        for i, image in enumerate(images):
            page_pdf = pytesseract.image_to_pdf_or_hocr(Image.open(image), extension="pdf")
            page = PdfReader(io.BytesIO(page_pdf)).pages[0]
            page_scale = max(page.mediabox.height / metadata_h, page.mediabox.width / metadata_w)
            pdf.add_page(page)
            
            for link in self.metadata[i].get("links"):
                link_url = link.pop("url")
                link.update((k, v * page_scale) for k, v in link.items())
                x, y, w, h = link.values()
                annotation = AnnotationBuilder.link(rect=(x, y, x + w, y + h), url=link_url)
                pdf.add_annotation(page_number=i, annotation=annotation)
        
        with io.BytesIO() as file:
            pdf.write(file)
            return file.getvalue()

    def __get_resume_metadata(self) -> None:
        response = requests.get(
            self.METADATA_URL.format(rendering_token=self.rendering_token, cache_date=self.cache_date),
        )
        self.__raise_for_status(response)
        self.metadata = json.loads(response.text).get("pages")

    def __download_images(self) -> list[io.BytesIO]:
        return [self.__download_image_from_url(
            self.IMAGES_URL.format(
                rendering_token=self.rendering_token,
                page_id=page_id,
                extension=self.extension,
                cache_date=self.cache_date,
                image_size=self.image_size,
            )
        ) for page_id in range(1, 1 + len(self.metadata))]

    def __download_image_from_url(self, url) -> io.BytesIO:
        response = requests.get(url)
        self.__raise_for_status(response)
        return io.BytesIO(response.content)

    def __raise_for_status(self, response) -> None:
        if response.status_code != 200:
            raise Exception(
                f"Error {response.status_code}: Unable to download resume (token: {self.rendering_token})"
            )

# Session state initialization
if "render_token" not in st.session_state:
    st.session_state["render_token"] = None
if "render_token_bool" not in st.session_state:
    st.session_state["render_token_bool"] = True

# Navigation bar configuration
pages = ["Home", "Download Resume", "About"]
nav_style = {
    "nav": {
        "background-color": "#1a1a2e",
        "padding": "1rem 2rem",
        "box-shadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
        "border-radius": "0 0 15px 15px"
    },
    "span": {
        "border-radius": "8px",
        "padding": "1rem 1.5rem",
        "font-family": "'Segoe UI', system-ui",
        "font-weight": "500",
        "transition": "all 0.3s ease"
    },
    "active": {"background-color": "#16213e"},
    "hover": {"background-color": "#0f3460"}
}

selected_page = st_navbar(
    pages,
    styles=nav_style,
    options={"show_menu": False, "show_sidebar": False}
)

# Page handling
if selected_page == "Home":
    st.subheader("Download Your Professional Resume")
    st.markdown("""
    <div class="guide-card">
        <h4 style='color: #2a2a72; margin-bottom: 1.5rem;'>🚀 Quick Start Guide</h4>
        <ol style='line-height: 2;'>
            <li>Visit <a href='https://resume.io/api/app/resumes' target='_blank'>resume.io/api/app/resumes</a></li>
            <li>Find and copy your <code>renderToken</code></li>
            <li>Paste it below and click Submit</li>
            <li>Proceed to download page</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📸 How to Get Your Render Token", expanded=False):
        st.image("copytoken.jpg", width=650, caption="Locate your token in browser dev tools")

    input_col, btn_col = st.columns([3, 1])
    with input_col:
        st.session_state["render_token"] = st.text_input(
            "Enter your renderToken",
            placeholder="Paste your token here...",
            label_visibility="collapsed"
        )

    with btn_col:
        if st.button("Submit Token", type="primary"):
            if st.session_state["render_token"]:
                st.session_state["render_token_bool"] = False
                st.success("Token validated successfully!")
            else:
                st.error("Please enter a valid token")

    st.markdown("---")
    cta_col = st.columns([1, 2, 1])[1]
    with cta_col:
        st.button(
            "🚀 Go to Download Page", 
            on_click=lambda: st.session_state.update({"selected": "Download Resume"}),
            disabled=st.session_state["render_token_bool"],
            help="Complete token validation to enable download"
        )

elif selected_page == "Download Resume":
    if st.session_state["render_token_bool"]:
        st.error("🔑 Valid renderToken required to proceed")
        st.toast("❌ RenderToken required", icon="⚠️")
    else:
        try:
            with st.spinner("✨ Crafting your professional resume..."):
                with hc.HyLoader('', hc.Loaders.pulse_bars()):
                    pdf_obj = ResumeioDownloader(rendering_token=st.session_state["render_token"])
                    pdf_data = pdf_obj.generate_pdf()
            
            st.markdown("""
            <div class='download-success'>
                <h3>✅ Resume Ready!</h3>
                <p>Your professionally formatted resume is prepared for download</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 Download Resume PDF",
                data=pdf_data,
                file_name=f'professional_resume_{datetime.now().strftime("%Y%m%d")}.pdf',
                mime='application/pdf'
            )
            
        except Exception as e:
            st.error(f"⚠️ Error generating resume: {str(e)}")
            st.toast("❌ Generation failed", icon="⚠️")

elif selected_page == "About":
    st.markdown("""
    <div class="guide-card">
        <h2 style='color: #2a2a72;'>About Resume IO</h2>
        <p style='line-height: 1.6;'>
            Professional resume generation tool with enhanced export capabilities.
            Maintains original formatting while providing seamless PDF conversion.
        </p>
        
        <h3 style='color: #2a2a72; margin-top: 1.5rem;'>Key Features</h3>
        <div style='display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: 1rem;'>
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <h4>🔒 Secure Processing</h4>
                <p>Token-based authentication ensures data privacy</p>
            </div>
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <h4>📄 Format Preservation</h4>
                <p>Maintains original resume layout and styling</p>
            </div>
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <h4>⚡ Instant Download</h4>
                <p>Generate and download PDFs in seconds</p>
            </div>
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <h4>🎯 Professional Output</h4>
                <p>Industry-standard PDF formatting</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
