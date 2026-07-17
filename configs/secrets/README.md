# Secrets（本地凭据）

本目录存放 **不应提交** 的 API Key / 远程凭据。

| 文件 | 用途 |
|------|------|
| `glm.env` | 智谱 GLM-5.2 API Key（gitignored） |
| `glm.env.example` | 模板，可提交 |

复制模板后填入真实 key：

```bash
cp configs/secrets/glm.env.example configs/secrets/glm.env
# 编辑 glm.env，写入 ZHIPU_API_KEY=...
```

诊断 demo 会按此顺序查找 key：

1. 环境变量 `ZHIPU_API_KEY` / `GLM_API_KEY`
2. `configs/secrets/glm.env`
