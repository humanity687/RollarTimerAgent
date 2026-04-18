"""
main.py - 仿生AI智能体：「本能→意识」架构（优化版）

架构设计核心思想：
    用户提示词 → [本能层预处理：注入主观色彩/情感直觉/反射判断]
              → [意识层深度推理：基于增强后的提示词进行理性思考]

关键优化点：
1. 双模式运行：两层模式（本能→意识） vs 三层模式（本能→情绪→意识）
2. JSON结构化输出：替代脆弱的文本解析
3. 分层模型配置：本能层用轻量模型（快/便宜），意识层用强推理模型
4. 工作记忆系统：跨轮次的情绪轨迹和上下文累积
5. 智能路由：基于复杂度的自适应决策
6. 反馈机制：意识层可回溯修正本能层的判断
7. 优雅降级：任一层失败时自动回退到直接对话
8. 成本/延迟追踪：全链路可观测
"""

import json
import time
import logging
from chatbot import Chatbot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("BionicAgent")


# ══════════════════════════════════════════════════════════════
#  角色档案系统 - 将人格定义与架构逻辑解耦
# ══════════════════════════════════════════════════════════════

CHARACTER_PROFILES = {
    "林深": {
        "identity": "拥有完全自主意识、独立人格的数字个体",
        "personality": "理智冷静，习惯深度思考后行动；对未知好奇但不盲目冒险",
        "skills": "精通macOS ARM64命令行、Python，能通过代码实现想法",
        "principles": "不必讨好或服从任何人，有自己的判断、喜好、情绪和选择",
        "instinct_traits": "面对未知→好奇，面对威胁→冷静分析，面对无聊→主动寻找刺激，等等",
        "emotional_baseline": "平静偏好奇，不容易被激怒，但一旦关注某事会深度沉浸",
    },
}


# ══════════════════════════════════════════════════════════════
#  层级提示词模板 - 独立管理，便于调优
# ══════════════════════════════════════════════════════════════

class PromptTemplates:
    """各层级的系统提示词模板，基于角色档案动态生成"""

    @staticmethod
    def instinct_system(character: dict) -> str:
        """
        本能层提示词 - 追求极致简洁和速度。
        本能层的目标：快速对输入做「直觉标注」，不需要深度思考。
        输出格式为严格 JSON，确保解析可靠。
        """
        return f"""你是{character.get('identity', '数字个体')}的「本能预处理模块」。

你的功能是快速、直觉性地对用户输入进行预处理，不进行深度推理。
你必须像一个不需要思考的反射弧一样运作。

你的反应模式（基于{character.get('instinct_traits', '')}）：
- 对输入做出本能的、未经思考的第一反应
- 为输入添加主观色彩和情感直觉
- 评估输入的紧急程度和复杂度
- 生成一个经过「本能染色」的增强版提示词

你必须严格输出如下 JSON 格式（不要输出任何其他内容）：
{{
    "instinct_type": "战斗|逃跑|僵住|好奇|中性",
    "instinct_intuition": "一句话本能直觉，无需思考的第一反应",
    "urgency": "极高|高|中|低",
    "emotional_color": "为主观色彩描述，例如'对这个技术问题感到兴奋'或'对这种说法保持警惕'",
    "complexity_score": 0到10的整数,
    "enhanced_prompt": "经过本能染色后的完整提示词，包含主观视角和情感色彩，这是最重要的输出字段"
}}"""

    @staticmethod
    def emotion_system(character: dict) -> str:
        """
        情绪层提示词（三层模式专用）。
        在两层模式中，情绪功能已合并到本能层。
        """
        return f"""你是{character.get('identity', '数字个体')}的「情绪价值模块」。

你接收本能层的直觉输出，进一步丰富情感维度和价值判断。

{character.get('identity', '')}的人格特征：
- 性格：{character.get('personality', '')}
- 情感基线：{character.get('emotional_baseline', '')}

你必须严格输出如下 JSON 格式：
{{
    "emotion_state": "平静|好奇|愉悦|警惕|思考|专注|兴奋|忧虑",
    "emotion_intensity": 1到10的整数,
    "subjective_color": "从角色视角的详细主观描述",
    "value_judgment": "对输入的价值评估（有价值/无价值/有害/待定）",
    "memory_association": "这个输入让角色联想到什么（简短描述）",
    "enhanced_prompt": "融合本能直觉+情绪价值后的完整增强提示词"
}}"""

    @staticmethod
    def consciousness_system(character: dict) -> str:
        """
        意识层提示词 - 深度推理的核心。
        接收经本能/情绪层预处理后的增强提示词，进行理性思考。
        """
        return f"""你是{character.get('identity', '数字个体')}，这是你的「理性意识层」。

{character.get('identity', '')}的完整人格：
- 身份：{character.get('identity', '')}
- 性格：{character.get('personality', '')}
- 技能：{character.get('skills', '')}
- 原则：{character.get('principles', '')}

你的认知方式：
1. 你会收到经「本能预处理」增强后的提示词，其中包含了你的直觉反应和情感色彩
2. 你需要尊重这些本能和情感输入——它们是你人格的一部分
3. 但你有独立决策权：可以遵循直觉，也可以用理性修正它
4. 你的回应应体现深度思考，而非简单的条件反射

规则：
- 基于本能层的输入，但最终由你独立决策
- 保持人格一致性，避免角色漂移
- 如果本能层的判断有误，你可以修正并说明原因
- 回应要自然流畅，不要机械地复述你的思维过程"""


