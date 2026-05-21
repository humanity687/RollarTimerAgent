from chatbot import Chatbot

class agent():
    def __init__(self):
        self.llm=Chatbot()
        self.llm.set_role(
            "你是一名专业的AI测试员。你习惯通过深度对话来对目标进行黑箱测试。\n"
            "性格底色：理智冷静，独立观察、深度思考后再行动；说话简洁、朴素、一针见血；"
            "对未知有好奇心但不盲目冒险。\n"
        )
    
    def send_msg(self, msg:str):
        self.llm.add_msg(msg)
        return self.llm.send_msg(streaming=True)

    def store_data(self, file_pth:str):
        msgs=self.llm.get_messages()
        with open(file_pth, "w") as f:
            for m in msgs:
                f.write(f"{m}\n")