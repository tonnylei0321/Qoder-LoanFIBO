#!/usr/bin/env python3
"""
继续执行剩余批次的LLM验证（从第2批开始）
"""

import json
import asyncio
import os
import glob
from pathlib import Path
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "siku_fibo_mapping_verification_v1.md"


def parse_prompt_file(file_path: Path) -> tuple[str, str]:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    system_start = content.find("## System Prompt")
    user_start = content.find("## User Prompt")
    
    system_prompt = content[system_start:user_start].replace("## System Prompt", "").strip()
    user_template = content[user_start:].replace("## User Prompt 模板", "").strip()
    
    return system_prompt, user_template


async def verify_single(llm, system_prompt, user_template, input_data):
    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    user_prompt = user_template.replace("{input_json}", input_json)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        content = response.content.strip()
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


async def process_batch(llm, system_prompt, user_template, batch_file, batch_num, total_batches):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 开始处理批次 {batch_num}/{total_batches}: {batch_file}")
    
    with open(batch_file, 'r', encoding='utf-8') as f:
        inputs = json.load(f)
    
    print(f"  批次包含 {len(inputs)} 个字段")
    
    results = []
    for i, inp in enumerate(inputs):
        field_code = inp['siku_field']['field_code']
        field_name = inp['siku_field']['field_name']
        
        print(f"  [{i+1}/{len(inputs)}] {field_code} - {field_name}", end=" ")
        
        result = await verify_single(llm, system_prompt, user_template, inp)
        results.append(result)
        
        if result.get('verification_result'):
            vr = result['verification_result']
            conf = vr.get('confidence_level', 'unknown')
            print(f"→ {conf}")
        elif result.get('uncertainty_exit'):
            print(f"→ uncertainty")
        elif result.get('error'):
            print(f"→ ERROR")
        else:
            print(f"→ unknown")
    
    # 保存批次结果
    output_file = batch_file.replace('.json', '_result.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"  批次结果已保存: {output_file}")
    
    # 批次统计
    def safe_get(r, key1, key2):
        if not r or not isinstance(r, dict):
            return None
        v = r.get(key1)
        if not v or not isinstance(v, dict):
            return None
        return v.get(key2)
    
    high = len([r for r in results if safe_get(r, 'verification_result', 'confidence_level') == 'high'])
    medium = len([r for r in results if safe_get(r, 'verification_result', 'confidence_level') == 'medium'])
    low = len([r for r in results if safe_get(r, 'verification_result', 'confidence_level') == 'low'])
    uncertainty = len([r for r in results if r and isinstance(r, dict) and r.get('uncertainty_exit')])
    errors = len([r for r in results if r and isinstance(r, dict) and r.get('error')])
    
    print(f"  批次统计: high={high}, medium={medium}, low={low}, uncertainty={uncertainty}, errors={errors}")
    
    return results


async def main():
    # 获取所有批次文件（排除已处理的和结果文件）
    batch_files = sorted(glob.glob('/tmp/hybrid_llm_batch_*.json'))
    batch_files = [f for f in batch_files if '_result' not in f and f != '/tmp/hybrid_llm_batch_001.json']
    
    total_batches = len(batch_files) + 1  # +1 for already processed batch 1
    print(f"发现 {len(batch_files)} 个待处理批次文件（第1批已完成）")
    
    # 解析Prompt
    system_prompt, user_template = parse_prompt_file(PROMPT_FILE)
    print("Prompt加载完成")
    
    # 初始化LLM
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "qwen-max"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0.1,
        max_retries=3
    )
    print(f"LLM初始化完成: {llm.model_name}")
    
    # 处理所有批次
    all_results = []
    start_time = datetime.now()
    
    for i, batch_file in enumerate(batch_files, 2):  # Start from batch 2
        batch_results = await process_batch(llm, system_prompt, user_template, batch_file, i, total_batches)
        all_results.extend(batch_results)
        
        # 每5批暂停一下
        if i % 5 == 0 and i < total_batches:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 已处理 {i}/{total_batches} 批，暂停10秒...")
            await asyncio.sleep(10)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # 最终统计
    print("\n" + "="*80)
    print("全部批次处理完成")
    print("="*80)
    print(f"总耗时: {duration:.1f}秒 ({duration/60:.1f}分钟)")
    print(f"总验证字段: {len(all_results)}")
    
    def safe_get(r, key1, key2):
        if not r or not isinstance(r, dict):
            return None
        v = r.get(key1)
        if not v or not isinstance(v, dict):
            return None
        return v.get(key2)
    
    high = len([r for r in all_results if safe_get(r, 'verification_result', 'confidence_level') == 'high'])
    medium = len([r for r in all_results if safe_get(r, 'verification_result', 'confidence_level') == 'medium'])
    low = len([r for r in all_results if safe_get(r, 'verification_result', 'confidence_level') == 'low'])
    reject = len([r for r in all_results if safe_get(r, 'verification_result', 'confidence_level') == 'reject'])
    uncertainty = len([r for r in all_results if r and isinstance(r, dict) and r.get('uncertainty_exit')])
    errors = len([r for r in all_results if r and isinstance(r, dict) and r.get('error')])
    
    print(f"\n置信度分布:")
    print(f"  高置信度(high): {high} ({high/len(all_results)*100:.1f}%)")
    print(f"  中置信度(medium): {medium} ({medium/len(all_results)*100:.1f}%)")
    print(f"  低置信度(low): {low} ({low/len(all_results)*100:.1f}%)")
    print(f"  拒绝(reject): {reject} ({reject/len(all_results)*100:.1f}%)")
    print(f"  不确定性出口: {uncertainty} ({uncertainty/len(all_results)*100:.1f}%)")
    print(f"  错误: {errors}")
    
    # 保存完整结果
    output = {
        "summary": {
            "total": len(all_results),
            "high": high,
            "medium": medium,
            "low": low,
            "reject": reject,
            "uncertainty": uncertainty,
            "errors": errors,
            "duration_seconds": duration
        },
        "results": all_results
    }
    
    with open('/tmp/hybrid_llm_remaining_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整结果已保存: /tmp/hybrid_llm_remaining_results.json")


if __name__ == "__main__":
    asyncio.run(main())
