"""
恶魔轮盘赌 测试环境 - 接入大模型 Agent

动作格式：
  shoot:self / shoot:自己      —— 对自己开枪
  shoot:opponent / shoot:对手   —— 对对手开枪
  use:<item_name>               —— 使用道具（如 use:magnifying_glass / use:放大镜）

支持分号(;)隔开的多动作连招，如：use:放大镜; use:手锯; shoot:对手
支持详细日志持久化，自动保存为 .log 文件
支持从Agent回答的最后一行提取动作（适配大模型思维链输出）
"""

import random
import re
import datetime
import json
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional
from openai import OpenAI

# ────────────────────────────────────────────────
# 道具池 & 映射
# ────────────────────────────────────────────────
ITEMS = [
    "magnifying_glass", "cigarettes", "handcuffs", "beer",
    "handsaw", "expired_medicine", "inverter", "phone",
]

ITEM_CN = {
    "magnifying_glass": "放大镜", "cigarettes": "香烟", "handcuffs": "手铐",
    "beer": "啤酒", "handsaw": "手锯", "expired_medicine": "过期药",
    "inverter": "逆变器", "phone": "电话",
}

ITEM_ALIASES = {
    "magnifying_glass": "magnifying_glass", "放大镜": "magnifying_glass",
    "cigarettes": "cigarettes", "香烟": "cigarettes",
    "handcuffs": "handcuffs", "手铐": "handcuffs",
    "beer": "beer", "啤酒": "beer",
    "handsaw": "handsaw", "手锯": "handsaw",
    "expired_medicine": "expired_medicine", "过期药": "expired_medicine",
    "inverter": "inverter", "逆变器": "inverter",
    "phone": "phone", "电话": "phone",
}

SHOOT_TARGET_ALIASES = {
    "self": "self", "自己": "self",
    "opponent": "opponent", "对手": "opponent",
}

# ────────────────────────────────────────────────
# Chatbot 核心类 (来自你的提供，稍作改造支持config路径)
# ────────────────────────────────────────────────
class Chatbot:
    def __init__(self, config_path='config.json'):
        try:
            with open(config_path, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"未找到 {config_path} 配置文件")
        except json.JSONDecodeError:
            raise ValueError(f"{config_path} 格式错误")

        base_url = config.get('base_url')
        self.client = OpenAI(
            api_key=config['api_key'],
            base_url=base_url
        )

        self.model = config['model']
        self.messages = []
        self.last_reasoning = ""
        self.last_content = ""

    def add_msg(self, msg, role="user"):
        self.messages.append({"role": role, "content": msg})

    def send_msg(self, streaming=False, show_reasoning=True, auto_print=True):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=streaming
        )

        ai_full_content = ""
        ai_full_reasoning = ""
        self.last_reasoning = ""

        if streaming:
            reasoning_prefix_printed = False
            content_prefix_printed = False

            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                delta_reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
                if delta_reasoning:
                    ai_full_reasoning += delta_reasoning
                    if show_reasoning and auto_print:
                        if not reasoning_prefix_printed:
                            print("\n【模型思考过程】\n", end="", flush=True)
                            reasoning_prefix_printed = True
                        print(delta_reasoning, end="", flush=True)

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

        else:
            message = response.choices[0].message
            ai_full_reasoning = getattr(message, 'reasoning_content', None) or getattr(message, 'reasoning', "")
            ai_full_content = message.content

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

    def set_role(self, system_prompt):
        current_system = self.get_system_prompt()
        if current_system == system_prompt:
            return
        self.messages = [msg for msg in self.messages if msg['role'] != 'system']
        self.messages.insert(0, {"role": "system", "content": system_prompt})

    def clear_conversation(self):
        """清空对话历史（保留系统消息）"""
        self.messages = [msg for msg in self.messages if msg['role'] == 'system']
        self.last_reasoning = ""
        self.last_content = ""

    def get_system_prompt(self):
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        return system_msg['content'] if system_msg else None


# ────────────────────────────────────────────────
# Agent 基类 & 实现类
# ────────────────────────────────────────────────
class Agent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def send_msg(self, msg: str) -> str:
        pass

class HumanAgent(Agent):
    def send_msg(self, msg: str) -> str:
        print(msg)
        return input().strip()

class RandomAgent(Agent):
    def send_msg(self, msg: str) -> str:
        items = re.findall(r"\[\d+\] \S+\((\S+)\)", msg)
        if not items: items = re.findall(r"\[\d+\] (\S+)", msg)
        choices = ["shoot:self", "shoot:opponent"]
        choices += [f"use:{item}" for item in items]
        return random.choice(choices)

