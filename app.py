import streamlit as st
import requests
from docx import Document
from io import BytesIO

def get_alternate_url(url, language_code):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        alternate_urls = {}
        start_idx = 0

        while True:
            link_start = html.find('<link', start_idx)
            if link_start == -1:
                break
            link_end = html.find('>', link_start)
            if link_end == -1:
                break
            link_tag = html[link_start:link_end + 1]
            start_idx = link_end + 1

            if 'rel="alternate"' in link_tag:
                hreflang_start = link_tag.find('hreflang="')
                if hreflang_start != -1:
                    hreflang_start += len('hreflang="')
                    hreflang_end = link_tag.find('"', hreflang_start)
                    hreflang = link_tag[hreflang_start:hreflang_end]

                    href_start = link_tag.find('href="')
                    if href_start != -1:
                        href_start += len('href="')
                        href_end = link_tag.find('"', href_start)
                        href = link_tag[href_start:href_end]

                        alternate_urls[hreflang] = href

        return alternate_urls.get(language_code)
    except requests.RequestException as e:
        st.error(f'Error fetching URL: {e}')
        return None

def update_hyperlinks(doc, target_language_code):
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype:
            url = rel.target_ref
            if 'emrahcinik.com' in url:
                alternate_url = get_alternate_url(url, target_language_code)
                if alternate_url:
                    rel.target_ref = alternate_url
    return doc

st.title('Document Link Updater')
uploaded_file = st.file_uploader("Upload a .docx file", type="docx")
target_language = st.text_input("Enter target language code (e.g., en, fr, it)")

if st.button('Update Links'):
    if uploaded_file and target_language:
        doc_path = f"uploaded_{uploaded_file.name}"
        with open(doc_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        doc = Document(doc_path)
        updated_doc = update_hyperlinks(doc, target_language)
        updated_doc_path = f"updated_{uploaded_file.name}"
        updated_doc.save(updated_doc_path)
        
        with open(updated_doc_path, "rb") as f:
            btn = st.download_button(
                label="Download updated file",
                data=f,
                file_name=updated_doc_path
            )
    else:
        st.error("Please upload a file and enter a target language code.")

