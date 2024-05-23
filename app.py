import streamlit as st
import requests
import re

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

def update_links(markdown_text, target_language_code):
    lines = markdown_text.split('\n')
    updated_lines = []
    for line in lines:
        if '](http' in line:
            start_idx = line.find('](http') + 2
            end_idx = line.find(')', start_idx)
            url = line[start_idx:end_idx]
            if 'emrahcinik.com' in url:
                alternate_url = get_alternate_url(url, target_language_code)
                if alternate_url:
                    line = line.replace(url, alternate_url)
        updated_lines.append(line)
    updated_text = '\n'.join(updated_lines)
    updated_text = re.sub(r'\[\d+\]: http.*\n?', '', updated_text)
    return updated_text

st.title('Markdown Link Updater')
markdown_text = st.text_area("Paste your markdown text here")
target_language = st.text_input("Enter target language code (e.g., en, fr, it)")

if st.button('Update Links'):
    if markdown_text and target_language:
        updated_markdown = update_links(markdown_text, target_language)
        
        st.success("Links updated! See the updated content below:")
        st.text_area("Updated Markdown", value=updated_markdown, height=400)
    else:
        st.error("Please paste your markdown text and enter a target language code.")