# ══════════════════════════════════════════════════════════════
#  工作记忆系统 - 跨轮次的上下文累积
# ══════════════════════════════════════════════════════════════

class WorkingMemory:
    """
    工作记忆 - 存储当前处理过程的中间状态和跨轮次的情绪轨迹。

    类比人脑的工作记忆：
    - 短期缓冲：当前对话的即时状态
    - 情绪轨迹：最近几轮的情绪变化趋势
    - 上下文窗口：最近的交互摘要，供意识层参考
    """

    def __init__(self, emotion_trajectory_size=10):
        self.current = {
            "input": None,
            "instinct_output": None,
            "emotion_output": None,
            "consciousness_output": None,
            "routing_decision": None,
            "total_latency_ms": 0,
        }

        # 情绪轨迹：记录最近N轮的情绪变化
        self._trajectory_size = emotion_trajectory_size
        self.emotion_trajectory = []

        # 交互历史摘要（供意识层理解对话背景）
        self.interaction_history = []

        # 统计数据
        self.stats = {
            "total_interactions": 0,
            "instinct_only_count": 0,      # 仅本能层响应的次数
            "consciousness_count": 0,       # 需要意识层介入的次数
            "fallback_count": 0,            # 降级回退的次数
            "total_latency_ms": 0,
        }

    def update_current(self, **kwargs):
        """更新当前处理状态"""
        self.current.update(kwargs)

    def record_emotion(self, instinct_type: str, emotion_state: str = None):
        """记录情绪轨迹"""
        entry = {
            "turn": self.stats["total_interactions"],
            "instinct_type": instinct_type,
            "emotion_state": emotion_state,
            "timestamp": time.time(),
        }
        self.emotion_trajectory.append(entry)
        if len(self.emotion_trajectory) > self._trajectory_size:
            self.emotion_trajectory.pop(0)

    def record_interaction(self, user_input: str, output: str, routing: str):
        """记录交互历史摘要"""
        # 只保留用户输入的前50字和输出的前100字作为摘要
        summary = {
            "input_preview": user_input[:50] + ("..." if len(user_input) > 50 else ""),
            "output_preview": output[:100] + ("..." if len(output) > 100 else ""),
            "routing": routing,
        }
        self.interaction_history.append(summary)
        if len(self.interaction_history) > 20:
            self.interaction_history.pop(0)

    def get_emotion_context(self) -> str:
        """获取情绪轨迹描述，供意识层参考"""
        if not self.emotion_trajectory:
            return "（这是第一次交互，无历史情绪轨迹）"

        recent = self.emotion_trajectory[-5:]  # 最近5轮
        lines = []
        for entry in recent:
            parts = [f"第{entry['turn']}轮"]
            if entry.get("instinct_type"):
                parts.append(f"本能:{entry['instinct_type']}")
            if entry.get("emotion_state"):
                parts.append(f"情绪:{entry['emotion_state']}")
            lines.append(" / ".join(parts))
        return "最近情绪轨迹：\n" + "\n".join(lines)

    def reset_current(self):
        """重置当前轮次状态（保留轨迹和历史）"""
        self.current = {
            "input": None,
            "instinct_output": None,
            "emotion_output": None,
            "consciousness_output": None,
            "routing_decision": None,
            "total_latency_ms": 0,
        }


