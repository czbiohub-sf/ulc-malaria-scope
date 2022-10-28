from typing import Dict
from urllib.error import URLError
from urllib.request import urlopen
import json


def _get_ngrok_json() -> Dict:
    """Calls the ngrok localhost status page and returns the status dictionary.

    Returns
    -------
    Dict:
        Dictionary of ngrok status

    Exceptions
    ----------
    URLError:
        If ngrok is not running, there will be nothing at this URL.
    """

    addr = "http://127.0.0.1:4040/api/tunnels"
    try:
        content = urlopen(addr).read().decode("utf-8")
        return json.loads(content)
    except URLError:
        print("Address unavailable - ngrok is not on.")


def is_ngrok_running() -> bool:
    """Check whether ngrok is running.

    Returns
    -------
    bool:
        Is ngrok running
    """

    addr = "http://127.0.0.1:4040/api/tunnels"
    try:
        _ = urlopen(addr).read().decode("utf-8")
        return True
    except URLError:
        return False


def _get_addr_from_json(json_dict: Dict):
    """Get the public_url from the json."""

    return json_dict["tunnels"][0]["public_url"]


def get_addr() -> str:
    """Get the public accessible ngrok URL.

    Note:
    The user should first check that ngrok is running (`is_ngrok_running()`)

    Returns
    -------
    str:
        ngrok public url
    """

    ngrok_json = _get_ngrok_json()
    return _get_addr_from_json(ngrok_json)
