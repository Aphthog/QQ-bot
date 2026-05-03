"""
网页爬取工具（使用 Playwright）
"""

import os
import re
from typing import Optional

os.environ.setdefault("HF_HUB_DISABLE_SAFETENSORS", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from bs4 import BeautifulSoup


def extract_text_from_html(html: str) -> str:
    """从 HTML 提取正文"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "meta", "link"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, str) and t.strip().startswith("<!--")):
        comment.extract()
    text = soup.get_text(separator="\n", strip=True)
    text = clean_text(text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def clean_text(text: str) -> str:
    """清洗文本噪音"""
    text = re.sub(r"\[\d+\]|\[edit\]|\[e\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{[^}]{0,200}\}\}", "", text)
    text = re.sub(r"~{3,}", "", text)
    text = re.sub(r"(参考资料|References|See also|参考文献|外部链接|延伸阅读)[：:\s\S]*$", "", text, flags=re.I)

    noise = [
        r"Jump to navigation", r"Search this site",
        r"此页面[最后]?编辑", r"登录[：:]|注册[：:]",
        r"^[前后]一篇：", r"^分类：", r"^页面分类：",
        r"编辑[\s]*链接", r"简?繁[体]?", r"^跳转到：", r"本页面.?经.",
    ]
    for p in noise:
        text = re.sub(p, "", text, flags=re.IGNORECASE)

    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if re.match(r"^[\d\s,，.。%%：:/\-+]+$", line):
            continue
        if len(re.sub(r"\s", "", line)) < 8:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://[^\s<>\"{}|\\^`\[\]]+", text, re.IGNORECASE)
    return m.group(0) if m else None


async def crawl_url_async(url: str) -> Optional[str]:
    """用 Playwright 异步爬取 URL"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(500)
            await page.evaluate("window.scrollTo(0, 0)")
            html = await page.content()
            await browser.close()

        text = extract_text_from_html(html)
        return text
    except Exception as e:
        print(f"[爬虫] 失败: {e}")
        return None


def crawl_url(url: str) -> Optional[str]:
    """同步封装"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(crawl_url_async(url))
