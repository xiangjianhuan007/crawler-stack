"""
爬虫栈 v4 — 四层自动降级爬虫引擎
==================================
针对 腾讯天御 Aegis / Cloudflare / SPA / OAuth 登录等反爬系统

层级：
  L0 - Cookie 注入层          — 从 cookie 文件注入到各层级请求
  L1 - curl_cffi              — 最快，模拟 TLS 指纹
  L1.1 - cloudscraper v3      — 专破 Cloudflare JS VM 挑战 + Turnstile
  L1.5 - DrissionPage (真实用户) — 复用 Edge 用户数据目录，自带登录态
  L2 - DrissionPage (无头)    — 中速，过浏览器指纹检测 + Aegis
  L2.5 - Edge 远程调试         — 通过 CDP 控制已登录的 Edge
  L3 - Playwright + anti-det  — 较重，JS 层反检测
  L3.5 - CloakBrowser         — 最重，Chromium 源码级反检测，过 Cloudflare 高级防护
  L4 - SPA 渲染增强           — 自动等待 JS 渲染、hash 路由、API 拦截

用法：
  from crawler_stack_v4 import fetch
  result = fetch('https://example.com')
  print(result.text)     # 文本内容
  print(result.status)   # 状态码
  print(result.method)   # 使用的层级
"""

import re
import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from http.cookiejar import MozillaCookieJar

logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================

EDGE_PATH = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
EDGE_USER_DATA = r'C:\Users\MI\AppData\Local\Microsoft\Edge\User Data'
DOWNLOAD_DIR = r'D:\HermesAgent\data\downloads'
COOKIE_DIR = r'D:\HermesAgent\data\cookies'