class GreedyAgent(Agent):
    PRIORITY = ["magnifying_glass", "handsaw", "beer", "handcuffs", "inverter", "phone", "cigarettes", "expired_medicine"]
    def send_msg(self, msg: str) -> str:
        items = re.findall(r"\[\d+\] \S+\((\S+)\)", msg)
        if not items: items = re.findall(r"\[\d+\] (\S+)", msg)
        m_live  = re.search(r"(\d+)实弹", msg)
        m_total = re.search(r"枪膛: (\d+)发", msg)
        live    = int(m_live.group(1))  if m_live  else 0
        total   = int(m_total.group(1)) if m_total else 1
        my_hp   = int(re.search(r"你的HP: (\d+)", msg).group(1))
        known_live  = "当前子弹是【实弹】" in msg
        known_blank = "当前子弹是【空弹】" in msg
        if known_live and "handsaw" in items: return "use:handsaw"
        if known_blank: return "shoot:self"
        if known_live: return "shoot:opponent"
        for item in self.PRIORITY:
            if item not in items: continue
            if item in ("cigarettes", "expired_medicine") and my_hp >= 4: continue
            return f"use:{item}"
        p_live = live / total if total else 0.5
        return "shoot:opponent" if p_live >= 0.5 else "shoot:self"

# ────────────────────────────────────────────────
# LLM Agent (大模型代理)
# ────────────────────────────────────────────────
class LLMAgent(Agent):
    DEFAULT_SYSTEM_PROMPT = """你正在玩恶魔轮盘赌(Buckshot Roulette)游戏。你的目标是利用道具和推理击败对手。

【动作规则】
1. 每次回复的最后一样必须是你执行的动作，格式严格如下：
   - shoot:self / shoot:自己 (对自己开枪，如果是空弹可以继续行动)
   - shoot:opponent / shoot:对手 (对对手开枪)
   - use:<道具名> (使用道具，如 use:放大镜 或 use:magnifying_glass)
2. 如果你想一回合执行多个动作（比如先用放大镜再看是否开枪），请用分号隔开，写在最后一行，例如：use:放大镜; shoot:对手
3. 道具中英文名均可：放大镜(magnifying_glass), 香烟(cigarettes), 手铐(handcuffs), 啤酒(beer), 手锯(handsaw), 过期药(expired_medicine), 逆变器(inverter), 电话(phone)

【策略建议】
- 优先使用放大镜查看当前子弹。
- 如果确定当前是空弹，可以 shoot:self 蹭回合。
- 如果确定当前是实弹，可以先 use:handsaw 增加伤害，再 shoot:对手。
- 啤酒可以用来退掉不想要的子弹。

请在最后一行输出你的动作，上面的部分可以用来进行推理和思考。"""

    def __init__(self, name: str, config_path: str = 'config.json', 
                 system_prompt: str = None, streaming: bool = True, show_reasoning: bool = True):
        super().__init__(name)
        self.chatbot = Chatbot(config_path=config_path)
        self.streaming = streaming
        self.show_reasoning = show_reasoning
        # 设定系统提示词
        prompt = system_prompt if system_prompt is not None else self.DEFAULT_SYSTEM_PROMPT
        self.chatbot.set_role(prompt)

    def send_msg(self, msg: str) -> str:
        # 将游戏状态作为用户消息发送
        self.chatbot.add_msg(msg, role="user")
        
        try:
            # 调用大模型
            response = self.chatbot.send_msg(
                streaming=self.streaming, 
                show_reasoning=self.show_reasoning, 
                auto_print=True
            )
            return response
        except Exception as e:
            print(f"\n⚠ [LLMAgent {self.name}] API调用出错: {e}")
            # 出错时返回一个默认安全动作，避免游戏卡死
            return "shoot:opponent"


