"""
基于大模型的意图识别器

支持：
- DeepSeek API
- 通义千问 API
- OpenAI 兼容接口

功能：
- 语义理解
- 意图分类
- 参数提取
- 置信度评分
"""
import json
import os
from typing import Dict, Any, Optional
from loguru import logger


class LLMIntentRecognizer:
    """基于大模型的意图识别器"""
    
    # 支持的意图
    SUPPORTED_INTENTS = {
        'download': '下载股票数据',
        'update': '更新数据',
        'status': '查看状态/统计信息',
        'cleanup': '清理缓存',
        'backtest': '回测策略',
        'workflow': '多步骤工作流',
        'sector_analysis': '板块分析',
        'unknown': '未知意图',
    }
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一个股票数据助手的意图识别专家。
请分析用户输入，提取意图和参数。

支持的意图：
- download: 下载数据（如"下载茅台 2024 年数据"）
- update: 更新数据（如"更新最近 30 天数据"）
- status: 查看状态（如"查看缓存状态"）
- cleanup: 清理缓存（如"清理旧数据"）
- backtest: 回测策略（如"回测双均线策略"）
- workflow: 多步骤工作流（如"下载数据然后回测"）
- sector_analysis: 板块分析（如"分析银行板块"）

股票名称映射：
- 茅台 -> 600519.SH
- 平安银行 -> 000001.SZ
- 万科 -> 000002.SZ
- 宁德时代 -> 300750.SZ
- 比亚迪 -> 002594.SZ

请分析用户输入，以 JSON 格式返回：
{
    "intent": "意图名称",
    "confidence": 0.0-1.0 的置信度,
    "parameters": {
        "ts_codes": ["股票代码列表"],
        "start_date": "开始日期 YYYYMMDD",
        "end_date": "结束日期 YYYYMMDD",
        "workers": 线程数（整数）,
        "strategy": "策略名称",
        "all_stocks": true/false
    },
    "reasoning": "简短的推理过程"
}

