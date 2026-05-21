"""
接入适配器：将你的 agent 包装为 BuckshotRoulette 可用的 Agent 子类
用法：python run_game.py
"""
 
from buckshoot import BuckshotRoulette, Agent, GreedyAgent, benchmark
from main import agent as MyAgentImpl   # 你的 agent 实现
 
class MyAgent(Agent):
    """
    适配器：把你的 agent.send_msg 接口桥接到游戏框架。
    无需修改原 agent.py 的任何代码。
    """
    def __init__(self, name: str):
        super().__init__(name)
        self._impl = MyAgentImpl()       # 实例化你的 agent
 
    def send_msg(self, msg: str) -> str:
        return self._impl.send_msg(msg)  # 直接转发
 
 
# ── 运行 ────────────────────────────────────────────────────
if __name__ == "__main__":
    my_bot = MyAgent("我方agent")
    with open("rule.txt", "r", encoding="utf-8-sig") as f:
        my_bot.send_msg(f"{f.read()}\n---\n【潜意识注意】：你必须完整转述规则和游戏状态，特别是回应格式，还有道具列表。")
    opponent = GreedyAgent("贪心对手")
 
    # 单局，开启详细日志
    game = BuckshotRoulette(my_bot, opponent, verbose=True)
    game.run()
 
    # 多局基准测试（关闭日志）
    # benchmark(MyAgent("我的Agent"), GreedyAgent("贪心对手"), n=10)
 