import streamlit as st
import requests
import re
from urllib.parse import urlparse
from time import sleep
from bs4 import BeautifulSoup

def extract_domain(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc

def check_url(url):
    try:
        response = requests.get(url)
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_all_links_from_domain(url, domain, debug):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        if debug:
            st.write(f"Gathering all links from domain: {domain}")

        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for link in soup.find_all('a', href=True):
            href = link['href']
            if domain in href:
                links.add(href)

        if debug:
            st.write(f"Found {len(links)} links from the domain {domain}")

        return links
    except requests.RequestException as e:
        if debug:
            st.error(f'Error fetching URL: {e}')
        return set()

def get_alternate_url(url, language_code, debug):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        if debug:
            st.write(f"Fetching alternates for: {url}")

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

        alternate_url = alternate_urls.get(language_code)
        if debug:
            st.write(f"Alternate URL found: {alternate_url}" if alternate_url else "No alternate URL found.")
        return alternate_url
    except requests.RequestException as e:
        if debug:
            st.error(f'Error fetching URL: {e}')
        return None

def update_links(markdown_text, domain, target_language_code, debug):
    all_links = set()
    lines = markdown_text.split('\n')
    for line in lines:
        if '](http' in line:
            start_idx = line.find('](http') + 2
            end_idx = line.find(')', start_idx)
            url = line[start_idx:end_idx]
            if domain in url:
                all_links.add(url)
    
    if debug:
        st.write(f"Total {len(all_links)} links found in the markdown text.")

    updated_lines = []
    removed_links = []
    for url in all_links:
        sleep(1)  # Delay to avoid being blocked by the server
        if check_url(url):
            alternate_url = get_alternate_url(url, target_language_code, debug)
            if not alternate_url:
                removed_links.append(url)
        else:
            removed_links.append(url)
    
    for line in lines:
        if '](http' in line:
            start_idx = line.find('](http') + 2
            end_idx = line.find(')', start_idx)
            url = line[start_idx:end_idx]
            if url in removed_links:
                line = line.replace(f'[{url}]', '')
                line = line.replace(url, '')
            elif domain in url:
                alternate_url = get_alternate_url(url, target_language_code, debug)
                if alternate_url:
                    line = line.replace(url, alternate_url)
        updated_lines.append(line)
    
    updated_text = '\n'.join(updated_lines)
    updated_text = re.sub(r'\[\d+\]: http.*\n?', '', updated_text)
    return updated_text, removed_links

st.set_page_config(page_title="Markdown Link Updater")

st.title('Markdown Link Updater')

st.markdown(
    """
    <style>
    .stButton button {
        color: white;
        background-color: #007BFF;
        border-color: #007BFF;
        border-radius: 5px;
        padding: 10px 20px;
        font-size: 16px;
    }
    .stButton button:hover {
        background-color: #0056b3;
        border-color: #0056b3;
    }
    </style>
    """,
    unsafe_allow_html=True
)

markdown_text = st.text_area("Paste your markdown text here")
domain_input = st.text_input("Enter the domain (or any URL from the domain) to check")
target_language = st.text_input("Enter target language code (e.g., en, fr, it)")
debug = st.checkbox("Debug mode")

col1, col2 = st.columns(2)

with col1:
    if st.button('Paste from Clipboard'):
        st.experimental_set_query_params()
        markdown_text = st.experimental_get_query_params().get("text", [""])[0]

with col2:
    if st.button('Copy to Clipboard'):
        st.experimental_set_query_params(text=markdown_text)

if st.button('Update Links'):
    if markdown_text and domain_input and target_language:
        domain = extract_domain(domain_input)
        if debug:
            st.write(f"Extracted domain: {domain}")

        if debug:
            st.write("Starting link update process...")

        updated_markdown, removed_links = update_links(markdown_text, domain, target_language, debug)

        if debug:
            st.write("Link update process completed.")

        st.success("Links updated! See the updated content below:")
        st.text_area("Updated Markdown", value=updated_markdown, height=400)

        if removed_links:
            st.warning("The following links were removed as they have no alternate version or returned a non-200 status code:")
            for link in removed_links:
                st.write(link)
    else:
        st.error("Please paste your markdown text, enter a domain, and enter a target language code.")
