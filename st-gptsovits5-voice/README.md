# GPT-SoVITS v5 角色配音台（SillyTavern 扩展）

顶栏耳机图标 → 给角色卡绑定**本机 GPT-SoVITS** 的音色，逐条朗读 / 自动朗读 / 多声线切换。
不经过任何云 API；扩展本身不跑模型，只调 `api_v2.py` 的 HTTP 接口。

> 第一次装？看 [安装指南.md](./安装指南.md)。
>
> 和「IndexTTS 版」的区别：GPT-SoVITS 的一个音色 = **GPT 权重 + SoVITS 权重 + 参考音频 + 参考文本**，
> 所以这里引入了「音色档案」；切换音色要真的换权重，插件为此做了**权重缓存 + 全局串行队列**。

```
顶栏耳机图标
   └─ 服务：地址 / 测试连接 / 直连or中继 / 状态
   └─ 音色档案：列表（就绪/缺什么）+ 表单（名称 / GPT 权重 / SoVITS 权重 / 参考音频 / 参考文本 / 参考语言）
   └─ 当前角色 · 声线：○自动 ○小d ○demon ｜ 每条：档案 · 语速 · 文本语言 · ▶试听
   └─ 全部角色：绑定摘要 · 🔊 · ✕
   └─ 朗读设置：自动朗读 / 去动作 / 只读引号 / 单段字数 / 文本语言 / 切分方法 / 默认档案
   └─ 高级参数：top_k / top_p / temperature / 重复惩罚 / sample_steps
```

## 一、安装

1. 把 `st-gptsovits5-voice` 放进 `SillyTavern/data/default-user/extensions/`
2. 启动 GPT-SoVITS 的 API（不是 WebUI）：

```bash
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

3. **CORS**：官方 `api_v2.py` 是裸 FastAPI，没挂 CORS，酒馆页面直连会被浏览器拒绝。
   两步验证：插件里点「测试连接」——
   - 显示 `已连接（/control → HTTP 400）` → 直连可用（你的整合包应该已经加了 CORS）
   - 显示 `未连接：Failed to fetch` → 启动 `server\start-relay.bat`，把插件地址改成
     `http://127.0.0.1:9881`（中继只补 CORS 头，字节原样转发，含流式）

4. 刷新酒馆（Ctrl+F5）→ 顶栏出现耳机图标。

## 二、音色档案

一个档案就是一次「声音」：

| 字段 | 说明 | 例 |
| --- | --- | --- |
| 名称 | 面板里显示 | `小d · 柔软` |
| GPT 权重 | 服务器上的 `.ckpt` | `GPT_SoVITS/pretrained_models/xiaod-e15.ckpt` |
| SoVITS 权重 | 服务器上的 `.pth` | `GPT_SoVITS/pretrained_models/xiaod_e8_s208.pth` |
| 参考音频 | 服务器上的 wav | `refs/xiaod_prompt.wav` |
| 参考文本 | 参考音频里说的那句话（越准越像） | `はい、そうです` |
| 参考语言 | 参考文本的语言 | `ja` |

路径按**服务端**的当前目录解析（一般是 GPT-SoVITS 根目录），相对绝对都行。
面板会标出「缺 GPT 权重 / 缺参考音频」这类问题，不用猜。

## 三、双声线

角色卡里声明接口（扩展会写）：

```json
"extensions": { "gptsovits5": {
  "version": 1, "character": "小鲸鱼娘", "defaultSlot": "xiaod",
  "slots": [
    { "id": "xiaod", "label": "小d · 柔软" },
    { "id": "demon", "label": "demon · 小恶魔" }
  ]
}}
```

- 播放时选哪条：**消息标注 > 面板激活 > 卡默认 > 第一个已绑档案的声线**
- 消息按钮：点=朗读；**Shift+点**=临时换下一条声线；**Alt+点 / 右键**=轮转并写入
  `extra.gptsovits5.slot`（存档里生效）
- 兼容旧卡：卡上只有 `indextts25` 块时也能读出声线，写回时用 `gptsovits5`

**代价要知道**：两条声线用不同权重时，每次切换都要重新加载权重（几秒）。
同一段台词里混用两条声线会明显停顿，日常建议固定一条、需要时再手动切。

## 四、用到的接口（api_v2.py）

| 用途 | 请求 |
| --- | --- |
| 探活 | `GET /control`（不带 command，期望 400 JSON） |
| 切 GPT | `GET /set_gpt_weights?weights_path=...` |
| 切 SoVITS | `GET /set_sovits_weights?weights_path=...` |
| 合成 | `POST /tts`（JSON：text / text_lang / ref_audio_path / prompt_text / prompt_lang / speed_factor / ...） |

插件默认 `streaming_mode: 0`（整段 wav），靠**分句 + 预取下一句**降低等待；
不解析流式 wav，避免拼帧出错。

## 五、自测

```bash
node tools/test-text.mjs        # 纯逻辑：清洗/断句/槽位/档案/缓存键 —— 66 项
node tools/check-ids.mjs        # 静态审计：id、manifest、事件名、禁止 import ST、禁止 restart —— 22 项
python tools/test-relay.py      # 中继契约：CORS、转发、chunked 透传 —— 18 项
```

实测：66 / 22 / 18 全通过；`node --check` 通过。

## 六、已知边界

1. **没在真实酒馆里跑过**（开发机没装 ST）：顶栏挂载按 ST 源码与官方扩展文档写，静态审计兜住了 id/manifest/事件名，
   但"图标出不出现"要你验。没有就看 F12 的 `[GPTSoVITS5]` 日志。
2. **CORS**：官方 api_v2 没挂，直连大概率失败，中继是保底方案（本机 9881）。
3. **切权重耗时**：`/set_*_weights` 是同步加载，几秒级；插件会缓存"当前已加载的权重对"，不重复切。
4. **文本语言**：参考音频日文、文本中文时，`text_lang=zh` + `prompt_lang=ja`（插件「文本语言=自动」就会判成 zh）。
5. **sample_steps / v5**：`sample_steps` 只对 v3/v5 系列有意义，留空用服务端默认；填了会随请求发 `sample_steps`。

## 七、目录

```
st-gptsovits5-voice/
├── manifest.json
├── index.js               # 顶栏面板 + 音色档案 + 权重切换缓存 + 播放队列
├── style.css
├── lib/tts-text.js        # 纯逻辑（清洗/断句/槽位/档案/缓存键）
├── server/
│   ├── gptsovits_relay.py # 纯标准库 CORS 中继（9881 → 9880）
│   └── start-relay.bat
└── tools/
    ├── test-text.mjs
    ├── check-ids.mjs
    ├── test-relay.py
    ├── fake_upstream.py   # 测试用假上游
    └── adapt_files.py     # 把 v1.1 文件适配成本插件格式（只加块，零改动）
```
