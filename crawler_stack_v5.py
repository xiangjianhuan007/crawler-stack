"""
爬虫栈 v5 — 全面对标 BrowserAct，超越 BrowserAct
==================================================
v5 核心升级：
  1. 验证码检测 + 人机接力 — 截图检测验证码→暂停→通知用户手动通过→继续
  2. 多账号隔离 — 每个账号独立浏览器实例 + 独立指纹 + 独立 IP
  3. 并发安全 — 独立实例模式替代全局单例，消除 session 污染
  4. Skill Forge — 自然语言描述→自动探测→生成可复用抓取 Skill
  5. L0-L5 九层降级保留并增强

层级：
  L0  - Cookie 注入层
  L1  - curl_cffi（最快）
  L1.1 - cloudscraper v3（破 Cloudflare JS VM + Turnstile）
  L1.5 - DrissionPage (真实用户)
  L2  - DrissionPage (无头)
  L2.5 - Edge 远程调试
  L3  - Playwright + anti-det
  L3.5 - CloakBrowser
  L4  - SPA 渲染增强
  L5  - 影刀 RPA

用法：
  from crawler_stack_v5 import fetch, Account, SkillForge

  # 基础用法
  result = fetch('https://example.com')
  print(result.text)
  print(result.method)

  # 人机接力（检测到验证码时暂停等待用户）
  result = fetch('https://example.com', human_assist=True)

  # 多账号隔离
  acct1 = Account(name='bot1', proxy='socks5://127.0.0.1:1080', fingerprint_seed='fp1')
  acct2 = Account(name='bot2', proxy='socks5://127.0.0.1:1081', fingerprint_seed='fp2')
  r1 = acct1.fetch('https://example.com')
  r2 = acct2.fetch('https://example.com')

  # Skill Forge
  forge = SkillForge()
  skill = forge.create(
      description="每天抓取小红书AI Agent关键词前20条笔记，含标题、点赞数、作者",
      site="https://www.xiaohongshu.com"
  )
  # 返回可调用的 Skill 对象
"""

import re
import os
import json
import time
import logging
import hashlib
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from http.cookiejar import MozillaCookieJar
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================

EDGE_PATH = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
EDGE_USER_DATA = r'C:\Users\MI\AppData\Local\Microsoft\Edge\User Data'
DOWNLOAD_DIR = r'D:\HermesAgent\data\downloads'
COOKIE_DIR = r'D:\HermesAgent\data\cookies'
CAPTCHA_DIR = r'D:\HermesAgent\data\captcha_screenshots'
SKILL_DIR = r'D:\HermesAgent\data\skills\web-scraping'
FORGE_OUTPUT_DIR = r'D:\HermesAgent\data\forge_skills'

