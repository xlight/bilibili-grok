"""BiliBili QR code login implementation."""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import qrcode


@dataclass
class Credentials:
    """BiliBili login credentials."""

    sessdata: str
    bili_jct: str
    buvid3: str
    dedeuserid: str
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "sessdata": self.sessdata,
            "bili_jct": self.bili_jct,
            "buvid3": self.buvid3,
            "dedeuserid": self.dedeuserid,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        return cls(
            sessdata=data["sessdata"],
            bili_jct=data["bili_jct"],
            buvid3=data["buvid3"],
            dedeuserid=data["dedeuserid"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


class LoginError(Exception):
    """Login error."""

    pass


class QRCodeExpiredError(LoginError):
    """QR code expired."""

    pass


class LoginCancelledError(LoginError):
    """Login cancelled by user."""

    pass


class BilibiliLogin:
    """BiliBili QR code login handler."""

    PASSPORT_URL = "https://passport.bilibili.com"
    QR_GEN_URL = f"{PASSPORT_URL}/x/passport-login/web/qrcode/generate?source=main-fe-header"
    QR_POL_URL = f"{PASSPORT_URL}/x/passport-login/web/qrcode/poll"

    def __init__(self, credential_path: str = "data/credentials.json"):
        self.credential_path = Path(credential_path)
        self._credentials: Credentials | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com/",
                    "Origin": "https://www.bilibili.com",
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate_qrcode(self) -> tuple[str, str]:
        """Generate QR code for login.

        Returns:
            tuple: (qrcode_key, auth_url)
        """
        resp = await self.client.get(self.QR_GEN_URL)
        resp.raise_for_status()
        data = resp.json()

        if data["code"] != 0:
            raise LoginError(f"Failed to generate QR code: {data.get('message')}")

        result = data["data"]
        qrcode_key = result["qrcode_key"]
        auth_url = result["url"]

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(auth_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        output_path = self.credential_path.parent / "qrcode.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)

        return qrcode_key, auth_url

    async def poll_login(
        self, qrcode_key: str, timeout: int = 120, interval: int = 2
    ) -> Credentials:
        """Poll login status until success or timeout.

        Args:
            qrcode_key: The QR code key from generate_qrcode
            timeout: Maximum time to wait in seconds
            interval: Polling interval in seconds

        Returns:
            Credentials object

        Raises:
            QRCodeExpiredError: If QR code expires
            LoginCancelledError: If login is cancelled
            LoginError: For other errors
        """
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < timeout:
            await asyncio.sleep(interval)
            poll_count += 1

            resp = await self.client.get(
                self.QR_POL_URL,
                params={"qrcode_key": qrcode_key, "source": "main-fe-header"},
            )
            resp.raise_for_status()
            data = resp.json()

            result = data.get("data", {})
            status = result.get("code", -1)
            message = result.get("message", "")

            if status == 86101:
                print(f"[{poll_count}] Waiting for scan... ({message})")
                continue
            if status == 86202:
                print(f"[{poll_count}] Scanned, waiting for confirmation...")
                continue
            if status == -1:
                raise QRCodeExpiredError("QR code expired or cancelled")
            if status == 0:
                url = result.get("url", "")
                if not url:
                    raise LoginError("Login failed: no URL in response")

                sessdata = ""
                bili_jct = ""
                buvid3 = ""
                dedeuserid = ""

                sessdata_match = re.search(r"SESSDATA=([^&]+)", url)
                if sessdata_match:
                    sessdata = sessdata_match.group(1)

                bili_jct_match = re.search(r"bili_jct=([^&]+)", url)
                if bili_jct_match:
                    bili_jct = bili_jct_match.group(1)

                buvid3_match = re.search(r"buvid3=([^&]+)", url)
                if buvid3_match:
                    buvid3 = buvid3_match.group(1)

                dedeuserid_match = re.search(r"DedeUserID=([^&]+)", url)
                if dedeuserid_match:
                    dedeuserid = dedeuserid_match.group(1)

                if not sessdata:
                    raise LoginError(f"Login failed: no SESSDATA in URL: {url}")

                expires_at = datetime.now() + timedelta(days=30)

                credentials = Credentials(
                    sessdata=sessdata,
                    bili_jct=bili_jct,
                    buvid3=buvid3,
                    dedeuserid=dedeuserid,
                    expires_at=expires_at,
                )

                await self.save_credentials(credentials)
                return credentials

        raise QRCodeExpiredError("Login timeout")

    async def login_interactive(self) -> Credentials:
        """Interactive login flow with QR code."""
        qrcode_key, auth_url = await self.generate_qrcode()
        output_path = self.credential_path.parent / "qrcode.png"
        print(f"QR code saved to: {output_path}")
        print(f"URL: {auth_url}")
        print("Please scan the QR code with Bilibili app and CONFIRM the login...")
        print("Waiting for scan... (will poll for 120 seconds)")

        return await self.poll_login(qrcode_key)

    async def save_credentials(self, credentials: Credentials) -> None:
        """Save credentials to file."""
        self.credential_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.credential_path, "w") as f:
            json.dump(credentials.to_dict(), f, indent=2)
        self._credentials = credentials

    async def load_credentials(self) -> Credentials | None:
        """Load credentials from file if exists and not expired."""
        if not self.credential_path.exists():
            return None

        try:
            with open(self.credential_path) as f:
                data = json.load(f)

            credentials = Credentials.from_dict(data)

            if credentials.is_expired:
                print("Credentials expired, please login again")
                return None

            self._credentials = credentials
            return credentials
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to load credentials: {e}")
            return None

    @property
    def credentials(self) -> Credentials | None:
        return self._credentials

    async def ensure_valid_credentials(self) -> Credentials:
        """Ensure valid credentials exist, either load or login."""
        credentials = await self.load_credentials()
        if credentials:
            return credentials

        print("\n=== BiliBili Login ===")
        print("QR code login requires scanning from web browser.")
        print("For bot use, you can manually create credentials file.")
        print(f"\nCreate file: {self.credential_path}")
        print("With content:")
        print("""{
  "sessdata": "your_sessdata_value",
  "bili_jct": "your_bili_jct_value", 
  "buvid3": "your_buvid3_value",
  "dedeuserid": "your_user_id",
  "expires_at": "2026-12-31T00:00:00"
}""")

        return await self.login_interactive()

    def get_cookie_dict(self) -> dict[str, str]:
        """Get credentials as cookie dict for httpx."""
        if not self._credentials:
            return {}
        return {
            "SESSDATA": self._credentials.sessdata,
            "bili_jct": self._credentials.bili_jct,
            "buvid3": self._credentials.buvid3,
            "DedeUserID": self._credentials.dedeuserid,
        }
