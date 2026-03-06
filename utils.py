"""
utility工具函数
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def load_json_file(file_path: Path) -> Optional[Dict]:
    """安全地加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON文件失败 ({file_path}): {e}")
        return None


def save_json_file(file_path: Path, data, pretty: bool = True):
    """安全地保存JSON文件"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(data, f, ensure_ascii=False)
        logger.info(f"JSON文件已保存: {file_path}")
    except Exception as e:
        logger.error(f"保存JSON文件失败 ({file_path}): {e}")


def normalize_text(text: str) -> str:
    """规范化文本"""
    # 删除多余空格
    text = ' '.join(text.split())
    # 转为简体中文
    # （可选，根据需要扩展）
    return text


def estimate_tokens(text: str) -> int:
    """粗略估计token数量"""
    # 中文平均3个字符1个token
    # 英文平均5个字符1个token
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_words = len(text.split())
    
    return chinese_count // 3 + english_words // 5


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_memory_for_display(memory: Dict) -> str:
    """格式化记忆用于显示"""
    return f"{memory.get('category', '')}: {memory.get('key', '')} - {memory.get('content', '')}"


def merge_similarity_scores(scores: List[float], method: str = 'average') -> float:
    """合并多个相似度评分"""
    if not scores:
        return 0.0
    
    if method == 'average':
        return sum(scores) / len(scores)
    elif method == 'max':
        return max(scores)
    elif method == 'min':
        return min(scores)
    else:
        return sum(scores) / len(scores)


class TextProcessor:
    """文本处理工具类"""
    
    @staticmethod
    def remove_emojis(text: str) -> str:
        """移除emoji"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  
            "\U0001F300-\U0001F5FF"  
            "\U0001F680-\U0001F6FF"  
            "\U0001F1E0-\U0001F1FF"  
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub(r'', text)
    
    @staticmethod
    def extract_emojis(text: str) -> List[str]:
        """提取emoji"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "]+"
        )
        return emoji_pattern.findall(text)
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """提取URL"""
        import re
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def is_question(text: str) -> bool:
        """判断是否是问句"""
        return text.strip().endswith('?') or text.strip().endswith('？')
    
    @staticmethod
    def is_exclamation(text: str) -> bool:
        """判断是否是感叹句"""
        return text.strip().endswith('!') or text.strip().endswith('！')


if __name__ == "__main__":
    # 简单测试
    test_text = "这是一个 测试 文本 😄"
    print(f"原文: {test_text}")
    print(f"Token数估计: {estimate_tokens(test_text)}")
    print(f"截断: {truncate_text(test_text, max_length=10)}")
