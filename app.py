import streamlit as st
from streamlit_navigation_bar import st_navbar
from streamlit_extras.row import row
import hydralit_components as hc
from parser.PdfEngine import ApplicationRunner

st.set_page_config(layout="wide", page_icon="images/icon.png", page_title="Resume IO")

def handle_click(page):
    st.session_state["selected"] = page

if "render_token" not in st.session_state:
    st.session_state["render_token"] = ""
if "render_token_bool" not in st.session_state:
    st.session_state["render_token_bool"] = True

pages = ["Home", "Download Resume", "About"]
style = {
    "nav": {
        "background-color": "#2c3e50", 
        "display": "flex",
        "justify-content": "left",
        "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.1)"  
    },
    "div": {
        "max-width": "auto",
    },
    "span": {
        "border-radius": "0.5rem",
        "color": "#ecf0f1",
        "padding": "0.75rem 1rem", 
        "font-family": "Arial, sans-serif",
        "transition": "background-color 0.3s ease"
    },
    "active": {
        "background-color": "rgba(255, 255, 255, 0.2)",
    },
    "hover": {
        "background-color": "rgba(255, 255, 255, 0.1)",
    },
}
options = {
    "show_menu": False,
    "show_sidebar": False,
    "use_padding": False
}

page = st_navbar(pages, styles=style, options=options, key="selected")

if page == "Home":
    st.subheader("How to download your resume.")
    st.write("""
        To fetch your resume from resume.io, you need to get your `rendering token` from https://resume.io/api/app/resumes 
    """)
    with st.expander(label="How to get renderToken", expanded=False):
        st.image("images/copytoken.jpg", width=500, caption="Copying rendering token")
    rows = row([0.7, 0.3], gap="large", vertical_align="center")
    with rows.container():
        render_token = st.text_input(
            label="Enter copied renderToken here", 
            placeholder="Paste renderToken here...", 
            label_visibility="collapsed"
        )
        st.session_state["render_token"] = render_token
    with rows.container():
        if st.button(label="Submit"):
            if st.session_state["render_token"]:
                st.session_state["render_token_bool"] = False
            else:
                st.error("renderToken required to proceed.")
                st.session_state["render_token_bool"] = True
    st.write("After copying render token. Proceed to download page.")
    st.button("Go to Download Resume", on_click=handle_click, args=["Download Resume"], disabled=st.session_state["render_token_bool"])

    st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; font-family: 'Arial', sans-serif; }
    .stTitle, .stHeader, .stSubheader { color: #4a90e2; }
    .stButton button {
      background-color: #4a90e2; color: white; border: none; padding: 10px 20px; text-align: center;
      text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer;
      border-radius: 12px; transition-duration: 0.4s;
    }
    .stButton button:hover {
      background-color: white; color: #4a90e2; border: 2px solid #4a90e2;
    }
    .stTextInput input {
      background-color: #ffffff; color: #4a90e2; border: 2px solid #4a90e2;
      padding: 10px; font-size: 16px; border-radius: 12px; transition-duration: 0.4s;
    }
    .stTextInput input:focus {
      border-color: #4a90e2; box-shadow: 0 0 5px #4a90e2;
    }
    </style>
    """, unsafe_allow_html=True)

if page == "Download Resume":
    if st.session_state["render_token_bool"]:
        st.toast(":red[renderToken required to proceed.]", icon=":material/error:")
        st.error("renderToken required to proceed.")
    else:
        try:
            st.markdown("Let's do the magic for you...")
            with hc.HyLoader('Creating your document...', hc.Loaders.standard_loaders, index=[3]):
                app_runner = ApplicationRunner()
                pdf_bytes = app_runner.execute_document_conversion(token=str(st.session_state["render_token"]).strip())
                st.write(str(st.session_state["render_token"]).strip())
                if pdf_bytes is None:
                    st.error("PDF generation failed. Please check if your render token is correct or try again.")
                else:
                    st.download_button(
                        label="Download PDF file",
                        file_name=f'{st.session_state["render_token"]}_resume.pdf',
                        data=pdf_bytes,
                        mime="application/pdf"
                    )
                    st.info("Done generating resume. You can download it now.", icon=":material/file_save:")
                    st.toast("Resume generated successfully!", icon=":material/check_circle:")
            st.markdown("""
            <style>
            .stApp { background-color: #f0f2f6; font-family: 'Arial', sans-serif; }
            .stTitle, .stHeader, .stSubheader { color: #4a90e2; }
            a {
                background-color: #4a90e2; color: white; border: none; padding: 10px 20px;
                text-align: center; text-decoration: none; display: inline-block; font-size: 16px;
                margin: 4px 2px; cursor: pointer; border-radius: 12px; transition-duration: 0.4s;
            }
            a:hover {
                background-color: white; color: #4a90e2; border: 2px solid #4a90e2;
            }
            </style>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Please check if `renderToken` is correct: {e}", icon=":material/warning:")
            st.toast("Please check if `renderToken` is correct", icon=":material/error:")

if page == "About":
    st.info("Not yet implemented", icon=":material/warning:")