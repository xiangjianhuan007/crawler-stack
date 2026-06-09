# 🔥 Crawler Stack — 地表最强八层自动降级爬虫引擎

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)
![Anti-Detection](https://img.shields.io/badge/anti--detection-C%2B%2B%20source--level-orange.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Turnstile%20%2F%20v3%20JS%20VM-purple.svg)
![Aegis](https://img.shields.io/badge/%E8%85%BE%E8%AE%AF%E5%A4%A9%E5%BE%A1-Aegis%20%E7%BB%95%E8%BF%87-success.svg)

**专为高防站点设计的终极爬虫方案。从最快到最稳，八层自动降级，不拿到内容誓不罢休。**

[English](README_EN.md) · [报告 Bug](https://github.com/xianjianhuang/crawler-stack/issues) · [请求功能](https://github.com/xianjianhuang/crawler-stack/issues)

</div>

---

## 🚀 核心亮点

| 💥 硬核能力 | 说明 |
|------------|------|
| **八层降级** | L0 → L1 → L1.1 → L1.5 → L2 → L2.5 → L3 → L3.5 → L4，层层递进，永不放弃 |
| **源码级反检测** | L3.5 CloakBrowser — 58 个 Chromium C++ 源码补丁，不是 JS 打补丁的玩具 |
| **reCAPTCHA v3 得分 0.9** | 人类级别，不是 0.1 的 bot 分数 |
| **Cloudflare 全系列通杀** | v1/v2/v3 JS VM + Turnstile，管你什么挑战模式 |
| **腾讯天御 Aegis 绕过** | 国内最大反爬系统之一，实测通过 |
| **Edge 用户数据复用** | 自带微信/各平台登录态，不用重复扫码 |
| **SPA 单页应用增强** | hash 路由注入、API 拦截、等待渲染，SPA 无所遁形 |

## 🏗️ 架构总览

```
fetch(url)
  ├─ L0: 🍪 Cookie 注入层                    — 从文件/列表注入 cookie
  ├─ L1: ⚡ curl_cffi + Chrome impersonation  → 模拟 TLS/JA3 指纹（<1s 极速）
  ├─ L1.1: 🛡️ cloudscraper v3                → 执行 Cloudflare JS VM + Turnstile（最新 JS 加密挑战）
  ├─ L1.5: 🔑 DrissionPage (用户数据)         — 复用 Edge 真实用户数据（自带微信登录态）
  ├─ L2: 🕶️ DrissionPage (无头)               — 过 腾讯天御 Aegis（国内最强反爬之一）
  ├─ L2.5: 🔌 Edge 远程调试 CDP               — 控制已登录的 Edge 浏览器
  ├─ L3: 🎭 Playwright + anti-detection       — JS 层全方位反检测
  ├─ L3.5: 💀 CloakBrowser                    — Chromium 58 个 C++ 源码补丁（终极反检测）
  └─ L4: 🌀 SPA 渲染增强                      — hash 路由、API 拦截、JS 渲染等待
```

> **设计哲学**：每一层失败后自动降级到下一层，用最快的方案拿到内容。能 1 秒搞定的绝不等 10 秒，但该上重武器时绝不手软。

---

## 📊 性能对比（和竞品说拜拜）

| 场景 | 普通爬虫 | **Crawler Stack** |
|------|---------|-------------------|
| 普通网站 | ✅ 正常 | ✅ **L1 0.3s** |
| Cloudflare v1 挑战 | ❌ 403 | ✅ **L1 0.5s** |
| Cloudflare v3 JS VM | ❌ 403 | ✅ **L1.1 5s** |
| Cloudflare Turnstile | ❌ 卡住 | ✅ **L1.1 自动过** |
| 腾讯天御 Aegis | ❌ 空 body | ✅ **L2 3s** |
| reCAPTCHA v3 | ❌ 0.1 bot | ✅ **L3.5 0.9 human** |
| FingerprintJS | ❌ 被拦截 | ✅ **L3.5 全通过** |
| BrowserScan | ❌ 被检测 | ✅ **L3.5 NORMAL** |
| SPA 单页应用 | ❌ 白页 | ✅ **L4 渲染完成** |
| 微信扫码登录页 | ❌ 无法处理 | ✅ **L1.5 复用登录态** |

## 🎯 快速开始

### 安装

```bash
# 核心依赖
pip install curl_cffi DrissionPage playwright requests

# Cloudflare JS 挑战破解（v3.0 主线版）
pip install git+https://github.com/VeNoMouS/cloudscraper.git

# 源码级反检测浏览器（终极武器）
npm install -g cloakbrowser
pip install cloakbrowser
```

### 一行代码开始爬

```python
from crawler_stack_v4 import fetch

# 自动降级 — 引擎替你选择最快方案
result = fetch('https://example.com')
print(result.text)    # 干净的内容
print(result.method)  # 实际使用的层级
```

### 指定跳过某些层级

```python
# 跳过 L1 curl_cffi，直接走 cloudscraper
result = fetch('https://cloudflare-site.com', skip_l1=True)

# 直接用 CloakBrowser 终极反检测（跳过前 6 层）
result = fetch('https://high-protection.com',
    skip_l1=True, skip_l11=True, skip_l15=True,
    skip_l2=True, skip_l25=True, skip_l3=True)
# result.method → 'L3.5-cloakbrowser'
```

### SPA 单页应用视频爬取

```python
result = fetch('https://spa-site.com/#/video/123',
    hash_route='/video/123',
    wait_for_selector='.player',
    intercept_api=True)
print(result.video_urls)  # 自动拦截 m3u8/mp4 地址
```

---

## 🧪 实战验证

### 已攻破的站点

| 站点 | 防护等级 | 攻破层级 | 耗时 |
|------|---------|---------|------|
| **69shuba.tw** | 🟠 腾讯天御 Aegis + Cloudflare | L2 DrissionPage | ~3s |
| **mp.weixin.qq.com** | 🟠 腾讯天御 Aegis | L2 DrissionPage | ~3s |
| **色花堂** | 🟡 年龄确认页 + Discuz! | L2 自动点击确认 | ~5s |
| **browserscan.net** | 🔴 深度浏览器指纹检测 | L3.5 CloakBrowser (NORMAL) | ~8s |
| **deviceandbrowserinfo.com** | 🔴 行为检测 24 项 | L3.5 CloakBrowser (0 true flags) | ~8s |
| **cloudflarestatus.com** | 🟡 Cloudflare CDN | L1 curl_cffi | ~0.3s |

### 检测分数（越高越好）

| 检测服务 | 普通 Playwright | **Crawler Stack** |
|---------|----------------|-------------------|
| reCAPTCHA v3 | 0.1 🤖 | **0.9 🧑** |
| Cloudflare Turnstile | ❌ 失败 | ✅ **通过** |
| FingerprintJS | ❌ 被拦截 | ✅ **通过** |
| `navigator.webdriver` | `true` | **`false`** |
| TLS 指纹 | 不匹配 | **与 Chrome 完全一致** |
| CDP 检测 | 被检测 | **未被检测** |

---

## 🧰 各层级详解

### L0 — Cookie 注入层 🍪
从 Netscape 格式文件或浏览器扩展导出的 JSON 列表加载 cookie，自动注入到所有后续层级。

```python
from crawler_stack_v4 import load_cookie_file, load_cookies_from_list

# 从 curl -c 导出的文件加载
load_cookie_file('/path/to/cookies.txt')

# 从浏览器扩展 JSON 加载
load_cookies_from_list([
    {'domain': '.example.com', 'name': 'session', 'value': 'abc123'},
])
```

### L1 — curl_cffi TLS 指纹模拟 ⚡
最快的层级。模拟 Chrome 的 TLS/JA3 指纹，通过 `impersonate='chrome131'` 参数一键伪装。适合纯 Cloudflare v1 JS 挑战的站点。

### L1.1 — cloudscraper v3 JS 挑战破解 🛡️
内置 JS2Py VM，真正**执行** Cloudflare 的 JavaScript 挑战，而不是假装。支持 v1/v2/v3 JS VM + Turnstile 全部挑战类型。v3.0 版本专为最新 Cloudflare 防护设计。

### L1.5 — DrissionPage Edge 用户数据复用 🔑
启动 Edge 浏览器的**真实用户数据目录**，自带所有登录态——微信、各平台、论坛……不需要重复登录。自动检测 SPA 登录页跳转并尝试 hash 路由注入。

### L2 — DrissionPage 无头模式 🕶️
**唯一已知能完整绕过腾讯天御 Aegis 的方案**。69shuba、微信公众平台等使用 Aegis 的站点实测通过。内置年龄确认页自动点击（色花堂等成人站点）。

### L2.5 — Edge 远程调试 CDP 🔌
通过 Chrome DevTools Protocol 控制**已经登录的 Edge 浏览器窗口**。自动检测 `localhost:9222` 调试端口，打开新标签页执行 JS，获取 HTML/cookie。

### L3 — Playwright + 反检测 🎭
全方位的 JS 层反检测：`navigator.webdriver` 设为 `false`、补全 `window.chrome` 对象、伪造插件列表、设置语言偏好。

### L3.5 — CloakBrowser 源码级反检测 💀
**终极武器**。基于 Chromium 的 58 个 C++ 源码补丁，不是 JS 注入那种玩具方案。

| 补丁覆盖 | 说明 |
|---------|------|
| Canvas / WebGL | 源码层注入噪声，指纹每次不同 |
| GPU 信息 | vendor/renderer 替换为真实硬件值 |
| 硬件参数 | 屏幕/CPU/内存全部伪装 |
| Navigator | `webdriver=false`、`plugins.length=5` |
| WebRTC | ICE 候选自动匹配代理出口 |
| TLS 指纹 | 与真实 Chrome 完全一致 |

### L4 — SPA 渲染增强 🌀
专门对付单页应用：hash 路由注入、等待指定元素渲染、拦截 XHR/fetch 获取 API 数据、自动提取 m3u8/mp4 视频地址。

---

## ⚠️ 已知局限（坦诚相告）

| 场景 | 原因 | 建议 |
|------|------|------|
| **微信 OAuth 扫码登录** | 需手机确认授权，纯 HTTP 无法模拟 | 用 L1.5 复用 Edge 登录态 |
| **Cloudflare Under Attack + reCAPTCHA** | 人类交互验证，非指纹问题 | 需手动通过后导出 cookie |

---

## 📦 项目结构

```
crawler-stack/
├── crawler_stack_v4.py    # 主引擎（1115+ 行，八层自动降级）
├── README.md              # 中文说明（就是本文件）
├── README_EN.md           # English version
├── LICENSE                # MIT
└── .gitignore
```

## 🤝 贡献

PR、Issues 都欢迎。如果 Crawler Stack 帮你解决了棘手的问题，点个 ⭐ 就是最好的支持！

## 📄 License

MIT — 随便用，随便改，保留版权声明即可。
