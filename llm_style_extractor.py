import asyncio
import json
import logging
import random
from typing import List, Dict
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database import db
from api_models import model_manager
from style_learner import StyleProfile, STYLE_DIR, style_learner

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMStyleExtractor:
    def __init__(self):
        self.chunk_size = 500

    async def extract_from_database(self, character_id: str = "default", limit: int = 3000):
        """通看聊天记录进行综合提取 (Look through up to 3000 records for comprehensive extraction)"""
        
        # 1. 基础特征依然通过传统的正则计算得到（保底）
        basic_profile = style_learner.learn_from_database(character_id)
        if not basic_profile:
            basic_profile = StyleProfile()
            
        logger.info(f"开始使用大语言模型通读及深度提取角色 {character_id} 的风格...")
        pairs = db.get_conversation_pairs(limit=limit, character_id=character_id)
        
        valid_pairs = [p for p in pairs if p.get('ai_response') and p.get('user_message')]
        
        # 筛选具备实际信息量的对话（过滤过短的哦、嗯）
        meaningful_pairs = [
            p for p in valid_pairs 
            if len(p['ai_response']) > 2 or '?' in p['ai_response'] or len(p['user_message']) > 2
        ]
        
        if len(meaningful_pairs) > limit:
            meaningful_pairs = meaningful_pairs[-limit:]
            
        if not meaningful_pairs:
            logger.warning("没有足够有意义的对话进行LLM提取")
            return basic_profile

        # 分块（避免上下文过长）
        chunks = []
        current_chunk = []
        current_len = 0
        for p in meaningful_pairs:
            # Add dialogue text
            text = f"男朋友: {p['user_message']}\n她(被模仿对象): {p['ai_response']}\n"
            if current_len + len(text) > 4000:  # 约 4000 字符一块
                chunks.append("\n".join(current_chunk))
                current_chunk = [text]
                current_len = len(text)
            else:
                current_chunk.append(text)
                current_len += len(text)
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))
            
        logger.info(f"分成 {len(chunks)} 个片段进行深度分析...")
        
        # 抽样处理（如果切件太多，只抽取首、中、尾最具代表性的片段，控制成本和时间）
        if len(chunks) > 5:
            sampled_chunks = chunks[-2:] + [chunks[0]] + random.sample(chunks[1:-2], 2)
        else:
            sampled_chunks = chunks
            
        all_catchphrases = []
        all_quirks = []
        all_endings = []
        all_moods = []

        extract_prompt_template = """你是一个高级语言病理学和角色性格分析专家。
分析以下真实情侣聊天记录中“她(被模仿对象)”的发言，精准提取她的语言特征。

要求：
1. 提取的“口头禅”和“句尾语气词”必须是她真实高频使用的词汇。
2. 提取的“代表性原句”必须是一字不差的原文，且能高度体现出她的性格、傲娇、小脾气或撒娇等特殊特征。
3. 请以严格的 JSON 格式输出（不要有任何其他分析文本）：

{
  "catchphrases": ["真实提取的口头禅1", "口头禅2", "常用词或短语"], 
  "quirks": ["说话小习惯，比如喜欢怎么连发表情、是否喜欢用特定符号、叠词习惯等"],
  "sentence_endings": ["她最爱用的句尾语气词(如: 哒, 鸭, 嘛)"],
  "signature_sentences": ["原句1...", "原句2..."]
}

以下为聊天记录片段：
"""

        for idx, chunk in enumerate(sampled_chunks):
            logger.info(f"正在分析第 {idx+1}/{len(sampled_chunks)} 个片段...")
            try:
                # Wrap with asyncio.wait_for to prevent infinite hang from WAF
                response = await asyncio.wait_for(
                    model_manager.generate(
                        message=extract_prompt_template + chunk, 
                        temperature=0.3, 
                        max_tokens=1500
                    ),
                    timeout=45.0
                )
                logger.info(f"成功获取 LLM 响应，长度 {len(response)}")
                logger.info(f"响应内容片段: {response[:300]}")
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    all_catchphrases.extend(data.get('catchphrases', []))
                    all_quirks.extend(data.get('quirks', []))
                    all_endings.extend(data.get('sentence_endings', []))
                    all_moods.extend(data.get('signature_sentences', []))
            except Exception as e:
                logger.error(f"提取特征时出错: {e}")

        # Meta summarization phase
        meta_prompt = f"""
你是一个角色侧写大师。我为你汇总了多个聊天片段中提取的女友语言特征：

初步提取的口头禅：{json.dumps(all_catchphrases, ensure_ascii=False)}
习惯小癖好：{json.dumps(all_quirks, ensure_ascii=False)}
句尾语气词：{json.dumps(all_endings, ensure_ascii=False)}
代表性原句：{json.dumps(all_moods, ensure_ascii=False)}

请对这些数据进行去重、精炼和筛选，保留最核心、最像真人语气的内容：
- 返回 8个 最独特的高频口头禅/常用短语
- 返回 6个 最典型的说话习惯标签
- 返回 6个 最真实的高频语气词
- 返回 8句 最能体现她灵魂的代表性原句（不要改变原话）

请严格返回可被解析的 JSON 字符串（不要加任何代码块标记）：
{{
  "final_catchphrases": ["..."],
  "final_quirks": ["..."],
  "final_endings": ["..."],
  "final_signatures": ["..."]
}}
"""
        logger.info("综合 3000 条记录的信息，正在生成最终风格总结...")
        try:
            final_res = await asyncio.wait_for(
                model_manager.generate(
                    message=meta_prompt,
                    temperature=0.4,
                    max_tokens=2048
                ),
                timeout=60.0
            )
            import re
            json_match = re.search(r'\{.*\}', final_res, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                # 覆写或合并到 basic_profile
                if data.get("final_catchphrases"):
                    basic_profile.catchphrases = data["final_catchphrases"]
                if data.get("final_quirks"):
                    basic_profile.style_tags = data["final_quirks"]
                if data.get("final_endings"):
                    # For dict-based ending_styles, just assign a high frequency to keep them on top
                    basic_profile.ending_styles = {e: 10 for e in data["final_endings"]}
                if data.get("final_signatures"):
                    basic_profile.signature_sentences = data["final_signatures"]
        except Exception as e:
            logger.error(f"生成最终总结出错: {e}")
            
        # Save to disk
        path = STYLE_DIR / f"{character_id}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(basic_profile.to_dict(), f, ensure_ascii=False, indent=2)
            
        logger.info(f"✅ 基于 LLM 的3000条记录深度综合提取完成，已保存至 {path} ！")
        return basic_profile

async def main():
    extractor = LLMStyleExtractor()
    await extractor.extract_from_database("default", limit=3000)

if __name__ == "__main__":
    asyncio.run(main())
