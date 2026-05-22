"""
数据验证工具模块
"""
import re
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class Validator:
    """数据验证器"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        验证邮箱格式
        
        Args:
            email: 邮箱地址
            
        Returns:
            是否有效
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_username(username: str) -> bool:
        """
        验证用户名格式
        
        Args:
            username: 用户名
            
        Returns:
            是否有效
        """
        # 用户名：3-20位，字母、数字、下划线
        pattern = r'^[a-zA-Z0-9_]{3,20}$'
        return bool(re.match(pattern, username))

    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """
        验证密码强度
        
        Args:
            password: 密码
            
        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "strength": "weak"
        }
        
        # 长度检查
        if len(password) < 8:
            result["valid"] = False
            result["errors"].append("密码长度至少8位")
        
        if len(password) > 50:
            result["valid"] = False
            result["errors"].append("密码长度不能超过50位")
        
        # 复杂度检查
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'[0-9]', password))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        
        complexity = sum([has_upper, has_lower, has_digit, has_special])
        
        if complexity < 2:
            result["valid"] = False
            result["errors"].append("密码需包含至少两种字符类型（大写、小写、数字、特殊字符）")
        
        # 强度评估
        if len(password) >= 12 and complexity >= 3:
            result["strength"] = "strong"
        elif len(password) >= 8 and complexity >= 2:
            result["strength"] = "medium"
        
        return result

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        验证URL格式
        
        Args:
            url: URL地址
            
        Returns:
            是否有效
        """
        pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        return bool(re.match(pattern, url))

    @staticmethod
    def validate_date(date_str: str, format: str = "%Y-%m-%d") -> bool:
        """
        验证日期格式
        
        Args:
            date_str: 日期字符串
            format: 日期格式
            
        Returns:
            是否有效
        """
        try:
            datetime.strptime(date_str, format)
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_pagination(page: int, page_size: int) -> Dict[str, Any]:
        """
        验证分页参数
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            验证后的分页参数
        """
        # 确保页码为正整数
        page = max(1, page)
        
        # 确保每页数量在合理范围内
        page_size = max(1, min(100, page_size))
        
        return {
            "page": page,
            "page_size": page_size,
            "offset": (page - 1) * page_size
        }

    @staticmethod
    def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
        """
        清理字符串
        
        Args:
            text: 原始字符串
            max_length: 最大长度
            
        Returns:
            清理后的字符串
        """
        if not text:
            return ""
        
        # 去除首尾空白
        text = text.strip()
        
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 截断长度
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        return text

    @staticmethod
    def validate_json_structure(data: Dict, required_fields: List[str]) -> Dict[str, Any]:
        """
        验证JSON结构
        
        Args:
            data: 数据字典
            required_fields: 必需字段列表
            
        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "missing_fields": [],
            "extra_fields": []
        }
        
        # 检查必需字段
        for field in required_fields:
            if field not in data:
                result["valid"] = False
                result["missing_fields"].append(field)
        
        return result


# 创建全局验证器实例
validator = Validator()
