import requests
from ..config import Config

def call_llm(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Add randomness to prompt and increase temperature for variety
    import random
    random_seed = random.randint(1, 999999)
    
    body = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,  # Increased for more randomness
        "seed": random_seed,  # Add random seed for variety
        "top_p": 0.95,  # Allow more diverse responses
        "max_tokens": 500
    }
    # body = {
    #     "model": "llama-3.1-8b-instant",   # ✅ changed here
    #     "messages": [{"role": "user", "content": prompt}],
    #     "temperature": 0.9,
    #     "seed": random_seed, 
    #     "top_p": 0.9,
    #     "max_tokens": 150
    # }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
    except Exception as e:
        print("LLM request error:", e)
        return None

    # If Groq returns an error payload, it may not have `choices`.
    try:
        data = response.json()
    except Exception:
        print("LLM non-JSON response:", response.text[:500])
        return None

    if not response.ok:
        # Best-effort extraction of error message
        err = data.get("error") or {}
        print("LLM HTTP error:", response.status_code, err.get("message") or data)
        
        # Check for rate limit specifically
        if response.status_code == 429:
            print("RATE LIMIT REACHED - Please try again later or upgrade plan")
        return None

    choices = data.get("choices")
    if not choices:
        print("LLM response missing choices:", data)
        return None

    msg = choices[0].get("message") or {}
    return msg.get("content")