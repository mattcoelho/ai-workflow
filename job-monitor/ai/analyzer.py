"""Gemini AI analyzer for job listings."""

import os
import json
from typing import Dict, Any
import google.generativeai as genai


def analyze_job(job: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze a job listing using Gemini AI.
    
    Args:
        job: Job dict with keys: id, title, company, url, location (may be empty)
        
    Returns:
        Dict with keys: score (int 1-10), reason (str), summary (str)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return {"score": 5, "reason": "Analysis unavailable", "summary": ""}
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Build prompt
        candidate_profile = """You are evaluating PM job listings for a candidate with this profile:
- Targeting: Staff PM, Principal PM, Senior PM (in that order)
- Domains wanted: AI/ML Platforms, Agentic AI, B2B/Enterprise SaaS, Customer Experience/CRM Tech, Internal Developer/Workflow Tools
- Domains to avoid: Hardware, Consumer Social, Marketing/Growth-only roles
- Location: SF Bay Area hybrid/on-site OR Remote
- Strong yes: roles requiring builder mindset, Python/Swift prototyping, P&L ownership, technical depth in data/SQL/architecture
- Hard no: environments where PMs are blocked from data, SQL, system design
- Company stage: Scaleup (Series B to Pre-IPO) or Enterprise; open to well-funded AI seed/series A"""
        
        job_title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "") or "Not specified"
        
        prompt = f"""{candidate_profile}

Evaluate this job listing based ONLY on the job title, company name, and location:
- Job Title: {job_title}
- Company: {company}
- Location: {location}

Return ONLY a JSON object with exactly these keys:
{{
    "score": <integer 1-10>,
    "reason": <one sentence max 20 words>,
    "summary": <two sentences describing the role based on title and company>
}}"""
        
        # Call Gemini API
        response = model.generate_content(prompt)
        
        # Parse JSON response
        response_text = response.text.strip()
        
        # Try to extract JSON from markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        
        # Validate and return
        return {
            "score": int(result.get("score", 5)),
            "reason": str(result.get("reason", "Analysis unavailable"))[:200],
            "summary": str(result.get("summary", ""))[:500]
        }
        
    except Exception as e:
        # Return default on any error
        return {"score": 5, "reason": "Analysis unavailable", "summary": ""}
