# 🔥 Crawler Stack — The Ultimate 8-Layer Auto-Degrading Crawler Engine

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)
![Anti-Detection](https://img.shields.io/badge/anti--detection-C%2B%2B%20source--level-orange.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Turnstile%20%2F%20v3%20JS%20VM-purple.svg)

**The ultimate anti-bot crawling engine. 8 layers of auto-degrading firepower — from TLS fingerprint spoofing to C++ source-level Chromium patches.**

[中文版](README.md)

</div>

---

## 🚀 Key Features

| Feature | Description |
|---------|-------------|
| **8-Layer Auto-Degrade** | L0 → L1 → L1.1 → L1.5 → L2 → L2.5 → L3 → L3.5 → L4, each layer a fortress. Falls back until content is yours |
| **C++ Source-Level Anti-Detection** | L3.5 CloakBrowser — 58 Chromium C++ patches modifying the browser engine at compile time. JS monkey-patching? That's for amateurs |
| **reCAPTCHA v3 Score 0.9** | Human-level 0.9 — Google itself can't tell you're not a person |
| **Full Cloudflare Coverage** | v1/v2/v3 JS VM + Turnstile — bring it on, we break them all |
| **Tencent Aegis Bypass** | One of the world's toughest anti-bot systems, crushed in production |
| **Edge/Chrome User Data Hijack** | Load the entire browser profile — all login sessions (WeChat, forums, SaaS) inherited. Zero re-authentication |
| **SPA Rendering Domination** | Hash route injection, XHR/fetch interception, dynamic render waiting. SPAs are just static HTML to us |
| **CDP Remote Hijack** | Mount a live authenticated browser window. What you see is what you get — cookies, sessions, the works |

## 🏗️ Architecture

```
fetch(url)
  ├─ L0: 🍪 Cookie Injection Layer
  ├─ L1: ⚡ curl_cffi TLS Fingerprint Spoofing (<1s)
  ├─ L1.1: 🛡️ cloudscraper v3 — Cloudflare JS VM + Turnstile
  ├─ L1.5: 🔑 DrissionPage Edge User Data Reuse
  ├─ L2: 🕶️ DrissionPage Headless — Aegis Bypass
  ├─ L2.5: 🔌 Edge Remote Debugging via CDP
  ├─ L3: 🎭 Playwright Anti-Detection
  ├─ L3.5: 💀 CloakBrowser — 58 C++ Chromium Patches
  └─ L4: 🌀 SPA Rendering Enhancement
```

## 📊 Performance

| Scenario | Ordinary Crawler | **Crawler Stack** |
|----------|----------------|-------------------|
| Normal sites | ✅ Works | ✅ **L1 0.3s — overkill** |
| Cloudflare v1 challenge | ❌ 403 blocked | ✅ **L1 0.5s — crushed** |
| Cloudflare v3 JS VM | ❌ 403 no chance | ✅ **L1.1 5s — decrypted** |
| Cloudflare Turnstile | ❌ Stuck forever | ✅ **L1.1 auto-pass, no interaction** |
| reCAPTCHA v3 | ❌ 0.1 bot detected | ✅ **L3.5 0.9 human certified** |
| FingerprintJS | ❌ Blocked & banned | ✅ **L3.5 passed, fingerprint zeroed** |
| BrowserScan | ❌ Detected & exposed | ✅ **L3.5 NORMAL — perfect disguise** |
| SPA pages | ❌ Blank nothing | ✅ **L4 fully rendered, source captured** |
| WeChat QR login | ❌ Can't handle | ✅ **L1.5 session hijack, no QR needed** |

## 🎯 Quick Start

```bash
pip install curl_cffi DrissionPage playwright requests
pip install git+https://github.com/VeNoMouS/cloudscraper.git
npm install -g cloakbrowser
pip install cloakbrowser
```

```python
from crawler_stack_v4 import fetch

# Auto-degrade — let the engine choose the fastest path
result = fetch('https://example.com')
print(result.text)    # Clean content
print(result.method)  # Actual layer used

# Skip straight to CloakBrowser (ultimate anti-detection)
result = fetch('https://high-protection.com',
    skip_l1=True, skip_l11=True, skip_l15=True,
    skip_l2=True, skip_l25=True, skip_l3=True)
```

## 🧪 Verified Targets

| Site | Protection | Layer Used |
|------|-----------|-----------|
| 69shuba.tw | Tencent Aegis + Cloudflare | L2 DrissionPage |
| mp.weixin.qq.com | Tencent Aegis | L2 DrissionPage |
| browserscan.net | Deep fingerprinting | L3.5 CloakBrowser (NORMAL) |
| deviceandbrowserinfo.com | 24-signal behavior detection | L3.5 CloakBrowser (0 flags) |

## ⚠️ Known Limitations

- **WeChat OAuth QR login**: requires phone confirmation, cannot be automated
- **Cloudflare Under Attack + reCAPTCHA**: human verification required

## 📄 License

MIT
