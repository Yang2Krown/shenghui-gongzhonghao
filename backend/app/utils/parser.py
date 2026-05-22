"""
数据解析工具模块
"""
import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from bs4 import BeautifulSoup
import feedparser

logger = logging.getLogger(__name__)


class ContentParser:
    """内容解析器"""

    @staticmethod
    def parse_html_content(html: str) -> Dict[str, Any]:
        """
        解析HTML内容
        
        Args:
            html: HTML字符串
            
        Returns:
            解析后的内容字典
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 提取标题
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            # 提取正文内容
            content = ""
            # 尝试常见的正文容器
            content_selectors = [
                "article", ".article-content", ".post-content",
                ".entry-content", ".content", "main", "#content"
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator="\n", strip=True)
                    break
            
            # 如果没有找到正文，使用body
            if not content:
                body = soup.find("body")
                if body:
                    content = body.get_text(separator="\n", strip=True)
            
            # 提取图片
            images = []
            for img in soup.find_all("img"):
                src = img.get("src")
                if src:
                    images.append(src)
            
            # 提取链接
            links = []
            for link in soup.find_all("a"):
                href = link.get("href")
                if href:
                    links.append({
                        "text": link.get_text(strip=True),
                        "href": href
                    })
            
            return {
                "title": title,
                "content": content,
                "images": images,
                "links": links[:10],  # 限制链接数量
                "content_length": len(content)
            }
            
        except Exception as e:
            logger.error(f"HTML解析失败: {e}")
            return {
                "title": "",
                "content": "",
                "images": [],
                "links": [],
                "content_length": 0
            }

    @staticmethod
    def parse_rss_feed(feed_url: str) -> List[Dict[str, Any]]:
        """
        解析RSS订阅源
        
        Args:
            feed_url: RSS订阅源URL
            
        Returns:
            文章列表
        """
        try:
            feed = feedparser.parse(feed_url)
            
            articles = []
            for entry in feed.entries:
                article = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                    "tags": [tag.get("term", "") for tag in entry.get("tags", [])]
                }
                articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"RSS解析失败: {e}")
            return []

    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
        """
        提取关键词
        
        Args:
            text: 文本内容
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        try:
            # 简单的关键词提取（基于词频）
            # 实际项目中可以使用jieba等分词工具
            
            # 清理文本
            text = re.sub(r'[^\w\s]', '', text)
            text = text.lower()
            
            # 分词（简单按空格分割）
            words = text.split()
            
            # 过滤停用词
            stop_words = {
                "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
                "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
                "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
                "the", "a", "an", "is", "are", "was", "were", "be", "been",
                "being", "have", "has", "had", "do", "does", "did", "will",
                "would", "could", "should", "may", "might", "must", "shall",
                "can", "need", "dare", "ought", "used", "to", "of", "in",
                "for", "on", "with", "at", "by", "from", "as", "into",
                "through", "during", "before", "after", "above", "below",
                "between", "out", "off", "over", "under", "again", "further",
                "then", "once"
            }
            
            filtered_words = [w for w in words if w not in stop_words and len(w) > 1]
            
            # 统计词频
            word_freq = {}
            for word in filtered_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # 按词频排序
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            
            # 返回前N个关键词
            keywords = [word for word, freq in sorted_words[:max_keywords]]
            
            return keywords
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

    @staticmethod
    def clean_text(text: str) -> str:
        """
        清理文本内容
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        try:
            # 去除多余空白字符
            text = re.sub(r'\s+', ' ', text)
            
            # 去除特殊字符
            text = re.sub(r'[^\w\s.,!?;:，。！？；：""''、\n]', '', text)
            
            # 去除首尾空白
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"文本清理失败: {e}")
            return text


# 创建全局解析器实例
parser = ContentParser()
