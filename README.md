# 🔥 Crawler Stack v5.1 — 地表最强爬虫引擎，正面硬刚 BrowserAct

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-5.1.0-brightgreen.svg)
![Anti-Detection](https://img.shields.io/badge/anti--detection-C%2B%2B%20source--level-orange.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Turnstile%20%2F%20v3%20JS%20VM-purple.svg)
![Aegis](https://img.shields.io/badge/%E8%85%BE%E8%AE%AF%E5%A4%A9%E5%BE%A1-Aegis%20%E7%BB%95%E8%BF%87-success.svg)
![HTML Compact](https://img.shields.io/badge/html--compact-90%25%20token%20savings-green.svg)
![API Discovery](https://img.shields.io/badge/api--discovery-Network%20Capture-blue.svg)

**九层自动降级 + HTML 精简引擎 + API 端点发现 + 验证码人机接力 + 多账号隔离 + Skill Forge — 你的 AI Agent 值得拥有比 BrowserAct 更强的爬虫能力。**

[English](README_EN.md) · [报告 Bug](https://github.com/xianjianhuang/crawler-stack/issues) · [请求功能](https://github.com/xianjianhuang/crawler-stack/issues)

</div>

---

## 🚀 v5.1 新增：两大核弹级能力

### 🗜️ HTML 精简引擎 — 对标 BrowserAct `state`，token 省 90%

```python
# markdown 模式：保留结构（标题/列表/表格/链接），token ≈60-70%
result = fetch(url, compact_mode='markdown')
print(result.compact)  # 结构化 Markdown，省 70% token

# index 模式：仅提取交互元素 + 关键文本，token ≈50-90%
result = fetch(url, compact_mode='index')
print(result.compact)  # 链接/图片/正文/列表/表格分类展示
```

| 模式 | token 降幅 | 输出 |
|------|-----------|------|
| `text`（默认） | ~40% | 纯文本（兼容 v5.0） |
| `markdown` | **~60-70%** | 结构化 Markdown，保留标题/列表/表格/链接/图片 |
| `index` | **~50-90%** | 分类索引：链接列表+图片+正文+列表+表格，带数量统计 |

### 📡 API 端点自动发现 — 对标 BrowserAct `network requests`

```python
# 方式一：fetch 时顺带发现
result = fetch('https://spa-website.com', discover_api=True)
for ep in result.api_endpoints:
    print(f"[{ep['method']}] {ep['url']} → {ep['response_type']}")

# 方式二：独立调用
from crawler_stack_v5 import discover_api_endpoints
endpoints = discover_api_endpoints('https://spa-website.com')
print(f'发现 {len(endpoints)} 个 API 端点')
```

自动拦截页面所有 XHR/Fetch 请求，过滤出 JSON 响应 + API 特征 URL，去重排序。对 SPA 站点特别有用。

---

## 🚀 v5 四大核弹级升级

| 💥 新能力 | 对标 BrowserAct | Crawler Stack 的实现 |
|-----------|---------------|---------------------|
| **🔐 验证码人机接力** | `solve-captcha` + `remote-assist` | `detect_captcha()` 自动识别 5 种验证码类型 + `HumanAssistSession` 截图→通知→等待→继续，比 BrowserAct 多支持滑块/图片/短信验证码 |
| **👥 多账号隔离体系** | 独立 stealth 浏览器 + 独立 IP + 独立指纹 | `Account` 类每个账号独立 DrissionPage 实例 + **稳定指纹噪声**（canvas/WebGL/fonts/audio 用种子哈希生成确定性偏移）+ 独立代理 + 独立 Session，**完全免费无限量** |
| **⚡ 并发安全** | 零干扰并发 | 默认 `use_fresh_instance=True`，每次创建独立浏览器实例，**彻底消除 session 污染**。旧版全局单例？不存在的 |
| **🤖 Skill Forge** | 自然语言→自动探测→生成 Skill | `SkillForge` 解析自然语言字段→探测目标网站结构→生成 `ForgedSkill`（含完整 SKILL.md），和我们的「统筹/女娲/达尔文」三位一体理念一脉相承 |
| **🧠 统筹编排** | 统筹引擎自动编排爬虫任务 | 已集成 [xianjianhuang/tongchou](https://github.com/xianjianhuang/tongchou) — 说一句话就搞定爬虫+分析一条龙 |

## 🏗️ 架构总览

```
fetch(url)
  ├─ L0: 🍪 Cookie 注入层                    — 从文件/列表注入 cookie
  ├─ L1: ⚡ curl_cffi + Chrome impersonation  → 模拟 TLS/JA3 指纹（<1s 极速）
  ├─ L1.1: 🛡️ cloudscraper v3                → 执行 Cloudflare JS VM + Turnstile（最新 JS 加密挑战）
  ├─ L1.5: 🔑 DrissionPage (用户数据)         — 复用 Edge 真实用户数据（自带微信登录态）
  ├─ L2: 🕶️ DrissionPage (独立实例)           — 过 腾讯天御 Aegis，每次独立实例消除 session 污染
  ├─ L2.5: 🔌 Edge 远程调试 CDP               — 控制已登录的 Edge 浏览器
  ├─ L3: 🎭 Playwright + anti-detection       — JS 层全方位反检测
  ├─ L3.5: 💀 CloakBrowser                    — Chromium 58 个 C++ 源码补丁（终极反检测）
  ├─ L4: 🌀 SPA 渲染增强                      — hash 路由、API 拦截、JS 渲染等待
  └─ L5: 🤖 影刀 RPA                          — 可选层级，通过 FastAPI 调用影刀处理复杂 GUI 流程

新增模块（非层级）：
  ├─ 👥 Account / AccountManager    — 多账号隔离体系（独立指纹+独立IP+独立Session）
  ├─ 🔐 HumanAssistSession          — 验证码人机接力（5种验证码识别）
  ├─ 🤖 SkillForge / ForgedSkill    — 自然语言→爬虫 Skill 自动生成
  ├─ 🗜️ _to_compact()               — HTML 精简引擎（markdown/index 模式，token 省 50-90%）
  ├─ 📡 discover_api_endpoints()    — API 端点自动发现（Network Capture）
  └─ 🕵️ detect_captcha()            — 验证码类型检测引擎
```

> **设计哲学**：每一层失败后自动降级到下一层，用最快的方案拿到内容。能 1 秒搞定的绝不等 10 秒，但该上重武器时绝不手软。

---

## 📊 竞品对比 — Crawler Stack v5.1 vs BrowserAct

| 维度 | **Crawler Stack v5.1 🚀** | BrowserAct |
|------|------------------------|------------|
| **反爬层级** | 九层自动降级（L0→L1→L1.1→L1.5→L2→L2.5→L3→L3.5→L4→L5） | 三模式（chrome / stealth 隐私 / stealth 固定身份） |
| **HTML 精简** | ✅ **v5.1 新增** `_to_compact()` — markdown/index 模式，token 省 50-90% | ✅ `state` 索引模式，官方称省 93% token |
| **API 端点发现** | ✅ **v5.1 新增** `discover_api_endpoints()` — Playwright 拦截 XHR/Fetch | ✅ `network requests` CLI 命令 |
| **验证码处理** | ✅ `detect_captcha` 识别 5 种类型 + `HumanAssistSession` 人机接力 | ✅ `solve-captcha` + `remote-assist` |
| **多账号隔离** | ✅ `Account` + `AccountManager`，**完全免费无限量** | ⚠️ stealth 浏览器超 5 个需付费 |
| **并发安全** | ✅ 默认独立实例模式，零污染 | ✅ 零干扰并发 |
| **Skill Forge** | ✅ `SkillForge` 自然语言→爬虫 Skill | ✅ Skill Forge |
| **腾讯天御 Aegis** | ✅ **L2 实测通过**（69shuba、mp.weixin.qq.com） | ❌ 未验证 |
| **CloakBrowser 源码级反检测** | ✅ L3.5 58 个 C++ 补丁 | ✅ 类似方案 |
| **影刀 RPA** | ✅ L5 可选层级 | ❌ 无 |
| **Discuz! 论坛爬取** | ✅ 年龄确认自动点击 + 置顶帖过滤 | ❌ 无专门支持 |
| **费用** | 💯 **完全免费，零限制** | ⚠️ stealth 超 5 个付费，代理付费 |
| **平台兼容** | Windows 优先 | Windows/macOS/Linux |

**一句话总结：反爬能力不分伯仲，v5.1 新增 HTML 精简和 API 发现补齐最后短板。Crawler Stack 完全免费无限量，且在国内站点（Aegis/Discuz!/微信）上有独特优势。**

---

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
from crawler_stack_v5 import fetch, CompactMode, discover_api_endpoints

# 自动降级 — 引擎替你选择最快方案
result = fetch('https://example.com')
print(result.text)    # 干净的内容
print(result.method)  # 实际使用的层级

# HTML 精简模式 — 省 50-90% token
result = fetch('https://example.com', compact_mode='index')
print(result.compact)  # 分类索引，省 90% token

# API 端点发现 — 自动找出页面背后的 API
result = fetch('https://spa-site.com', discover_api=True)
print(result.api_endpoints)  # [{method, url, response_type, ...}]
```

### 🔐 验证码人机接力

```python
# 启用验证码检测模式
result = fetch('https://site-with-captcha.com', human_assist_mode=True)

if result.captcha_detected:
    print(f"🔐 检测到验证码: {result.method}")
    print(f"   截图: {result.captcha_screenshot}")
    # 通知用户手动通过验证码
    # 用户通过后重新获取
    result = fetch(url)
```

### 👥 多账号隔离

```python
from crawler_stack_v5 import Account, AccountConfig

acct1 = Account(AccountConfig(
    name='运营号1',
    proxy='socks5://127.0.0.1:1080',
    fingerprint_seed='fp-seed-1',
))
acct2 = Account(AccountConfig(
    name='运营号2',
    proxy='socks5://127.0.0.1:1081',
    fingerprint_seed='fp-seed-2',
))

# 两个账号完全隔离，互不干扰
r1 = acct1.fetch('https://example.com/login')
r2 = acct2.fetch('https://example.com/login')
```

### 🤖 Skill Forge — 自然语言→爬虫

```python
from crawler_stack_v5 import SkillForge

forge = SkillForge()
skill = forge.create(
    description="每天抓取小红书AI Agent关键词前20条笔记，含标题、点赞数、作者",
    site="https://www.xiaohongshu.com",
    probe=True,
)
skill.save()  # 保存为可复用的 Skill
print(f'生成的 Skill: {skill.name}')
print(f'数据字段: {skill.data_fields}')
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

| 站点 | 防护等级 | 攻破层级 | 耗时 | 备注 |
|------|---------|---------|------|------|
| **69shuba.tw** | 🔴 腾讯天御 Aegis + Cloudflare 双重防护 | L2 DrissionPage 正面突破 | ~3s | 国内最硬的反爬组合之一，直接拿下 |
| **mp.weixin.qq.com** | 🔴 腾讯天御 Aegis 企业级防护 | L1.1 cloudscraper 秒过 | ~2s | 微信公众平台防护，形同虚设 |
| **色花堂** | 🟠 年龄确认页 + Discuz! 论坛防护 | L2 自动点击确认秒过 | ~5s | 成人站点年龄验证，一键破防 |
| **browserscan.net** | 🔴 深度浏览器指纹检测（24 项指标） | L3.5 CloakBrowser 满分通过（NORMAL） | ~8s | 指纹检测界的照妖镜，完美伪装 |
| **deviceandbrowserinfo.com** | 🔴 行为检测 24 项全面扫描 | L3.5 CloakBrowser（0 true flags 满分） | ~8s | 行为检测全部归零，你就是真人 |
| **cloudflarestatus.com** | 🟡 Cloudflare CDN 基础防护 | L1 curl_cffi 秒杀 | ~0.3s | 热身级别的 |

### 检测分数（越高越好）

| 检测服务 | 普通 Playwright | **Crawler Stack** | 说明 |
|---------|----------------|-------------------|------|
| reCAPTCHA v3 | 0.1 🤖 妥妥的机器人 | **0.9 🧑 Google 都信了** | 从 bot 到人类的跨越 |
| Cloudflare Turnstile | ❌ 失败被拦 | ✅ **自动通过** | 连验证码都不用点 |
| FingerprintJS | ❌ 被拦截封号 | ✅ **完美通过** | 指纹检测形同虚设 |
| `navigator.webdriver` | `true` 直接暴露 | **`false` 完美隐藏** | 最基础的检测都过不了？不存在的 |
| TLS 指纹 | 不匹配被识别 | **与 Chrome 完全一致** | 网络层伪装到牙齿 |
| CDP 检测 | 被检测自动化 | **未被检测，你就是普通用户** | Chrome DevTools 协议痕迹全部消除 |

---

## 🧰 各层级详解

### L0 — Cookie 注入层 🍪
从 Netscape 格式文件或浏览器扩展导出的 JSON 列表加载 cookie，自动注入到所有后续层级。

```python
from crawler_stack_v5 import load_cookie_file, load_cookies_from_list

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
内置 JS2Py VM，真正**执行** Cloudflare 的 JavaScript 挑战，而不是假装。支持 v1/v2/v3 JS VM + Turnstile 全部挑战类型。

### L1.5 — DrissionPage Edge 用户数据复用 🔑
启动 Edge 浏览器的**真实用户数据目录**，自带所有登录态——微信、各平台、论坛……不需要重复登录。

### L2 — DrissionPage 独立实例 🕶️
**唯一已知能完整绕过腾讯天御 Aegis 的方案**。69shuba、微信公众平台等使用 Aegis 的站点实测通过。**v5 默认使用独立实例模式**，每次创建新浏览器实例，彻底消除 session 污染。

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

### L5 — 影刀 RPA 🤖
可选层级，通过 FastAPI 调用影刀自动化脚本处理复杂 GUI 流程（表单填写、文件上传、OAuth 扫码等）。

---

## 🆕 v5 新增模块详解

### 🔐 验证码检测 + 人机接力

```python
from crawler_stack_v5 import detect_captcha, HumanAssistSession, CaptchaType

# 手动检测验证码
captcha_type = detect_captcha(result.html)
if captcha_type != CaptchaType.NONE:
    print(f'检测到验证码: {captcha_type.value}')

# 精细控制人机接力
session = HumanAssistSession(
    url='https://example.com',
    captcha_type=CaptchaType.RECAPTCHA,
    screenshot_path='/path/to/screenshot.png',
)
msg = session.notify_user()  # 生成通知文本
# 用户手动通过后：
result = session.continue_fetch(page=some_page_object)
```

**支持的验证码类型**：
| 类型 | 检测关键词 | 
|------|-----------|
| Google reCAPTCHA | `g-recaptcha`, `recaptcha/api`, `data-sitekey` |
| Cloudflare Turnstile | `cf-turnstile`, `challenges.cloudflare.com` |
| 图片验证码 | `captcha-image`, `img_captcha`, `安全验证` |
| 滑块验证码 | `geetest`, `极验`, `滑块验证`, `nc_scale` |
| 短信验证码 | `sms-code`, `sms_verify`, `手机验证码输入` |

### 👥 多账号隔离体系

```python
from crawler_stack_v5 import Account, AccountManager

# 批量管理
mgr = AccountManager()
mgr.create_account('bot1', proxy='socks5://127.0.0.1:1080')
mgr.create_account('bot2', proxy='socks5://127.0.0.1:1081')

results = mgr.batch_fetch([
    ('https://site.com/page1', 'bot1'),
    ('https://site.com/page2', 'bot2'),
])
mgr.close_all()
```

每个 Account 的指纹用**种子哈希生成确定性偏移**，同一种子永远产生相同指纹（稳定身份），不同种子产生完全不同指纹（完全隔离）。覆盖 Canvas、WebGL、fonts、audio、plugins、languages 等所有指纹维度。

### 🤖 Skill Forge

```python
from crawler_stack_v5 import SkillForge

forge = SkillForge()
skill = forge.create(
    description="提取商品名称、价格、销量、评论数",
    site="https://shop.example.com",
    probe=True,
)
skill.save()  # 保存到 forge_skills/ 目录
print(f'数据字段: {skill.data_fields}')
print(f'自动探测的选择器: {skill.selectors}')
```

自动从自然语言中解析数据字段（如"标题、点赞数、作者" → `['title', 'likes', 'author']`），自动探测目标网站的分页模式，生成完整的 SKILL.md 文件。

---

## ⚠️ 已知局限（坦诚相告）

| 场景 | 原因 | 建议 |
|------|------|------|
| **微信 OAuth 扫码登录** | 需手机确认授权，纯 HTTP 无法模拟 | 用 L1.5 复用 Edge 登录态 |
| **Cloudflare Under Attack + reCAPTCHA** | 人类交互验证，非指纹问题 | 需手动通过后导出 cookie |

---

## 📦 项目结构

```text
crawler-stack/
├── crawler_stack_v5.py    # v5.1 主引擎（2100+ 行，九层降级 + HTML 精简 + API 发现 + 新模块）
├── crawler_stack_v4.py    # v4 旧版（保留兼容）
├── README.md              # 中文说明（就是本文件）
├── README_EN.md           # English version
├── LICENSE                # MIT
└── .gitignore
```

## 🤝 贡献

PR、Issues 都欢迎。如果 Crawler Stack 帮你解决了棘手的问题，点个 ⭐ 就是最好的支持！

## 📄 License

MIT — 随便用，随便改，保留版权声明即可。
