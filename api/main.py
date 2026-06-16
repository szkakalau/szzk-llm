# -*- coding: utf-8 -*-
"""
SZZKLLM FastAPI 后端
用法: python api/main.py --model models/qwen7b-merged
"""
import argparse, sys, re
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ── 全局模型 ──
model = None
tokenizer = None
model_loaded = False

SYSTEM_PROMPT = "你是一个专业的中学学科答疑助手，请用简洁准确的语言回答问题。"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载模型"""
    global model, tokenizer, model_loaded
    print(f"Loading model from {app.state.model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(app.state.model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    load_kwargs = {"trust_remote_code": True}
    if device == "cuda":
        load_kwargs["torch_dtype"] = torch.bfloat16
        load_kwargs["device_map"] = "auto"
    else:
        load_kwargs["dtype"] = torch.float32
        load_kwargs["device_map"] = "cpu"

    model = AutoModelForCausalLM.from_pretrained(app.state.model_path, **load_kwargs)
    model.eval()
    model_loaded = True
    print(f"Model loaded on {device}")
    yield
    print("Shutting down...")


app = FastAPI(title="SZZKLLM", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    question: str
    subject: str | None = None


class ChatResponse(BaseModel):
    answer: str
    subject: str | None = None


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not model_loaded:
        raise HTTPException(503, "模型未加载")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.question},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=[tokenizer.eos_token_id, 151645],
        )

    response = tokenizer.decode(
        outputs[0][len(inputs["input_ids"][0]):],
        skip_special_tokens=True,
    )
    return ChatResponse(answer=response.strip(), subject=req.subject)


@app.get("/api/health")
async def health():
    return {"status": "ok", "model_loaded": model_loaded}


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML_PAGE)


# ── Web 前端 ──
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SZZKLLM - 深圳中考AI答疑</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
  .container { max-width: 800px; margin: 0 auto; padding: 20px; }
  h1 { text-align: center; padding: 20px 0; font-size: 1.5em; color: #1a73e8; }
  .subjects { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; justify-content: center; }
  .subj-btn { padding: 6px 16px; border: 2px solid #ddd; border-radius: 20px; cursor: pointer; background: white; font-size: 14px; transition: all 0.2s; }
  .subj-btn:hover, .subj-btn.active { border-color: #1a73e8; color: #1a73e8; }
  .chat-box { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.08); overflow: hidden; }
  .messages { padding: 20px; max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
  .msg { max-width: 85%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; font-size: 15px; }
  .msg.user { align-self: flex-end; background: #1a73e8; color: white; }
  .msg.assistant { align-self: flex-start; background: #f0f4f8; }
  .msg .label { font-size: 11px; opacity: 0.7; margin-bottom: 4px; }
  .msg .answer-letter { font-size: 1.5em; font-weight: bold; color: #1a73e8; }
  .input-area { display: flex; padding: 16px; border-top: 1px solid #eee; gap: 8px; }
  .input-area input { flex: 1; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 24px; font-size: 15px; outline: none; }
  .input-area input:focus { border-color: #1a73e8; }
  .input-area button { padding: 12px 24px; background: #1a73e8; color: white; border: none; border-radius: 24px; cursor: pointer; font-size: 15px; }
  .input-area button:hover { background: #1557b0; }
  .input-area button:disabled { background: #ccc; }
  .loading { text-align: center; color: #999; padding: 10px; }
  .example { padding: 16px 20px; background: #fafafa; border-bottom: 1px solid #eee; }
  .example p { font-size: 13px; color: #888; margin-bottom: 8px; }
  .example span { display: inline-block; padding: 4px 12px; margin: 2px; background: #e8f0fe; border-radius: 12px; font-size: 13px; cursor: pointer; color: #1a73e8; }
  .example span:hover { background: #d2e3fc; }
  .stats { text-align: center; padding: 10px; font-size: 13px; color: #999; }
  .stats strong { color: #1a73e8; }
</style>
</head>
<body>
<div class="container">
  <h1>📚 SZZKLLM 深圳中考 AI 答疑</h1>
  <div class="stats">基于 Qwen2.5-7B | Benchmark 准确率 <strong>89.3%</strong> | 覆盖7学科</div>

  <div class="subjects">
    <button class="subj-btn active" onclick="selectSubject('')">全部</button>
    <button class="subj-btn" onclick="selectSubject('数学')">数学</button>
    <button class="subj-btn" onclick="selectSubject('物理')">物理</button>
    <button class="subj-btn" onclick="selectSubject('化学')">化学</button>
    <button class="subj-btn" onclick="selectSubject('语文')">语文</button>
    <button class="subj-btn" onclick="selectSubject('英语')">英语</button>
    <button class="subj-btn" onclick="selectSubject('历史')">历史</button>
    <button class="subj-btn" onclick="selectSubject('道法')">道法</button>
  </div>

  <div class="chat-box">
    <div class="example">
      <p>💡 试试这些问题：</p>
      <span onclick="ask('-3的绝对值是（ ）A. 3 B. -3 C. 1/3 D. -1/3')">|-3| = ?</span>
      <span onclick="ask('下列物质中，属于纯净物的是（ ）A. 空气 B. 海水 C. 蒸馏水 D. 石灰水')">纯净物判断</span>
      <span onclick="ask('我国宪法规定，中华人民共和国的一切权力属于（ ）A. 公民 B. 人民 C. 政府 D. 全国人大')">宪法知识</span>
      <span onclick="ask('下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 直角三角形 C. 圆 D. 梯形')">轴对称</span>
    </div>
    <div class="messages" id="messages"></div>
    <div class="input-area">
      <input id="question" placeholder="输入你的中考题目..." onkeydown="if(event.key==='Enter')send()">
      <button id="sendBtn" onclick="send()">发送</button>
    </div>
  </div>
</div>

<script>
let subject = '';
function selectSubject(s) {
  subject = s;
  document.querySelectorAll('.subj-btn').forEach(b => b.classList.toggle('active', b.textContent === (s || '全部')));
}
function ask(q) { document.getElementById('question').value = q; send(); }

async function send() {
  const input = document.getElementById('question');
  const q = input.value.trim();
  if (!q) return;

  const btn = document.getElementById('sendBtn');
  const msgs = document.getElementById('messages');

  msgs.innerHTML += `<div class="msg user"><div class="label">你</div>${q}</div>`;
  msgs.innerHTML += `<div class="loading" id="ld">思考中...</div>`;
  msgs.scrollTop = msgs.scrollHeight;

  input.value = '';
  btn.disabled = true;

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q, subject: subject || null})
    });
    const data = await resp.json();
    document.getElementById('ld')?.remove();
    const answer = data.answer || '暂无回答';
    const letter = answer.match(/[A-D]/)?.[0];
    const display = letter ? `<span class="answer-letter">${letter}</span><br>${answer}` : answer;
    msgs.innerHTML += `<div class="msg assistant"><div class="label">AI</div>${display}</div>`;
  } catch(e) {
    document.getElementById('ld')?.remove();
    msgs.innerHTML += `<div class="msg assistant"><div class="label">AI</div>⚠ 服务异常: ${e.message}</div>`;
  }

  msgs.scrollTop = msgs.scrollHeight;
  btn.disabled = false;
  input.focus();
}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/qwen7b-merged", help="模型路径")
    parser.add_argument("--port", type=int, default=8000, help="端口")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    args = parser.parse_args()

    if not Path(args.model).exists():
        print(f"模型不存在: {args.model}")
        print("请先运行 python sft/merge_lora.py 合并模型")
        sys.exit(1)

    app.state.model_path = args.model

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
