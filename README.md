# 让Agent组成大脑——RollarTimerAgent

一个创新的仿生AI智能体框架，通过分层架构实现"本能→意识"的智能推理过程。

## 核心特性

### 🧠 分层架构
- **本能层**：快速反应，注入主观色彩和情感直觉
- **情绪层**（可选）：中间推理，综合本能判断和理性分析
- **意识层**：深度推理，基于增强后的提示词进行理性思考

### 🎯 关键优化
- **双/三层模式**：灵活选择 (本能→意识) 或 (本能→情绪→意识)
- **JSON结构化输出**：替代脆弱的文本解析，可靠性大幅提升
- **分层模型配置**：本能层用轻量模型（快/便宜），意识层用强推理模型
- **工作记忆系统**：跨轮次的情绪轨迹和上下文累积
- **智能路由**：基于复杂度的自适应决策
- **优雅降级**：任一层失败时自动回退到直接对话
- **成本追踪**：全链路可观测，Token用量透明化

### 🛡️ 健壮性设计
- 指数退避重试机制
- 超时控制避免阻塞
- 多重异常处理
- 反馈机制：意识层可回溯修正本能层的判断

## 快速开始

### 环境要求
- Python 3.8+
- OpenAI API 密钥

### 安装

```bash
git clone https://github.com/humanity687/rollartimeragent.git
cd rollartimeragent
```

### 配置

1. 复制配置模板：
```bash
cp config_template.json config.json
```

2. 编辑 `config.json`，填入你的 OpenAI API 密钥和配置：
```json
{
    "global": {
        "api_key": "your-api-key-here",
        "base_url": "https://api.openai.com/v1",
        "timeout": 30
    },
    "layers": {
        "instinct": {
            "model": "gpt-4o-mini",
            "temperature": 0.8,
            "max_tokens": 500
        },
        "consciousness": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    }
}
```

### 使用

```python
from main import BionicAgent

# 创建智能体实例
agent = BionicAgent(mode="dual")  # 或 "triple" 三层模式

# 与Agent交互
response = agent.process("你的问题或任务")
print(response)
```

## 项目结构

```
├── main.py              # 核心智能体实现与推理流程
├── chatbot.py           # 大模型通信底层模块
├── config.json          # 配置文件（需自行创建）
├── config_template.json # 配置模板参考
└── README.md            # 项目文档
```

## 设计思想

这个框架的核心创新在于模拟人脑的多层次决策过程：

1. **本能反应**：快速、直觉、成本低
2. **意识思考**：深度、理性、成本高
3. **反馈循环**：让意识层能纠正本能层的判断

通过这种设计，AI系统不仅更高效，也更接近人类的思维方式。

## 配置详解

### 层级配置选项

- `model`：使用的模型名称
- `temperature`：温度参数（0-1），控制输出的随机性
- `max_tokens`：最大输出Token数
- `json_mode`：是否启用JSON结构化输出
- `retry`：重试配置

### 动态调优建议

- 本能层：温度较高（0.7-0.9），启用JSON模式，快速响应
- 意识层：温度较低（0.5-0.7），更多Token预算，深度思考

## 监控与追踪

所有API调用都支持：
- Token用量追踪
- 执行时间统计
- 错误日志记录
- 分层性能指标

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，欢迎通过GitHub Issue联系我。

---

**打造让Agent组成大脑的未来！**🚀
