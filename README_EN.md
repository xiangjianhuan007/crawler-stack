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
| **8-Layer Auto-Degrade** | L0 → L1 → L1.1 → L1.5 → L2 → L2.5 → L3 → L3.5 → L4, never give up |
| **C++ Source-Level Anti-Detection** | L3.5 CloakBrowser — 58 Chromium C++ patches, not JS monkey-patching |
| **reCAPTCHA v3 Score 0.9** | Human-level, not 0.1 bot score |
| **Full Cloudflare Coverage** | v1/v2/v3 JS VM + Turnstile, all challenge types |
| **Tencent Aegis Bypass** | Verified against China's #1 anti-bot system |
| **Edge User Data Reuse** | Carry all login sessions (WeChat, forums, etc.) |
| **SPA Enhancement** | Hash route injection, API interception, render waiting |

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
| Normal sites | ✅ OK | ✅ **L1 0.3s** |
| Cloudflare v1 challenge | ❌ 403 | ✅ **L1 0.5s** |
| Cloudflare v3 JS VM | ❌ 403 | ✅ **L1.1 5s** |
| Cloudflare Turnstile | ❌ Stuck | ✅ **L1.1 auto** |
| reCAPTCHA v3 | ❌ 0.1 bot | ✅ **L3.5 0.9 human** |
| FingerprintJS | ❌ Blocked | ✅ **L3.5 passed** |
| SPA pages | ❌ Blank | ✅ **L4 rendered** |

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
