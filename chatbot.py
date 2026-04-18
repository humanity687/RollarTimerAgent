"""
chatbot.py - 仿生AI智能体底层通信模块（优化版）

核心优化：
1. 分层模型配置 - 不同层可使用不同模型/端点，降低成本
2. JSON 结构化输出 - 替代脆弱的文本解析，可靠性大幅提升
3. 指数退避重试 - API 调用更健壮
4. Token 用量追踪 - 成本可视化
5. 超时控制 - 避免某层阻塞整个链路
6. 优雅降级 - 单层失败不影响整体运行
"""

import json
import time
import logging
from openai import OpenAI, APITimeoutError, APIError, RateLimitError

logger = logging.getLogger(__name__)


class Chatbot:
    """
    大模型通信封装，支持分层配置、JSON模式、重试、token追踪。

    每个实例可独立配置模型、端点、温度等参数，
    适配「本能层用小模型、意识层用大模型」的架构需求。
    """

    # 默认重试配置
    DEFAULT_RETRY_CONFIG = {
        "max_retries": 3,
        "base_delay": 1.0,       # 首次重试等待1秒
        "max_delay": 10.0,       # 最大等待10秒
        "backoff_factor": 2,     # 指数退避因子
    }

    def __init__(self, layer_name="default", model_config=None, global_config=None):
        """
        初始化 Chatbot 实例。

        Args:
            layer_name: 层名称标识，如 'instinct', 'emotion', 'consciousness'
            model_config: 该层专属模型配置（优先级最高）
            global_config: 全局默认配置（model_config 未指定时回退）
        """
        self.layer_name = layer_name
        self.messages = []
        self.last_reasoning = ""
        self.last_content = ""

        # Token 用量统计
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
        }

        # 合并配置：layer_config > global_config > 默认值
        config = self._resolve_config(model_config, global_config)

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 30),
        )

        self.model = config.get("model", "gpt-3.5-turbo")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)
        self.json_mode = config.get("json_mode", False)

        # 重试配置
        retry_cfg = config.get("retry", {})
        self.retry_config = {**self.DEFAULT_RETRY_CONFIG, **retry_cfg}

        logger.info(f"[{layer_name}] 初始化完成 | 模型: {self.model} | JSON模式: {self.json_mode}")

    def _resolve_config(self, model_config, global_config):
        """配置合并：层级专属 > 全局 > 内置默认"""
        defaults = {
            "api_key": None,
            "base_url": None,
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 4096,
            "timeout": 30,
            "json_mode": False,
        }

        # 先加载全局
        if global_config:
            defaults.update({k: v for k, v in global_config.items() if v is not None})

        # 再覆盖层级专属
        if model_config:
            defaults.update({k: v for k, v in model_config.items() if v is not None})

        if not defaults.get("api_key"):
            raise ValueError(f"[{self.layer_name}] 缺少 api_key 配置")

        return defaults

    def add_msg(self, msg, role="user"):
        """添加消息"""
        self.messages.append({"role": role, "content": msg})

    def send_msg(self, streaming=False, show_reasoning=True, auto_print=True,
                 json_mode_override=None):
        """
        发送消息并获取回复（含重试机制）。

        Args:
            streaming: 是否流式输出
            show_reasoning: 是否显示思考过程
            auto_print: 是否自动打印
            json_mode_override: 临时覆盖JSON模式设置

        Returns:
            AI回复内容（JSON模式时返回原始字符串，由调用方解析）
        """
        use_json = json_mode_override if json_mode_override is not None else self.json_mode

        last_error = None
        for attempt in range(self.retry_config["max_retries"]):
            try:
                return self._do_send(
                    streaming=streaming,
                    show_reasoning=show_reasoning,
                    auto_print=auto_print,
                    json_mode=use_json,
                )
            except (APITimeoutError, RateLimitError) as e:
                last_error = e
                delay = min(
                    self.retry_config["base_delay"] * (self.retry_config["backoff_factor"] ** attempt),
                    self.retry_config["max_delay"]
                )
                logger.warning(
                    f"[{self.layer_name}] API调用失败 (尝试 {attempt+1}/{self.retry_config['max_retries']}): "
                    f"{type(e).__name__}，{delay:.1f}s 后重试"
                )
                time.sleep(delay)
            except APIError as e:
                last_error = e
                # 4xx 错误不重试（除了429已在RateLimitError中处理）
                if hasattr(e, 'status_code') and 400 <= e.status_code < 500:
                    logger.error(f"[{self.layer_name}] 客户端错误，不重试: {e}")
                    raise
                delay = min(
                    self.retry_config["base_delay"] * (self.retry_config["backoff_factor"] ** attempt),
                    self.retry_config["max_delay"]
                )
                logger.warning(f"[{self.layer_name}] 服务端错误，{delay:.1f}s 后重试")
                time.sleep(delay)

        # 所有重试耗尽
        logger.error(f"[{self.layer_name}] 重试耗尽，最后错误: {last_error}")
        raise ConnectionError(
            f"[{self.layer_name}] API 调用失败，已重试 {self.retry_config['max_retries']} 次。"
            f"最后错误: {last_error}"
        )

    def _do_send(self, streaming, show_reasoning, auto_print, json_mode):
        """实际执行API调用"""

        kwargs = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": streaming,
        }

        # JSON 模式：要求模型输出合法 JSON
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)

        # 更新 token 统计（非流式时可用）
        if not streaming and hasattr(response, 'usage') and response.usage:
            self.token_usage["prompt_tokens"] += response.usage.prompt_tokens
            self.token_usage["completion_tokens"] += response.usage.completion_tokens
            self.token_usage["total_tokens"] += response.usage.total_tokens
            self.token_usage["api_calls"] += 1

        ai_full_content = ""
        ai_full_reasoning = ""
        self.last_reasoning = ""

        if streaming:
            ai_full_content, ai_full_reasoning = self._handle_stream(
                response, show_reasoning, auto_print
            )
        else:
            message = response.choices[0].message
            ai_full_reasoning = getattr(message, 'reasoning_content', None) or getattr(message, 'reasoning', "")
            ai_full_content = message.content or ""

            if auto_print:
                if show_reasoning and ai_full_reasoning:
                    print("\n【模型思考过程】")
                    print(ai_full_reasoning)
                    print("\n【AI最终回复】")
                print(ai_full_content)

        self.last_reasoning = ai_full_reasoning
        self.last_content = ai_full_content
        self.messages.append({"role": "assistant", "content": ai_full_content})
        return ai_full_content

    def _handle_stream(self, response, show_reasoning, auto_print):
        """处理流式响应"""
        ai_full_content = ""
        ai_full_reasoning = ""
        reasoning_prefix_printed = False
        content_prefix_printed = False

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 思考过程
            delta_reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
            if delta_reasoning:
                ai_full_reasoning += delta_reasoning
                if show_reasoning and auto_print:
                    if not reasoning_prefix_printed:
                        print("\n【模型思考过程】\n", end="", flush=True)
                        reasoning_prefix_printed = True
                    print(delta_reasoning, end="", flush=True)

            # 最终内容
            delta_content = delta.content
            if delta_content:
                ai_full_content += delta_content
                if auto_print:
                    if not content_prefix_printed:
                        if reasoning_prefix_printed:
                            print("\n\n【AI最终回复】\n", end="", flush=True)
                        else:
                            print("\n【AI回复】\n", end="", flush=True)
                        content_prefix_printed = True
                    print(delta_content, end="", flush=True)

        if auto_print:
            print("\n", flush=True)

        return ai_full_content, ai_full_reasoning

    # ================== 上下文管理 ==================

    def set_role(self, system_prompt):
        """设置系统角色（避免重复设置相同角色）"""
        current_system = self.get_system_prompt()
        if current_system == system_prompt:
            return
        self.messages = [msg for msg in self.messages if msg['role'] != 'system']
        self.messages.insert(0, {"role": "system", "content": system_prompt})

    def append_system_prompt(self, additional_prompt):
        """在现有系统提示基础上追加内容"""
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        if system_msg:
            system_msg['content'] += "\n\n" + additional_prompt
        else:
            self.set_role(additional_prompt)

    def clear_messages(self):
        """清空所有消息（包括系统消息）"""
        self.messages = []
        self.last_reasoning = ""
        self.last_content = ""

    def clear_conversation(self):
        """清空对话历史（保留系统消息）"""
        self.messages = [msg for msg in self.messages if msg['role'] == 'system']
        self.last_reasoning = ""
        self.last_content = ""

    # ================== 查询接口 ==================

    def get_messages(self):
        return self.messages.copy()

    def get_system_prompt(self):
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        return system_msg['content'] if system_msg else None

    def get_last_reasoning(self):
        return self.last_reasoning

    def get_last_content(self):
        return self.last_content

    def message_count(self):
        return len(self.messages)

    def get_token_usage(self):
        """获取该层的 Token 用量统计"""
        return self.token_usage.copy()

    def get_cost_summary(self):
        """获取成本摘要（基于大致的定价估算）"""
        # 这些是参考价格，实际价格取决于具体模型
        # GPT-4o-mini: $0.15/1M input, $0.6/1M output
        # GPT-4o: $2.5/1M input, $10/1M output
        # GPT-3.5-turbo: $0.5/1M input, $1.5/1M output
        pricing = {
            "gpt-4o": (2.5 / 1_000_000, 10 / 1_000_000),
            "gpt-4o-mini": (0.15 / 1_000_000, 0.6 / 1_000_000),
            "gpt-3.5-turbo": (0.5 / 1_000_000, 1.5 / 1_000_000),
        }
        model_key = self.model.lower()
        if model_key in pricing:
            input_price, output_price = pricing[model_key]
        else:
            input_price, output_price = 1.0 / 1_000_000, 3.0 / 1_000_000  # 默认估算

        cost = (
            self.token_usage["prompt_tokens"] * input_price +
            self.token_usage["completion_tokens"] * output_price
        )
        return {
            "layer": self.layer_name,
            "model": self.model,
            "api_calls": self.token_usage["api_calls"],
            "prompt_tokens": self.token_usage["prompt_tokens"],
            "completion_tokens": self.token_usage["completion_tokens"],
            "total_tokens": self.token_usage["total_tokens"],
            "estimated_cost_usd": round(cost, 6),
        }
