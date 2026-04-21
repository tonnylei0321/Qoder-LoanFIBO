#!/usr/bin/env python3
"""
LLM验证进度监控脚本
"""

import json
import glob
import time
from datetime import datetime

def check_progress():
    # 检查已完成的批次
    result_files = sorted(glob.glob('/tmp/hybrid_llm_batch_*_result.json'))
    total_batches = 19
    completed = len(result_files)
    
    # 统计已完成的结果
    total_processed = 0
    stats = {'high': 0, 'medium': 0, 'low': 0, 'uncertainty': 0, 'error': 0}
    
    for result_file in result_files:
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        total_processed += len(results)
        
        for r in results:
            if r and isinstance(r, dict):
                if r.get('verification_result'):
                    level = r['verification_result'].get('confidence_level', 'unknown')
                    stats[level] = stats.get(level, 0) + 1
                elif r.get('uncertainty_exit'):
                    stats['uncertainty'] += 1
                elif r.get('error'):
                    stats['error'] += 1
    
    # 估算剩余时间
    avg_time_per_batch = 2.5
    remaining_batches = total_batches - completed
    estimated_remaining = remaining_batches * avg_time_per_batch
    
    return {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'completed': completed,
        'total': total_batches,
        'percentage': completed / total_batches * 100,
        'processed': total_processed,
        'stats': stats,
        'remaining_minutes': estimated_remaining
    }

if __name__ == "__main__":
    print("="*80)
    print("LLM验证进度监控")
    print("="*80)
    print("按 Ctrl+C 停止监控\n")
    
    try:
        while True:
            progress = check_progress()
            
            print(f"\r[{progress['timestamp']}] "
                  f"批次: {progress['completed']}/{progress['total']} "
                  f"({progress['percentage']:.1f}%) | "
                  f"字段: {progress['processed']} | "
                  f"剩余: {progress['remaining_minutes']:.0f}分钟", 
                  end='', flush=True)
            
            # 如果完成，显示最终统计
            if progress['completed'] >= progress['total']:
                print("\n\n" + "="*80)
                print("验证完成！")
                print("="*80)
                print(f"\n总处理字段: {progress['processed']}")
                print(f"\n置信度分布:")
                for level, count in sorted(progress['stats'].items(), key=lambda x: -x[1]):
                    if count > 0:
                        print(f"  {level:12s}: {count:3d} ({count/progress['processed']*100:5.1f}%)")
                break
            
            time.sleep(10)  # 每10秒检查一次
            
    except KeyboardInterrupt:
        print("\n\n监控已停止")
