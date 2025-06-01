import os
import tempfile

import gradio as gr
import requests

from .file_to_text import file_to_text


def url_to_text(url: str) -> str:
    """ Download the webpage from the URL and convert to markdown text. """
    with tempfile.TemporaryDirectory() as tmpdirname:
        response = requests.get(url)
        html_file_path = os.path.join(tmpdirname, 'page.html')
        with open(html_file_path, 'w', encoding='utf-8') as html_file:
            html_file.write(response.text)
        return file_to_text(html_file_path)

def is_firecrawl_available():
    return os.environ.get("FIRECRAWL_API_BASE", "https://api.firecrawl.dev").rstrip("/") != "https://api.firecrawl.dev" or os.environ.get("FIRECRAWL_API_KEY")

def firecrawl_url_to_text(url: str) -> str:
    """ Use FireCrawl to download and convert webpage to markdown text. """
    headers = {'Content-Type': 'application/json'}
    if os.environ.get("FIRECRAWL_API_KEY"):
        headers['Authorization'] = f'Bearer {os.environ["FIRECRAWL_API_KEY"]}'
    data = {
        "url": url,
        "formats": ["markdown"]
    }
    response = requests.post(os.environ.get("FIRECRAWL_API_BASE", "https://api.firecrawl.dev").rstrip("/") + "/v1/scrape", headers=headers, json=data)
    response_json = response.json()
    if "error" in response_json:
        raise gr.Error(response_json["error"])
    return response.json()['data']['markdown']
