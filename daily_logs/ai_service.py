"""
ai_service.py

This module contains all AI-related logic for the Daily Logs feature.

Design goals:
- Views should not directly talk to AI providers
- API keys must never be hardcoded
- AI provider should be replaceable (Groq, OpenAI, etc.)
"""

import os
import re
from groq import Groq


# --------------------------------------------------
# Read API key from OS environment
# This keeps secrets out of the codebase and GitHub
# --------------------------------------------------
API_KEY = os.getenv("GROQ_API_KEY")
client = None


def _get_client() -> Groq:
    """
    Lazily initialize Groq client so the app can start
    even when AI features are not used.
    """
    global client
    if client is None:
        if not API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set"
            )
        client = Groq(api_key=API_KEY)
    return client


def generate_log_summary(log_text: str) -> dict:
    """
    Analyze user's daily logs using AI and return structured insights.

    Input:
    - log_text: Combined text of all logs for a user

    Output (dict):
    - mood: Emotional state (e.g., Stressed, Happy)
    - score: Intensity score from 1-10
    - summary: Short reflection summary
    - suggestion: One practical improvement suggestion
    """

    prompt = f"""
You are a personal mental wellness assistant.

Analyze the user's daily logs and respond STRICTLY in this format:

MOOD: <one word>
SCORE: <number from 1 to 10>
SUMMARY: <2-3 lines>
SUGGESTION: <one practical suggestion>

Daily Logs:
{log_text}
"""

    response = _get_client().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Raw AI text
    ai_text = response.choices[0].message.content

    # Parse structured response safely
    result = {
        "mood": "",
        "score": "",
        "summary": "",
        "suggestion": ""
    }

    for line in ai_text.splitlines():
        if line.startswith("MOOD:"):
            result["mood"] = line.replace("MOOD:", "").strip()
        elif line.startswith("SCORE:"):
            result["score"] = line.replace("SCORE:", "").strip()
        elif line.startswith("SUMMARY:"):
            result["summary"] = line.replace("SUMMARY:", "").strip()
        elif line.startswith("SUGGESTION:"):
            result["suggestion"] = line.replace("SUGGESTION:", "").strip()

    return result


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"\b\w+\b", text.lower()) if len(w) > 2]


def _select_relevant_logs(
    logs: list[tuple[str, str]],
    question: str,
    max_logs: int = 8,
    max_chars: int = 4000
) -> list[tuple[str, str]]:
    """
    Select the most relevant logs based on keyword overlap.
    """
    question_terms = set(_tokenize(question))
    if not question_terms:
        return logs[:max_logs]

    scored = []
    for date_str, content in logs:
        content_terms = set(_tokenize(content))
        overlap = len(question_terms.intersection(content_terms))
        scored.append((overlap, date_str, content))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = []
    total_chars = 0
    for score, date_str, content in scored:
        if score == 0 and picked:
            break
        snippet = content.strip()
        if len(snippet) > 800:
            snippet = snippet[:800].rstrip() + "..."
        total_chars += len(snippet)
        if total_chars > max_chars:
            break
        picked.append((date_str, snippet))

    return picked if picked else logs[:max_logs]


def chat_with_logs(logs: list[tuple[str, str]], user_question: str) -> str:
    """
    Allows the user to chat with their own logs.

    Inputs:
    - user_logs (str): Combined text of user's historical logs
    - user_question (str): User's question

    Output:
    - AI-generated answer grounded strictly in the logs
    """

    selected_logs = _select_relevant_logs(logs, user_question)
    context = "\n\n".join(
        f"DATE: {date_str}\nCONTENT: {content}"
        for date_str, content in selected_logs
    )

    prompt = f"""
You are a personal reflection assistant.

RULES:
- Use the user's logs as your primary evidence.
- If the logs do not contain enough information, say you do not have enough
  evidence from the logs and ask a concise clarifying question.
- When you can infer a likely reason, explain it briefly and ground it in the logs.
- Provide a short "Evidence" section citing relevant dates from the logs.
- Keep the tone supportive and concise.

USER LOGS:
{context}

QUESTION:
{user_question}
"""

    response = _get_client().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content
