import os
import tempfile
from pathlib import Path
import logging
import requests
import base64

from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _read_local_file(path, mode="rb"):
    """Internal helper to read a local file given file://path"""
    local_path = path.replace("file://", "", 1)
    if not os.path.exists(local_path):
        raise Exception(f"file not found! {path}")

    try:
        with open(local_path, mode) as f:
            return f.read()
    except Exception:
        return None


def download_file_as_byte(url):
    if url.startswith("file://"):
        return _read_local_file(url, mode="rb")

    return download_from_url_with_retry(url)


@retry(
    wait=wait_exponential(min=4, max=16),
    stop=stop_after_attempt(8),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def download_from_url_with_retry(url):
    # Handle HTTP/HTTPS
    logger.info(f"Downloading file from URL: {url}")
    response = requests.get(url)
    response.raise_for_status()

    return response.content


def download_file_as_base64(url):
    # Handle local file
    if url.startswith("file://"):
        content = _read_local_file(url, mode="rb")
        if content is None:
            return None
        return base64.b64encode(content).decode("utf-8")

    content = download_from_url_with_retry(url)
    encoded = base64.b64encode(content).decode("utf-8")
    return encoded


def download_file_as_text(url, encoding="utf-8"):
    # Handle local file
    if url.startswith("file://"):
        content = _read_local_file(url, mode="rb")
        if content is None:
            return None
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            return None

    # Handle HTTP/HTTPS
    response = requests.get(url)
    if response.status_code != 200:
        return None
    try:
        return response.content.decode(encoding)
    except UnicodeDecodeError:
        return None


def download_to_temp(url) -> str:
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Error downloading file {url}")

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(url).suffix
    ) as temp_file:
        temp_file.write(response.content)
        # Get the temporary file path
        return temp_file.name
