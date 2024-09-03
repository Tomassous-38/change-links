import streamlit as st
import aiohttp
import asyncio
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time

MAX_CONCURRENT_REQUESTS = 20

def normalize_domain(domain):
    if not domain.startswith('http://') and not domain.startswith('https://'):
        domain = 'https://' + domain
    parsed_url = urlparse(domain)
    return parsed_url.netloc

def is_same_domain(url, domain):
    parsed_url = urlparse(url)
    return parsed_url.netloc.endswith(domain)

def get_all_links_from_markdown(markdown_text):
    link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
    return [match.group(2) for match in link_pattern.finditer(markdown_text)]

async def fetch(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            return url, response.status, str(response.url), await response.text()
    except Exception as e:
        return url, None, None, str(e)

async def process_link(session, url, domain, target_language, semaphore):
    async with semaphore:
        original_url, status, final_url, html = await fetch(session, url)
        if status == 200 and is_same_domain(final_url, domain):
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('link', rel='alternate'):
                if link.get('hreflang') == target_language:
                    return original_url, urljoin(final_url, link.get('href'))
    return original_url, None

async def update_links(markdown_text, domain, target_language):
    all_links = get_all_links_from_markdown(markdown_text)
    domain_links = [link for link in all_links if is_same_domain(link, domain)]
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession() as session:
        tasks = [process_link(session, url, domain, target_language, semaphore) for url in domain_links]
        results = await asyncio.gather(*tasks)
    
    alternate_urls = {original: alternate for original, alternate in results if alternate}
    
    for original, alternate in alternate_urls.items():
        markdown_text = markdown_text.replace(original, alternate)
    
    return markdown_text, alternate_urls

st.set_page_config(page_title="Markdown Link Updater", layout="wide")

st.title('Markdown Link Updater')

markdown_text = st.text_area("Paste your markdown text here", height=300)
domain_input = st.text_input("Enter the domain (e.g., example.com)")
target_language = st.text_input("Enter target language code (e.g., en, fr, it)")

if st.button('Update Links'):
    if markdown_text and domain_input and target_language:
        domain = normalize_domain(domain_input)
        
        with st.spinner('Updating links...'):
            try:
                start_time = time.time()
                updated_markdown, alternate_urls = asyncio.run(update_links(markdown_text, domain, target_language))
                end_time = time.time()

                st.success(f"Links updated in {end_time - start_time:.2f} seconds!")

                st.subheader("Updated Markdown")
                st.text_area("", value=updated_markdown, height=300)

                st.subheader("Results Summary")
                st.metric("Updated Links", len(alternate_urls))

                if alternate_urls:
                    st.subheader("Updated Links")
                    st.table({"Original Link": alternate_urls.keys(), "New Link": alternate_urls.values()})

                st.download_button(
                    label="Download Updated Markdown",
                    data=updated_markdown,
                    file_name="updated_markdown.md",
                    mime="text/markdown"
                )

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
    else:
        st.error("Please fill in all fields before updating links.")
