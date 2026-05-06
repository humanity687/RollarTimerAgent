import json
from openai import OpenAI

class Chatbot:
    def __init__(self):
        # Robust config loading
        try:
            with open('config.json', 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("config.json not found")
        except json.JSONDecodeError:
            raise ValueError("config.json has invalid format")

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
        """Add a message with role support"""
        self.messages.append({"role": role, "content": msg})

    def send_msg(self, streaming=False, show_reasoning=True, auto_print=True):
        """
        Send message and get reply
        :param streaming: whether to use streaming output
        :param show_reasoning: whether to display the reasoning process
        :param auto_print: whether to auto-print content (set False to only return content)
        :return: AI reply content
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

                # Process reasoning
                delta_reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
                if delta_reasoning:
                    ai_full_reasoning += delta_reasoning
                    if show_reasoning and auto_print:
                        if not reasoning_prefix_printed:
                            print("\n[Model Reasoning]\n", end="", flush=True)
                            reasoning_prefix_printed = True
                        print(delta_reasoning, end="", flush=True)

                # Process final content
                delta_content = delta.content
                if delta_content:
                    ai_full_content += delta_content
                    if auto_print:
                        if not content_prefix_printed:
                            if reasoning_prefix_printed:
                                print("\n\n[AI Final Response]\n", end="", flush=True)
                            else:
                                print("\n[AI Response]\n", end="", flush=True)
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
                    print("\n[Model Reasoning]")
                    print(ai_full_reasoning)
                    print("\n[AI Final Response]")
                print(ai_full_content)

        self.last_reasoning = ai_full_reasoning
        self.last_content = ai_full_content
        self.messages.append({"role": "assistant", "content": ai_full_content})
        return ai_full_content

    def set_role(self, system_prompt):
        """
        Set system role (avoids re-setting identical roles)
        :param system_prompt: system prompt text
        """
        # Check if the same system prompt already exists, avoid duplicates
        current_system = self.get_system_prompt()
        if current_system == system_prompt:
            return

        # Replace system prompt
        self.messages = [msg for msg in self.messages if msg['role'] != 'system']
        self.messages.insert(0, {"role": "system", "content": system_prompt})

    def append_system_prompt(self, additional_prompt):
        """
        Append content to existing system prompt
        :param additional_prompt: prompt content to append
        """
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        if system_msg:
            system_msg['content'] += "\n\n" + additional_prompt
        else:
            self.set_role(additional_prompt)

    def clear_messages(self):
        """Clear all messages (including system messages)"""
        self.messages = []
        self.last_reasoning = ""
        self.last_content = ""

    def clear_conversation(self):
        """Clear conversation history (keep system message)"""
        self.messages = [msg for msg in self.messages if msg['role'] == 'system']
        self.last_reasoning = ""
        self.last_content = ""

    def get_messages(self):
        """Get a copy of the current message list"""
        return self.messages.copy()

    def get_system_prompt(self):
        """Get the current system prompt"""
        system_msg = next((msg for msg in self.messages if msg['role'] == 'system'), None)
        return system_msg['content'] if system_msg else None

    def get_last_reasoning(self):
        """Get the last reasoning process"""
        return self.last_reasoning

    def get_last_content(self):
        """Get the last reply content"""
        return self.last_content

    def message_count(self):
        """Get the length of the current message list"""
        return len(self.messages)
