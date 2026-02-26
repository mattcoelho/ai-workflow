"""Flash Lite AI title filter for PM roles."""
import os
from google import genai


def is_pm_role(title: str) -> bool:
    """Return True if the job title is a PM or closely related role, else False."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARN] is_pm_role: GEMINI_API_KEY not set")
        return False

    prompt = (
        "Is this job title a Product Management role or closely related (e.g. Product Manager, Product Lead, Group PM, Head of Product, Director of Product, Staff PM)? Reply with only YES or NO.\n\n"
        f"Title: {title}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = (response.text or "").strip().upper()
        return "YES" in text
    except Exception as e:
        print(f"[WARN] is_pm_role failed for '{title[:50]}': {e}")
        return False
