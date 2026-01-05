from groq import Groq
import os

# ⚠️ For now, hardcode key (local only)
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_log_summary(log_text: str) -> str:
    prompt = f"""
You are a personal reflection assistant.

Analyze the following daily logs and provide:
1. A short summary
2. Emotional tone (happy, stressed, neutral, etc.)
3. One improvement suggestion

Daily Logs:
{log_text}
"""

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return completion.choices[0].message.content
