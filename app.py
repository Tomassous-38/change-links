import streamlit as st
import aiohttp
import asyncio
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time
import json

MAX_REDIRECTS = 4
MAX_CONCURRENT_REQUESTS = 10

def normalize_domain(domain):
    if not domain.startswith('http://') and not domain.startswith('https://'):
        domain = 'https://' + domain
    parsed_url = urlparse(domain)
    return parsed_url.netloc

def is_same_domain(url, domain):
    parsed_url = urlparse(url)
    domain_parts = domain.split('.')
    url_parts = parsed_url.netloc.split('.')
    return url_parts[-len(domain_parts):] == domain_parts

async def fetch(session, url, allow_redirects=True, max_redirects=MAX_REDIRECTS):
    try:
        async with session.get(url, allow_redirects=allow_redirects, timeout=10) as response:
            if response.status == 301 and max_redirects > 0:
                new_url = response.headers.get('Location')
                if new_url:
                    return await fetch(session, new_url, allow_redirects=allow_redirects, max_redirects=max_redirects - 1)
            return url, response.status, str(response.url), await response.text()
    except asyncio.TimeoutError:
        return url, 408, None, "Request timed out"
    except Exception as e:
        return url, None, None, str(e)

def get_all_links_from_domain(markdown_text, domain):
    links = set()
    link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
    for match in link_pattern.finditer(markdown_text):
        alt_text, url = match.groups()
        if is_same_domain(url, domain) and not url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg')):
            links.add(url)
    return links

async def process_links(session, urls, language_code, progress_bar):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async def process_url(url):
        async with semaphore:
            status, final_url, html = await fetch(session, url)
            alternate_url = None
            if status == 200:
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('link', rel='alternate'):
                    if link.get('hreflang') == language_code:
                        alternate_url = urljoin(final_url, link.get('href'))
                        break
            progress_bar.progress(progress_bar.progress() + 1 / len(urls))
            return url, status, final_url, alternate_url

    tasks = [process_url(url) for url in urls]
    return await asyncio.gather(*tasks)

async def update_links(markdown_text, domain, target_language_code):
    all_links = get_all_links_from_domain(markdown_text, domain)
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    async with aiohttp.ClientSession() as session:
        results = await process_links(session, all_links, target_language_code, progress_bar)

    final_alternate_urls = {url: alt_url for url, status, final_url, alt_url in results if alt_url}
    removed_links = [url for url, status, final_url, alt_url in results if status != 200 or not alt_url]

    updated_lines = []
    for line in markdown_text.split('\n'):
        for url in all_links:
            if url in line:
                alternate_url = final_alternate_urls.get(url)
                if alternate_url:
                    line = re.sub(re.escape(url), alternate_url, line)
                elif url in removed_links:
                    line = line.replace(f'[{url}]', '')
                    line = line.replace(url, '')
        updated_lines.append(line)
    
    updated_text = '\n'.join(updated_lines)
    updated_text = re.sub(r'\[\d+\]: http.*\n?', '', updated_text)

    progress_bar.empty()
    status_text.success("Link update process completed!")

    return updated_text, removed_links, final_alternate_urls

st.set_page_config(page_title="Markdown Link Updater", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .stButton button {
        width: 100%;
    }
    .help-text {
        font-size: 0.8em;
        color: #888;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title('Markdown Link Updater')

col1, col2 = st.columns(2)

with col1:
    markdown_text = st.text_area("Paste your markdown text here", height=300)
    st.markdown('<p class="help-text">Enter the markdown content containing the links you want to update.</p>', unsafe_allow_html=True)

with col2:
    domain_input = st.text_input("Enter the domain")
    st.markdown('<p class="help-text">Enter the domain of the website you\'re updating links for (e.g., example.com).</p>', unsafe_allow_html=True)

    target_language = st.text_input("Enter target language code")
    st.markdown('<p class="help-text">Enter the two-letter language code for the target language (e.g., en, fr, it).</p>', unsafe_allow_html=True)

if st.button('Update Links'):
    if markdown_text and domain_input and target_language:
        domain = normalize_domain(domain_input)
        
        try:
            start_time = time.time()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            updated_markdown, removed_links, final_alternate_urls = loop.run_until_complete(update_links(markdown_text, domain, target_language))
            loop.close()
            end_time = time.time()

            st.success(f"Links updated in {end_time - start_time:.2f} seconds!")

            st.subheader("Updated Markdown")
            st.text_area("", value=updated_markdown, height=300)

            st.subheader("Results Summary")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Links", len(final_alternate_urls) + len(removed_links))
            col2.metric("Updated Links", len(final_alternate_urls))
            col3.metric("Removed Links", len(removed_links))

            if final_alternate_urls:
                st.subheader("Updated Links")
                st.table({"Original Link": final_alternate_urls.keys(), "New Link": final_alternate_urls.values()})

            if removed_links:
                st.subheader("Removed Links")
                st.write(", ".join(removed_links))

            st.download_button(
                label="Download Updated Markdown",
                data=updated_markdown,
                file_name="updated_markdown.md",
                mime="text/markdown"
            )

            st.download_button(
                label="Download Results as JSON",
                data=json.dumps({"updated_links": final_alternate_urls, "removed_links": removed_links}, indent=2),
                file_name="link_update_results.json",
                mime="application/json"
            )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
    else:
        st.error("Please fill in all fields before updating links.")
