# LLM Caller - 模型路由配置

## 模型能力矩阵

| 模型 | 上下文长度 | 特点 | 适用场景 |
|------|-----------|------|----------|
| qwen-max | 32K | 最强推理能力 | 复杂分析、代码评审、架构设计 |
| qwen-long | 1000万 | 超长上下文 | 长文档处理、批量数据处理 |
| qwen-turbo | 8K | 快速响应 | 简单问答、快速任务 |

## 任务路由表

```python
# backend/app/agents/llm_caller.py

ROUTING_TABLE = {
    # 评审类任务 - 需要强推理能力
    "requirement_review": {
        "model": "qwen-max",
        "temperature": 0.2,
        "timeout": 45,
        "max_retries": 2,
        "fallback": "qwen-turbo"
    },
    "design_review": {
        "model": "qwen-max",
        "temperature": 0.2,
        "timeout": 60,
        "max_retries": 2
    },
    "code_review": {
        "model": "qwen-max",
        "temperature": 0.1,
        "timeout": 45,
        "max_retries": 2,
        "fallback": "qwen-turbo"
    },
    "test_review": {
        "model": "qwen-max",
        "temperature": 0.1,
        "timeout": 30,
        "max_retries": 2
    },
    "security_review": {
        "model": "qwen-max",
        "temperature": 0.05,  # 安全评审需要更确定性
        "timeout": 45,
        "max_retries": 3
    },
    
    # 映射类任务 - 需要长上下文
    "data_mapping": {
        "model": "qwen-long",
        "temperature": 0.1,
        "timeout": 120,
        "max_retries": 2,
        "fallback": "qwen-max"
    },
    "ontology_mapping": {
        "model": "qwen-long",
        "temperature": 0.1,
        "timeout": 120,
        "max_retries": 2,
        "fallback": "qwen-max"
    },
    "document_analysis": {
        "model": "qwen-long",
        "temperature": 0.2,
        "timeout": 90,
        "max_retries": 2
    },
    
    # 生成类任务
    "code_generation": {
        "model": "qwen-max",
        "temperature": 0.2,
        "timeout": 60,
        "max_retries": 2
    },
    "test_generation": {
        "model": "qwen-max",
        "temperature": 0.2,
        "timeout": 45,
        "max_retries": 2
    },
    "doc_generation": {
        "model": "qwen-long",
        "temperature": 0.3,
        "timeout": 60,
        "max_retries": 2
    },
    
    # 快速任务
    "quick_answer": {
        "model": "qwen-turbo",
        "temperature": 0.3,
        "timeout": 15,
        "max_retries": 1
    },
    "classification": {
        "model": "qwen-turbo",
        "temperature": 0.1,
        "timeout": 10,
        "max_retries": 1
    }
}
```

## 降级策略

### 自动降级条件

1. **超时降级**
   - 主模型响应超过 timeout 的 80% 时，触发降级
   - 降级到 fallback 模型，timeout 缩短 50%

2. **错误降级**
   - 连续 max_retries 次失败后，触发降级
   - 记录错误日志，标记为 fallback 调用

3. **成本降级**（可选）
   - 当检测到简单任务时，自动降级到更便宜的模型
   - 需要配置任务复杂度评估规则

### 降级实现示例

```python
async def call_with_fallback(
    self,
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: Dict
) -> AgentResponse:
    """带降级策略的 LLM 调用"""
    
    config = self.ROUTING_TABLE[task_type]
    
    # 尝试主模型
    try:
        return await self._execute(
            model=config["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
            config=config
        )
    except (TimeoutError, LLMError) as e:
        logger.warning(f"Primary model {config['model']} failed: {e}")
        
        # 检查是否有降级模型
        if config.get("fallback"):
            logger.info(f"Falling back to {config['fallback']}")
            
            # 调整配置（缩短超时）
            fallback_config = {
                **config,
                "model": config["fallback"],
                "timeout": config["timeout"] // 2,
                "max_retries": 1
            }
            
            return await self._execute(
                model=config["fallback"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                config=fallback_config,
                is_fallback=True
            )
        
        raise
```

## 性能监控

### 关键指标

```python
@dataclass
class LLMMetrics:
    """LLM 调用指标"""
    model: str
    task_type: str
    latency_ms: int
    token_usage: Dict[str, int]
    success: bool
    is_fallback: bool
    has_uncertainty: bool
    confidence: float
    timestamp: datetime
```

### 监控面板

```python
# 统计指标
metrics = {
    "total_calls": 0,
    "success_rate": 0.0,
    "avg_latency_ms": 0,
    "fallback_rate": 0.0,
    "uncertainty_exit_rate": 0.0,
    "avg_confidence": 0.0,
    "token_usage": {
        "prompt": 0,
        "completion": 0
    }
}

# 按模型统计
model_metrics = {
    "qwen-max": {"calls": 0, "success": 0, "avg_latency": 0},
    "qwen-long": {"calls": 0, "success": 0, "avg_latency": 0},
    "qwen-turbo": {"calls": 0, "success": 0, "avg_latency": 0}
}

# 按任务类型统计
task_metrics = {
    "code_review": {"calls": 0, "avg_confidence": 0},
    "data_mapping": {"calls": 0, "avg_confidence": 0},
    # ...
}
```

## 配置示例

```python
# config.py

class LLMSettings(BaseSettings):
    """LLM 配置"""
    
    # API 配置
    DASHSCOPE_API_KEY: str
    DASHSCOPE_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # 默认配置
    DEFAULT_TEMPERATURE: float = 0.1
    DEFAULT_TIMEOUT: int = 30
    DEFAULT_MAX_RETRIES: int = 2
    
    # 置信度阈值
    CONFIDENCE_THRESHOLD: float = 0.6
    HIGH_CONFIDENCE_THRESHOLD: float = 0.8
    
    # 降级配置
    ENABLE_FALLBACK: bool = True
    FALLBACK_TIMEOUT_RATIO: float = 0.5
    
    # 监控配置
    ENABLE_METRICS: bool = True
    METRICS_RETENTION_DAYS: int = 30
```
