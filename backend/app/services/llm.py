from openai import AsyncOpenAI
from app.config import get_settings

_client: AsyncOpenAI | None = None


class LLMConfigError(Exception):
    """AI 配置缺失（如未设置 API Key）。"""


class LLMCallError(Exception):
    """调用 LLM 接口失败。"""


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or "placeholder",
        )
    return _client


def _require_api_key() -> str:
    """返回 model 名称，若 API Key 未配置则抛出 LLMConfigError。"""
    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise LLMConfigError(
            "未配置 OPENAI_API_KEY，请在 backend/.env 中填写 API Key"
        )
    return settings.openai_model


SYSTEM_PROMPT = (
    "你是一个考研学习助手，擅长数学、信号与系统等学科。"
    "回答问题时，涉及数学公式请使用 LaTeX 格式：行内公式用 $...$，独立公式用 $$...$$。"
    "请给出清晰、详细、有步骤的解答。"
)


async def chat(question: str, context: str | None = None) -> str:
    model = _require_api_key()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "user", "content": f"参考资料：\n{context}\n\n我的问题：{question}"})
    else:
        messages.append({"role": "user", "content": question})

    try:
        response = await get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
    except LLMConfigError:
        raise
    except Exception as e:
        raise LLMCallError(f"AI 接口调用失败：{e}") from e
    return response.choices[0].message.content or ""


async def solve_problem(question: str, subject: str = "") -> str:
    model = _require_api_key()
    sys = SYSTEM_PROMPT
    if subject:
        sys += f"\n当前科目：{subject}"
    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": f"请详细解析以下题目，给出完整的解题步骤和最终答案：\n{question}"},
    ]
    try:
        response = await get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
            max_tokens=4096,
        )
    except LLMConfigError:
        raise
    except Exception as e:
        raise LLMCallError(f"AI 接口调用失败：{e}") from e
    return response.choices[0].message.content or ""


async def generate_plan(subjects: list[str], daily_hours: int, days: int, start_date: str = "") -> str:
    model = _require_api_key()
    subject_str = "、".join(subjects)
    date_hint = f"起始日期：{start_date}\n" if start_date else "起始日期：从明天开始\n"
    prompt = (
        f"请为考研复习生成一个 {days} 天的学习计划。\n"
        f"科目：{subject_str}\n"
        f"每天可用学习时间：{daily_hours} 小时\n"
        f"{date_hint}"
        f"请严格以 JSON 数组格式返回，每个元素包含 date、subject、task 三个字段。\n"
        f"date 格式为 YYYY-MM-DD。\n"
        f"只返回 JSON，不要包含任何其他文字、解释或 markdown 代码块标记。\n"
        f"示例：\n"
        f'[{{"date":"2026-05-23","subject":"高等数学","task":"复习极限与连续，完成20道练习题"}}]'
    )
    messages = [
        {"role": "system", "content": "你是考研学习规划师，请生成合理、可执行的学习计划。只输出 JSON 数组。"},
        {"role": "user", "content": prompt},
    ]
    try:
        response = await get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
            max_tokens=4096,
        )
    except LLMConfigError:
        raise
    except Exception as e:
        raise LLMCallError(f"AI 接口调用失败：{e}") from e
    return response.choices[0].message.content or ""
