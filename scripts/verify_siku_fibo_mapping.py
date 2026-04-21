#!/usr/bin/env python3
"""
司库监管字段FIBO映射验证脚本
使用LLM验证规则映射结果，评估置信度
"""

import json
import asyncio
import os
from typing import List, Dict, Any
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入LLM调用库
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# 读取Prompt文件
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "siku_fibo_mapping_verification_v1.md"


def parse_prompt_file(file_path: Path) -> tuple[str, str]:
    """解析Prompt文件，提取System Prompt和User Prompt模板"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取System Prompt（从"## System Prompt"到"## User Prompt"之前）
    system_start = content.find("## System Prompt")
    user_start = content.find("## User Prompt")
    
    if system_start == -1 or user_start == -1:
        raise ValueError("Prompt文件格式不正确")
    
    system_prompt = content[system_start:user_start].strip()
    # 移除"## System Prompt"标题
    system_prompt = system_prompt.replace("## System Prompt", "").strip()
    
    # 提取User Prompt模板
    user_template = content[user_start:].strip()
    user_template = user_template.replace("## User Prompt 模板", "").strip()
    
    return system_prompt, user_template


def create_verification_input(
    siku_field: Dict[str, Any],
    rule_mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """创建验证输入"""
    return {
        "siku_field": {
            "field_code": siku_field.get("field_code", ""),
            "field_name": siku_field.get("field_name", ""),
            "module": siku_field.get("module", ""),
            "field_type": siku_field.get("field_type", ""),
            "field_length": siku_field.get("field_length", ""),
            "field_rule": siku_field.get("field_rule", "N/A")[:200]  # 截断避免过长
        },
        "rule_mapping": {
            "mapping_type": rule_mapping.get("mapping_type", ""),
            "fiboclass": rule_mapping.get("fiboclass", rule_mapping.get("fibo_attribute", "")),
            "fiboproperty": rule_mapping.get("fiboproperty", rule_mapping.get("final_fibo", "")),
            "notes": rule_mapping.get("notes", rule_mapping.get("description", ""))
        }
    }


async def verify_single_field(
    llm: ChatOpenAI,
    system_prompt: str,
    user_template: str,
    siku_field: Dict[str, Any],
    rule_mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """验证单个字段的映射"""
    
    # 创建输入
    input_data = create_verification_input(siku_field, rule_mapping)
    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    
    # 构建User Prompt
    user_prompt = user_template.replace("{input_json}", input_json)
    
    try:
        # 调用LLM
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        # 解析响应
        content = response.content.strip()
        
        # 移除可能的markdown代码块
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # 解析JSON
        result = json.loads(content)
        
        # 添加元数据
        result["_meta"] = {
            "field_code": siku_field.get("field_code"),
            "field_name": siku_field.get("field_name"),
            "module": siku_field.get("module")
        }
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "_meta": {
                "field_code": siku_field.get("field_code"),
                "field_name": siku_field.get("field_name"),
                "module": siku_field.get("module")
            },
            "error": f"JSON解析失败: {e}",
            "raw_response": content if 'content' in locals() else None
        }
    except Exception as e:
        return {
            "_meta": {
                "field_code": siku_field.get("field_code"),
                "field_name": siku_field.get("field_name"),
                "module": siku_field.get("module")
            },
            "error": f"LLM调用失败: {e}"
        }


async def batch_verify(
    input_file: str,
    output_file: str,
    max_concurrency: int = 5,
    sample_size: int = None
) -> None:
    """
    批量验证映射结果
    
    Args:
        input_file: 输入JSON文件路径（规则映射结果）
        output_file: 输出JSON文件路径
        max_concurrency: 最大并发数
        sample_size: 抽样数量（None表示全部）
    """
    
    # 加载输入数据
    with open(input_file, 'r', encoding='utf-8') as f:
        all_mappings = json.load(f)
    
    # 如果指定了抽样数量，随机抽样
    if sample_size and sample_size < len(all_mappings):
        import random
        mappings = random.sample(all_mappings, sample_size)
        print(f"从{len(all_mappings)}个字段中抽样{sample_size}个进行验证")
    else:
        mappings = all_mappings
        print(f"验证全部{len(mappings)}个字段")
    
    # 解析Prompt
    system_prompt, user_template = parse_prompt_file(PROMPT_FILE)
    print(f"已加载Prompt文件: {PROMPT_FILE}")
    
    # 初始化LLM
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "qwen-max"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0.1,  # 低温度确保一致性
        max_retries=3
    )
    print(f"已初始化LLM: {llm.model_name}")
    
    # 使用信号量控制并发
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def verify_with_limit(siku_field, rule_mapping):
        async with semaphore:
            return await verify_single_field(
                llm, system_prompt, user_template, siku_field, rule_mapping
            )
    
    # 创建任务
    tasks = []
    for m in mappings:
        # 确定使用哪个映射结果
        if "mapping_type" in m:
            rule_mapping = m
        elif "final_category" in m:
            rule_mapping = {
                "mapping_type": m.get("final_category"),
                "fiboclass": m.get("final_fibo"),
                "notes": m.get("final_desc")
            }
        else:
            continue
        
        tasks.append(verify_with_limit(m, rule_mapping))
    
    # 执行验证
    print(f"开始验证，并发数: {max_concurrency}...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果
    valid_results = []
    errors = []
    
    for r in results:
        if isinstance(r, Exception):
            errors.append({"error": str(r)})
        elif r is None:
            errors.append({"error": "返回结果为None"})
        elif isinstance(r, dict) and "error" in r:
            errors.append(r)
        else:
            valid_results.append(r)
    
    # 统计
    def safe_get_confidence_level(r):
        if not r or not isinstance(r, dict):
            return None
        vr = r.get("verification_result")
        if not vr or not isinstance(vr, dict):
            return None
        return vr.get("confidence_level")
    
    high_confidence = [r for r in valid_results if safe_get_confidence_level(r) == "high"]
    medium_confidence = [r for r in valid_results if safe_get_confidence_level(r) == "medium"]
    low_confidence = [r for r in valid_results if safe_get_confidence_level(r) == "low"]
    reject = [r for r in valid_results if safe_get_confidence_level(r) == "reject"]
    uncertainty = [r for r in valid_results if r and isinstance(r, dict) and r.get("uncertainty_exit")]
    
    print("\n" + "="*80)
    print("验证结果统计")
    print("="*80)
    total_results = len(results) if len(results) > 0 else 1  # 避免除零
    print(f"总验证数: {len(results)}")
    print(f"高置信度(high): {len(high_confidence)} ({len(high_confidence)/total_results*100:.1f}%)")
    print(f"中置信度(medium): {len(medium_confidence)} ({len(medium_confidence)/total_results*100:.1f}%)")
    print(f"低置信度(low): {len(low_confidence)} ({len(low_confidence)/total_results*100:.1f}%)")
    print(f"拒绝(reject): {len(reject)} ({len(reject)/total_results*100:.1f}%)")
    print(f"不确定性出口: {len(uncertainty)} ({len(uncertainty)/total_results*100:.1f}%)")
    print(f"错误: {len(errors)}")
    
    # 保存结果
    output_data = {
        "summary": {
            "total": len(results),
            "high_confidence": len(high_confidence),
            "medium_confidence": len(medium_confidence),
            "low_confidence": len(low_confidence),
            "reject": len(reject),
            "uncertainty": len(uncertainty),
            "errors": len(errors)
        },
        "results": valid_results,
        "errors": errors
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存至: {output_file}")
    
    # 输出需要修正的字段
    if low_confidence or reject:
        print("\n" + "="*80)
        print("需要修正的字段（低置信度或拒绝）")
        print("="*80)
        for r in low_confidence + reject:
            vr = r.get("verification_result", {})
            print(f"  {vr.get('field_code'):25s} | {vr.get('field_name'):20s} | 置信度: {vr.get('confidence_score')}")
            if vr.get("correction", {}).get("needs_correction"):
                print(f"    建议修正: {vr.get('correction', {}).get('suggested_fiboclass')}.{vr.get('correction', {}).get('suggested_fiboproperty')}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="验证司库字段FIBO映射")
    parser.add_argument("--input", "-i", default="/tmp/sikufields_fibo_mapping.json",
                       help="输入JSON文件路径")
    parser.add_argument("--output", "-o", default="/tmp/sikufields_verification_result.json",
                       help="输出JSON文件路径")
    parser.add_argument("--concurrency", "-c", type=int, default=5,
                       help="最大并发数")
    parser.add_argument("--sample", "-s", type=int, default=None,
                       help="抽样数量（默认全部）")
    
    args = parser.parse_args()
    
    asyncio.run(batch_verify(
        input_file=args.input,
        output_file=args.output,
        max_concurrency=args.concurrency,
        sample_size=args.sample
    ))