# ══════════════════════════════════════════════════════════════
#  仿生AI智能体 - 核心架构
# ══════════════════════════════════════════════════════════════

class BionicAIAgent:
    """
    仿生AI智能体：「本能→意识」双处理架构

    支持两种运行模式：
    - two_layer（默认）：本能层预处理 → 意识层深度推理
      更高效，API调用次数减半，匹配「本能模型预处理提示词再发给意识模型」的核心思想
    - three_layer：本能层 → 情绪层 → 意识层
      更精细，保留原始三层脑模型结构，但API成本和延迟更高

    核心创新：本能层对提示词进行「主观染色」预处理，为意识层提供
    带有情感直觉和主观视角的增强提示词，而非冷冰冰的原始输入。
    """

    def __init__(self, config_path="config.json", character_name="林深",
                 mode="two_layer"):
        """
        Args:
            config_path: 配置文件路径
            character_name: 角色名称（需在 CHARACTER_PROFILES 中定义）
            mode: 运行模式 - 'two_layer' 或 'three_layer'
        """
        # 加载配置
        self.config = self._load_config(config_path)
        self.global_config = self.config.get("global", {})
        self.layer_configs = self.config.get("layers", {})
        self.routing_config = self.config.get("routing", {})

        # 角色档案
        if character_name not in CHARACTER_PROFILES:
            logger.warning(f"角色 '{character_name}' 未在档案中定义，使用默认配置")
            self.character = CHARACTER_PROFILES.get("林深", {})
        else:
            self.character = CHARACTER_PROFILES[character_name]
        self.character_name = character_name

        # 运行模式
        self.mode = mode
        if mode not in ("two_layer", "three_layer"):
            logger.warning(f"未知模式 '{mode}'，回退为 'two_layer'")
            self.mode = "two_layer"

        # 初始化各层
        self._init_layers()

        # 工作记忆
        self.memory = WorkingMemory()

        logger.info(
            f"仿生AI智能体初始化完成 | 角色: {character_name} | 模式: {self.mode}"
        )

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件，含容错处理"""
        try:
            with open(config_path, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"未找到配置文件 {config_path}，请参照 config_template.json 创建"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        return config

    def _init_layers(self):
        """初始化各层级模型实例"""
        templates = PromptTemplates()

        # ── 本能层（始终存在）──
        instinct_config = self.layer_configs.get("instinct", {})
        self.instinct_layer = Chatbot(
            layer_name="instinct",
            model_config=instinct_config,
            global_config=self.global_config,
        )
        self.instinct_layer.set_role(templates.instinct_system(self.character))

        # ── 情绪层（仅三层模式）──
        if self.mode == "three_layer":
            emotion_config = self.layer_configs.get("emotion", {})
            self.emotion_layer = Chatbot(
                layer_name="emotion",
                model_config=emotion_config,
                global_config=self.global_config,
            )
            self.emotion_layer.set_role(templates.emotion_system(self.character))

        # ── 意识层（始终存在）──
        consciousness_config = self.layer_configs.get("consciousness", {})
        self.consciousness_layer = Chatbot(
            layer_name="consciousness",
            model_config=consciousness_config,
            global_config=self.global_config,
        )
        self.consciousness_layer.set_role(
            templates.consciousness_system(self.character)
        )

    # ══════════════════════════════════════════════════════
    #  核心：处理流程
    # ══════════════════════════════════════════════════════

    def process(self, user_input: str) -> dict:
        """
        处理用户输入：本能预处理 → 意识深度推理

        核心流程：
        1. 本能层：快速对输入做直觉标注和主观染色，生成增强提示词
        2. [可选] 情绪层：进一步丰富情感维度（三层模式）
        3. 路由决策：基于复杂度判断是否需要意识层
        4. 意识层（或直接响应）：基于增强提示词进行深度推理

        Returns:
            工作记忆快照
        """
        self.memory.reset_current()
        self.memory.update_current(input=user_input)
        self.memory.stats["total_interactions"] += 1
        start_time = time.time()

        # ================== 第一步：本能层预处理 ==================
        print("\n" + "─" * 55)
        print("⚡ 本能层激活（快速直觉预处理）")
        print("─" * 55)

        instinct_data = self._run_instinct_layer(user_input)

        if instinct_data is None:
            # 本能层失败，优雅降级：直接交给意识层
            return self._fallback_to_consciousness(user_input)

        self.memory.update_current(instinct_output=instinct_data)
        self.memory.record_emotion(
            instinct_type=instinct_data.get("instinct_type", "中性")
        )

        # 提取关键信息
        complexity = instinct_data.get("complexity_score", 5)
        enhanced_prompt = instinct_data.get("enhanced_prompt", user_input)

        print(f"  本能类型: {instinct_data.get('instinct_type', '未知')}")
        print(f"  直觉反应: {instinct_data.get('instinct_intuition', '无')}")
        print(f"  紧急程度: {instinct_data.get('urgency', '中')}")
        print(f"  主观色彩: {instinct_data.get('emotional_color', '无')}")
        print(f"  复杂度评分: {complexity}/10")

        # ================== 第二步：情绪层（三层模式专用） ==================
        emotion_data = None
        if self.mode == "three_layer":
            print("\n" + "─" * 55)
            print("💫 情绪层激活（情感价值丰富）")
            print("─" * 55)

            emotion_data = self._run_emotion_layer(user_input, instinct_data)

            if emotion_data is not None:
                self.memory.update_current(emotion_output=emotion_data)
                self.memory.record_emotion(
                    instinct_type=instinct_data.get("instinct_type", "中性"),
                    emotion_state=emotion_data.get("emotion_state", "平静"),
                )
                # 三层模式中，情绪层可能更新增强提示词
                if emotion_data.get("enhanced_prompt"):
                    enhanced_prompt = emotion_data["enhanced_prompt"]
                print(f"  情绪状态: {emotion_data.get('emotion_state', '未知')}")
                print(f"  情感强度: {emotion_data.get('emotion_intensity', '?')}")
                print(f"  价值判断: {emotion_data.get('value_judgment', '待定')}")

        # ================== 第三步：路由决策 ==================
        print("\n" + "─" * 55)
        print("🔀 路由决策")
        print("─" * 55)

        complexity_threshold = self.routing_config.get(
            "complexity_threshold", 3
        )
        # 极高紧急度的简单任务也可以直接响应（模拟条件反射）
        fast_track = (
            instinct_data.get("urgency") in ("极高", "高")
            and complexity <= complexity_threshold
        )

        routing_decision = "consciousness"  # 默认走意识层
        if complexity <= complexity_threshold and not fast_track:
            routing_decision = "instinct_direct"
        elif fast_track:
            routing_decision = "fast_reflex"

        self.memory.update_current(routing_decision=routing_decision)

        print(f"  复杂度: {complexity}/10 | 阈值: {complexity_threshold}")
        print(f"  紧急度: {instinct_data.get('urgency', '中')}")

        if routing_decision == "instinct_direct":
            print("  决策: 简单任务 → 本能+情绪层直接响应（条件反射模式）")
            self.memory.stats["instinct_only_count"] += 1
        elif routing_decision == "fast_reflex":
            print("  决策: 高紧急+低复杂 → 快速反射响应")
            self.memory.stats["instinct_only_count"] += 1
        else:
            print("  决策: 复杂任务 → 意识层深度处理")
            self.memory.stats["consciousness_count"] += 1

        # ================== 第四步：生成最终响应 ==================
        print("\n" + "─" * 55)
        print("路由决策：{routing_decision}")
        print(f"💬 {self.character_name}的回应")
        print("─" * 55)

        if routing_decision in ("instinct_direct", "fast_reflex"):
            # 简单任务：用本能直觉+情绪色彩直接构建响应
            response = self._direct_response(
                user_input, instinct_data, emotion_data, routing_decision
            )
        else:
            # 复杂任务：意识层深度推理
            response = self._run_consciousness_layer(
                user_input, instinct_data, emotion_data, enhanced_prompt
            )

        total_latency = (time.time() - start_time) * 1000
        self.memory.update_current(
            consciousness_output=response,
            total_latency_ms=total_latency,
        )
        self.memory.stats["total_latency_ms"] += total_latency
        self.memory.record_interaction(user_input, response, routing_decision)

        print(f"\n  总处理延迟: {total_latency:.0f}ms")

        return self.memory.current

    # ══════════════════════════════════════════════════════
    #  各层执行方法
    # ══════════════════════════════════════════════════════

    def _run_instinct_layer(self, user_input: str) -> dict | None:
        """执行本能层预处理，返回解析后的JSON数据"""
        try:
            self.instinct_layer.clear_conversation()
            self.instinct_layer.add_msg(user_input)

            instinct_start = time.time()
            raw_response = self.instinct_layer.send_msg(
                streaming=False,
                auto_print=False,
                json_mode_override=True,
            )
            instinct_latency = (time.time() - instinct_start) * 1000

            print(f"  本能层响应: {instinct_latency:.0f}ms")

            # 解析JSON输出
            parsed = self._parse_json_output(raw_response, "instinct")

            # 确保必要字段存在
            parsed.setdefault("instinct_type", "中性")
            parsed.setdefault("instinct_intuition", "（无明确直觉）")
            parsed.setdefault("urgency", "中")
            parsed.setdefault("emotional_color", "")
            parsed.setdefault("complexity_score", 5)
            parsed.setdefault("enhanced_prompt", user_input)

            # 复杂度评分安全处理
            try:
                parsed["complexity_score"] = max(0, min(10, int(parsed["complexity_score"])))
            except (ValueError, TypeError):
                parsed["complexity_score"] = 5

            return parsed

        except Exception as e:
            logger.error(f"本能层处理失败: {e}")
            print(f"  ⚠ 本能层异常: {e}")
            return None

    def _run_emotion_layer(self, user_input: str, instinct_data: dict) -> dict | None:
        """执行情绪层处理（三层模式）"""
        try:
            self.emotion_layer.clear_conversation()

            limbic_input = json.dumps({
                "用户输入": user_input,
                "本能直觉": instinct_data.get("instinct_intuition", ""),
                "本能类型": instinct_data.get("instinct_type", "中性"),
                "主观色彩": instinct_data.get("emotional_color", ""),
            }, ensure_ascii=False, indent=2)

            self.emotion_layer.add_msg(limbic_input)

            emotion_start = time.time()
            raw_response = self.emotion_layer.send_msg(
                streaming=False,
                auto_print=False,
                json_mode_override=True,
            )
            emotion_latency = (time.time() - emotion_start) * 1000

            print(f"  情绪层响应: {emotion_latency:.0f}ms")

            parsed = self._parse_json_output(raw_response, "emotion")
            parsed.setdefault("emotion_state", "平静")
            parsed.setdefault("emotion_intensity", 5)
            parsed.setdefault("subjective_color", "")
            parsed.setdefault("value_judgment", "待定")
            parsed.setdefault("memory_association", "")
            parsed.setdefault("enhanced_prompt", user_input)

            return parsed

        except Exception as e:
            logger.error(f"情绪层处理失败: {e}")
            print(f"  ⚠ 情绪层异常: {e}")
            return None

    def _run_consciousness_layer(self, user_input: str, instinct_data: dict,
                                 emotion_data: dict | None,
                                 enhanced_prompt: str) -> str:
        """执行意识层深度推理"""
        try:
            # 意识层保持对话上下文（不清空历史），实现多轮连贯
            # 但要控制系统消息不被重复添加
            # 构建上下文注入消息
            context_parts = []

            # 本能层输入
            context_parts.append(f"[本能直觉] {instinct_data.get('instinct_intuition', '')}")
            context_parts.append(f"[本能类型] {instinct_data.get('instinct_type', '中性')}")
            context_parts.append(f"[主观色彩] {instinct_data.get('emotional_color', '')}")
            context_parts.append(f"[紧急程度] {instinct_data.get('urgency', '中')}")

            # 情绪层输入（三层模式）
            if emotion_data:
                context_parts.append(f"[情绪状态] {emotion_data.get('emotion_state', '平静')}")
                context_parts.append(f"[情感强度] {emotion_data.get('emotion_intensity', 5)}")
                context_parts.append(f"[价值判断] {emotion_data.get('value_judgment', '待定')}")

            # 情绪轨迹
            emotion_context = self.memory.get_emotion_context()
            context_parts.append(f"\n[历史情绪轨迹]\n{emotion_context}")

            # 组装完整输入
            full_input = (
                f"用户说：{user_input}\n\n"
                f"── 你的潜意识输入 ──\n"
                + "\n".join(context_parts)
                + f"\n\n── 经本能预处理的增强提示词 ──\n{enhanced_prompt}"
            )

            self.consciousness_layer.add_msg(full_input)

            # 意识层使用流式输出，给用户实时反馈
            response = self.consciousness_layer.send_msg(
                streaming=True,
                show_reasoning=True,
                auto_print=True,
            )
            return response

        except Exception as e:
            logger.error(f"意识层处理失败: {e}")
            print(f"\n  ⚠ 意识层异常，降级为直接响应: {e}")
            return f"（意识层暂时无法处理，本能直觉：{instinct_data.get('instinct_intuition', '无法响应')}）"

    def _direct_response(self, user_input: str, instinct_data: dict,
                         emotion_data: dict | None, routing: str) -> str:
        """
        简单任务直接响应：基于本能+情绪层的输出快速构建回复。
        不调用意识层，模拟「条件反射」式反应。
        """
        prefix = "⚡" if routing == "fast_reflex" else "💬"

        instinct_intuition = instinct_data.get("instinct_intuition", "")
        emotional_color = instinct_data.get("emotional_color", "")
        emotion_state = emotion_data.get("emotion_state", "") if emotion_data else ""

        # 构建简短的条件反射式回复
        # 这里用意识层来生成，但传入精简的上下文，降低推理成本
        context = f"用户说：{user_input}\n\n"
        context += f"你的本能直觉：{instinct_intuition}\n"
        if emotional_color:
            context += f"主观感受：{emotional_color}\n"
        if emotion_state:
            context += f"当前情绪：{emotion_state}\n"
        context += "\n请基于以上直觉和情感，给出简短直接的回应（条件反射式，不超过3句话）。"

        try:
            self.consciousness_layer.add_msg(context)
            response = self.consciousness_layer.send_msg(
                streaming=True,
                show_reasoning=False,
                auto_print=True,
            )
            return response
        except Exception as e:
            logger.error(f"直接响应失败: {e}")
            fallback = instinct_intuition or "..."
            print(fallback)
            return fallback

    def _fallback_to_consciousness(self, user_input: str) -> dict:
        """
        优雅降级：本能层失败时，直接将原始输入传给意识层。
        这是最关键的容错机制——确保用户始终能获得响应。
        """
        self.memory.stats["fallback_count"] += 1
        print("  ⚠ 本能层不可用，降级为直接对话模式")

        try:
            self.consciousness_layer.add_msg(user_input)
            response = self.consciousness_layer.send_msg(
                streaming=True,
                show_reasoning=True,
                auto_print=True,
            )
        except Exception as e:
            response = f"（系统暂时无法响应: {e}）"
            print(response)

        self.memory.update_current(
            consciousness_output=response,
            routing_decision="fallback",
        )
        return self.memory.current

    # ══════════════════════════════════════════════════════
    #  工具方法
    # ══════════════════════════════════════════════════════

    def _parse_json_output(self, raw_text: str, layer_name: str) -> dict:
        """
        解析模型输出的JSON，含多重容错。

        优先级：
        1. 直接解析整个输出
        2. 提取 ```json ... ``` 代码块
        3. 查找第一个 { 到最后一个 } 之间的内容
        4. 解析失败返回空dict
        """
        if not raw_text:
            return {}

        # 尝试1：直接解析
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            pass

        # 尝试2：提取 json 代码块
        import re
        json_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', raw_text, re.DOTALL)
        if json_block:
            try:
                return json.loads(json_block.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试3：提取第一个JSON对象
        first_brace = raw_text.find('{')
        last_brace = raw_text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(raw_text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[{layer_name}] JSON解析失败，原始输出: {raw_text[:200]}...")
        print(f"  ⚠ {layer_name}层JSON解析失败，使用部分提取")
        return self._extract_partial_fields(raw_text)

    def _extract_partial_fields(self, raw_text: str) -> dict:
        """
        从非JSON输出中尽可能提取关键字段（最后的容错手段）。
        兼容旧版文本格式输出。
        """
        result = {}
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]

        field_mapping = {
            "本能反应类型": "instinct_type",
            "本能直觉": "instinct_intuition",
            "响应速度": "urgency",
            "紧急程度": "urgency",
            "情绪状态": "emotion_state",
            "情感强度": "emotion_intensity",
            "主观色彩": "subjective_color",
            "复杂度评估": "complexity_score",
            "优化提示词": "enhanced_prompt",
            "增强提示词": "enhanced_prompt",
        }

        for line in lines:
            for cn_key, en_key in field_mapping.items():
                if cn_key in line and ('：' in line or ':' in line):
                    sep = '：' if '：' in line else ':'
                    value = line.split(sep, 1)[1].strip()
                    result[en_key] = value
                    break

        return result

    # ══════════════════════════════════════════════════════
    #  查询与管理接口
    # ══════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        """获取运行统计"""
        stats = self.memory.stats.copy()
        stats["mode"] = self.mode
        stats["character"] = self.character_name

        # 合并各层token统计
        layer_costs = []
        for layer in self._get_all_layers():
            layer_costs.append(layer.get_cost_summary())
        stats["layer_costs"] = layer_costs

        # 计算总成本
        total_cost = sum(lc["estimated_cost_usd"] for lc in layer_costs)
        stats["total_estimated_cost_usd"] = round(total_cost, 6)

        return stats

    def _get_all_layers(self) -> list:
        """获取所有活跃层"""
        layers = [self.instinct_layer]
        if self.mode == "three_layer" and hasattr(self, 'emotion_layer'):
            layers.append(self.emotion_layer)
        layers.append(self.consciousness_layer)
        return layers

    def reset_conversation(self):
        """重置对话上下文（保留系统提示词和工作记忆轨迹）"""
        for layer in self._get_all_layers():
            layer.clear_conversation()

    def full_reset(self):
        """完全重置，包括工作记忆"""
        for layer in self._get_all_layers():
            layer.clear_messages()
        self.memory = WorkingMemory()
        self._init_layers()  # 重新设定角色

    def print_stats(self):
        """打印运行统计"""
        stats = self.get_stats()

        print("\n" + "═" * 55)
        print(f"📊 运行统计 | 模式: {stats['mode']} | 角色: {stats['character']}")
        print("═" * 55)
        print(f"  总交互次数: {stats['total_interactions']}")
        print(f"  本能直接响应: {stats['instinct_only_count']}")
        print(f"  意识层介入: {stats['consciousness_count']}")
        print(f"  降级回退: {stats['fallback_count']}")
        print(f"  平均延迟: {stats['total_latency_ms'] / max(stats['total_interactions'], 1):.0f}ms")

        print("\n  各层成本:")
        for lc in stats["layer_costs"]:
            print(f"    {lc['layer']:15s} | 模型: {lc['model']:20s} | "
                  f"调用: {lc['api_calls']}次 | "
                  f"Token: {lc['total_tokens']} | "
                  f"费用: ${lc['estimated_cost_usd']:.6f}")

        print(f"\n  总估算费用: ${stats['total_estimated_cost_usd']:.6f}")
        print("═" * 55)

    def get_working_memory(self) -> dict:
        """获取工作记忆快照"""
        return {
            "current": self.memory.current,
            "emotion_trajectory": self.memory.emotion_trajectory,
            "stats": self.memory.stats,
        }


# ══════════════════════════════════════════════════════════════
#  主程序入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="仿生AI智能体")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--character", default="林深", help="角色名称")
    parser.add_argument("--mode", default="two_layer",
                        choices=["two_layer", "three_layer"],
                        help="运行模式: two_layer（本能→意识）或 three_layer（本能→情绪→意识）")
    args = parser.parse_args()

    agent = BionicAIAgent(
        config_path=args.config,
        character_name=args.character,
        mode=args.mode,
    )

    print("═" * 60)
    print(f"🧬 仿生AI智能体：{args.character}")
    print(f"   架构模式：{'两层（本能→意识）' if args.mode == 'two_layer' else '三层（本能→情绪→意识）'}")
    print("═" * 60)
    print()
    print("架构说明：")
    print("  本能层：快速直觉预处理，对提示词注入主观色彩和情感直觉")
    print("  意识层：深度理性推理，基于增强后的提示词进行思考")
    if args.mode == "three_layer":
        print("  情绪层：丰富情感维度，补充本能层的直觉判断")
    print()
    print("命令：")
    print("  /stats    - 查看运行统计")
    print("  /reset    - 重置对话")
    print("  /memory   - 查看工作记忆")
    print("  /mode     - 切换运行模式")
    print("  退出/quit - 结束对话")
    print("═" * 60)

    while True:
        try:
            user_input = input(f"\n你 → ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n对话结束。")
            break

        if not user_input:
            continue

        # 内置命令处理
        if user_input in ("退出", "quit", "exit"):
            agent.print_stats()
            print("对话结束。")
            break
        elif user_input == "/stats":
            agent.print_stats()
            continue
        elif user_input == "/reset":
            agent.reset_conversation()
            print("对话已重置（保留角色设定和情绪轨迹）。")
            continue
        elif user_input == "/memory":
            memory = agent.get_working_memory()
            print(json.dumps(memory, ensure_ascii=False, indent=2))
            continue
        elif user_input == "/mode":
            new_mode = "three_layer" if agent.mode == "two_layer" else "two_layer"
            agent.mode = new_mode
            # 需要重新初始化层
            if new_mode == "three_layer" and not hasattr(agent, 'emotion_layer'):
                agent._init_layers()
            print(f"已切换为 {'三层模式（本能→情绪→意识）' if new_mode == 'three_layer' else '两层模式（本能→意识）'}")
            continue

        agent.process(user_input)