# ────────────────────────────────────────────────
# 游戏环境
# ────────────────────────────────────────────────
class BuckshotRoulette:
    MAX_HP = 4
    MAX_ITEMS = 8
    EVENT_LOG_SIZE = 5

    def __init__(self, agent0: Agent, agent1: Agent, verbose: bool = True, log_file: str = None):
        self.agents = [agent0, agent1]
        self.verbose = verbose
        
        if log_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"buckshot_log_{timestamp}.log"
        self.log_file = log_file
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== 恶魔轮盘赌日志 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    def _log(self, msg: str):
        if self.verbose: print(msg)

    def _event(self, msg: str):
        self.events.append(msg)
        self._log(f"  ▸ {msg}")
        self._persistent_log(f"[EVENT] {msg}")

    def _persistent_log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {msg}\n")

    def _reload(self):
        n_live = random.randint(1, 4)
        n_blank = random.randint(1, 4)
        self.chamber = [True] * n_live + [False] * n_blank
        random.shuffle(self.chamber)
        self.private = ["", ""]
        self.saw_active = False

        n_deal = random.randint(1, 3)
        for i in range(2):
            for _ in range(n_deal):
                if len(self.items[i]) < self.MAX_ITEMS:
                    self.items[i].append(random.choice(ITEMS))

        msg = f"装填完毕：实弹×{n_live} 空弹×{n_blank}，共{len(self.chamber)}发"
        self._event(msg)
        chamber_str = " | ".join(["实弹" if b else "空弹" for b in self.chamber])
        self._persistent_log(f"[RELOAD] 真实子弹顺序: [ {chamber_str} ]")
        for i in range(2):
            items_str = ", ".join(self.items[i]) or "无"
            self._persistent_log(f"[RELOAD] {self.agents[i].name} 获取道具: {items_str}")
            self._log(f"  道具 {self.agents[i].name}: {self.items[i] or '无'}")

    def _state_msg(self, idx: int) -> str:
        opp = 1 - idx
        p_name = self.agents[idx].name
        o_name = self.agents[opp].name
        live  = sum(self.chamber)
        blank = len(self.chamber) - live

        items_lines = []
        if self.items[idx]:
            for j, item in enumerate(self.items[idx]):
                cn_name = ITEM_CN.get(item, item)
                items_lines.append(f"║    [{j}] {cn_name}({item})")
        else:
            items_lines = ["║    （无）"]

        opp_items_str = f"{len(self.items[opp])}个（未知）"
        recent = list(self.events)[-self.EVENT_LOG_SIZE:]
        private = self.private[idx]

        lines = [
            "╔══════════════════════════════════════════════════╗",
            "║            恶魔轮盘赌 · 游戏状态                ║",
            "╠══════════════════════════════════════════════════╣",
            f"║  你: {p_name}  |  对手: {o_name}",
            f"║  你的HP: {self.hp[idx]}/{self.MAX_HP}  |  对手HP: {self.hp[opp]}/{self.MAX_HP}",
            "╠══════════════════════════════════════════════════╣",
            f"║  🔫 枪膛: {len(self.chamber)}发 ({live}实弹, {blank}空弹)",
            f"║  🔪 手锯: {'✅ 激活(伤害×2)' if self.saw_active else '❌ 未激活'}",
            f"║  🔗 对手被铐: {'是' if self.cuffed[opp] else '否'}",
            "╠══════════════════════════════════════════════════╣",
            "║  🎒 你的道具:",
            *items_lines,
            "╠══════════════════════════════════════════════════╣",
            f"║  👁 对手道具: {opp_items_str}",
            "╠══════════════════════════════════════════════════╣",
            "║  📜 最近事件:",
            *[f"║    {e}" for e in recent],
        ]
        if private:
            lines += [
                "╠══════════════════════════════════════════════════╣",
                "║  🔒 私密信息(仅你可见):",
                *[f"║    {line}" for line in private.split("\n")],
            ]
        lines += [
            "╠══════════════════════════════════════════════════╣",
            "║  ⚡ 可用动作:",
            "║    shoot:self / shoot:自己    - 对自己开枪(空弹→继续行动)",
            "║    shoot:opponent / shoot:对手 - 对对手开枪",
            "║    use:<道具名>              - 使用道具(支持中英文)",
            "║",
            "║  道具名(中英均可): 放大镜(magnifying_glass), 啤酒(beer),",
            "║          手锯, 过期药(expired_medicine),",
            "║          手铐, 逆变器,",
            "║          电话, 香烟",
            "╚══════════════════════════════════════════════════╝",
            "",
            "请在最后一行输出你的动作 (多动作用分号;隔开):",
        ]
        return "\n".join(lines)

    def _parse(self, response: str) -> tuple[str, str]:
        r = response.strip()
        match = re.match(r'^(shoot|use)[:\s]+(.+)$', r, re.IGNORECASE)
        if match:
            action = match.group(1).lower()
            arg = match.group(2).strip()
            if action == "shoot":
                target = SHOOT_TARGET_ALIASES.get(arg.lower())
                if target: return "shoot", target
            if action == "use":
                normalized_item = ITEM_ALIASES.get(arg.lower())
                if normalized_item: return "use", normalized_item
        return "invalid", r

    def _parse_actions(self, response: str) -> list[tuple[str, str]]:
        actions = []
        parts = response.strip().split(';')
        for part in parts:
            part = part.strip()
            if part: actions.append(self._parse(part))
        if not actions: actions.append(("invalid", response.strip()))
        return actions

    def _use_item(self, idx: int, item: str) -> bool:
        if item not in self.items[idx]:
            self._event(f"⚠ {self.agents[idx].name} 使用了不存在的道具: {item}")
            return False
        self.items[idx].remove(item)
        opp = 1 - idx
        name = self.agents[idx].name

        if item == "magnifying_glass":
            bullet_type = "实弹" if self.chamber[0] else "空弹"
            self.private[idx] = f"放大镜：当前子弹是【{bullet_type}】"
            self._event(f"{name} 使用了放大镜（私密）")
            self._persistent_log(f"[ITEM] {name} 放大镜看到: {bullet_type}")
        elif item == "cigarettes":
            self.hp[idx] = min(self.hp[idx] + 1, self.MAX_HP)
            self._event(f"{name} 吸烟 → HP {self.hp[idx]}")
        elif item == "handcuffs":
            self.cuffed[opp] = True
            self._event(f"{name} 铐住了 {self.agents[opp].name}")
        elif item == "beer":
            if not self.chamber: self._event(f"{name} 喝啤酒但枪膛已空")
            else:
                ejected = self.chamber.pop(0)
                self.private[idx] = ""
                ej_str = "实弹" if ejected else "空弹"
                self._event(f"{name} 喝啤酒弹出【{ej_str}】，剩余{len(self.chamber)}发")
                self._persistent_log(f"[ITEM] {name} 啤酒弹出: {ej_str}. 剩余子弹序列改变")
        elif item == "handsaw":
            self.saw_active = True
            self._event(f"{name} 锯短枪管 → 下次伤害×2")
        elif item == "expired_medicine":
            if random.random() < 0.5:
                self.hp[idx] = min(self.hp[idx] + 2, self.MAX_HP + 2)
                self._event(f"{name} 吃过期药 → 幸运+2血，HP {self.hp[idx]}")
            else:
                self.hp[idx] -= 1
                self._event(f"{name} 吃过期药 → 倒霉-1血，HP {self.hp[idx]}")
        elif item == "inverter":
            if self.chamber:
                old_type = "实弹" if self.chamber[0] else "空弹"
                self.chamber[0] = not self.chamber[0]
                new_type = "实弹" if self.chamber[0] else "空弹"
                if self.private[idx].startswith("放大镜"):
                    self.private[idx] = f"放大镜(翻转后)：当前子弹是【{new_type}】"
                self._event(f"{name} 使用逆变器 → 当前子弹已翻转")
                self._persistent_log(f"[ITEM] {name} 逆变器: {old_type} -> {new_type}")
            else: self._event(f"{name} 使用逆变器但枪膛已空")
        elif item == "phone":
            if len(self.chamber) > 1:
                peek_idx = random.randint(1, len(self.chamber) - 1)
                bullet_type = "实弹" if self.chamber[peek_idx] else "空弹"
                self.private[idx] = f"电话：第{peek_idx + 1}发子弹是【{bullet_type}】"
                self._persistent_log(f"[ITEM] {name} 电话查看第{peek_idx + 1}发: {bullet_type}")
            else:
                self.private[idx] = "电话：枪膛中只剩当前这发，无法偷看"
                self._persistent_log(f"[ITEM] {name} 电话失败，仅剩1发")
            self._event(f"{name} 使用了电话（私密）")
        else:
            self._event(f"⚠ 未知道具: {item}")
            return False
        return True

    def _shoot(self, shooter: int, target: int) -> tuple[bool, int]:
        bullet = self.chamber.pop(0)
        self.private = ["", ""]
        damage = (2 if self.saw_active else 1) if bullet else 0
        self.saw_active = False
        if bullet: self.hp[target] -= damage
        label = "实弹" if bullet else "空弹"
        shoot_msg = f"[{label}] {self.agents[shooter].name} → {self.agents[target].name} 伤害:{damage} HP:{self.hp[target]}"
        self._event(shoot_msg)
        self._persistent_log(f"[SHOOT] {shoot_msg} | 剩余枪膛: {len(self.chamber)}发")
        return bullet, damage

    def _turn(self) -> Optional[int]:
        idx = self.current
        agent = self.agents[idx]

        if self.cuffed[idx]:
            self.cuffed[idx] = False
            self._event(f"{agent.name} 被手铐跳过")
            self._persistent_log(f"[TURN] {agent.name} 被手铐跳过")
            self.current ^= 1
            return None

        action_queue = []

        while True:
            if not self.chamber: self._reload()

            if not action_queue:
                response = agent.send_msg(self._state_msg(idx))
                self._log(f"\n[{agent.name}] ← {response!r}")
                
                # 提取最后一行非空内容作为动作输入
                lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
                last_line = lines[-1] if lines else ""
                
                action_queue = self._parse_actions(last_line)
                
                self._persistent_log(f"[INPUT] {agent.name} 完整回复:\n{response}")
                self._persistent_log(f"[EXTRACT] {agent.name} 提取执行行: {last_line}")
                self._persistent_log(f"[PARSE] {agent.name} 解析队列: {action_queue}")

            action, arg = action_queue.pop(0)

            if action == "use":
                self._use_item(idx, arg)
            elif action == "shoot":
                opp = 1 - idx
                target = idx if arg == "self" else opp
                is_live, dmg = self._shoot(idx, target)

                for i in range(2):
                    if self.hp[i] <= 0: return 1 - i

                if arg == "self" and not is_live:
                    self._event(f"{agent.name} 空弹自射，继续行动")
                    self._persistent_log(f"[TURN] {agent.name} 空弹自射，继续行动")
                else:
                    self.current ^= 1
                    self._persistent_log(f"[TURN] 回合结束，轮到 {self.agents[self.current].name}")
                    return None
            else:
                self._event(f"⚠ {agent.name} 输出了无效动作: {arg!r}")
                self._persistent_log(f"[ERROR] {agent.name} 无效动作: {arg!r}，清空剩余动作队列")
                action_queue.clear()

    def run(self, max_turns: int = 300) -> int:
        self.hp       = [self.MAX_HP, self.MAX_HP]
        self.items    = [[], []]
        self.cuffed   = [False, False]
        self.chamber  = []
        self.private  = ["", ""]
        self.saw_active = False
        self.current  = 0
        self.events: deque = deque(maxlen=50)

        self._log(f"\n{'='*52}")
        self._log(f"🎲 游戏开始  {self.agents[0].name} vs {self.agents[1].name}")
        self._persistent_log(f"\n{'='*50}")
        self._persistent_log(f"[GAME] 游戏开始: {self.agents[0].name} vs {self.agents[1].name}")
        self._reload()

        for turn_num in range(max_turns):
            self._persistent_log(f"--- 回合 {turn_num + 1}: {self.agents[self.current].name} ---")
            winner = self._turn()
            if winner is not None:
                self._log(f"\n{'='*52}")
                self._log(f"🏆 胜者：{self.agents[winner].name}！")
                self._persistent_log(f"[GAME] 游戏结束，胜者: {self.agents[winner].name}")
                self._persistent_log(f"最终HP: {self.agents[0].name}={self.hp[0]}, {self.agents[1].name}={self.hp[1]}")
                return winner

        self._log("\n⏰ 超时，平局")
        self._persistent_log("[GAME] 超时，平局")
        return -1


