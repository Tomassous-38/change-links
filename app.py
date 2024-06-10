import streamlit as st
import aiohttp
import asyncio
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from time import sleep

def extract_domain(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc

async def fetch(session, url):
    try:
        async with session.get(url) as response:
            return url, response.status, await response.text()
    except Exception as e:
        return url, None, str(e)

async def check_urls(urls):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            tasks.append(fetch(session, url))
        results = await asyncio.gather(*tasks)
    return results

def get_all_links_from_domain(markdown_text, domain):
    links = set()
    link_pattern = re.compile(r'\[.*?\]\((https?://[^\s)]+)\)')
    for match in link_pattern.finditer(markdown_text):
        url = match.group(1)
        if domain in url:
            links.add(url)
    return links

async def get_alternate_urls(session, urls, language_code, debug):
    tasks = []
    for url in urls:
        tasks.append(fetch(session, url))
    results = await asyncio.gather(*tasks)
    
    alternate_urls = {}
    for url, status, html in results:
        if status == 200:
            alternate_urls[url] = None
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('link', rel='alternate'):
                hreflang = link.get('hreflang')
                href = link.get('href')
                if hreflang and href:
                    if hreflang == language_code:
                        alternate_urls[url] = href
                        break
        if debug:
            st.write(f"Fetched {url}: {status}")
    return alternate_urls

async def update_links(markdown_text, domain, target_language_code, debug):
    all_links = get_all_links_from_domain(markdown_text, domain)
    
    if debug:
        st.write(f"Total {len(all_links)} links found in the markdown text.")

    async with aiohttp.ClientSession() as session:
        valid_links = []
        tasks = [fetch(session, url) for url in all_links]
        results = await asyncio.gather(*tasks)
        for url, status, _ in results:
            if status == 200:
                valid_links.append(url)

        alternate_urls = await get_alternate_urls(session, valid_links, target_language_code, debug)
    
    updated_lines = []
    removed_links = []
    for line in markdown_text.split('\n'):
        for url in all_links:
            if url in line:
                if url in removed_links:
                    line = line.replace(f'[{url}]', '')
                    line = line.replace(url, '')
                else:
                    alternate_url = alternate_urls.get(url)
                    if alternate_url:
                        line = line.replace(url, alternate_url)
                    else:
                        removed_links.append(url)
                        line = line.replace(f'[{url}]', '')
                        line = line.replace(url, '')
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

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        updated_markdown, removed_links = loop.run_until_complete(update_links(markdown_text, domain, target_language, debug))
        loop.close()

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
