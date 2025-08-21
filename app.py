import streamlit as st
from PIL import Image

# Page config
st.set_page_config(page_title="We’ve Moved!", page_icon="🚀", layout="centered")

# Optional: Add a logo if you have one
# logo = Image.open("logo.png")
# st.image(logo, width=120)

# Title & message
st.title("🚀 We’ve Migrated!")

st.markdown(
    """
    Thanks for visiting! 👋 
    
    We’ve moved away from Streamlit due to some limitations, and we’re excited to share our **new and improved platform** with you.
    
    👉 Please visit us at our new home: [**resumegenn.site**](https://www.resumegenn.site)
    
    We can’t wait for you to explore the upgraded experience! 💡
    """,
    unsafe_allow_html=True
)

# Button to redirect
if st.button("Go to resumegenn.site 🚀"):
    st.markdown("<meta http-equiv='refresh' content='0; url=https://www.resumegenn.site'>", unsafe_allow_html=True)

# Footer
st.write("---")
st.caption("Made with ❤️, now on our new platform ✨")
