import os
import logging
from datetime import datetime
import smtplib
import email.message
import socket

from ulc_mm_package.scope_constants import EMAIL_PW_TOKEN
from ulc_mm_package.utilities.ngrok_utils import make_tcp_tunnel, NgrokError


DEFAULT_EMAIL_LINE = (
    "A million miles away and it's you who has the key to my tcp tunnel <3"  # Default
)
DATE_FMT = "%Y-%m-%d"

logger = logging.getLogger(__name__)


class EmailError(Exception):
    pass


class EmailPWNotSet(Exception):
    pass


def send_email(sender: str, receiver: str, subject: str, payload: str) -> None:
    """Send an email

    Parameters
    ----------

    Exceptions
    ----------
    EmailError - EmailPWNotSet
        Raised if the GMAIL_TOKEN environment variable is not set in /home/pi/.bashrc
    """

    # Set up email object
    msg = email.message.EmailMessage()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.add_header("Content-Type", "text")
    msg.set_content(payload)

    # creates SMTP session, start TLS
    s = smtplib.SMTP("smtp.gmail.com", 587)
    s.starttls()

    # Authentication
    try:
        token = _get_pw()
        s.login(sender, token)
    except EmailError:
        raise

    s.send_message(msg)


def send_ngrok_email(
    sender: str = "lfmscope@gmail.com",
    receiver: str = "lfmscope@gmail.com",
) -> None:
    """Send an email with the ngrok address.

    Parameters
    ----------
    sender: str
        Sending email
    receiver: str
        Receipient email

    Exceptions
    ----------
    NgrokError:
        Raised if there's an issue creating/returning the ngrok address.
    """

    try:
        ngrok_addr: str = make_tcp_tunnel()
    except NgrokError:
        raise
    scope_name = _get_scope_name()
    subject = f"{scope_name} - {ngrok_addr}"
    curr_time = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    msg = (
        f"Current time: {curr_time}\n"
        f"Scope : {scope_name}\n"
        f"ngrok address : {ngrok_addr}\n"
        f"{_load_saga()}"
    )
    send_email(sender, receiver, subject, msg)


def _get_pw() -> str:
    """
    Get the gmail device-specific password stored in the environment variables.

    Returns
    -------
    str
    """

    pw = os.environ.get(EMAIL_PW_TOKEN)
    if pw == None:
        raise EmailError(
            f"{EMAIL_PW_TOKEN} environment variable not set.\n"
            "You can set the ngrok token in the .bashrc file by:\n"
            "Open the file with: nano /home/pi/.bashrc\n"
            "then add the following line (without the '<' '>' signs) to the file:\n"
            "EXPORT NGROK_AUTH_TOKEN=<TOKEN_HERE>"
        )
    return pw


def _get_scope_name() -> str:
    """Return the hostname (i.e lfm-ohmu)"""

    return socket.gethostname()


def _parse_date_str(datetime_str: str, fmt: str = DATE_FMT):
    return datetime.strptime(datetime_str, fmt)


def _get_days_since_inception(reset: bool = False) -> int:
    if reset:
        start_date = os.environ.get("INCEPTION", datetime.now().strftime(DATE_FMT))
        os.environ["INCEPTION"] = datetime.now().strftime(DATE_FMT)
        return 0
    else:
        start_date = os.environ.get("INCEPTION", datetime.now().strftime(DATE_FMT))
        curr_date = datetime.now().strftime(DATE_FMT)
        start_date, curr_date = _parse_date_str(start_date), _parse_date_str(curr_date)
        return (curr_date - start_date).days


def _get_saga_line() -> str:
    import csv

    file = [x for x in os.listdir(".") if "_saga.txt" in x]
    file = file[0] if len(file) > 0 else None
    if file == None:
        _get_days_since_inception(reset=True)
        saga_counter = int(os.environ.get("SAGA_COUNTER", "0"))
        os.environ["SAGA_COUNTER"] = "0"
        return DEFAULT_EMAIL_LINE
    saga_counter = int(os.environ.get("SAGA_COUNTER", "0"))
    with open(file, "r") as f:
        reader = csv.reader(f, delimiter="^")
        for i, row in enumerate(reader):
            if i == saga_counter:
                os.environ["SAGA_COUNTER"] = str(saga_counter + 1)
                return row[0]
    return DEFAULT_EMAIL_LINE


def _load_saga() -> str:
    days_since_inception = _get_days_since_inception()
    line = _get_saga_line()
    return f"Day {days_since_inception}: {line}"
