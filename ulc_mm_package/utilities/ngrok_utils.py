import os
import subprocess
import logging
from urllib.error import URLError
from urllib.request import urlopen
import json
from typing import Dict

from pyngrok import ngrok, conf

from ulc_mm_package.scope_constants import NGROK_AUTH_TOKEN_ENV_VAR

logger = logging.getLogger(__name__)


class NgrokError(Exception):
    pass


class AuthTokenNotSet(NgrokError):
    pass


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
        logger.info("Address unavailable - ngrok is not on.")


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


def _make_tcp_tunnel() -> ngrok.NgrokTunnel:
    """Attempt to create an ngrok tcp tunnel. Return an existing tunnel if one is already open.

    Returns
    -------
    pyngrok.NgrokTunnel:
        pyngrok object

    Exceptions
    ----------
    NgrokError:
        Unable to create the tunnel.
    """

    try:
        return ngrok.connect(22, "tcp")
    except ngrok.PyngrokError as e:
        raise NgrokError(e)


def _get_public_url_from_ngrok_tunnel_obj(tunnel_obj: ngrok.NgrokTunnel) -> str:
    """Ingest a pyngrok object and return the publicly accessible URL.

    Parameters
    ----------
    pyngrok.NgrokTunnel obj

    Returns
    -------
    str
    """
    return tunnel_obj.public_url


def _kill_old_ngrok_sessions() -> None:
    """Ensure any old ngrok tunnels are terminated.

    The free-tier account is limited to one active tunnel. Ensure that any stale
    sessions are terminated before a new one is made.

    Exceptions
    ----------
    None:
        Catch-all which logs the exception+traceback
    """

    try:
        # Redirect subprocess output to DEVNULL to avoid cluttering the console.
        subprocess.run(
            ["killall", "ngrok"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
    except Exception:
        logger.exception(f"Unknown failure when attempting to `killall ngrok`: {e}")


def make_tcp_tunnel() -> str:
    """Returns the publicly accessible ngrok ssh address.

    Returns
    -------
    str:
        Publicly accessible ngrok URL.

    Exceptions
    ----------
    NgrokError:
        Unable to create the ngrok tunnel.
    """

    try:
        # Check for existing ngrok tunnel
        if is_ngrok_running():
            addr = get_addr()
            return addr
        else:
            # Create a new tunnel
            try:
                _kill_old_ngrok_sessions()
                set_ngrok_auth_token()
                return _get_public_url_from_ngrok_tunnel_obj(_make_tcp_tunnel())
            except NgrokError:
                raise
    except:
        raise NgrokError(
            "NgrokError : existing ngrok tunnel detected but errored out during either is_ngrok_running() or get_addr()."
        )


def _get_ngrok_auth_token() -> str:
    """Get the ngrok token stored in the environment variable.

    Returns
    -------
    str
    """

    token = os.environ.get(NGROK_AUTH_TOKEN_ENV_VAR)
    if token is None:
        raise AuthTokenNotSet(
            f"{NGROK_AUTH_TOKEN_ENV_VAR} environment variable not set.\n"
            "You can set the ngrok token in the .bashrc file by:\n"
            "Open the file with: nano /home/pi/.bashrc\n"
            "then add the following line (without the '<' '>' signs) to the file:\n"
            "EXPORT NGROK_AUTH_TOKEN=<TOKEN_HERE>"
        )
    else:
        return token


def _set_ngrok_auth_token(token: str) -> None:
    """Set the ngrok token."""

    ngrok.set_auth_token(token)
    conf.get_default().auth_token = token


def set_ngrok_auth_token():
    """Attempt to set the ngrok token.

    Exceptions
    ----------
    NgrokError.AuthTokenNotSet
    """

    token = _get_ngrok_auth_token()
    _set_ngrok_auth_token(token)


if __name__ == "__main__":
    print(f"{make_tcp_tunnel()}")
    input("Press enter to exit and close the tunnel...")
