"""
复杂指令解析器

支持：
- 多步骤工作流 (Workflow)
- 条件判断 (if/else)
- 变量引用 ($var)
- 循环 (for each)
- 并行执行
"""
import re
import asyncio
import yaml
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from enum import Enum

from .skill_system import SkillResult, get_executor, get_registry


class InstructionType(Enum):
    """指令类型"""
    SIMPLE = "simple"           # 简单指令
    WORKFLOW = "workflow"       # 工作流
    CONDITIONAL = "conditional" # 条件指令
    LOOP = "loop"              # 循环
    PARALLEL = "parallel"       # 并行
    VARIABLE = "variable"       # 变量定义


@dataclass
class ParsedInstruction:
    """解析后的指令"""
    type: InstructionType
    raw: str
    steps: List[Dict] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    conditions: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    skill: str
    params: Dict[str, Any]
    condition: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    output_var: Optional[str] = None


class CommandParser:
    """命令解析器"""
    
    def __init__(self):
        # 变量模式 $var 或 ${var}
        self.var_pattern = re.compile(r'\$\{?(\w+)\}?')
        
        # 工作流标记
        self.workflow_markers = ['然后', '接着', '再', 'and then', '&&', ';', '\n']
        
        # 条件标记
        self.conditional_markers = ['如果', '假如', 'if ', '否则', 'else']
        
        # 循环标记
        self.loop_markers = ['对每个', '遍历', 'for each', '循环']
        
        # 并行标记
        self.parallel_markers = ['同时', '并行', 'parallel', '&']
    
    def parse(self, command: str) -> ParsedInstruction:
        """解析命令"""
        command = command.strip()
        
        # 1. 检查是否包含变量定义
        variables = self._extract_variables(command)
        
        # 2. 检查是否是多步骤工作流
        if self._is_workflow(command):
            return self._parse_workflow(command, variables)
        
        # 3. 检查是否是条件指令
        if self._is_conditional(command):
            return self._parse_conditional(command, variables)
        
        # 4. 检查是否是循环指令
        if self._is_loop(command):
            return self._parse_loop(command, variables)
        
        # 5. 检查是否是并行指令
        if self._is_parallel(command):
            return self._parse_parallel(command, variables)
        
        # 6. 简单指令
        return self._parse_simple(command, variables)
    
    def _extract_variables(self, command: str) -> Dict[str, Any]:
        """提取变量定义"""
        variables = {}
        
        # 匹配 "设 X 为 Y" 或 "set X = Y"
        set_patterns = [
            r'设\s*(\w+)\s*(?:为 | 等于 |=)\s*([^\s,;]+)',
            r'set\s+(\w+)\s*=\s*([^\s,;]+)',
        ]
        
        for pattern in set_patterns:
            matches = re.findall(pattern, command, re.IGNORECASE)
            for name, value in matches:
                variables[name] = self._parse_value(value)
        
        return variables
    
    def _parse_value(self, value: str) -> Any:
        """解析值"""
        value = value.strip().strip('"\'')
        
        # 数字
        if value.isdigit():
            return int(value)
        
        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass
        
        # 布尔值
        if value.lower() in ['true', '是', 'yes']:
            return True
        if value.lower() in ['false', '否', 'no']:
            return False
        
        # 列表
        if value.startswith('[') and value.endswith(']'):
            return [v.strip() for v in value[1:-1].split(',')]
        
        return value
    
    def _is_workflow(self, command: str) -> bool:
        """是否工作流"""
        # 检查是否包含多个动作
        actions = ['下载', '更新', '清理', '回测', '分析', '查看']
        action_count = sum(1 for a in actions if a in command)
        
        # 检查是否有分隔符
        has_separator = any(m in command for m in self.workflow_markers)
        
        return action_count >= 2 or has_separator
    
    def _is_conditional(self, command: str) -> bool:
        """是否条件指令"""
        return any(m in command.lower() for m in self.conditional_markers)
    
    def _is_loop(self, command: str) -> bool:
        """是否循环指令"""
        return any(m in command.lower() for m in self.loop_markers)
    
    def _is_parallel(self, command: str) -> bool:
        """是否并行指令"""
        return any(m in command for m in self.parallel_markers)
    
    def _parse_simple(self, command: str, variables: Dict) -> ParsedInstruction:
        """解析简单指令"""
        return ParsedInstruction(
            type=InstructionType.SIMPLE,
            raw=command,
            variables=variables,
            steps=[{'raw': command}]
        )
    
    def _parse_workflow(self, command: str, variables: Dict) -> ParsedInstruction:
        """解析工作流"""
        steps = []
        
        # 分割工作流步骤
        separators = ['然后', '接着', '再', '&&', ';']
        current = command
        
        for sep in separators:
            if sep in current:
                parts = current.split(sep)
                steps = [p.strip() for p in parts if p.strip()]
                break
        
        # 如果没有找到分隔符，尝试按动作分割
        if not steps:
            # 按动作关键词分割
            action_keywords = ['下载', '更新', '清理', '回测', '分析', '查看', '状态']
            last_pos = 0
            for i, char in enumerate(command):
                for kw in action_keywords:
                    if command[i:].startswith(kw):
                        if last_pos < i:
                            step = command[last_pos:i].strip()
                            if step:
                                steps.append(step)
                        last_pos = i
                        break
            
            if last_pos < len(command):
                step = command[last_pos:].strip()
                if step:
                    steps.append(step)
        
        # 如果没有成功分割，尝试按行分割
        if len(steps) < 2 and '\n' in command:
            steps = [s.strip() for s in command.split('\n') if s.strip()]
        
        # 如果还是只有一个步骤，可能是隐含的多步骤
        if len(steps) < 2:
            # 尝试智能分割
            steps = self._smart_split_workflow(command)
        
        return ParsedInstruction(
            type=InstructionType.WORKFLOW,
            raw=command,
            variables=variables,
            steps=[{'raw': s} for s in steps if s]
        )
    
    def _smart_split_workflow(self, command: str) -> List[str]:
        """智能分割工作流"""
        steps = []
        
        # 常见工作流模式
        patterns = [
            # "下载 2024 年数据，然后清理缓存"
            r'(下载 [^，;]+)[，;]?(?:然后 | 接着)?\s*(.*)',
            # "先下载数据，再清理"
            r'先\s*(.+?)\s*，?\s*再\s*(.+)',
            # "下载数据并清理缓存"
            r'(下载 [^并]+)\s*并\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                steps = [g.strip() for g in match.groups() if g and g.strip()]
                break
        
        return steps
    
    def _parse_conditional(self, command: str, variables: Dict) -> ParsedInstruction:
        """解析条件指令"""
        # "如果缓存大于 1GB，清理缓存"
        condition_pattern = r'(?:如果 | 假如 | if)\s*(.+?)\s*(?:，|,)?\s*(?:则 | 就 | 那么)?\s*(.+?)(?:\s*(?:否则 | else)\s*(.+))?$'
        
        match = re.search(condition_pattern, command, re.IGNORECASE | re.DOTALL)
        if match:
            condition = match.group(1).strip()
            then_action = match.group(2).strip()
            else_action = match.group(3).strip() if match.group(3) else None
            
            return ParsedInstruction(
                type=InstructionType.CONDITIONAL,
                raw=command,
                variables=variables,
                conditions={
                    'condition': condition,
                    'then': then_action,
                    'else': else_action
                }
            )
        
        return ParsedInstruction(
            type=InstructionType.CONDITIONAL,
            raw=command,
            variables=variables
        )
    
    def _parse_loop(self, command: str, variables: Dict) -> ParsedInstruction:
        """解析循环指令"""
        # "对每个股票下载数据"
        loop_pattern = r'(?:对每个 | 遍历 | for each)\s*(\w+)\s*(?:，|,)?\s*(.+)'
        
        match = re.search(loop_pattern, command, re.IGNORECASE)
        if match:
            item_var = match.group(1).strip()
            action = match.group(2).strip()
            
            return ParsedInstruction(
                type=InstructionType.LOOP,
                raw=command,
                variables=variables,
                metadata={
                    'item_var': item_var,
                    'action': action
                }
            )
        
        return ParsedInstruction(
            type=InstructionType.LOOP,
            raw=command,
            variables=variables
        )
    
    def _parse_parallel(self, command: str, variables: Dict) -> ParsedInstruction:
        """解析并行指令"""
        parts = []
        
        # 分割并行任务
        separators = ['同时', '并行', '&']
        for sep in separators:
            if sep in command:
                parts = [p.strip() for p in command.split(sep) if p.strip()]
                break
        
        return ParsedInstruction(
            type=InstructionType.PARALLEL,
            raw=command,
            variables=variables,
            steps=[{'raw': p} for p in parts]
        )
    
    def substitute_variables(self, text: str, context: Dict[str, Any]) -> str:
        """替换变量"""
        def replace(match):
            var_name = match.group(1)
            value = context.get(var_name, match.group(0))
            return str(value)
        
        return self.var_pattern.sub(replace, text)


class WorkflowExecutor:
    """工作流执行器"""
    
    def __init__(self, parser: CommandParser):
        self.parser = parser
        self.executor = get_executor()
        self.context: Dict[str, Any] = {}
    
    async def execute(self, instruction: ParsedInstruction, context: Dict[str, Any]) -> List[SkillResult]:
        """执行指令"""
        # 合并上下文变量
        self.context = {**context, **instruction.variables}
        
        if instruction.type == InstructionType.SIMPLE:
            return [await self._execute_step(instruction.steps[0])]
        
        elif instruction.type == InstructionType.WORKFLOW:
            return await self._execute_workflow(instruction.steps)
        
        elif instruction.type == InstructionType.CONDITIONAL:
            return await self._execute_conditional(instruction.conditions)
        
        elif instruction.type == InstructionType.LOOP:
            return await self._execute_loop(instruction.metadata)
        
        elif instruction.type == InstructionType.PARALLEL:
            return await self._execute_parallel(instruction.steps)
        
        return []
    
    async def _execute_step(self, step: Dict) -> SkillResult:
        """执行单一步骤"""
        raw = step.get('raw', '')
        
        # 变量替换
        command = self.parser.substitute_variables(raw, self.context)
        
        # 解析为 Skill 调用
        skill_name, params = self._parse_skill_call(command)
        
        if not skill_name:
            return SkillResult(
                success=False,
                message=f"无法解析命令：{command}"
            )
        
        # 执行 Skill
        result = await self.executor.execute(skill_name, self.context, **params)
        
        # 更新上下文
        if result.success and result.context_updates:
            for key, value in result.context_updates.items():
                self.context[key] = value
        
        # 保存输出变量
        if step.get('output_var') and result.data:
            self.context[step['output_var']] = result.data
        
        return result
    
    def _parse_skill_call(self, command: str) -> Tuple[Optional[str], Dict]:
        """解析 Skill 调用"""
        registry = get_registry()
        command_lower = command.lower()
        
        # 搜索匹配的 Skill
        matches = registry.search(command_lower)
        
        if not matches:
            return None, {}
        
        # 使用最佳匹配
        skill_name, score = matches[0]
        skill = registry.get(skill_name)
        
        if not skill:
            return None, {}
        
        # 提取参数
        params = self._extract_params(command, skill.definition.parameters)
        
        return skill_name, params
    
    def _extract_params(self, command: str, param_specs: Dict) -> Dict:
        """从命令中提取参数"""
        params = {}
        command_lower = command.lower()
        
        # 日期范围提取
        date_patterns = [
            (r'(\d{8})[\s\-~到至](\d{8})', lambda m: {'start_date': m.group(1), 'end_date': m.group(2)}),
            (r'(20\d{2}) 年', lambda m: {'start_date': m.group(1)+'0101', 'end_date': m.group(1)+'1231'}),
            (r'今年', lambda m: {'start_date': datetime.now().strftime('%Y0101'), 'end_date': datetime.now().strftime('%Y1231')}),
            (r'去年', lambda m: {'start_date': f'{datetime.now().year-1}0101', 'end_date': f'{datetime.now().year-1}1231'}),
        ]
        
        for pattern, extractor in date_patterns:
            match = re.search(pattern, command)
            if match:
                params.update(extractor(match))
        
        # 线程数提取
        workers_match = re.search(r'(\d+)\s*线程', command)
        if workers_match:
            params['workers'] = int(workers_match.group(1))
        
        # 全部股票
        if any(w in command for w in ['全部', '所有', '批量']):
            params['all_stocks'] = True
        
        # 股票代码提取
        code_pattern = r'(\d{6}\.(SZ|SH|BJ))'
        codes = re.findall(code_pattern, command, re.IGNORECASE)
        if codes:
            params['ts_codes'] = [c[0].upper() for c in codes]
        
        # 股票名映射
        stock_names = {
            '茅台': '600519.SH',
            '平安银行': '000001.SZ',
            '万科': '000002.SZ',
            '宁德': '300750.SZ',
            '比亚迪': '002594.SZ',
        }
        for name, code in stock_names.items():
            if name in command:
                if 'ts_codes' not in params:
                    params['ts_codes'] = []
                params['ts_codes'].append(code)
        
        return params
    
    async def _execute_workflow(self, steps: List[Dict]) -> List[SkillResult]:
        """顺序执行工作流"""
        results = []
        
        for i, step in enumerate(steps):
            # 检查条件
            if step.get('condition'):
                if not self._evaluate_condition(step['condition']):
                    logger.info(f"跳过步骤 {i+1}: 条件不满足")
                    continue
            
            result = await self._execute_step(step)
            results.append(result)
            
            # 检查是否需要继续
            if not result.success and step.get('on_failure'):
                logger.warning(f"步骤 {i+1} 失败，执行 on_failure")
                if step['on_failure'] == 'stop':
                    break
        
        return results
    
    async def _execute_conditional(self, conditions: Dict) -> List[SkillResult]:
        """执行条件指令"""
        if not conditions:
            return []
        
        condition_str = conditions.get('condition', '')
        
        if self._evaluate_condition(condition_str):
            return [await self._execute_step({'raw': conditions.get('then', '')})]
        else:
            else_action = conditions.get('else')
            if else_action:
                return [await self._execute_step({'raw': else_action})]
        
        return []
    
    async def _execute_loop(self, metadata: Dict) -> List[SkillResult]:
        """执行循环指令"""
        item_var = metadata.get('item_var', 'item')
        action = metadata.get('action', '')
        
        # 获取要遍历的列表
        items = self.context.get(item_var, [])
        
        if not items:
            return [SkillResult(success=False, message=f"未找到变量：{item_var}")]
        
        results = []
        for item in items:
            self.context[item_var] = item
            result = await self._execute_step({'raw': action})
            results.append(result)
        
        return results
    
    async def _execute_parallel(self, steps: List[Dict]) -> List[SkillResult]:
        """并行执行"""
        tasks = [self._execute_step(step) for step in steps]
        return await asyncio.gather(*tasks)
    
    def _evaluate_condition(self, condition: str) -> bool:
        """评估条件"""
        # 简单条件评估
        # "缓存大于 1GB" -> 检查 context['cache_size'] > 1
        
        condition = condition.lower()
        
        # 提取比较条件
        patterns = [
            (r'大于\s*(\d+)', lambda x: float(x) if x else 0, lambda a, b: a > b),
            (r'小于\s*(\d+)', lambda x: float(x) if x else 0, lambda a, b: a < b),
            (r'等于\s*(\d+)', lambda x: float(x) if x else 0, lambda a, b: a == b),
        ]
        
        # 获取上下文值
        cache_size = self.context.get('cache_size', 0)
        
        for pattern, converter, comparator in patterns:
            match = re.search(pattern, condition)
            if match:
                threshold = converter(match.group(1))
                return comparator(cache_size, threshold)
        
        # 默认返回 True
        return True


# 全局解析器和执行器
_global_parser: Optional[CommandParser] = None
_global_workflow_executor: Optional[WorkflowExecutor] = None


def get_parser() -> CommandParser:
    """获取全局解析器"""
    global _global_parser
    if _global_parser is None:
        _global_parser = CommandParser()
    return _global_parser


def get_workflow_executor() -> WorkflowExecutor:
    """获取全局工作流执行器"""
    global _global_workflow_executor
    if _global_workflow_executor is None:
        _global_workflow_executor = WorkflowExecutor(get_parser())
    return _global_workflow_executor
