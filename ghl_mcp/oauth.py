"""OAuth 2.1 Authorization Server for the GHL MCP remote connector.

Claude's remote connectors (claude.ai, Claude Desktop, Claude mobile, and
Claude Code's ``--transport http`` mode) authenticate via OAuth (dynamic
client registration + authorization-code + PKCE), not a static token. This
provider implements the MCP SDK's OAuthAuthorizationServerProvider:

  * Clients self-register at /register (DCR).
  * /authorize auto-issues an auth code — the *human gate* is HTTP Basic auth
    on /authorize at the nginx layer (a shared password prompt in the
    browser), matching the pattern used by the SBD Google connector.
  * /token exchanges the code (SDK verifies PKCE) for an access token.
  * /mcp requires a valid access token (enforced by the SDK).

State (clients + tokens) is persisted to JSON so a service restart doesn't
force everyone to re-authorise.
"""

import json
import os
import secrets
import time

from pydantic import AnyHttpUrl

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

STATE_PATH = os.environ.get("GHL_MCP_OAUTH_STATE", "/opt/ghl-mcp/oauth_state.json")
CODE_TTL = 300                  # auth code lifetime (5 min)
TOKEN_TTL = 60 * 60 * 24 * 30   # access token lifetime (30 days)
SCOPES = ["user"]


class GHLOAuthProvider:
    """In-memory + JSON-persisted OAuth provider."""

    def __init__(self) -> None:
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.codes: dict[str, AuthorizationCode] = {}
        self.access: dict[str, AccessToken] = {}
        self.refresh: dict[str, RefreshToken] = {}
        self._load()

    # ---- persistence ----
    def _load(self) -> None:
        try:
            with open(STATE_PATH) as fh:
                d = json.load(fh)
            self.clients = {k: OAuthClientInformationFull(**v) for k, v in d.get("clients", {}).items()}
            self.access = {k: AccessToken(**v) for k, v in d.get("access", {}).items()}
            self.refresh = {k: RefreshToken(**v) for k, v in d.get("refresh", {}).items()}
        except Exception:
            pass

    def _save(self) -> None:
        try:
            tmp = STATE_PATH + ".tmp"
            with open(tmp, "w") as fh:
                json.dump({
                    "clients": {k: v.model_dump(mode="json") for k, v in self.clients.items()},
                    "access": {k: v.model_dump(mode="json") for k, v in self.access.items()},
                    "refresh": {k: v.model_dump(mode="json") for k, v in self.refresh.items()},
                }, fh)
            os.replace(tmp, STATE_PATH)
        except Exception:
            pass

    # ---- clients ----
    async def get_client(self, client_id: str):
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.clients[client_info.client_id] = client_info
        self._save()

    # ---- authorize (auto-approve; human gate is nginx Basic auth on /authorize) ----
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or SCOPES,
            expires_at=time.time() + CODE_TTL,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str):
        c = self.codes.get(authorization_code)
        if not c or c.client_id != client.client_id or c.expires_at < time.time():
            return None
        return c

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        self.codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    # ---- refresh ----
    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str):
        r = self.refresh.get(refresh_token)
        if not r or r.client_id != client.client_id:
            return None
        return r

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        self.refresh.pop(refresh_token.token, None)
        return self._issue(client.client_id, scopes or refresh_token.scopes, None)

    # ---- access tokens ----
    async def load_access_token(self, token: str):
        a = self.access.get(token)
        if not a:
            return None
        if a.expires_at and a.expires_at < int(time.time()):
            self.access.pop(token, None)
            self._save()
            return None
        return a

    async def revoke_token(self, token) -> None:
        t = getattr(token, "token", token)
        self.access.pop(t, None)
        self.refresh.pop(t, None)
        self._save()

    # ---- helper ----
    def _issue(self, client_id: str, scopes: list[str], resource) -> OAuthToken:
        now = int(time.time())
        at = secrets.token_urlsafe(32)
        rt = secrets.token_urlsafe(32)
        self.access[at] = AccessToken(token=at, client_id=client_id, scopes=scopes, expires_at=now + TOKEN_TTL, resource=resource)
        self.refresh[rt] = RefreshToken(token=rt, client_id=client_id, scopes=scopes, expires_at=now + TOKEN_TTL * 2)
        self._save()
        return OAuthToken(access_token=at, token_type="Bearer", expires_in=TOKEN_TTL, scope=" ".join(scopes), refresh_token=rt)


provider = GHLOAuthProvider()


def build_auth_settings(public_url: str) -> AuthSettings:
    return AuthSettings(
        issuer_url=AnyHttpUrl(public_url),
        resource_server_url=AnyHttpUrl(public_url),
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=SCOPES, default_scopes=SCOPES
        ),
        required_scopes=SCOPES,
    )
