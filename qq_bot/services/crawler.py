"""
网页爬取工具（使用 httpx + BeautifulSoup）
"""

import re
from typing import Optional

import httpx
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
    """用 httpx 异步抓取 URL 并提取正文"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            html = resp.text
        text = extract_text_from_html(html)
        return text
    except Exception as e:
        print(f"[爬虫] 失败: {e}")
        return None


def crawl_url(url: str) -> Optional[str]:
    """同步封装"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(crawl_url_async(url))
