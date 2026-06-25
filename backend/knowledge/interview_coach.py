"""Interview coach — grades a spoken answer against a candidate's real STAR story.

Shared by the CLI practice tool (backend/scripts/interview_practice.py) and the
admin-only practice panel on the portfolio site. Always runs on the local
Ollama model — no candidate answers leave the machine.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.llm.router import LLMTier, get_llm

COACH_SYSTEM_PROMPT = (
    "You are an interview coach helping a candidate rehearse for technical interviews. "
    "You will be given an interview question, the candidate's REFERENCE answer (their real "
    "situation/action/result), and the ANSWER they just gave out loud. "
    "Compare the two. Be concise and direct:\n"
    "1. What they covered well (1-2 bullets).\n"
    "2. What's missing or weak compared to the reference (1-3 bullets) — specific facts, "
    "numbers, or steps they left out.\n"
    "3. A tightened 3-5 sentence model answer combining the best of both.\n"
    "Be encouraging but honest. No preamble."
)


def grade_answer(question: str, situation: str, action: str, result: str, answer: str) -> str:
    reference = f"Situation: {situation}\n\nAction: {action}\n\nResult: {result}"
    user_prompt = (
        f"Interview question: {question}\n\n"
        f"REFERENCE answer:\n{reference}\n\n"
        f"CANDIDATE's spoken answer:\n{answer}"
    )
    llm = get_llm(LLMTier.LOCAL, json_mode=False)
    response = llm.invoke([
        SystemMessage(content=COACH_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])
    return response.content
