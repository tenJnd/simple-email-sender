from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Optional

CRED_PATH = os.getenv("GMAIL_SERVICE_ACCOUNT_FILE")
ADMIN_EMAIL = os.getenv("GMAIL_ADMIN_EMAIL")
SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "info@partonomy.eu")
DISPLAY_NAME = os.getenv("GMAIL_DISPLAY_NAME", "Partonomy")


class Sender:
    def send(self, to_email: str, subject: str, body: str,
             from_email: Optional[str] = None) -> None:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class ConsoleSender(Sender):
    def send(self, to_email: str, subject: str, body: str, from_email: Optional[str] = None) -> None:
        print("---- EMAIL (console) ----")
        if from_email:
            print(f"From: {from_email}")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print()
        print(body)
        print("-------------------------")


class GmailServiceAccountSender(Sender):
    """
    Gmail API sender using Service Account with Domain-Wide Delegation.

    Setup:
    - Create a Service Account in Google Cloud Console with Gmail API enabled.
    - Enable Domain-Wide Delegation for the service account.
    - Download the service account credentials JSON file.
    - In Google Workspace Admin, authorize the service account's Client ID with scope:
      https://www.googleapis.com/auth/gmail.send
    - Set GMAIL_SERVICE_ACCOUNT_FILE environment variable or pass credentials_path.
    - Set GMAIL_SENDER_EMAIL environment variable or pass sender_email to specify the
      email address to send from (must be in your domain).
    - Set GMAIL_DISPLAY_NAME environment variable to specify the display name for the sender.

    Usage:
      sender = GmailServiceAccountSender(
          credentials_path="service-account.json",
          sender_email="info@partonomy.eu"
      )
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(
            self,
            sender_email: Optional[str] = None
    ) -> None:
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2 import service_account  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing Google API deps. Install: google-api-python-client google-auth google-auth-httplib2"
            ) from e

        self._build = build
        self._service_account = service_account

        self.sender_email = sender_email or SENDER_EMAIL

        if not os.path.exists(CRED_PATH):
            raise RuntimeError(
                f"Service account credentials not found. Place service-account.json at {CRED_PATH} "
                "or set GMAIL_SERVICE_ACCOUNT_FILE."
            )

        # Load service account credentials
        credentials = self._service_account.Credentials.from_service_account_file(
            CRED_PATH,
            scopes=self.SCOPES
        ).with_subject(ADMIN_EMAIL)

        print(f"DEBUG: Impersonating user: {self.sender_email}")

        # Build Gmail API service
        self.service = self._build("gmail", "v1", credentials=credentials)

    def _build_message(self, to_email: str, subject: str, body: str, from_email: Optional[str] = None) -> dict:
        msg = MIMEText(body, _subtype="plain", _charset="utf-8")
        msg["to"] = to_email
        msg["subject"] = subject

        email_address = from_email or self.sender_email

        msg["from"] = f"{DISPLAY_NAME} <{email_address}>"
        msg["Reply-To"] = email_address

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        return {"raw": raw}

    def send(self, to_email: str, subject: str, body: str,
             from_email: Optional[str] = None) -> None:  # pragma: no cover
        # Minimal retry for transient 5xx or rate limits
        message = self._build_message(to_email, subject, body, from_email)
        attempts = 0
        delay = 1.0
        while True:
            try:
                self.service.users().messages().send(userId="me", body=message).execute()
                return
            except Exception as e:  # best-effort classification
                attempts += 1
                if attempts >= 3:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 8.0)