os.makedirs(COOKIE_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dataclass
class FetchResult:
    text: str
    status: int
    method: str  # 层级名称
    html: str = ''
    cookies: List[dict] = field(default_factory=list)
    video_urls: List[str] = field(default_factory=list)


# ============================================================
# L0: Cookie 注入层
# ============================================================

_COOKIE_JAR: Dict[str, List[dict]] = {}  # domain -> [{name, value, domain, path}]


def load_cookie_file(filepath: str) -> int:
    """
    从 Netscape cookie 文件加载 cookie。
    支持标准 Netscape 格式（curl -c 导出的格式）。
    
    Args:
        filepath: cookie 文件路径
    
    Returns:
        加载的 cookie 数量
    """
    global _COOKIE_JAR
    
    if not os.path.exists(filepath):
        logger.warning(f'[crawler_stack] Cookie file not found: {filepath}')
        return 0
    
    try:
        jar = MozillaCookieJar(filepath)
        jar.load(ignore_discard=True, ignore_expires=True)
        
        count = 0
        for c in jar:
            domain = c.domain
            if domain not in _COOKIE_JAR:
                _COOKIE_JAR[domain] = []
            _COOKIE_JAR[domain].append({
                'name': c.name,
                'value': c.value,
                'domain': c.domain,
                'path': c.path,
                'secure': c.secure,
                'expires': c.expires,
            })
            count += 1
        
        logger.info(f'[crawler_stack] L0: Loaded {count} cookies from {filepath}')
        return count
    except Exception as e:
        logger.warning(f'[crawler_stack] L0: Failed to load cookies: {e}')
        return 0


def load_cookies_from_list(cookies: List[dict]) -> int:
    """
    从 cookie 字典列表加载（从浏览器扩展导出格式）。
    
    Args:
        cookies: [{domain, name, value, ...}, ...]
    
    Returns:
        加载的 cookie 数量
    """
    global _COOKIE_JAR
    
    count = 0
    for c in cookies:
        domain = c.get('domain', '')
        if not domain:
            continue
        # 标准化域名
        if not domain.startswith('.'):
            domain = '.' + domain
        if domain not in _COOKIE_JAR:
            _COOKIE_JAR[domain] = []
        _COOKIE_JAR[domain].append({
            'name': c.get('name', ''),
            'value': c.get('value', ''),
            'domain': domain,
            'path': c.get('path', '/'),
            'secure': c.get('secure', False),
            'expires': c.get('expirationDate', 0),
        })
        count += 1
    
    logger.info(f'[crawler_stack] L0: Loaded {count} cookies from list')
    return count


def _inject_cookies_into_curl(url: str) -> str:
    """
    为 curl 请求生成 Cookie header 值。
    匹配 URL 域名对应的所有 cookie。
    """
    global _COOKIE_JAR
    
    if not _COOKIE_JAR:
        return ''
    
    # 提取域名
    m = re.search(r'https?://([^/]+)', url)
    if not m:
        return ''
    host = m.group(1)
    
    # 收集匹配的 cookie
    matched = []
    for domain, cookies in _COOKIE_JAR.items():
        # 域名匹配：cookie 域是 .example.com，host 是 sub.example.com 或 example.com
        clean_domain = domain.lstrip('.')
        if host == clean_domain or host.endswith('.' + clean_domain):
            for c in cookies:
                matched.append(f"{c['name']}={c['value']}")
    
    return '; '.join(matched)


def _inject_cookies_into_drission(page, url: str):
    """
    将已加载的 cookie 注入到 DrissionPage 页面。
    """
    global _COOKIE_JAR
    
    if not _COOKIE_JAR:
        return
    
    m = re.search(r'https?://([^/]+)', url)
    if not m:
        return
    host = m.group(1)
    
    for domain, cookies in _COOKIE_JAR.items():
        clean_domain = domain.lstrip('.')
        if host == clean_domain or host.endswith('.' + clean_domain):
            for c in cookies:
                try:
                    page.run_js(f"""
                    document.cookie = "{c['name']}={c['value']}; path={c.get('path', '/')}; domain={c.get('domain', '')}";
                    """)
                except Exception:
                    pass


# ============================================================
# L1: curl_cffi — 最快，过 Cloudflare JS 挑战
# ============================================================

def _fetch_curl_cffi(url: str, timeout: int = 15) -> Optional[FetchResult]:
    """curl_cffi with Chrome impersonation + cookie 注入。"""
    try:
        from curl_cffi import requests
        
        headers = {}
        cookie_str = _inject_cookies_into_curl(url)
        if cookie_str:
            headers['Cookie'] = cookie_str
        
        r = requests.get(url, impersonate='chrome131', timeout=timeout, headers=headers)
        text = r.text
        
        # Check if it's real content (not Cloudflare challenge)
        if len(text) > 500 and 'verify' not in text.lower()[:2000] and 'Ray ID' not in text:
            return FetchResult(
                text=_strip_html(text),
                status=r.status_code,
                method='L1-curl_cffi',
                html=text,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L1 curl_cffi failed: {e}')
        return None


# ============================================================
# L1.1: cloudscraper v3 — 专破 Cloudflare JS VM + Turnstile
# ============================================================

def _fetch_cloudscraper(url: str, timeout: int = 20) -> Optional[FetchResult]:
    """
    cloudscraper v3 — 内置 JS2Py VM 执行 Cloudflare JS 挑战。
    
    相比 curl_cffi（只模拟 TLS 指纹），cloudscraper 能：
    - 执行 Cloudflare v3 JS VM 挑战（最新的 JS 加密挑战）
    - 自动处理 Cloudflare Turnstile
    - 支持所有 Cloudflare 挑战类型（v1/v2/v3/Turnstile）
    
    注意：遇到 Cloudflare Under Attack 模式 + reCAPTCHA 时仍然会超时，
    需要降级到 L3.5 CloakBrowser 或 L2 DrissionPage。
    """
    try:
        import cloudscraper
        
        scraper = cloudscraper.create_scraper(
            interpreter='js2py',  # 用 js2py 执行 JS 挑战
            debug=False,
        )
        
        # 注入 cookie（如果有）
        headers = {}
        cookie_str = _inject_cookies_into_curl(url)
        if cookie_str:
            headers['Cookie'] = cookie_str
        
        r = scraper.get(url, timeout=timeout, headers=headers)
        text = r.text
        
        # 检测是否真的过了 Cloudflare
        if len(text) > 500 and 'Ray ID' not in text[:2000]:
            return FetchResult(
                text=_strip_html(text),
                status=r.status_code,
                method='L1.1-cloudscraper',
                html=text,
            )
        return None
    except ImportError:
        logger.warning('[crawler_stack] L1.1 cloudscraper not installed. Run: pip install cloudscraper')
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L1.1 cloudscraper failed: {e}')
        return None


# ============================================================
# L1.5: DrissionPage (真实用户数据) — 复用 Edge 登录态
# ============================================================

_DRISSION_USER_BROWSER = None

def _get_drission_user() -> Optional[Any]:
    """
    用 Edge 真实用户数据目录启动 DrissionPage。
    复用用户已有的所有登录态（微信、各平台等）。
    
    注意：当 Edge 已有窗口在运行时会冲突，
    需要先关掉其他 Edge 窗口或使用不同的端口。
    """
    global _DRISSION_USER_BROWSER
    
    if _DRISSION_USER_BROWSER is not None:
        return _DRISSION_USER_BROWSER
    
    try:
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_user_data_path(EDGE_USER_DATA)
        co.auto_port()
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-features=PrivacySandboxSettings4')
        co.set_argument('--disable-gpu')
        co.set_argument('--window-size=1280,720')
        co.headless(True)
        
        _DRISSION_USER_BROWSER = Chromium(co)
        logger.info('[crawler_stack] L1.5: DrissionPage (user data) started')
        return _DRISSION_USER_BROWSER
    except Exception as e:
        logger.warning(f'[crawler_stack] L1.5: Failed to start DrissionPage with user data: {e}')
        return None


def _fetch_drission_user(url: str, wait_seconds: int = 8) -> Optional[FetchResult]:
    """
    用 Edge 真实用户数据获取页面。
    适合需要登录态的站点（如课程平台、论坛等）。
    """
    try:
        browser = _get_drission_user()
        if browser is None:
            return None
        
        page = browser.latest_tab
        page.get(url)
        page.wait(wait_seconds)
        time.sleep(3)
        
        # 检测是否跳转到登录页（Spa 登录态失效的情况）
        current_url = page.url
        if 'login' in current_url.lower() or 'qrLogin' in current_url:
            # 尝试设置 hash 路由（Spa 应用）
            if '#' in url:
                hash_part = url.split('#', 1)[1]
                if hash_part:
                    page.run_js(f"window.location.hash = '{hash_part}'")
                    time.sleep(5)
            
            current_url2 = page.url
            if 'login' in current_url2.lower() or 'qrLogin' in current_url2:
                logger.warning('[crawler_stack] L1.5: Still on login page, login state not available')
                # 不返回 None，返回页面内容让上层判断
                html = page.html
                if html and len(html) > 200:
                    return FetchResult(
                        text=_strip_html(html),
                        status=200,
                        method='L1.5-drission-user',
                        html=html,
                    )
                return None
        
        html = page.html
        if html and len(html) > 200:
            return FetchResult(
                text=_strip_html(html),
                status=200,
                method='L1.5-drission-user',
                html=html,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L1.5 DrissionPage (user) failed: {e}')
        return None


# ============================================================
# L2: DrissionPage (无头) — 原爬虫栈的 L2
# ============================================================

_DRISSION_BROWSER = None


def _get_drission():
    global _DRISSION_BROWSER
    if _DRISSION_BROWSER is None:
        from DrissionPage import Chromium, ChromiumOptions
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.headless(True)
        _DRISSION_BROWSER = Chromium(co)
    return _DRISSION_BROWSER


def _fetch_drission(url: str, wait_seconds: int = 5) -> Optional[FetchResult]:
    """DrissionPage 无头模式 — 反检测最强，适合过 Aegis。"""
    try:
        browser = _get_drission()
        page = browser.latest_tab
        page.get(url)
        page.wait(wait_seconds)
        time.sleep(2)
        
        # 检测是否有年龄确认页
        try:
            for _try_text in ['满18岁', 'please click here', '我已成年', '进入网站', 'Enter']:
                try:
                    _btn = page.ele(f'tag:a@@text():{_try_text}', timeout=1)
                    if _btn:
                        logger.info(f'[crawler_stack] 检测到年龄确认页，点击"{_try_text}"...')
                        _btn.click()
                        time.sleep(3)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        html = page.html
        if html and len(html) > 200:
            return FetchResult(
                text=_strip_html(html),
                status=200,
                method='L2-drission',
                html=html,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L2 DrissionPage failed: {e}')
        return None


# ============================================================
# L2.5: Edge 远程调试 — 通过 CDP 控制已登录的 Edge
# ============================================================

def _fetch_edge_remote(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """
    通过 Edge 远程调试端口控制已登录的 Edge 浏览器。
    需要 Edge 以 --remote-debugging-port=9222 启动。
    
    检测流程：
    1. 检查 localhost:9222 是否有 Edge 实例
    2. 打开新标签页导航到目标 URL
    3. 等待页面加载，获取 HTML
    4. 关闭标签页
    """
    import urllib.request
    import json as _json
    
    try:
        # 1. 检测 Edge 远程调试
        req = urllib.request.Request('http://localhost:9222/json/version')
        resp = urllib.request.urlopen(req, timeout=5)
        info = _json.loads(resp.read())
        logger.info(f'[crawler_stack] L2.5: Edge remote debugging detected')
        
        # 2. 打开新标签页
        req2 = urllib.request.Request(
            f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe="")}',
            method='PUT'
        )
        resp2 = urllib.request.urlopen(req2, timeout=5)
        tab = _json.loads(resp2.read())
        tab_id = tab['id']
        ws_url = tab['webSocketDebuggerUrl']
        
        # 3. 通过 CDP 等待页面加载
        try:
            from websocket import create_connection
            ws = create_connection(ws_url, timeout=10)
            
            # Page.enable
            ws.send(_json.dumps({'id': 1, 'method': 'Page.enable'}))
            ws.recv()
            
            # 等待页面加载
            time.sleep(5)
            
            # 获取页面 HTML
            ws.send(_json.dumps({
                'id': 2, 'method': 'Runtime.evaluate',
                'params': {'expression': 'document.documentElement.outerHTML'}
            }))
            resp3 = _json.loads(ws.recv())
            html = resp3.get('result', {}).get('result', {}).get('value', '')
            
            # 获取页面 URL
            ws.send(_json.dumps({
                'id': 3, 'method': 'Runtime.evaluate',
                'params': {'expression': 'window.location.href'}
            }))
            resp4 = _json.loads(ws.recv())
            current_url = resp4.get('result', {}).get('result', {}).get('value', '')
            
            # 获取 cookie
            ws.send(_json.dumps({
                'id': 4, 'method': 'Runtime.evaluate',
                'params': {'expression': 'document.cookie'}
            }))
            resp5 = _json.loads(ws.recv())
            cookies_str = resp5.get('result', {}).get('result', {}).get('value', '')
            
            ws.close()
            
            # 4. 关闭标签页
            try:
                req_close = urllib.request.Request(
                    f'http://localhost:9222/json/close/{tab_id}',
                    method='PUT'
                )
                urllib.request.urlopen(req_close, timeout=3)
            except Exception:
                pass
            
            if html and len(html) > 200:
                # 把 cookie 保存到全局，后续请求可用
                if cookies_str:
                    parsed = []
                    for pair in cookies_str.split(';'):
                        if '=' in pair:
                            name, value = pair.split('=', 1)
                            parsed.append({'name': name.strip(), 'value': value.strip()})
                    if parsed:
                        load_cookies_from_list(parsed)
                
                return FetchResult(
                    text=_strip_html(html),
                    status=200,
                    method='L2.5-edge-remote',
                    html=html,
                    cookies=parsed if cookies_str else [],
                )
            
        except Exception as e:
            logger.debug(f'[crawler_stack] L2.5 CDP failed: {e}')
            # 尝试关闭标签页
            try:
                req_close = urllib.request.Request(
                    f'http://localhost:9222/json/close/{tab_id}',
                    method='PUT'
                )
                urllib.request.urlopen(req_close, timeout=3)
            except Exception:
                pass
        
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L2.5 Edge remote failed: {e}')
        return None


# ============================================================
# L3: Playwright — 兜底
# ============================================================

def _fetch_playwright(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """Playwright with anti-detection init script + cookie 注入。"""
    try:
        import asyncio
        from playwright.async_api import async_playwright

        async def _run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    executable_path=EDGE_PATH,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    locale='zh-CN',
                )
                await context.add_init_script('''
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                ''')
                
                # 注入 cookie
                cookie_str = _inject_cookies_into_curl(url)
                if cookie_str:
                    # Playwright 的 add_cookies 需要特定格式
                    m = re.search(r'https?://([^/]+)', url)
                    if m:
                        host = m.group(1)
                        for pair in cookie_str.split('; '):
                            if '=' in pair:
                                name, value = pair.split('=', 1)
                                try:
                                    await context.add_cookies([{
                                        'name': name.strip(),
                                        'value': value.strip(),
                                        'domain': host,
                                        'path': '/',
                                    }])
                                except Exception:
                                    pass
                
                page = await context.new_page()
                resp = await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                s = resp.status if resp else 0
                await browser.close()
                if html and len(html) > 200:
                    return FetchResult(
                        text=_strip_html(html),
                        status=s,
                        method='L3-playwright',
                        html=html,
                    )
                return None

        return asyncio.run(_run())
    except Exception as e:
        logger.debug(f'[crawler_stack] L3 Playwright failed: {e}')
        return None


# ============================================================
# L3.5: CloakBrowser — 源码级反检测，过 Cloudflare 高级防护
# ============================================================

def _fetch_cloakbrowser(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """
    CloakBrowser — 基于 Chromium 源码级补丁的反检测浏览器。
    
    58 个 C++ 源码补丁，覆盖 canvas/WebGL/audio/fonts/GPU/screen/WebRTC/TLS，
    reCAPTCHA v3 得分 0.9，Cloudflare Turnstile 全通过，FingerprintJS 不拦截。
    
    适用场景：
    - Cloudflare 高级防护（Under Attack 模式）
    - reCAPTCHA v3/v3 Enterprise
    - DataDome / Akamai / Kasada 等强风控
    - 当前 L1-L3 全部失败的高防站点
    
    需要先安装：npm install -g cloakbrowser
    二进制自动下载到 ~/.cloakbrowser/（首次运行约 535MB）
    """
    try:
        from cloakbrowser import launch
        
        browser = launch(
            headless=True,
            humanize=True,  # 真人行为模拟（贝塞尔曲线鼠标、逐字输入、随机延时）
            timeout=timeout * 1000,
        )
        page = browser.new_page()
        
        # 注入 cookie（如果有）
        cookie_str = _inject_cookies_into_curl(url)
        if cookie_str:
            m = re.search(r'https?://([^/]+)', url)
            if m:
                host = m.group(1)
                context = browser.contexts[0] if browser.contexts else None
                if context:
                    for pair in cookie_str.split('; '):
                        if '=' in pair:
                            name, value = pair.split('=', 1)
                            try:
                                context.add_cookies([{
                                    'name': name.strip(),
                                    'value': value.strip(),
                                    'domain': host,
                                    'path': '/',
                                }])
                            except Exception:
                                pass
        
        resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
        page.wait_for_timeout(3000)  # 等 JS 渲染
        html = page.content()
        s = resp.status if resp else 0
        browser.close()
        
        if html and len(html) > 200:
            return FetchResult(
                text=_strip_html(html),
                status=s,
                method='L3.5-cloakbrowser',
                html=html,
            )
        return None
    except ImportError:
        logger.warning('[crawler_stack] L3.5 CloakBrowser not installed. Run: pip install cloakbrowser')
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L3.5 CloakBrowser failed: {e}')
        return None


# ============================================================
# L4: SPA 渲染增强
# ============================================================

def _enhance_spa(
    url: str,
    wait_for_selector: Optional[str] = None,
    hash_route: Optional[str] = None,
    intercept_api: bool = False,
    timeout: int = 30,
) -> Optional[FetchResult]:
    """
    SPA 页面增强渲染。
    
    专门处理单页应用的场景：
    - 等待 JS 渲染完成
    - 注入 hash 路由
    - 拦截 XHR/fetch 请求获取 API 数据
    - 检测页面是否真正加载完成
    
    Args:
        url: 目标 URL
        wait_for_selector: 等待某个 CSS 选择器出现（如 '.course-content'）
        hash_route: 手动指定 hash 路由（如 '#/course/video?courseId=123'）
        intercept_api: 是否拦截 API 请求
        timeout: 超时秒数
    """
    try:
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-features=PrivacySandboxSettings4')
        co.headless(True)
        
        browser = Chromium(co)
        page = browser.latest_tab
        
        # 先导航到基本 URL
        base_url = url.split('#')[0] if '#' in url else url
        page.get(base_url)
        page.wait(3)
        
        # 注入 hash 路由（如果有）
        if hash_route:
            page.run_js(f"window.location.hash = '{hash_route}'")
            time.sleep(5)
        elif '#' in url:
            hash_part = url.split('#', 1)[1]
            page.run_js(f"window.location.hash = '{hash_part}'")
            time.sleep(5)
        
        # 等待指定元素出现
        if wait_for_selector:
            try:
                page.ele(wait_for_selector, timeout=timeout)
            except Exception:
                pass
        
        # 额外等待 JS 完全渲染
        time.sleep(3)
        
        # 检测页面是否真的加载了（不是空白登录页）
        title = page.run_js("document.title")
        body_text = page.run_js("(document.body.innerText || '').length")
        
        logger.info(f'[crawler_stack] L4 SPA: title="{title}", body_len={body_text}')
        
        # 拦截 API 请求（获取视频地址等）
        api_data = []
        if intercept_api:
            try:
                # 获取所有资源请求中的 API 调用
                api_data_raw = page.run_js("""
                (function() {
                    try {
                        return JSON.stringify(
                            performance.getEntriesByType('resource')
                                .filter(e => e.name.includes('/api/') || e.name.includes('course') || e.name.includes('video'))
                                .map(e => ({url: e.name, type: e.initiatorType}))
                        );
                    } catch(e) { return '[]'; }
                })()
                """)
                if api_data_raw and api_data_raw != '[]':
                    api_data = json.loads(api_data_raw)
            except Exception:
                pass
        
        html = page.html
        browser.quit()
        
        if html and len(html) > 500:  # SPA 页面通常比普通页面大
            result = FetchResult(
                text=_strip_html(html),
                status=200,
                method='L4-spa',
                html=html,
            )
            if api_data:
                result.video_urls = [
                    e['url'] for e in api_data 
                    if 'm3u8' in e['url'] or 'mp4' in e['url'] or 'video' in e['url']
                ]
            return result
        
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack] L4 SPA failed: {e}')
        return None


# ============================================================
# 视频地址提取
# ============================================================

def extract_video_urls(html: str) -> List[str]:
    """
    从 HTML 中提取视频地址。
    支持 m3u8、mp4、flv 等格式。
    """
    urls = []
    
    # 在页面文本中搜
    patterns = [
        r'https?://[^\s"\'<>]*(?:m3u8)[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.mp4[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.flv[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.ts[^\s"\'<>]*',
    ]
    
    for pattern in patterns:
        found = re.findall(pattern, html)
        urls.extend(found)
    
    # 在 JS 变量中搜 videoUrl/playUrl
    js_patterns = [
        r'["\'](videoUrl|playUrl|video_url|play_url)["\']\s*[:=]\s*["\']([^"\']+)["\']',
        r'["\'](url|src)["\']\s*[:=]\s*["\']([^"\']*m3u8[^"\']*)["\']',
        r'["\'](url|src)["\']\s*[:=]\s*["\']([^"\']*\.mp4[^"\']*)["\']',
    ]
    
    for pattern in js_patterns:
        found = re.findall(pattern, html)
        for f in found:
            if len(f) >= 2 and f[1].startswith('http'):
                urls.append(f[1])
    
    return list(set(urls))  # 去重


# ============================================================
# 入口：自动降级
# ============================================================

def fetch(
    url: str,
    timeout: int = 30,
    skip_l1: bool = False,
    skip_l11: bool = False,
    skip_l15: bool = False,
    skip_l2: bool = False,
    skip_l25: bool = False,
    skip_l3: bool = False,
    skip_l35: bool = False,
    skip_l4: bool = False,
    use_user_data: bool = True,
    wait_for_selector: Optional[str] = None,
    hash_route: Optional[str] = None,
    intercept_api: bool = False,
) -> FetchResult:
    """
    获取网页内容，自动降级。
    
    降级顺序：L1 -> L1.1 -> L1.5 -> L2 -> L2.5 -> L3 -> L3.5 -> L4
    
    L1.1 cloudscraper v3：专破 Cloudflare JS VM 挑战 / Turnstile
    L3.5 CloakBrowser：Chromium 源码级反检测，过深度设备指纹
    
    Args:
        url: 目标 URL
        timeout: 超时秒数
        skip_l1: 跳过 L1 curl_cffi
        skip_l11: 跳过 L1.1 cloudscraper
        skip_l15: 跳过 L1.5 DrissionPage (user data)
        skip_l2: 跳过 L2 DrissionPage (headless)
        skip_l25: 跳过 L2.5 Edge remote debugging
        skip_l3: 跳过 L3 Playwright
        skip_l35: 跳过 L3.5 CloakBrowser
        skip_l4: 跳过 L4 SPA
        use_user_data: 是否尝试复用 Edge 用户数据（默认 True）
        wait_for_selector: SPA 等待指定元素出现
        hash_route: SPA hash 路由
        intercept_api: 是否拦截 API 请求
    """
    result = None
    
    # L1: curl_cffi（最快）
    if not skip_l1:
        result = _fetch_curl_cffi(url, min(timeout, 15))
        if result:
            logger.info(f'[crawler_stack] ✅ L1 curl_cffi: {url}')
            return result
    
    # L1.1: cloudscraper v3 — 专破 Cloudflare JS VM + Turnstile
    if not skip_l11:
        result = _fetch_cloudscraper(url, min(timeout, 20))
        if result:
            logger.info(f'[crawler_stack] ✅ L1.1 cloudscraper: {url}')
            return result
    
    # L1.5: DrissionPage (user data) — 复用登录态
    if not skip_l15 and use_user_data:
        result = _fetch_drission_user(url, min(timeout // 2, 8))
        if result:
            logger.info(f'[crawler_stack] ✅ L1.5 DrissionPage (user): {url}')
            return result
    
    # L2: DrissionPage (headless)
    if not skip_l2:
        result = _fetch_drission(url, min(timeout // 2, 5))
        if result:
            logger.info(f'[crawler_stack] ✅ L2 DrissionPage: {url}')
            return result
    
    # L2.5: Edge remote debugging
    if not skip_l25:
        result = _fetch_edge_remote(url, timeout)
        if result:
            logger.info(f'[crawler_stack] ✅ L2.5 Edge remote: {url}')
            return result
    
    # L3: Playwright
    if not skip_l3:
        result = _fetch_playwright(url, timeout)
        if result:
            logger.info(f'[crawler_stack] ✅ L3 Playwright: {url}')
            return result
    
    # L3.5: CloakBrowser — 源码级反检测，过 Cloudflare 高级防护
    if not skip_l35:
        result = _fetch_cloakbrowser(url, timeout)
        if result:
            logger.info(f'[crawler_stack] ✅ L3.5 CloakBrowser: {url}')
            return result
    
    # L4: SPA 增强
    if not skip_l4:
        result = _enhance_spa(
            url,
            wait_for_selector=wait_for_selector,
            hash_route=hash_route,
            intercept_api=intercept_api,
            timeout=timeout,
        )
        if result:
            logger.info(f'[crawler_stack] ✅ L4 SPA: {url}')
            return result
    
    raise RuntimeError(f'All layers failed for {url}')


# ============================================================
# 工具函数
# ============================================================

def _strip_html(html: str) -> str:
    """Remove HTML tags, normalize whitespace."""
    import html as html_mod
    
    text = html

    # 1. 提取微信文章 JS 变量
    m = re.search(r'var msg_title = "([^"]+)"', text)
    wx_title = m.group(1) if m else ''
    m = re.search(r'var content_htm = "([^"]*)"', text)
    wx_content = ''
    if m:
        raw = m.group(1)
        raw = raw.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
        wx_content = html_mod.unescape(raw)
        wx_content = re.sub(r'<[^>]+>', '', wx_content)
        wx_content = re.sub(r'\s+', ' ', wx_content).strip()
    
    # 2. 删 style/script
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    
    # 3. 去 HTML 标签
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()
    
    # 4. js_content div 提取
    m = re.search(r'id="js_content"[^>]*>([\s\S]*?)</div>\s*<script', html)
    if m:
        js_text = html_mod.unescape(m.group(1))
        js_text = re.sub(r'<[^>]+>', '', js_text)
        js_text = re.sub(r'\s+', ' ', js_text).strip()
        if len(js_text) > len(text) * 0.5:
            wx_content = js_text
            for pat in [
                r'id="activity-name"[^>]*>([\s\S]*?)</h',
                r'class="rich_media_title[^"]*"[^>]*>([\s\S]*?)</h',
                r'class="rich_media_title[^"]*"[^>]*>([\s\S]*?)</div>',
            ]:
                tm = re.search(pat, html)
                if tm:
                    wx_title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
                    wx_title = html_mod.unescape(wx_title)
                    wx_title = re.sub(r'\s+', ' ', wx_title).strip()
                    break
    
    if wx_content and len(wx_content) > 100:
        if wx_title:
            return f'{wx_title}\n\n{wx_content}'
        return wx_content
    
    # 5. 兜底
    for container_id in ['article', 'content', 'main', 'post', 'page-content']:
        m = re.search(rf'id=[\'"]{container_id}[\'"][^>]*>([\s\S]*?)</div>', html)
        if m:
            c = re.sub(r'<[^>]+>', '', m.group(1))
            c = html_mod.unescape(c)
            c = re.sub(r'\s+', ' ', c).strip()
            if len(c) > 100:
                return c
    
    return text


def extract_chapter_links(html: str, book_path: str = '') -> list:
    """从 HTML 中提取小说章节链接。"""
    links = re.findall(
        r'<a[^>]*href=[\'"]([^\'"]*/read/\d+/\d+)[\'"][^>]*>([^<]+)</a>',
        html,
    )
    result = []
    seen = set()
    for href, text in links:
        text = text.strip()
        if text and text not in seen and len(text) < 80:
            seen.add(text)
            result.append({
                'title': text,
                'url': href if href.startswith('http') else f'https://69shuba.tw{href}',
            })
    return result


def extract_book_info(html: str) -> Dict[str, str]:
    """从小说详情页提取书名、作者等信息。"""
    info = {}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    if m:
        info['title'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'作者[：:]\s*([^<\n]+)', html)
    if m:
        info['author'] = m.group(1).strip()
    m = re.search(r'简介[：:]\s*([^<]+)', html)
    if m:
        info['description'] = m.group(1).strip()
    return info


# ============================================================
# CLI 测试
# ============================================================

if __name__ == '__main__':
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://mp.weixin.qq.com'
    
    skip_l1 = '--skip-l1' in sys.argv
    skip_l11 = '--skip-l11' in sys.argv
    skip_l15 = '--skip-l15' in sys.argv
    skip_l2 = '--skip-l2' in sys.argv
    skip_l25 = '--skip-l25' in sys.argv
    skip_l3 = '--skip-l3' in sys.argv
    skip_l35 = '--skip-l35' in sys.argv
    skip_l4 = '--skip-l4' in sys.argv
    
    cookie_file = None
    for i, arg in enumerate(sys.argv):
        if arg == '--cookie' and i + 1 < len(sys.argv):
            cookie_file = sys.argv[i + 1]
    
    if cookie_file:
        count = load_cookie_file(cookie_file)
        print(f'Loaded {count} cookies from {cookie_file}')
    
    hash_route = None
    for i, arg in enumerate(sys.argv):
        if arg == '--hash' and i + 1 < len(sys.argv):
            hash_route = sys.argv[i + 1]
    
    result = fetch(
        url,
        skip_l1=skip_l1,
        skip_l11=skip_l11,
        skip_l15=skip_l15,
        skip_l2=skip_l2,
        skip_l25=skip_l25,
        skip_l3=skip_l3,
        skip_l35=skip_l35,
        skip_l4=skip_l4,
        hash_route=hash_route,
    )
    print(f'Method: {result.method}')
    print(f'Status: {result.status}')
    print(f'Text ({len(result.text)} chars):')
    print(result.text[:500])
    if result.video_urls:
        print(f'Video URLs: {result.video_urls}')
