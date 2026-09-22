from __future__ import annotations

_BASE = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;padding:0;background:#0a0a0c;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}
.wrap{{max-width:560px;margin:0 auto;padding:40px 24px}}
.card{{background:#16161a;border:1px solid #232329;border-radius:16px;padding:40px 36px}}
.logo{{font-size:20px;font-weight:800;color:#eeeef0;text-align:center;margin-bottom:32px}}
.logo span{{color:#6366f1}}
h1{{font-size:22px;font-weight:700;color:#eeeef0;margin:0 0 12px;line-height:1.3}}
p{{font-size:14px;color:#8b8b95;line-height:1.7;margin:0 0 16px}}
.btn{{display:inline-block;padding:12px 32px;background:#6366f1;color:#fff;border-radius:10px;font-weight:600;font-size:14px;text-decoration:none;margin:8px 0 24px}}
.highlight{{background:#111114;border:1px solid #232329;border-radius:10px;padding:16px 20px;margin:16px 0}}
.highlight code{{font-family:'JetBrains Mono',monospace;font-size:13px;color:#eeeef0;word-break:break-all}}
.badge{{display:inline-block;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:700}}
.badge-green{{background:rgba(16,185,129,.12);color:#10b981}}
.badge-amber{{background:rgba(245,158,11,.12);color:#f59e0b}}
.badge-red{{background:rgba(239,68,68,.12);color:#ef4444}}
.footer{{text-align:center;padding:24px 0 0;font-size:11px;color:#555}}
.footer a{{color:#6366f1;text-decoration:none}}
</style></head><body><div class="wrap"><div class="card">
<div class="logo">AI Context<span>Engine</span></div>
{content}
</div><div class="footer">AI Context Engine &mdash; Production code from AI, your architecture rules.<br><a href="{base_url}">Open Dashboard</a></div></div></body></html>"""


def welcome_email(email: str, api_key: str, base_url: str) -> tuple[str, str]:
    subject = "Welcome to AI Context Engine"
    content = f"""\
<h1>Welcome aboard!</h1>
<p>Your account is ready. You can now generate production-ready code with AI, enforced by your exact architecture rules.</p>
<p>Here's your API key for programmatic access:</p>
<div class="highlight"><code>{api_key}</code></div>
<p style="color:#ef4444;font-size:12px;font-weight:600">Save this key — it's shown only once and cannot be recovered.</p>
<p>What you can do now:</p>
<p>&#x2728; Generate code in 20 languages with 50+ frameworks<br>
&#x1F50D; Review existing code against 20 architecture rules<br>
&#x1F4CB; Use 12 battle-tested task templates<br>
&#x26A1; Stream output in real time via SSE</p>
<a href="{base_url}/dashboard.html" class="btn">Open Dashboard</a>
<p>Your free plan includes 100 generations/month. Need more? Upgrade anytime from Settings.</p>"""
    return subject, _BASE.format(content=content, base_url=base_url)


def password_reset_email(email: str, reset_token: str, base_url: str) -> tuple[str, str]:
    subject = "Reset your password — AI Context Engine"
    reset_url = f"{base_url}/dashboard.html?reset_token={reset_token}"
    content = f"""\
<h1>Password reset requested</h1>
<p>We received a request to reset the password for <strong>{email}</strong>.</p>
<p>Click the button below to set a new password:</p>
<a href="{reset_url}" class="btn">Reset Password</a>
<p style="margin-top:16px;font-size:12px;color:#888">Or copy this link: {reset_url}</p>
<p>This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>"""
    return subject, _BASE.format(content=content, base_url=base_url)


def usage_alert_80_email(email: str, used: int, limit: int, base_url: str) -> tuple[str, str]:
    subject = "Usage alert: 80% of your monthly limit"
    pct = round((used / limit) * 100) if limit > 0 else 0
    content = f"""\
<h1>You've used 80% of your plan</h1>
<p><span class="badge badge-amber">{pct}% used</span></p>
<p>You've used <strong>{used:,}</strong> of your <strong>{limit:,}</strong> monthly generations.</p>
<p>At this pace, you may run out before your billing cycle resets. Consider upgrading to get more generations and uninterrupted access.</p>
<a href="{base_url}/dashboard.html" class="btn">Check Usage</a>"""
    return subject, _BASE.format(content=content, base_url=base_url)


def usage_alert_95_email(email: str, used: int, limit: int, base_url: str) -> tuple[str, str]:
    subject = "Urgent: 95% of your monthly limit reached"
    pct = round((used / limit) * 100) if limit > 0 else 0
    content = f"""\
<h1>Almost at your limit</h1>
<p><span class="badge badge-red">{pct}% used</span></p>
<p>You've used <strong>{used:,}</strong> of your <strong>{limit:,}</strong> monthly generations. You're about to hit your limit.</p>
<p>Upgrade now to avoid interruption:</p>
<p><strong>Pro</strong> — 5,000 generations/mo — $49<br>
<strong>Agency</strong> — 25,000 generations/mo — $199</p>
<a href="{base_url}/dashboard.html" class="btn">Upgrade Now</a>"""
    return subject, _BASE.format(content=content, base_url=base_url)


def subscription_activated_email(email: str, plan: str, limit: int, base_url: str) -> tuple[str, str]:
    subject = f"Your {plan} plan is active!"
    content = f"""\
<h1>You're on the {plan} plan!</h1>
<p><span class="badge badge-green">ACTIVE</span></p>
<p>Your subscription is now active. Here's what you get:</p>
<p>&#x2705; <strong>{limit:,}</strong> generations per month<br>
&#x2705; All 20 languages &amp; 50+ frameworks<br>
&#x2705; All 20 architecture rules<br>
&#x2705; Code generation + code review<br>
&#x2705; 12 task templates<br>
&#x2705; API access for CI/CD integration</p>
<a href="{base_url}/dashboard.html" class="btn">Start Generating</a>
<p>Thank you for supporting AI Context Engine!</p>"""
    return subject, _BASE.format(content=content, base_url=base_url)
