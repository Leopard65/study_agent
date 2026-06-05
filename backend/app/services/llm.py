from openai import AsyncOpenAI
from app.config import get_settings, is_ai_configured

_client: AsyncOpenAI | None = None
_client_config: tuple[str, str] | None = None  # (api_key, base_url) 缓存快照


class LLMConfigError(Exception):
    """AI 配置缺失（如未设置 API Key）。"""


class LLMCallError(Exception):
    """调用 LLM 接口失败。"""


_CONFIG_ERROR_MSG = (
    "未配置有效的 OPENAI_API_KEY，请在 backend/.env 中填写真实的 API Key；"
    "留空或使用占位符（如 your_api_key_here、sk-xxx）时 AI 功能不可用"
)


def _check_ai_configured() -> None:
    """统一使用 is_ai_configured() 检查，不通过则抛出 LLMConfigError。"""
    if not is_ai_configured():
        raise LLMConfigError(_CONFIG_ERROR_MSG)


def get_client() -> AsyncOpenAI:
    """获取 AsyncOpenAI 单例。当 API Key 或 base_url 变化时自动重建。"""
    global _client, _client_config
    settings = get_settings()
    _check_ai_configured()
    current = (settings.openai_api_key, settings.openai_base_url)
    if _client is not None and _client_config == current:
        return _client
    # 配置变化或首次创建 → 重建 client
    _client = AsyncOpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
    )
    _client_config = current
    return _client


def _require_api_key() -> str:
    """返回 model 名称，若 API Key 未配置则抛出 LLMConfigError。"""
    _check_ai_configured()
    return get_settings().openai_model


def reset_client() -> None:
    """重置缓存的 AsyncOpenAI client（用于测试或配置热更新后）。"""
    global _client, _client_config
    _client = None
    _client_config = None


SYSTEM_PROMPT = (
    "你是一个考研学习助手，擅长数学、信号与系统等学科。"
    "回答问题时，涉及数学公式请使用 LaTeX 格式：行内公式用 $...$，独立公式用 $$...$$。"
    "请给出清晰、详细、有步骤的解答。"
)


async def chat(
    question: str,
    context: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    model = _require_api_key()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 加入对话历史
    if history:
        messages.extend(history)
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
    if not response.choices:
        raise LLMCallError("AI 返回了空响应，请重试")
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
    if not response.choices:
        raise LLMCallError("AI 返回了空响应，请重试")
    return response.choices[0].message.content or ""


async def generate_exam_questions(
    subject: str, topic: str, count: int, difficulty: str = "", context: str = ""
) -> str:
    model = _require_api_key()
    diff_hint = f"难度：{difficulty}\n" if difficulty else ""
    ctx_hint = f"参考资料：\n{context}\n\n" if context else ""
    prompt = (
        f"{ctx_hint}"
        f"请为考研复习生成 {count} 道练习题。\n"
        f"科目：{subject or '不限'}\n"
        f"知识点/主题：{topic}\n"
        f"{diff_hint}"
        f"请严格以 JSON 数组格式返回，每个元素包含以下字段：\n"
        f'  - title: 题目标题（简短概括）\n'
        f'  - subject: 所属科目\n'
        f'  - year: 出题年份（可用"模拟"或留空）\n'
        f'  - question: 题目正文（数学公式用 LaTeX 格式：行内 $...$，独立 $$...$$）\n'
        f'  - answer: 参考答案\n'
        f'  - solution: 详细解析过程\n'
        f'  - tags: 标签（逗号分隔）\n'
        f"只返回 JSON，不要包含任何其他文字、解释或 markdown 代码块标记。\n"
        f"示例：\n"
        f'[{{"title":"极限计算","subject":"高等数学","year":"模拟","question":"求极限 $\\\\lim_{{x\\\\to 0}} \\\\frac{{\\\\sin x}}{{x}}$","answer":"1","solution":"由等价无穷小 $\\\\sin x \\\\sim x$，极限为 1。","tags":"极限,等价无穷小"}}]'
    )
    messages = [
        {"role": "system", "content": "你是考研出题专家，请生成高质量的练习题。只输出 JSON 数组。"},
        {"role": "user", "content": prompt},
    ]
    try:
        response = await get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=8192,
        )
    except LLMConfigError:
        raise
    except Exception as e:
        raise LLMCallError(f"AI 接口调用失败：{e}") from e
    if not response.choices:
        raise LLMCallError("AI 返回了空响应，请重试")
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
    if not response.choices:
        raise LLMCallError("AI 返回了空响应，请重试")
    return response.choices[0].message.content or ""