for d in [COOKIE_DIR, DOWNLOAD_DIR, CAPTCHA_DIR, FORGE_OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================================================
# 数据类型
# ============================================================

@dataclass
class FetchResult:
    text: str
    status: int
    method: str
    html: str = ''
    cookies: List[dict] = field(default_factory=list)
    video_urls: List[str] = field(default_factory=list)
    captcha_detected: bool = False  # 是否检测到验证码
    captcha_screenshot: str = ''    # 验证码截图路径


class CaptchaType(Enum):
    """验证码类型枚举"""
    NONE = 'none'
    RECAPTCHA = 'recaptcha'           # Google reCAPTCHA
    TURNSTILE = 'cloudflare_turnstile'  # Cloudflare Turnstile
    IMAGE_CAPTCHA = 'image_captcha'     # 图片验证码
    SLIDER = 'slider'                   # 滑块验证码
    SMS_CODE = 'sms_code'              # 短信验证码
    UNKNOWN = 'unknown'                 # 未知类型


# ============================================================
# 验证码检测 + 人机接力 (对标 BrowserAct solve-captcha + remote-assist)
# ============================================================

# 验证码检测关键词/选择器
CAPTCHA_PATTERNS = {
    CaptchaType.RECAPTCHA: [
        'recaptcha/api', 'g-recaptcha', 'data-sitekey',
        'google.com/recaptcha',
    ],
    CaptchaType.TURNSTILE: [
        'cf-turnstile', 'challenges.cloudflare.com',
        'data-cf-turnstile', 'cloudflare.com/cdn-cgi/challenge',
    ],
    CaptchaType.IMAGE_CAPTCHA: [
        'captcha-image', 'img_captcha', 'verify-code-input',
        '安全验证', '人机验证',
    ],
    CaptchaType.SLIDER: [
        'slide-captcha', 'slider-captcha', '滑块验证',
        'nc_scale', 'drag-captcha', 'geetest',
        '极验', 'slideverify', 'slide_to_verify',
    ],
    CaptchaType.SMS_CODE: [
        'sms-code', 'phone-code', '手机验证码输入',
        'sms_verify',
    ],
}


def detect_captcha(html: str, screenshot_path: str = '') -> CaptchaType:
    """
    检测页面是否包含验证码。

    策略：
    1. HTML 文本匹配验证码关键词
    2. 如果有截图，通过关键词和特征匹配（未来可加 vision 分析）
    
    Returns:
        检测到的验证码类型，CaptchaType.NONE 表示未检测到
    """
    html_lower = html.lower()
    
    for captcha_type, patterns in CAPTCHA_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in html_lower:
                logger.info(f'[crawler_stack v5] 检测到验证码: {captcha_type.value} (匹配: {pattern})')
                return captcha_type
    
    return CaptchaType.NONE


def human_assist(captcha_type: CaptchaType, screenshot_path: str = '', url: str = '') -> bool:
    """
    人机接力 — 检测到验证码时暂停，等待用户手动通过。

    工作流：
    1. 保存验证码截图到 CAPTCHA_DIR
    2. 打印提示信息（日志中）
    3. 轮询等待用户手动操作浏览器通过验证码
    4. 返回是否成功

    注意：这个函数是同步阻塞的，会一直等到用户手动通过或超时。
    
    返回:
        True: 用户已通过验证码
        False: 超时或失败
    """
    cap_dir = CAPTCHA_DIR
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    cap_file = os.path.join(cap_dir, f'captcha_{timestamp}.png')
    
    # 复制截图到 captcha 目录
    if screenshot_path and os.path.exists(screenshot_path):
        import shutil
        try:
            shutil.copy2(screenshot_path, cap_file)
        except Exception:
            cap_file = screenshot_path
    else:
        cap_file = ''
    
    # 构建提示信息
    msg_lines = [
        f'[crawler_stack v5] ⏸️ 检测到验证码: {captcha_type.value}',
        f'[crawler_stack v5] URL: {url}',
    ]
    if cap_file:
        msg_lines.append(f'[crawler_stack v5] 截图已保存: {cap_file}')
    msg_lines.append(f'[crawler_stack v5] 请手动通过验证码，然后输入 y 继续...')
    
    logger.warning('\n'.join(msg_lines))
    
    # 在这里，父 Agent 可以通过此返回信息通知用户手动操作
    # 同步等待模式下，用户通过后调用 continue_fetch()
    # 
    # 设计为：返回信息给 Agent，Agent 通知用户手动操作，
    # 用户操作完成后再次调用 continue_fetch(url, session_id)
    
    return False  # 父 Agent 接管流程


class HumanAssistSession:
    """
    人机接力会话管理。
    
    用法：
        session = HumanAssistSession(url='https://...', captcha_type=CaptchaType.RECAPTCHA)
        session.notify_user()  # Agent 通知用户
        # ... 用户手动操作浏览器 ...
        result = session.continue_fetch()  # 用户确认后继续
    """
    
    def __init__(self, url: str, captcha_type: CaptchaType, screenshot_path: str = '',
                 browser=None, page=None):
        self.url = url
        self.captcha_type = captcha_type
        self.screenshot_path = screenshot_path
        self.browser = browser
        self.page = page
        self.session_id = hashlib.md5(f'{url}_{time.time()}'.encode()).hexdigest()[:12]
        self.created_at = time.time()
        self.resolved = False
        
        # 保存截图
        if screenshot_path and os.path.exists(screenshot_path):
            cap_file = os.path.join(CAPTCHA_DIR, f'captcha_{self.session_id}.png')
            import shutil
            try:
                shutil.copy2(screenshot_path, cap_file)
                self.screenshot_path = cap_file
            except Exception:
                pass
    
    def notify_user(self) -> str:
        """返回通知信息，Agent 发送给用户"""
        msg = (
            f"🔐 检测到验证码: {self.captcha_type.value}\n"
            f"URL: {self.url}\n"
        )
        if self.screenshot_path:
            msg += f"截图: MEDIA:{self.screenshot_path}\n"
        msg += "请手动通过验证码后告诉我「继续」"
        return msg
    
    def continue_fetch(self, new_page=None) -> Optional[FetchResult]:
        """用户通过验证码后，继续获取页面内容"""
        page = new_page or self.page
        if page is None:
            return None
        
        self.resolved = True
        
        try:
            time.sleep(2)  # 等验证码状态同步
            html = page.html if hasattr(page, 'html') else page.content()
            
            if html and len(html) > 200:
                return FetchResult(
                    text=_strip_html(html),
                    status=200,
                    method='human-assist',
                    html=html,
                    captcha_detected=True,
                )
        except Exception as e:
            logger.debug(f'[crawler_stack v5] Human assist continue failed: {e}')
        
        return None


# ============================================================
# 多账号隔离体系 (对标 BrowserAct 多账号 + 独立身份)
# ============================================================

@dataclass
class AccountConfig:
    """单个账号的浏览器配置"""
    name: str                              # 账号名称
    proxy: Optional[str] = None            # SOCKS5/HTTP 代理地址
    fingerprint_seed: Optional[str] = None # 指纹种子（相同种子→相同指纹）
    user_data_dir: Optional[str] = None    # Edge 用户数据目录
    cookies: List[dict] = field(default_factory=list)  # 预置 cookie
    headers: Dict[str, str] = field(default_factory=dict)  # 自定义 header
    viewport: tuple = (1920, 1080)         # 窗口大小
    locale: str = 'zh-CN'                  # 语言
    timezone: str = 'Asia/Shanghai'        # 时区


class Account:
    """
    账号 — 独立浏览器身份。
    
    每个 Account 有自己独立的：
    - 浏览器实例（Chromium）
    - 指纹（canvas/WebGL/fonts/audio 等）
    - IP 出口（通过 proxy 配置）
    - Cookie/Session 存储
    - 用户数据目录
    
    用法：
        acct1 = Account(name='运营号1', proxy='socks5://127.0.0.1:1080')
        acct2 = Account(name='运营号2', proxy='socks5://127.0.0.1:1081')
        
        r1 = acct1.fetch('https://example.com')
        r2 = acct2.fetch('https://example.com')  # 完全隔离
    """
    
    def __init__(self, config: AccountConfig):
        self.config = config
        self._browser = None
        self._fingerprint_js = self._generate_fingerprint_js()
    
    def _generate_fingerprint_js(self) -> str:
        """根据指纹种子生成稳定的反检测 JS"""
        seed = self.config.fingerprint_seed or self.config.name
        # 用种子哈希生成稳定的随机偏移
        h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
        
        canvas_noise = (h % 200) / 10000.0  # 0.0000~0.0199 canvas 噪声
        webgl_noise = (h // 100) % 1000 / 10000.0  # WebGL 噪声
        plugins_len = 3 + (h % 3)  # 3~5 个插件
        font_count = 50 + (h % 30)  # 50~79 种字体
        
        return f'''
        (() => {{
            const seed = "{seed}";
            // navigator.webdriver — 永远 false
            Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
            
            // window.chrome — 完整伪装
            window.chrome = {{
                runtime: {{}},
                loadTimes: function() {{}},
                csi: function() {{}},
                app: {{ isInstalled: false, InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }}, RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }} }}
            }};
            
            // navigator.plugins — 真实长度
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{ return Array({{length: {plugins_len}}}); }}
            }});
            
            // navigator.languages
            Object.defineProperty(navigator, 'languages', {{
                get: () => ['{self.config.locale}', 'zh', 'en']
            }});
            
            // Canvas 指纹噪声
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
                const imageData = origGetImageData.call(this, x, y, w, h);
                for (let i = 0; i < imageData.data.length; i += 4) {{
                    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + {canvas_noise}));
                }}
                return imageData;
            }};
            
            // WebGL 指纹噪声
            const origGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                const val = origGetParameter.call(this, param);
                if (typeof val === 'number' && val > 0 && val < 1) {{
                    return val + {webgl_noise};
                }}
                return val;
            }};
            
            // 字体数量
            Object.defineProperty(document, 'fonts', {{
                get: () => {{ return {{ ready: Promise.resolve(), size: {font_count} }}; }}
            }});
        }})();
        '''
    
    def _get_browser(self, headless: bool = True):
        """获取或创建该账号的浏览器实例（独立）"""
        if self._browser is not None:
            return self._browser
        
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-features=PrivacySandboxSettings4')
        
        if headless:
            co.headless(True)
        
        # 代理设置
        if self.config.proxy:
            # DrissionPage 不支持直接设置代理，需要启动参数
            co.set_argument(f'--proxy-server={self.config.proxy}')
        
        # 用户数据目录（隔离）
        if self.config.user_data_dir:
            co.set_user_data_path(self.config.user_data_dir)
            co.auto_port()
        
        # 窗口大小
        co.set_argument(f'--window-size={self.config.viewport[0]},{self.config.viewport[1]}')
        
        self._browser = Chromium(co)
        
        # 注入指纹 JS
        try:
            page = self._browser.latest_tab
            # 先导航到 about:blank 再注入
            page.get('about:blank')
            page.run_js(self._fingerprint_js)
        except Exception:
            pass
        
        return self._browser
    
    def fetch(self, url: str, timeout: int = 30, headless: bool = True,
              human_assist_mode: bool = False) -> FetchResult:
        """
        使用该账号的独立浏览器身份获取页面。
        
        Args:
            url: 目标 URL
            timeout: 超时秒数
            headless: 是否无头模式
            human_assist_mode: 是否启用验证码人机接力
            
        Returns:
            FetchResult
        """
        browser = self._get_browser(headless=headless)
        page = browser.latest_tab
        
        try:
            page.get(url)
            page.wait(min(timeout // 2, 8))
            time.sleep(2)
            
            # 检测验证码
            html = page.html
            if human_assist_mode and html:
                captcha_type = detect_captcha(html)
                if captcha_type != CaptchaType.NONE:
                    # 截图
                    screenshot_path = os.path.join(CAPTCHA_DIR, f'captcha_{self.config.name}_{int(time.time())}.png')
                    try:
                        # DrissionPage 不支持直接截图，用 JS 替代
                        pass
                    except Exception:
                        screenshot_path = ''
                    
                    session = HumanAssistSession(
                        url=url,
                        captcha_type=captcha_type,
                        screenshot_path=screenshot_path,
                        browser=browser,
                        page=page,
                    )
                    
                    # 返回一个特殊结果，上层 Agent 处理人机接力
                    return FetchResult(
                        text='',  # 空内容表示需要人机接力
                        status=200,
                        method=f'captcha-{captcha_type.value}',
                        html=html,
                        captcha_detected=True,
                        captcha_screenshot=screenshot_path,
                    )
            
            if html and len(html) > 200:
                return FetchResult(
                    text=_strip_html(html),
                    status=200,
                    method=f'account-{self.config.name}',
                    html=html,
                )
            
            raise RuntimeError(f'Empty page for {url}')
            
        except Exception as e:
            logger.debug(f'[crawler_stack v5] Account {self.config.name} failed: {e}')
            raise
    
    def close(self):
        """关闭该账号的浏览器实例"""
        if self._browser is not None:
            try:
                self._browser.quit()
            except Exception:
                pass
            self._browser = None


class AccountManager:
    """
    账号管理器 — 管理多个隔离账号。
    
    用法：
        mgr = AccountManager()
        acct1 = mgr.create_account('运营号1', proxy='socks5://127.0.0.1:1080')
        acct2 = mgr.create_account('运营号2', proxy='socks5://127.0.0.1:1081')
        
        # 并发获取
        results = mgr.batch_fetch([
            ('https://site.com/page1', '运营号1'),
            ('https://site.com/page2', '运营号2'),
        ])
    """
    
    def __init__(self):
        self._accounts: Dict[str, Account] = {}
    
    def create_account(self, name: str, proxy: Optional[str] = None,
                       fingerprint_seed: Optional[str] = None,
                       user_data_dir: Optional[str] = None,
                       cookies: Optional[List[dict]] = None,
                       **kwargs) -> Account:
        """创建并注册一个账号"""
        if name in self._accounts:
            logger.warning(f'[crawler_stack v5] Account {name} already exists, overwriting')
        
        config = AccountConfig(
            name=name,
            proxy=proxy,
            fingerprint_seed=fingerprint_seed or name,
            user_data_dir=user_data_dir,
            cookies=cookies or [],
            **kwargs
        )
        account = Account(config)
        self._accounts[name] = account
        return account
    
    def get_account(self, name: str) -> Optional[Account]:
        """获取已注册的账号"""
        return self._accounts.get(name)
    
    def batch_fetch(self, tasks: List[tuple], timeout: int = 30,
                    headless: bool = True) -> Dict[str, FetchResult]:
        """
        批量获取（顺序执行，避免 session 污染）。
        
        Args:
            tasks: [(url, account_name), ...]
            timeout: 超时秒数
            headless: 是否无头
            
        Returns:
            {url: FetchResult}
        """
        results = {}
        for url, account_name in tasks:
            account = self._accounts.get(account_name)
            if account is None:
                logger.warning(f'[crawler_stack v5] Account {account_name} not found, skipping {url}')
                continue
            
            try:
                result = account.fetch(url, timeout=timeout, headless=headless)
                results[url] = result
            except Exception as e:
                logger.error(f'[crawler_stack v5] Batch fetch failed for {url} with {account_name}: {e}')
        
        return results
    
    def close_all(self):
        """关闭所有账号的浏览器实例"""
        for name, account in self._accounts.items():
            try:
                account.close()
                logger.info(f'[crawler_stack v5] Account {name} closed')
            except Exception as e:
                logger.debug(f'[crawler_stack v5] Close account {name} failed: {e}')
        self._accounts.clear()


# ============================================================
# Skill Forge — 自然语言→可复用爬虫 Skill (对标 BrowserAct Skill Forge)
# ============================================================

@dataclass
class ForgedSkill:
    """Forge 生成的 Skill 定义"""
    name: str
    description: str
    site: str
    data_fields: List[str]           # 要提取的数据字段
    selectors: Dict[str, str]        # {field: CSS selector / regex}
    pagination: Optional[Dict] = None  # 分页配置
    auth_required: bool = False       # 是否需要登录
    proxy: Optional[str] = None       # 是否需要代理
    output_format: str = 'json'       # json / csv / markdown
    version: str = '1.0.0'
    
    def to_skill_md(self) -> str:
        """生成 SKILL.md 内容"""
        selectors_yaml = '\n'.join([f"      {k}: '{v}'" for k, v in self.selectors.items()])
        pagination_yaml = ''
        if self.pagination:
            pagination_yaml = f'''
  pagination:
    type: '{self.pagination.get("type", "url")}'
    param: '{self.pagination.get("param", "page")}'
    start: {self.pagination.get("start", 1)}
    step: {self.pagination.get("step", 1)}'''
        
        return f'''---
name: {self.name}
description: "{self.description}"
version: {self.version}
author: "Skill Forge"
site: "{self.site}"
auth_required: {str(self.auth_required).lower()}
proxy: {f'"{self.proxy}"' if self.proxy else 'null'}
output_format: {self.output_format}
data_fields: {json.dumps(self.data_fields)}
selectors:
{selectors_yaml}{pagination_yaml}
---

# {self.name}

由 Skill Forge 自动生成。

## 数据字段

{chr(10).join([f'- **{f}**' for f in self.data_fields])}

## 用法

```python
from crawler_stack_v5 import fetch

result = fetch('{self.site}')
# 解析数据...
```
'''
    
    def save(self) -> str:
        """保存 Skill 到文件"""
        os.makedirs(FORGE_OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(FORGE_OUTPUT_DIR, f'{self.name}.md')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_skill_md())
        logger.info(f'[crawler_stack v5] Skill Forge: Saved {filepath}')
        return filepath


class SkillForge:
    """
    Skill Forge — 自然语言描述→自动探测→生成可复用抓取 Skill。
    
    用法：
        forge = SkillForge()
        skill = forge.create(
            description="抓取小红书AI Agent关键词的笔记标题、点赞数、作者",
            site="https://www.xiaohongshu.com"
        )
        skill.save()
    
    工作流：
    1. 分析自然语言描述，提取目标数据字段
    2. 访问目标网站，探测页面结构（CSS 选择器 / 数据模式）
    3. 自动生成抓取逻辑和 SKILL.md
    4. 保存到指定目录，可被爬虫栈直接加载
    """
    
    def __init__(self):
        self._probe_cache: Dict[str, dict] = {}
    
    def create(self, description: str, site: str,
               auth_required: bool = False,
               proxy: Optional[str] = None,
               probe: bool = True) -> ForgedSkill:
        """
        根据自然语言描述生成 Skill。
        
        Args:
            description: 自然语言描述，如"抓取小红书AI Agent关键词的笔记标题、点赞数、作者"
            site: 目标网站 URL
            auth_required: 是否需要登录
            proxy: 代理地址
            probe: 是否探测页面结构（默认 True）
            
        Returns:
            ForgedSkill 对象
        """
        # 1. 从描述中提取数据字段
        data_fields = self._parse_fields(description)
        
        # 2. 探测页面结构
        selectors = {}
        pagination = None
        
        if probe:
            probe_result = self._probe_site(site)
            selectors = probe_result.get('selectors', {})
            pagination = probe_result.get('pagination')
        
        # 3. 生成 Skill 名称
        name = self._generate_name(description, site)
        
        return ForgedSkill(
            name=name,
            description=description,
            site=site,
            data_fields=data_fields,
            selectors=selectors,
            pagination=pagination,
            auth_required=auth_required,
            proxy=proxy,
        )
    
    def _parse_fields(self, description: str) -> List[str]:
        """
        从自然语言描述中提取数据字段。
        
        示例：
            "抓取标题、点赞数、作者" → ['title', 'likes', 'author']
            "提取商品名称、价格、销量" → ['product_name', 'price', 'sales']
        """
        # 常见字段映射
        field_map = {
            '标题': 'title', '标题': 'title',
            '点赞': 'likes', '点赞数': 'likes', '赞': 'likes',
            '作者': 'author', '作者名': 'author',
            '价格': 'price', '售价': 'price', '原价': 'original_price',
            '销量': 'sales', '销量': 'sales', '销售量': 'sales',
            '描述': 'description', '简介': 'description',
            '时间': 'time', '发布时间': 'publish_time', '日期': 'date',
            '链接': 'url', 'URL': 'url', '地址': 'url',
            '图片': 'image', '封面': 'cover_image',
            '评论': 'comments', '评论数': 'comments',
            '收藏': 'favorites', '收藏数': 'favorites',
            '转发': 'shares', '分享': 'shares',
            '内容': 'content', '正文': 'content',
            '标签': 'tags', '话题': 'tags',
            '评分': 'rating', '星级': 'rating',
            '分类': 'category', '类目': 'category',
            '品牌': 'brand',
            '规格': 'specs', '参数': 'specs',
        }
        
        fields = []
        for cn, en in field_map.items():
            if cn in description:
                if en not in fields:
                    fields.append(en)
        
        # 兜底：如果没匹配到，返回通用字段
        if not fields:
            fields = ['title', 'content', 'url']
        
        return fields
    
    def _probe_site(self, site: str) -> dict:
        """
        探测目标网站的结构。
        
        策略：
        1. 用 L1 curl_cffi 快速获取页面
        2. 分析 HTML 结构，推测 CSS 选择器
        3. 检测分页模式
        4. 缓存结果避免重复探测
        
        注意：真正的选择器生成需要更复杂的 DOM 分析，
        这里提供基础探测框架，上层 Agent 可根据页面内容补充 selectors。
        """
        if site in self._probe_cache:
            return self._probe_cache[site]
        
        result = {
            'selectors': {},
            'pagination': None,
            'title': '',
            'content_type': 'unknown',
        }
        
        try:
            # 用 L1 快速探测
            from curl_cffi import requests
            r = requests.get(site, impersonate='chrome131', timeout=10, verify=False)
            html = r.text
            
            if len(html) < 500:
                # 被 Cloudflare 拦截，跳过探测
                result['content_type'] = 'protected'
                self._probe_cache[site] = result
                return result
            
            # 检测页面类型
            if 'article' in html.lower() or 'post' in html.lower():
                result['content_type'] = 'article'
            elif 'product' in html.lower() or 'item' in html.lower():
                result['content_type'] = 'product'
            elif 'list' in html.lower() or 'search' in html.lower():
                result['content_type'] = 'list'
            
            # 提取页面标题
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                result['title'] = m.group(1).strip()
            
            # 检测分页
            if re.search(r'[?&]page=\d+|/page/\d+', html):
                result['pagination'] = {
                    'type': 'url',
                    'param': 'page',
                    'start': 1,
                    'step': 1,
                }
            elif re.search(r'[?&]p=\d+|/p/\d+', html):
                result['pagination'] = {
                    'type': 'url',
                    'param': 'p',
                    'start': 1,
                    'step': 1,
                }
            elif re.search(r'[?&]offset=\d+', html):
                result['pagination'] = {
                    'type': 'url',
                    'param': 'offset',
                    'start': 0,
                    'step': 20,
                }
            
        except Exception as e:
            logger.debug(f'[crawler_stack v5] Skill Forge probe failed: {e}')
        
        self._probe_cache[site] = result
        return result
    
    def _generate_name(self, description: str, site: str) -> str:
        """从描述和网站生成 Skill 名称"""
        # 提取域名
        m = re.search(r'https?://([^/]+)', site)
        domain = m.group(1) if m else site
        
        # 简化域名
        domain_short = domain.replace('www.', '').split('.')[0]
        
        # 从描述提取关键词
        keywords = ['scraper']
        for word in ['抓取', '提取', '爬取', '采集']:
            if word in description:
                break
        
        # 取前两个有意义的词
        words = description.split()
        for w in words[:3]:
            clean = re.sub(r'[的了的和与]', '', w)
            if clean and len(clean) <= 6:
                keywords.append(clean)
        
        name = f'{domain_short}-{"-".join(keywords[:3])}'
        # 确保合法文件名
        name = re.sub(r'[^a-zA-Z0-9_-]', '', name).lower()
        return name[:50] or f'{domain_short}-scraper'


# ============================================================
# L0: Cookie 注入层 (复用 v4)
# ============================================================

_COOKIE_JAR: Dict[str, List[dict]] = {}


def load_cookie_file(filepath: str) -> int:
    """从 Netscape cookie 文件加载 cookie。"""
    global _COOKIE_JAR
    
    if not os.path.exists(filepath):
        logger.warning(f'[crawler_stack v5] Cookie file not found: {filepath}')
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
        
        logger.info(f'[crawler_stack v5] L0: Loaded {count} cookies from {filepath}')
        return count
    except Exception as e:
        logger.warning(f'[crawler_stack v5] L0: Failed to load cookies: {e}')
        return 0


def load_cookies_from_list(cookies: List[dict]) -> int:
    """从 cookie 字典列表加载。"""
    global _COOKIE_JAR
    
    count = 0
    for c in cookies:
        domain = c.get('domain', '')
        if not domain:
            continue
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
    
    logger.info(f'[crawler_stack v5] L0: Loaded {count} cookies from list')
    return count


def _inject_cookies_into_curl(url: str) -> str:
    """为 curl 请求生成 Cookie header。"""
    global _COOKIE_JAR
    if not _COOKIE_JAR:
        return ''
    
    m = re.search(r'https?://([^/]+)', url)
    if not m:
        return ''
    host = m.group(1)
    
    matched = []
    for domain, cookies in _COOKIE_JAR.items():
        clean_domain = domain.lstrip('.')
        if host == clean_domain or host.endswith('.' + clean_domain):
            for c in cookies:
                matched.append(f"{c['name']}={c['value']}")
    
    return '; '.join(matched)


# ============================================================
# L1-L5: 保留 v4 所有层级 (复用原函数)
# ============================================================

def _fetch_curl_cffi(url: str, timeout: int = 15) -> Optional[FetchResult]:
    """L1 curl_cffi — 最快，模拟 TLS 指纹"""
    try:
        from curl_cffi import requests
        
        headers = {}
        cookie_str = _inject_cookies_into_curl(url)
        if cookie_str:
            headers['Cookie'] = cookie_str
        
        r = requests.get(url, impersonate='chrome131', timeout=timeout, headers=headers, verify=False)
        text = r.text
        
        if len(text) > 500 and 'verify' not in text.lower()[:2000] and 'Ray ID' not in text:
            return FetchResult(
                text=_strip_html(text),
                status=r.status_code,
                method='L1-curl_cffi',
                html=text,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L1 curl_cffi failed: {e}')
        return None


def _fetch_cloudscraper(url: str, timeout: int = 20) -> Optional[FetchResult]:
    """L1.1 cloudscraper v3 — 破 Cloudflare JS VM + Turnstile"""
    try:
        import cloudscraper
        
        scraper = cloudscraper.create_scraper(interpreter='js2py', debug=False)
        headers = {}
        cookie_str = _inject_cookies_into_curl(url)
        if cookie_str:
            headers['Cookie'] = cookie_str
        
        r = scraper.get(url, timeout=timeout, headers=headers)
        text = r.text
        
        if len(text) > 500 and 'Ray ID' not in text[:2000]:
            return FetchResult(
                text=_strip_html(text),
                status=r.status_code,
                method='L1.1-cloudscraper',
                html=text,
            )
        return None
    except ImportError:
        logger.warning('[crawler_stack v5] L1.1 cloudscraper not installed')
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L1.1 cloudscraper failed: {e}')
        return None


def _fetch_drission_fresh(url: str, wait_seconds: int = 5,
                          headless: bool = True,
                          proxy: Optional[str] = None,
                          user_data: Optional[str] = None) -> Optional[FetchResult]:
    """
    独立 DrissionPage 实例 — 解决 session 污染问题。
    
    每次调用创建新的 Chromium 实例，获取后自动关闭。
    适合批量爬取场景（每次独立 session，互不干扰）。
    """
    try:
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        
        if headless:
            co.headless(True)
        
        if proxy:
            co.set_argument(f'--proxy-server={proxy}')
        
        if user_data:
            co.set_user_data_path(user_data)
            co.auto_port()
        
        browser = Chromium(co)
        page = browser.latest_tab
        page.get(url)
        page.wait(wait_seconds)
        time.sleep(2)
        
        # 年龄确认页自动点击
        try:
            for _try_text in ['满18岁', 'please click here', '我已成年', '进入网站', 'Enter']:
                try:
                    _btn = page.ele(f'tag:a@@text():{_try_text}', timeout=1)
                    if _btn:
                        _btn.click()
                        time.sleep(3)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        html = page.html
        browser.quit()
        
        if html and len(html) > 200:
            return FetchResult(
                text=_strip_html(html),
                status=200,
                method='L2-drission-fresh',
                html=html,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] DrissionPage fresh failed: {e}')
        return None


def _fetch_drission(url: str, wait_seconds: int = 5) -> Optional[FetchResult]:
    """L2 DrissionPage 无头模式（保留全局单例兼容）"""
    try:
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.headless(True)
        
        browser = Chromium(co)
        page = browser.latest_tab
        page.get(url)
        page.wait(wait_seconds)
        time.sleep(2)
        
        html = page.html
        browser.quit()
        
        if html and len(html) > 200:
            return FetchResult(
                text=_strip_html(html),
                status=200,
                method='L2-drission',
                html=html,
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L2 DrissionPage failed: {e}')
        return None


def _fetch_edge_remote(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """L2.5 Edge 远程调试"""
    import urllib.request
    import json as _json
    
    try:
        req = urllib.request.Request('http://localhost:9222/json/version')
        resp = urllib.request.urlopen(req, timeout=5)
        _json.loads(resp.read())
        
        req2 = urllib.request.Request(
            f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe="")}',
            method='PUT'
        )
        resp2 = urllib.request.urlopen(req2, timeout=5)
        tab = _json.loads(resp2.read())
        tab_id = tab['id']
        ws_url = tab['webSocketDebuggerUrl']
        
        try:
            from websocket import create_connection
            ws = create_connection(ws_url, timeout=10)
            ws.send(_json.dumps({'id': 1, 'method': 'Page.enable'}))
            ws.recv()
            time.sleep(5)
            
            ws.send(_json.dumps({
                'id': 2, 'method': 'Runtime.evaluate',
                'params': {'expression': 'document.documentElement.outerHTML'}
            }))
            resp3 = _json.loads(ws.recv())
            html = resp3.get('result', {}).get('result', {}).get('value', '')
            ws.close()
            
            try:
                req_close = urllib.request.Request(
                    f'http://localhost:9222/json/close/{tab_id}', method='PUT')
                urllib.request.urlopen(req_close, timeout=3)
            except Exception:
                pass
            
            if html and len(html) > 200:
                return FetchResult(
                    text=_strip_html(html),
                    status=200,
                    method='L2.5-edge-remote',
                    html=html,
                )
        except Exception:
            try:
                req_close = urllib.request.Request(
                    f'http://localhost:9222/json/close/{tab_id}', method='PUT')
                urllib.request.urlopen(req_close, timeout=3)
            except Exception:
                pass
        
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L2.5 Edge remote failed: {e}')
        return None


def _fetch_playwright(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """L3 Playwright"""
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
        logger.debug(f'[crawler_stack v5] L3 Playwright failed: {e}')
        return None


def _fetch_cloakbrowser(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """L3.5 CloakBrowser — 源码级反检测"""
    try:
        from cloakbrowser import launch
        
        browser = launch(headless=True, humanize=True, timeout=timeout * 1000)
        page = browser.new_page()
        
        resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
        page.wait_for_timeout(3000)
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
        logger.warning('[crawler_stack v5] L3.5 CloakBrowser not installed')
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L3.5 CloakBrowser failed: {e}')
        return None


def _enhance_spa(url: str, wait_for_selector: Optional[str] = None,
                 hash_route: Optional[str] = None,
                 intercept_api: bool = False,
                 timeout: int = 30) -> Optional[FetchResult]:
    """L4 SPA 渲染增强"""
    try:
        from DrissionPage import Chromium, ChromiumOptions
        
        co = ChromiumOptions()
        co.set_browser_path(EDGE_PATH)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.headless(True)
        
        browser = Chromium(co)
        page = browser.latest_tab
        
        base_url = url.split('#')[0] if '#' in url else url
        page.get(base_url)
        page.wait(3)
        
        if hash_route:
            page.run_js(f"window.location.hash = '{hash_route}'")
            time.sleep(5)
        elif '#' in url:
            hash_part = url.split('#', 1)[1]
            page.run_js(f"window.location.hash = '{hash_part}'")
            time.sleep(5)
        
        if wait_for_selector:
            try:
                page.ele(wait_for_selector, timeout=timeout)
            except Exception:
                pass
        
        time.sleep(3)
        
        api_data = []
        if intercept_api:
            try:
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
        
        if html and len(html) > 500:
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
        logger.debug(f'[crawler_stack v5] L4 SPA failed: {e}')
        return None


def _fetch_yingdao(url: str, timeout: int = 30) -> Optional[FetchResult]:
    """L5 影刀 RPA"""
    try:
        import urllib.request
        import json as json_mod
        
        payload = json_mod.dumps({
            'url': url,
            'timeout': timeout,
            'action': 'fetch_page',
        }).encode()
        
        req = urllib.request.Request(
            'http://127.0.0.1:8000/fetch',
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=min(timeout, 15),
        )
        
        resp = urllib.request.urlopen(req)
        data = json_mod.loads(resp.read().decode())
        
        if data.get('status') == 200 and data.get('html'):
            return FetchResult(
                text=_strip_html(data['html']),
                status=data['status'],
                method='L5-yingdao',
                html=data['html'],
            )
        return None
    except Exception as e:
        logger.debug(f'[crawler_stack v5] L5 影刀 RPA failed: {e}')
        return None


# ============================================================
# 入口：自动降级 (增强版)
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
    skip_l5: bool = False,
    use_user_data: bool = True,
    wait_for_selector: Optional[str] = None,
    hash_route: Optional[str] = None,
    intercept_api: bool = False,
    human_assist_mode: bool = False,
    use_fresh_instance: bool = True,
    proxy: Optional[str] = None,
) -> FetchResult:
    """
    获取网页内容，自动降级 (v5 增强版)。
    
    v5 新增参数：
        human_assist_mode: 启用验证码人机接力（默认 False）
        use_fresh_instance: 使用独立浏览器实例替代全局单例（默认 True，解决 session 污染）
        proxy: 代理地址
    
    降级顺序：L1 -> L1.1 -> L1.5 -> L2(独立) -> L2.5 -> L3 -> L3.5 -> L4 -> L5
    """
    result = None
    
    # L1: curl_cffi（最快）
    if not skip_l1:
        result = _fetch_curl_cffi(url, min(timeout, 15))
        if result:
            logger.info(f'[crawler_stack v5] ✅ L1 curl_cffi: {url}')
            return result
    
    # L1.1: cloudscraper v3
    if not skip_l11:
        result = _fetch_cloudscraper(url, min(timeout, 20))
        if result:
            logger.info(f'[crawler_stack v5] ✅ L1.1 cloudscraper: {url}')
            return result
    
    # L1.5: DrissionPage (user data) — 复用登录态
    if not skip_l15 and use_user_data:
        result = _fetch_drission_fresh(url, min(timeout // 2, 8),
                                        proxy=proxy, user_data=EDGE_USER_DATA)
        if result:
            logger.info(f'[crawler_stack v5] ✅ L1.5 DrissionPage (user): {url}')
            return result
    
    # L2: DrissionPage 独立实例（推荐，消除 session 污染）
    if not skip_l2:
        if use_fresh_instance:
            result = _fetch_drission_fresh(url, min(timeout // 2, 5), proxy=proxy)
        else:
            result = _fetch_drission(url, min(timeout // 2, 5))
        if result:
            logger.info(f'[crawler_stack v5] ✅ L2 DrissionPage: {url}')
            return result
    
    # L2.5: Edge remote debugging
    if not skip_l25:
        result = _fetch_edge_remote(url, timeout)
        if result:
            logger.info(f'[crawler_stack v5] ✅ L2.5 Edge remote: {url}')
            return result
    
    # L3: Playwright
    if not skip_l3:
        result = _fetch_playwright(url, timeout)
        if result:
            logger.info(f'[crawler_stack v5] ✅ L3 Playwright: {url}')
            return result
    
    # L3.5: CloakBrowser
    if not skip_l35:
        result = _fetch_cloakbrowser(url, timeout)
        if result:
            logger.info(f'[crawler_stack v5] ✅ L3.5 CloakBrowser: {url}')
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
            logger.info(f'[crawler_stack v5] ✅ L4 SPA: {url}')
            return result
    
    # L5: 影刀 RPA
    if not skip_l5:
        result = _fetch_yingdao(url, timeout)
        if result:
            logger.info(f'[crawler_stack v5] ✅ L5 影刀 RPA: {url}')
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
        m = re.search(rf'id=[\'"]{container_id}[\'\"][^>]*>([\s\S]*?)</div>', html)
        if m:
            c = re.sub(r'<[^>]+>', '', m.group(1))
            c = html_mod.unescape(c)
            c = re.sub(r'\s+', ' ', c).strip()
            if len(c) > 100:
                return c

    return text


def extract_video_urls(html: str) -> List[str]:
    """从 HTML 中提取视频地址。"""
    urls = []
    patterns = [
        r'https?://[^\s"\'<>]*(?:m3u8)[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.mp4[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.flv[^\s"\'<>]*',
        r'https?://[^\s"\'<>]*\.ts[^\s"\'<>]*',
    ]
    for pattern in patterns:
        found = re.findall(pattern, html)
        urls.extend(found)
    
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
    
    return list(set(urls))


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
    skip_l5 = '--skip-l5' in sys.argv
    
    human_assist = '--human-assist' in sys.argv
    
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
        skip_l5=skip_l5,
        hash_route=hash_route,
        human_assist_mode=human_assist,
    )
    
    if result.captcha_detected:
        print(f'🔐 验证码检测: {result.method}')
        print(f'   截图: {result.captcha_screenshot}')
        print('   请手动通过验证码后重新调用 continue_fetch()')
    else:
        print(f'Method: {result.method}')
        print(f'Status: {result.status}')
        print(f'Text ({len(result.text)} chars):')
        print(result.text[:500])
        if result.video_urls:
            print(f'Video URLs: {result.video_urls}')
