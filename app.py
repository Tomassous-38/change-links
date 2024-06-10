import streamlit as st
import aiohttp
import asyncio
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from time import sleep

def extract_domain(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

async def fetch(session, url, allow_redirects=True):
    try:
        async with session.get(url, allow_redirects=allow_redirects) as response:
            return url, response.status, await response.text(), str(response.url)
    except Exception as e:
        return url, None, str(e), None

def get_all_links_from_domain(markdown_text, domain):
    links = set()
    images = set()
    link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
    for match in link_pattern.finditer(markdown_text):
        alt_text, url = match.groups()
        if extract_domain(url) == domain:
            if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg')):
                images.add(url)
            else:
                links.add(url)
    return links, images

async def get_alternate_urls(session, urls, domain, language_code, debug_messages, console_placeholder):
    tasks = []
    for url in urls:
        tasks.append(fetch(session, url))
    results = await asyncio.gather(*tasks)
    
    alternate_urls = {}
    for url, status, html, final_url in results:
        if status == 200:
            alternate_urls[url] = ""
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('link', rel='alternate'):
                hreflang = link.get('hreflang')
                href = link.get('href')
                if hreflang and href:
                    full_href = urljoin(url, href)
                    if hreflang == language_code and extract_domain(full_href) == domain:
                        alternate_urls[url] = full_href
                        break
            # Verify the alternate URL
            if alternate_urls[url]:
                _, final_status, _, final_url = await fetch(session, alternate_urls[url])
                if final_status == 200:
                    alternate_urls[url] = final_url
                elif final_status == 404:
                    alternate_urls[url] = ""
                    debug_messages.append(f"❌ Alternate URL not found (404): {alternate_urls[url]}")
                else:
                    alternate_urls[url] = ""
                    debug_messages.append(f"❌ Alternate URL invalid: {alternate_urls[url]}")
        else:
            alternate_urls[url] = None
        debug_messages.append(f"🔍 Fetched {url}: {status}")
        console_output = "\n".join(debug_messages)
        console_placeholder.markdown(f'<div class="console-output terminal">{console_output}</div>', unsafe_allow_html=True)
        await asyncio.sleep(0.2)  # Simulate typing effect
    return alternate_urls

async def update_links(markdown_text, domain, target_language_code, debug_messages, console_placeholder):
    all_links, images = get_all_links_from_domain(markdown_text, domain)
    
    debug_messages.append(f"🔗 Total {len(all_links)} links and {len(images)} images found in the markdown text.")
    console_output = "\n".join(debug_messages)
    console_placeholder.markdown(f'<div class="console-output terminal">{console_output}</div>', unsafe_allow_html=True)

    async with aiohttp.ClientSession() as session:
        valid_links = []
        tasks = [fetch(session, url) for url in all_links]
        results = await asyncio.gather(*tasks)
        for url, status, _, final_url in results:
            if status == 200:
                valid_links.append(url)

        alternate_urls = await get_alternate_urls(session, valid_links, domain, target_language_code, debug_messages, console_placeholder)
    
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
                    if alternate_url is not None:
                        line = line.replace(url, alternate_url if alternate_url else "")
                    else:
                        removed_links.append(url)
                        line = line.replace(f'[{url}]', '')
                        line = line.replace(url, '')
        updated_lines.append(line)
    
    updated_text = '\n'.join(updated_lines)
    updated_text = re.sub(r'\[\d+\]: http.*\n?', '', updated_text)
    return updated_text, removed_links, alternate_urls, images

st.set_page_config(page_title="Markdown Link Updater")

st.markdown(
    """
    <style>
    body {
        background-color: #2E2E2E;
        color: #FFFFFF;
        font-family: monospace;
        padding-top: 3rem;
    }
    .block-container {
        padding-top: 2rem;
    }
    .stButton button {
        color: #FFFFFF;
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
    .terminal {
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .console-output {
        font-family: monospace;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title('Markdown Link Updater')

markdown_text = st.text_area("Paste your markdown text here")
domain_input = st.text_input("Enter the domain (or any URL from the domain) to check")
target_language = st.text_input("Enter target language code (e.g., en, fr, it)")
debug = True

if st.button('Update Links'):
    if markdown_text and domain_input and target_language:
        domain = extract_domain(domain_input)
        debug_messages = ["👋 Hi there! Let's get started."]
        debug_messages.append(f"🔍 Extracted domain: {domain}")
        debug_messages.append("⏳ Starting link update process...")

        console_placeholder = st.empty()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        updated_markdown, removed_links, alternate_urls, images = loop.run_until_complete(update_links(markdown_text, domain, target_language, debug_messages, console_placeholder))
        loop.close()

        debug_messages.append("✅ Link update process completed!")

        st.success("Links updated! See the updated content below:")
        st.text_area("Updated Markdown", value=updated_markdown, height=400)

        if removed_links:
            debug_messages.append("🗑️ The following links were removed as they have no alternate version or returned a non-200 status code:")
            for link in removed_links:
                debug_messages.append(link)

        # Display final console output
        console_output = "\n".join(debug_messages)
        console_placeholder.markdown(f'<div class="console-output terminal">{console_output}</div>', unsafe_allow_html=True)

        # Display table of links and their alternatives
        st.markdown("### Links and their Alternatives")
        data = [{"Original Link": url, "Alternate Link": alt_url if alt_url else ""} for url, alt_url in alternate_urls.items()]
        st.table(data)
    else:
        st.error("Please paste your markdown text, enter a domain, and enter a target language code.")
