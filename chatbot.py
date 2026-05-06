import json
from openai import OpenAI

class Chatbot:
    def __init__(self):
        # 更稳健的配置读取
        try:
            with open('config.json', 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("未找到 config.json 配置文件")
        except json.JSONDecodeError:
            raise ValueError("config.json 格式错误")

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
        """添加消息，支持角色指定"""
        self.messages.append({"role": role, "content": msg})

    def send_msg(self, streaming=False, show_reasoning=True, auto_print=True):
        """
        发送消息并获取回复
        :param streaming: 是否流式输出
        :param show_reasoning: 是否显示思考过程
        :param auto_print: 是否自动打印内容（False时仅返回内容）
        :return: AI回复内容
        """
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

                # 处理思考过程
                delta_reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
                if delta_reasoning:
                    ai_full_reasoning += delta_reasoning
                    if show_reasoning and auto_print:
                        if not reasoning_prefix_printed:
                            print("\n【模型思考过程】\n", end="", flush=True)
                            reasoning_prefix_printed = True
                        print(delta_reasoning, end="", flush=True)

                # 处理最终内容
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
        """
        设置系统角色（避免重复设置相同角色）
        :param system_prompt: 系统提示词
        """
        # 检查是否已有相同的系统提示，避免重复设置
        current_system = self.get_system_prompt()
        if current_system == system_prompt:
            return

        # 替换系统提示
        self.messages = [msg for msg in self.messages if msg['role'] != 'system']
        self.messages.insert(0, {"role": "system", "content": system_prompt})

    def append_system_prompt(self, additional_prompt):
        """
        在现有系统提示基础上追加内容
        :param additional_prompt: 要追加的提示内容
        """
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

    def get_messages(self):
        """获取当前消息列表的副本"""
        return self.messages.copy()

    def get_system_prompt(self):
        """获取当前系统提示词"""
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        return system_msg['content'] if system_msg else None

    def get_last_reasoning(self):
        """获取上一次的思考过程"""
        return self.last_reasoning

    def get_last_content(self):
        """获取上一次的回复内容"""
        return self.last_content

    def message_count(self):
        """获取当前消息列表的长度"""
        return len(self.messages)