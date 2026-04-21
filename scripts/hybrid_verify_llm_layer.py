#!/usr/bin/env python3
"""
混合验证 - LLM验证层（简化版）
"""

import json
import asyncio
import os
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# 读取Prompt文件
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "siku_fibo_mapping_verification_v1.md"


def parse_prompt_file(file_path: Path) -> tuple[str, str]:
    """解析Prompt文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取System Prompt
    system_start = content.find("## System Prompt")
    user_start = content.find("## User Prompt")
    
    system_prompt = content[system_start:user_start].replace("## System Prompt", "").strip()
    
    # 提取User Prompt模板
    user_template = content[user_start:].replace("## User Prompt 模板", "").strip()
    
    return system_prompt, user_template


async def verify_single(llm, system_prompt, user_template, input_data):
    """验证单个字段"""
    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    user_prompt = user_template.replace("{input_json}", input_json)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        content = response.content.strip()
        
        # 移除markdown代码块
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        result["_input"] = input_data
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "_input": input_data
        }


async def main():
    # 读取输入
    with open('/tmp/hybrid_llm_inputs.json', 'r', encoding='utf-8') as f:
        inputs = json.load(f)
    
    print(f"加载了 {len(inputs)} 个字段待验证")
    
    # 解析Prompt
    system_prompt, user_template = parse_prompt_file(PROMPT_FILE)
    print("Prompt加载完成")
    
    # 初始化LLM
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "qwen-max"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0.1,
        max_retries=3
    )
    print(f"LLM初始化完成: {llm.model_name}")
    
    # 串行验证（避免并发问题）
    results = []
    for i, inp in enumerate(inputs):
        print(f"\n验证 [{i+1}/{len(inputs)}]: {inp['siku_field']['field_code']} - {inp['siku_field']['field_name']}")
        result = await verify_single(llm, system_prompt, user_template, inp)
        results.append(result)
        
        # 打印简要结果
        if result.get('verification_result'):
            vr = result['verification_result']
            print(f"  置信度: {vr.get('confidence_score')} ({vr.get('confidence_level')})")
            if vr.get('correction', {}).get('needs_correction'):
                print(f"  需要修正: {vr['correction'].get('suggested_fiboclass')}.{vr['correction'].get('suggested_fiboproperty')}")
        elif result.get('uncertainty_exit'):
            print(f"  不确定性出口: {result.get('exit_reason', '')[:50]}...")
        elif result.get('error'):
            print(f"  错误: {result['error']}")
    
    # 统计
    print("\n" + "="*80)
    print("验证结果统计")
    print("="*80)
    
    high = [r for r in results if r.get('verification_result', {}).get('confidence_level') == 'high']
    medium = [r for r in results if r.get('verification_result', {}).get('confidence_level') == 'medium']
    low = [r for r in results if r.get('verification_result', {}).get('confidence_level') == 'low']
    reject = [r for r in results if r.get('verification_result', {}).get('confidence_level') == 'reject']
    uncertainty = [r for r in results if r.get('uncertainty_exit')]
    errors = [r for r in results if r.get('error')]
    
    total = len(results)
    print(f"总验证数: {total}")
    print(f"高置信度: {len(high)} ({len(high)/total*100:.1f}%)")
    print(f"中置信度: {len(medium)} ({len(medium)/total*100:.1f}%)")
    print(f"低置信度: {len(low)} ({len(low)/total*100:.1f}%)")
    print(f"拒绝: {len(reject)} ({len(reject)/total*100:.1f}%)")
    print(f"不确定性出口: {len(uncertainty)} ({len(uncertainty)/total*100:.1f}%)")
    print(f"错误: {len(errors)}")
    
    # 保存结果
    output = {
        "summary": {
            "total": total,
            "high": len(high),
            "medium": len(medium),
            "low": len(low),
            "reject": len(reject),
            "uncertainty": len(uncertainty),
            "errors": len(errors)
        },
        "results": results
    }
    
    with open('/tmp/hybrid_llm_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: /tmp/hybrid_llm_results.json")


if __name__ == "__main__":
    asyncio.run(main())
