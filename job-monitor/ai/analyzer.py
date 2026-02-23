"""Gemini AI analyzer for job listings."""
import os
import json
import time
from typing import Dict, Any
from google import genai

def analyze_job(job: Dict[str, str]) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"score": 5, "reason": "No API key", "summary": ""}

    try:
        client = genai.Client(api_key=api_key)
        
        job_title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "") or "Not specified"

        prompt = f"""You are evaluating PM job listings for a candidate with this profile:
- Targeting: Staff PM, Principal PM, Senior PM (in that order)
- Domains wanted: AI/ML Platforms, Agentic AI, B2B/Enterprise SaaS, Customer Experience/CRM Tech, Internal Developer/Workflow Tools
- Domains to avoid: Hardware, Consumer Social, Marketing/Growth-only roles
- Location: SF Bay Area hybrid/on-site OR Remote
- Strong yes: roles requiring builder mindset, Python/Swift prototyping, P&L ownership, technical depth in data/SQL/architecture
- Hard no: environments where PMs are blocked from data, SQL, system design
- Company stage: Scaleup (Series B to Pre-IPO) or Enterprise; open to well-funded AI seed/series A

Evaluate this job:
- Job Title: {job_title}
- Company: {company}
- Location: {location}

Return ONLY a JSON object, no markdown, no explanation:
{{"score": <integer 1-10>, "reason": "<one sentence max 20 words>", "summary": "<two sentences about the role>"}}"""

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(35)
                    continue
                raise
        
        response_text = response.text.strip()
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.split("```")[0].strip()

        result = json.loads(response_text)
        return {
            "score": int(result.get("score", 5)),
            "reason": str(result.get("reason", ""))[:200],
            "summary": str(result.get("summary", ""))[:500]
        }

    except Exception as e:
        print(f"[AI ERROR] analyze_job failed for '{job.get('title')}': {e}")
        return {"score": 5, "reason": "Analysis unavailable", "summary": ""}