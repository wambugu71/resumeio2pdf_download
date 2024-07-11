import  streamlit as  st
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
import  hydralit_components as  hc
st.set_page_config(layout="wide", page_icon="icon.png", page_title="Resume IO")

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
        """Set the cache date to the current time."""
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
        content = json.loads(response.text)
        self.metadata = content.get("pages")

    def __download_images(self) -> list[io.BytesIO]:
        images = []
        for page_id in range(1, 1 + len(self.metadata)):
            image_url = self.IMAGES_URL.format(
                rendering_token=self.rendering_token,
                page_id=page_id,
                extension=self.extension,
                cache_date=self.cache_date,
                image_size=self.image_size,
            )
            image = self.__download_image_from_url(image_url)
            images.append(image)

        return images

    def __download_image_from_url(self, url) -> io.BytesIO:
        response = requests.get(url)
        self.__raise_for_status(response)
        return io.BytesIO(response.content)

    def __raise_for_status(self, response) -> None:
        if response.status_code != 200:
            raise Exception(
                status_code=response.status_code,
                detail=f"Unable to download resume (rendering token: {self.rendering_token})",
            )
def handle_click(page):
    st.session_state["selected"] = page

if  "render_token" not in st.session_state:
    st.session_state["render_token"]  = None
if  "render_token_bool" not  in st.session_state:
    st.session_state["render_token_bool"] = True
    
pages = ["Home", "Download Resume", "About"]
style = {
    "nav": {
        "background-color": "#2c3e50", 
        "display": "flex",
        "justify-content": "left",
        #"padding": "auto",
        "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.1)"  
    },
    "div": {
        "max-width": "auto",  # Increased max-width for larger screens
       # "margin": "0 auto"  # Centers the container
    },
    "span": {
        "border-radius": "0.5rem",
        "color": "#ecf0f1",  # Light text color for contrast
        #"margin": "0 auto",  # More margin for better spacing
       "padding": "0.75rem 1rem", 
        "font-family": "Arial, sans-serif",  # Modern font
        #"font-size": "1rem",  # Slightly larger font size
        "transition": "background-color 0.3s ease"  # Smooth transition for hover and active states
    },
    "active": {
        "background-color": "rgba(255, 255, 255, 0.2)",  # Slightly darker for active state
    },
    "hover": {
        "background-color": "rgba(255, 255, 255, 0.1)",  # Subtle hover effect
    },
}
options = {
    "show_menu": False,
    "show_sidebar": False,
    "use_padding": False
    
}
page = st_navbar(pages, styles=style, options=options, key="selected")
if page =="Home":
    # Add a subheader
    st.subheader("How to download  your  resume.")
    # Add some text
    st.write("""
             To fetch your  resume  from  resume.io, you need to get  your  `rendering token` from https://resume.io/api/app/resumes 
    """)
    # Add some more text

    # Add an image
    with st.expander(label="How to get renderToken", expanded=False):
        st.image("copytoken.jpg",width=500, caption="Copying rendring token")
    # Add a footer
    rows = row([0.7, 0.3],gap="large", vertical_align= "center")
    with rows.container():
        st.session_state["render_token"] = render_token = st.text_input(label="Enter  copied  renderToken here", placeholder="Paste renderToken here...", label_visibility="collapsed")
    with rows.container():
        if st.session_state["render_token"] != None  and st.button(label="Submit") and  st.session_state["render_token"] != "":
            st.session_state["render_token_bool"] = False
        else:
            st.error("renderToken required to proceed.")
            st.session_state["render_token_bool"] = True
    st.write("After copying  render token. Proceed to download  page.")
    st.button("Go to Download Resume", on_click=handle_click, args=["Download Resume"], disabled=st.session_state["render_token_bool"])
    # Add some styling
    st.markdown("""
    <style>
    .stApp {
        background-color: #f0f2f6;
        font-family: 'Arial', sans-serif;
    }
    .stTitle {
        color: #4a90e2;
    }
    .stHeader {
        color: #4a90e2;
    }
    .stSubheader {
        color: #4a90e2;
    }
    .stButton button {
      background-color: #4a90e2;
      color: white;
      border: none;
      padding: 10px 20px;
      text-align: center;
      text-decoration: none;
      display: inline-block;
      font-size: 16px;
      margin: 4px 2px;
      cursor: pointer;
      border-radius: 12px;
      transition-duration: 0.4s;
  }
  .stButton button:hover {
      background-color: white;
      color: #4a90e2;
      border: 2px solid #4a90e2;
  }
    .stTextInput input {
      background-color: #ffffff;
      color: #4a90e2;
      border: 2px solid #4a90e2;
      padding: 10px;
      font-size: 16px;
      border-radius: 12px;
      transition-duration: 0.4s;
  }
  .stTextInput input:focus {
      border-color: #4a90e2;
      box-shadow: 0 0 5px #4a90e2;
  }
    </style>
    """, unsafe_allow_html=True)

if  page == "Download Resume":
    if   st.session_state["render_token_bool"] == True:
        st.toast(":red[renderToken required to proceed.]", icon=":material/error:",)
        st.error("renderToken required to proceed.")
    else:
        try:
            st.markdown("Let's do the  magic  for  you...")
            with hc.HyLoader('Creating  your  document',hc.Loaders.standard_loaders, index=[3]):
                pdf_obj    = ResumeioDownloader(rendering_token=st.session_state["render_token"])
                st.download_button(label="Download  pdf file", file_name=f'{st.session_state["render_token"]}_resume.pdf', data=pdf_obj.generate_pdf())
                st.info("Done generating  resume. You can  download  it  now.", icon=":material/file_save:")
                st.toast("Resume generated  succesfully!", icon=":material/check_circle:")
            st.markdown("""
    <style>
    .stApp {
        background-color: #f0f2f6;
        font-family: 'Arial', sans-serif;
    }
    .stTitle {
        color: #4a90e2;
    }
    .stHeader {
        color: #4a90e2;
    }
    .stSubheader {
        color: #4a90e2;
    }
    a {
        background-color: #4a90e2;
        color: white;
        border: none;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 12px;
        transition-duration: 0.4s;
    }
    a:hover {
        background-color: white;
        color: #4a90e2;
        border: 2px solid #4a90e2;
    }
    </style>
    """, unsafe_allow_html=True)
        except:
            st.error("Please check if `renderToken` is  correct", icon=":material/warning:")
            st.toast("Please check if  `renderToken` is  correct", icon=":material/error:")
if  page == "About":
    st.info("Not  yet  implimented", icon=":material/warning:")
