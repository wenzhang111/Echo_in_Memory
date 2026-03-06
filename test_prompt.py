import asyncio
from api_models import model_manager

async def main():
    print('Sending prompt...')
    prompt = '''你是一个高级语言病理学和角色性格分析专家。
请以严格的 JSON 格式输出（不要有任何其他分析文本）：
{
  "catchphrases": ["真实提取的口头禅1", "口头禅2"], 
  "quirks": ["说话小习惯"],
  "sentence_endings": ["她最爱用的句尾语气词"],
  "signature_sentences": ["原句1..."]
}

以下为聊天记录片段：
男朋友: 测试
她(被模仿对象): 测试你个大头鬼
'''
    try:
        res = await model_manager.generate(message=prompt, temperature=0.3)
        print('res:', res)
    except Exception as e:
        print('err', e)

asyncio.run(main())
