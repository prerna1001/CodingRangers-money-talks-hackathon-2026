"""The server-rendered login screen served at `GET /`.

Kept out of main.py so the route wiring there stays readable. The page is
static apart from the signed-in branch, which renders the Auth0 profile and
then hands the browser off to the original application.
"""

from __future__ import annotations

from html import escape

_STYLE = """
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
    background: #0b0e14;
    background-image:
        radial-gradient(1000px 600px at 12% -10%, rgba(0, 168, 204, 0.18), transparent 60%),
        radial-gradient(900px 600px at 105% 110%, rgba(88, 80, 236, 0.20), transparent 55%);
    color: #e2e8f0;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    margin: 0;
    padding: 1.5rem;
}
.container {
    background: rgba(30, 34, 45, 0.82);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 22px;
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55);
    padding: 3rem 2.75rem;
    max-width: 520px;
    width: 100%;
    text-align: center;
    animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes rise {
    from { opacity: 0; transform: translateY(18px) scale(0.98); }
    to   { opacity: 1; transform: none; }
}
.logo {
    width: 150px;
    margin-bottom: 1.75rem;
    filter: drop-shadow(0 6px 18px rgba(0, 0, 0, 0.45));
}
h1 {
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #f7fafc;
    margin: 0 0 0.5rem;
}
.subtitle {
    color: #94a3b8;
    font-size: 1.02rem;
    margin: 0 0 2rem;
    line-height: 1.5;
}
.action-card {
    background: rgba(45, 49, 60, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 16px;
    padding: 2.25rem 1.75rem;
}
.action-text {
    font-size: 1.1rem;
    color: #cbd5e0;
    margin: 0 0 1.6rem;
}
.success {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: #68d391;
    background: rgba(104, 211, 145, 0.12);
    border: 1px solid rgba(104, 211, 145, 0.3);
    border-radius: 999px;
    padding: 0.5rem 1.1rem;
    margin-bottom: 1.75rem;
}
.profile {
    background: rgba(45, 49, 60, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 18px;
    padding: 2rem 1.5rem;
    margin-bottom: 2rem;
}
.profile-image {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    border: 3px solid #00a8cc;
    box-shadow: 0 0 0 6px rgba(0, 168, 204, 0.14);
    object-fit: cover;
    margin-bottom: 1.1rem;
}
.profile-name {
    font-size: 1.6rem;
    font-weight: 600;
    color: #f7fafc;
    margin-bottom: 0.35rem;
}
.profile-email {
    font-size: 1rem;
    color: #a0aec0;
    word-break: break-all;
}
.button {
    padding: 1rem 2.6rem;
    font-size: 1.05rem;
    font-weight: 600;
    border-radius: 11px;
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    font-family: inherit;
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                background-color 0.3s ease;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
    text-transform: uppercase;
    letter-spacing: 0.07em;
}
.button.login {
    background: linear-gradient(135deg, #00a8cc, #635bff);
    color: #ffffff;
}
.button.login:hover {
    transform: translateY(-4px) scale(1.03);
    box-shadow: 0 16px 34px rgba(0, 168, 204, 0.35);
}
.button.logout {
    background: #fc8181;
    color: #1a1e27;
}
.button.logout:hover {
    background: #e53e3e;
    transform: translateY(-4px) scale(1.03);
    box-shadow: 0 16px 34px rgba(0, 0, 0, 0.5);
}
.meta {
    margin-top: 2rem;
    font-size: 0.82rem;
    color: #64748b;
    line-height: 1.6;
}
.meta code {
    background: rgba(148, 163, 184, 0.14);
    border-radius: 5px;
    padding: 0.1rem 0.4rem;
    color: #a5b4fc;
}
@media (prefers-reduced-motion: reduce) {
    .container { animation: none; }
    .button { transition: none; }
}
"""

_AUTH0_LOGO = (
    "https://cdn.auth0.com/quantum-assets/dist/latest/logos/auth0/"
    "auth0-lockup-en-ondark.png"
)


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>{_STYLE}</style>
</head>
<body>
    <div class="container">
        <img src="{_AUTH0_LOGO}" alt="Auth0" class="logo">
        {body}
    </div>
</body>
</html>"""


def login_page(login_url: str, app_url: str) -> str:
    return _page(
        "Sign in | Ledgerlight",
        f"""
        <h1>Ledgerlight</h1>
        <p class="subtitle">Sign in to load your financial intelligence workspace.</p>
        <div class="action-card">
            <p class="action-text">Get started by signing in to your account</p>
            <a href="{escape(login_url, quote=True)}" class="button login">Log In</a>
        </div>
        <p class="meta">
            Redirects to <code>{escape(app_url)}</code> once authenticated.
        </p>
        """,
    )


def signed_in_page(user: dict | None, app_url: str) -> str:
    user = user or {}
    name = user.get("name") or user.get("nickname") or "Signed-in user"
    email = user.get("email", "")
    picture = user.get("picture") or (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>"
        "<rect width='96' height='96' fill='%232d313c'/>"
        "<circle cx='48' cy='38' r='16' fill='%2363b3ed'/>"
        "<path d='M16 88c6-20 18-30 32-30s26 10 32 30z' fill='%2363b3ed'/>"
        "</svg>"
    )
    return _page(
        f"Signed in as {name} | Ledgerlight",
        f"""
        <h1>Ledgerlight</h1>
        <div class="success">&#10003; Successfully authenticated</div>
        <div class="profile">
            <img src="{escape(picture, quote=True)}" alt="{escape(name)}" class="profile-image">
            <div class="profile-name">{escape(name)}</div>
            <div class="profile-email">{escape(email)}</div>
        </div>
        <p class="meta">Loading your workspace&hellip;</p>
        <script>window.location.replace({escape(app_url, quote=True)});</script>
        <noscript>
            <a href="{escape(app_url, quote=True)}" class="button login">Open App</a>
        </noscript>
        """,
    )


def setup_required_page(missing: list[str], app_url: str) -> str:
    """Shown instead of a login button when the tenant is not configured yet,
    so an unconfigured deployment explains itself instead of redirecting to a
    broken Auth0 authorize URL."""
    names = "".join(
        f'<li><code>{escape(name)}</code></li>' for name in sorted(missing)
    )
    return _page(
        "Auth0 not configured | Ledgerlight",
        f"""
        <h1>Ledgerlight</h1>
        <p class="subtitle">Auth0 is not configured yet, so the API is running open.</p>
        <div class="action-card">
            <p class="action-text">Set these values in <code>backend/.env</code>:</p>
            <ul class="meta" style="text-align:left; display:inline-block;">{names}</ul>
        </div>
        <p class="meta">
            <a href="{escape(app_url, quote=True)}" class="button login">Continue without login</a>
        </p>
        """,
    )
