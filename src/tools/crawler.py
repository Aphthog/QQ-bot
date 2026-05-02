"""
网页爬取工具（使用 Playwright）
"""
import os
import re
from typing import Optional

os.environ["HF_HUB_DISABLE_SAFETENSORS"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

from bs4 import BeautifulSoup


def extract_text_from_html(html: str) -> str:
    """从HTML中提取正文"""
    soup = BeautifulSoup(html, 'html.parser')
    # 移除 script/style/nav/header/footer/aside
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'meta', 'link']):
        tag.decompose()
    # 移除所有注释
    for comment in soup.find_all(string=lambda t: isinstance(t, str) and t.strip().startswith('<!--')):
        comment.extract()
    # 提取文本
    text = soup.get_text(separator='\n', strip=True)
    # 清洗文本
    text = clean_text(text)
    # 合并空行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def clean_text(text: str) -> str:
    """
    通用文本清洗：去除引用标记、模板、导航噪音等
    """
    # 去掉 [1] [2] [edit] [e] 等引用标记
    text = re.sub(r'\[\d+\]|\[edit\]|\[e\]', '', text, flags=re.IGNORECASE)
    # 去掉 {{模板}} （最多匹配200字符防止贪婪）
    text = re.sub(r'\{\{[^}]{0,200}\}\}', '', text)
    # 去掉 ~~~ 分隔线
    text = re.sub(r'~{3,}', '', text)
    # 去掉 参考资料 / References / See also 及其以后内容
    text = re.sub(r'(参考资料|References|See also|参考文献|外部链接|延伸阅读)[：:\s\S]*$', '', text, flags=re.I)
    # 去掉常见的导航噪音
    noise_patterns = [
        r'Jump to navigation',
        r'Search this site',
        r'此页面[最后]?编辑',
        r'登录[：:]|注册[：:]',
        r'^[前后]一篇：',
        r'^分类：',
        r'^页面分类：',
        r'编辑[​\s]*链接',
        r'简?繁[体]?',
        r'^跳转到：',
        r'本页面.?经.',
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # 去掉连续的数字行（通常是表格行、统计行）
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # 跳过全是数字/符号的行
        if re.match(r'^[\d\s,，.。%%：:/\-+]+$', line):
            continue
        # 跳过只含少量字符的噪音行（<10个可见字符）
        if len(re.sub(r'\s', '', line)) < 8:
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    return text


def extract_url(text: str) -> Optional[str]:
    """从文本中提取URL"""
    url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )
    match = url_pattern.search(text)
    return match.group(0) if match else None


async def crawl_url_async(url: str) -> Optional[str]:
    """
    用 Playwright 异步爬取 URL，返回正文

    Args:
        url: 目标URL

    Returns:
        提取的正文，失败返回 None
    """
    try:
        from playwright.async_api import async_playwright

        print(f"[爬虫] 开始爬取: {url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000, wait_until='domcontentloaded')
            # 等待网络空闲（SPA页面需要等JS执行完）
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            # 自动滚动触发懒加载
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(500)
            await page.evaluate("window.scrollTo(0, 0)")
            html = await page.content()
            await browser.close()
        print(f"[爬虫] 获取HTML长度: {len(html)}")

        text = extract_text_from_html(html)
        print(f"[爬虫] 提取文本长度: {len(text)}")
        return text
    except Exception as e:
        print(f"[爬虫] 失败: {e}")
        return None


def crawl_url(url: str) -> Optional[str]:
    """同步封装，兼容现有代码"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(crawl_url_async(url))