用户输入：{user_input}
"""

    def __init__(self, api_key: str = None, provider: str = 'deepseek'):
        """
        初始化 LLM 意图识别器
        
        Args:
            api_key: API 密钥，默认从环境变量读取
            provider: 提供商 ('deepseek', 'aliyun', 'openai')
        """
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)
        self.base_url = self._get_base_url(provider)
        self.model = self._get_model(provider)
        
        # 检查 API 密钥
        if not self.api_key:
            logger.warning("LLM API 密钥未设置，将降级到规则引擎")
            self.available = False
        else:
            self.available = True
            logger.info(f"LLM 意图识别器已初始化：{provider}/{self.model}")
    
    def _get_api_key(self, provider: str) -> str:
        """获取 API 密钥"""
        key_map = {
            'deepseek': os.getenv('DEEPSEEK_API_KEY'),
            'aliyun': os.getenv('DASHSCOPE_API_KEY'),
            'openai': os.getenv('OPENAI_API_KEY'),
        }
        return key_map.get(provider, '')
    
    def _get_base_url(self, provider: str) -> str:
        """获取 API 基础 URL"""
        url_map = {
            'deepseek': 'https://api.deepseek.com',
            'aliyun': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'openai': 'https://api.openai.com/v1',
        }
        return url_map.get(provider, 'https://api.deepseek.com')
    
    def _get_model(self, provider: str) -> str:
        """获取模型名称"""
        model_map = {
            'deepseek': 'deepseek-chat',
            'aliyun': 'qwen-turbo',
            'openai': 'gpt-3.5-turbo',
        }
        return model_map.get(provider, 'deepseek-chat')
    
    def recognize(self, command: str) -> Dict[str, Any]:
        """
        识别用户意图
        
        Args:
            command: 用户输入的命令
            
        Returns:
            识别结果字典
        """
        if not self.available:
            return self._fallback_result(command)
        
        try:
            result = self._call_llm(command)
            return self._parse_result(result, command)
        except Exception as e:
            logger.warning(f"LLM 意图识别失败：{e}，降级到规则引擎")
            return self._fallback_result(command)
    
    def _call_llm(self, command: str) -> str:
        """调用 LLM API"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            prompt = self.SYSTEM_PROMPT.format(user_input=command)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的意图识别助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except ImportError:
            logger.error("未安装 openai 库，请安装：pip install openai")
            raise ImportError("请安装 openai 库：pip install openai")
        except Exception as e:
            logger.error(f"LLM API 调用失败：{e}")
            raise
    
    def _parse_result(self, llm_response: str, original_command: str) -> Dict[str, Any]:
        """解析 LLM 返回结果"""
        try:
            # 尝试提取 JSON
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                result = json.loads(json_str)
            else:
                result = json.loads(llm_response)
            
            # 构建标准返回格式
            intent = result.get('intent', 'unknown')
            confidence = result.get('confidence', 0.5)
            params = result.get('parameters', {})
            
            return {
                'type': 'ai',
                'action': intent,
                'params': self._normalize_params(params),
                'confidence': confidence,
                'reasoning': result.get('reasoning', ''),
                'raw': original_command,
                'source': 'llm'
            }
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"解析 LLM 响应失败：{e}")
            return self._fallback_result(original_command)
    
    def _normalize_params(self, params: Dict) -> Dict:
        """标准化参数格式"""
        normalized = {}
        
        # 日期格式标准化
        for date_field in ['start_date', 'end_date']:
            if date_field in params:
                date_str = str(params[date_field])
                # 移除可能的分隔符
                date_str = date_str.replace('-', '').replace('/', '')
                normalized[date_field] = date_str
        
        # 股票代码
        if 'ts_codes' in params:
            codes = params['ts_codes']
            if isinstance(codes, str):
                codes = [codes]
            normalized['ts_codes'] = [c.upper().strip() for c in codes]
        
        # 单只股票代码
        if 'ts_code' in params:
            normalized['ts_code'] = str(params['ts_code']).upper().strip()
        
        # 线程数
        if 'workers' in params:
            try:
                w = int(params['workers'])
                normalized['workers'] = min(max(w, 1), 16)
            except (ValueError, TypeError):
                normalized['workers'] = 4
        
        # 全部股票标志
        if 'all_stocks' in params:
            normalized['all_stocks'] = bool(params['all_stocks'])
        
        # 策略名称
        if 'strategy' in params:
            normalized['strategy'] = str(params['strategy'])
        
        return normalized
    
    def _fallback_result(self, command: str) -> Dict[str, Any]:
        """降级结果（当 LLM 不可用时）"""
        return {
            'type': 'ai',
            'action': 'unknown',
            'params': {},
            'confidence': 0.0,
            'reasoning': 'LLM 不可用，降级到规则引擎',
            'raw': command,
            'source': 'fallback'
        }


# 全局实例
_global_recognizer: Optional[LLMIntentRecognizer] = None


def get_llm_recognizer(api_key: str = None, provider: str = 'deepseek') -> LLMIntentRecognizer:
    """获取全局 LLM 意图识别器实例"""
    global _global_recognizer
    if _global_recognizer is None:
        _global_recognizer = LLMIntentRecognizer(api_key, provider)
    return _global_recognizer


def recognize_intent(command: str, use_llm: bool = True) -> Dict[str, Any]:
    """
    便捷函数：识别用户意图
    
    Args:
        command: 用户输入
        use_llm: 是否使用 LLM
        
    Returns:
        识别结果
    """
    if use_llm:
        recognizer = get_llm_recognizer()
        if recognizer.available:
            return recognizer.recognize(command)
    
    # 降级到规则引擎
    from quant_strategy.tools.ai_assistant_pro import AIAssistantPro
    ai = AIAssistantPro()
    return ai.parse_command(command)
