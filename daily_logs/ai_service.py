"""
ai_service.py

This module contains all AI-related logic for the Daily Logs feature.

Design goals:
- Views should not directly talk to AI providers
- API keys must never be hardcoded
- AI provider should be replaceable (Groq, OpenAI, etc.)
"""

import os
from groq import Groq


# --------------------------------------------------
# Read API key from OS environment
# This keeps secrets out of the codebase and GitHub
# --------------------------------------------------
API_KEY = os.getenv("GROQ_API_KEY")

# Fail fast with a clear error if key is missing
if not API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY environment variable is not set"
    )

# Initialize Groq client once at startup
client = Groq(api_key=API_KEY)


def generate_log_summary(log_text: str) -> dict:
    """
    Analyze user's daily logs using AI and return structured insights.

    Input:
    - log_text: Combined text of all logs for a user

    Output (dict):
    - mood: Emotional state (e.g., Stressed, Happy)
    - score: Intensity score from 1–10
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

    response = client.chat.completions.create(
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