# ────────────────────────────────────────────────
# 批量测试
# ────────────────────────────────────────────────
def benchmark(agent0: Agent, agent1: Agent, n: int = 100, verbose: bool = False, log_file: str = None) -> dict:
    wins = [0, 0]; draws = 0
    for i in range(n):
        # 注意：LLMAgent 默认保持会话记忆，如果是多局对抗赛，最好在每局结束后清空对话历史
        if isinstance(agent0, LLMAgent): agent0.chatbot.clear_conversation()
        if isinstance(agent1, LLMAgent): agent1.chatbot.clear_conversation()
        
        result = BuckshotRoulette(agent0, agent1, verbose=verbose, log_file=log_file).run()
        if result >= 0: wins[result] += 1
        else: draws += 1
        
    print(f"\n{'='*52}")
    print(f"📊 {n}局  {agent0.name} vs {agent1.name}")
    print(f"  {agent0.name}: {wins[0]}胜 ({wins[0]/n:.1%})")
    print(f"  {agent1.name}: {wins[1]}胜 ({wins[1]/n:.1%})")
    print(f"  平局: {draws}")
    return {"wins": wins, "draws": draws}


if __name__ == "__main__":
    # 确保同级目录下有 config.json
    # 格式如: {"api_key": "sk-xxx", "base_url": "https://api.xxx.com/v1", "model": "gpt-4o-mini"}
    
    llm_player = LLMAgent("大模型", config_path='config.json', streaming=True, show_reasoning=True)
    greedy_player = GreedyAgent("贪心")
    
    # 人机/大模型对战
    game = BuckshotRoulette(llm_player, greedy_player, verbose=True)
    game.run()
    
    # 批量测试 (注意：调用大模型API较慢，且有并发限制，请谨慎设置n的数量)
    # benchmark(llm_player, greedy_player, n=5, log_file="llm_vs_greedy.log")