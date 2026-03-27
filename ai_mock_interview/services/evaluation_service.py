import requests
import re
import json
from ..config import Config

# -------------------------------
# LLM CALL (Reusable)
# -------------------------------

def call_llm(prompt, temperature=0):
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are an expert technical interviewer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("LLM Error:", e)
        return None


# -------------------------------
def generate_answer_feedback(question, answer, score):
    """Generate specific feedback for a single answer"""
    prompt = f"""
    You are an expert interview coach providing feedback on a candidate's answer.
    
    Question: {question}
    Answer: {answer}
    Score: {score.get('total_score', 0)}/5
    
    Provide concise, constructive feedback in 2-3 sentences. Focus on:
    - What was done well
    - What could be improved
    - Specific suggestions for better answers
    
    Keep it encouraging and professional.
    """
    
    try:
        content = call_llm(prompt, temperature=0.7)
        if content and content.strip():
            # Clean up the response
            feedback = content.strip().replace('"', '').replace("'", "")
            return feedback[:300]  # Limit length
    except Exception as e:
        print(f"Error generating answer feedback: {e}")
    
    # Fallback feedback based on score
    score_val = score.get('total_score', 0)
    if score_val >= 4:
        return "Excellent answer! You demonstrated strong understanding and clear communication."
    elif score_val >= 3:
        return "Good answer with solid understanding. Consider adding more specific examples next time."
    elif score_val >= 2:
        return "Decent attempt. Try to provide more detailed technical explanations and examples."
    else:
        return "Keep practicing! Focus on understanding the core concepts and structuring your answers more clearly."

# ANSWER EVALUATION
# -------------------------------

def evaluate_answer(question, answer):
    prompt = f"""
You are an expert interview evaluator evaluating technical interview answers. Your job is to be FAIR and OBJECTIVE.

Question: {question}
Answer: {answer}

Evaluate the answer on a 0-5 scale for each criteria:

**1. Relevance (0-5):**
- Does the answer address the question asked?
- Does it contain relevant technical information?
- Is it on-topic?

**2. Technical Accuracy (0-5):**
- Is the technical information correct?
- Are the concepts explained properly?
- Are there factual errors?

**3. Understanding (0-5):**
- Does the candidate understand the concept?
- Can they explain it in their own words?
- Do they show comprehension?

**4. Communication (0-5):**
- Is the answer clear and coherent?
- Is it well-structured?
- Is the communication effective?

**SCORING GUIDELINES:**
- Give credit for correct technical information
- Don't penalize for minor imperfections
- Recognize good explanations even if not perfect
- Be generous with partial understanding
- Focus on what the candidate DOES know, not what they miss

**EXAMPLES FOR FAIR SCORING:**
- Good Java answer about OOP concepts: Relevance 4-5, Technical 3-5, Understanding 3-5, Communication 3-5
- Partially correct answer: Relevance 3-4, Technical 2-4, Understanding 2-4, Communication 2-4
- Basic but correct answer: Relevance 3-4, Technical 2-3, Understanding 2-3, Communication 2-3
- "I don't know": All scores 0

**IMPORTANT:**
- If the answer contains correct technical information about the topic, relevance should be at least 3
- If the answer shows understanding of the concept, understanding should be at least 3
- Only give 0 if the answer is completely unrelated or is "I don't know"

Return ONLY JSON format:
{{
"relevance": [0-5],
"technical": [0-5],
"understanding": [0-5],
"communication": [0-5],
"total_score": [0-5]
}}
"""

    content = call_llm(prompt)

    if not content:
        print("DEBUG: LLM returned None, trying LLM fallback evaluation")
        return llm_fallback_evaluation(question, answer)

    print(f"DEBUG: LLM evaluation response: {content}")

    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)

        if match:
            scores = json.loads(match.group())
            print(f"DEBUG: Parsed scores: {scores}")

            # Update safety checks for new criteria
            for key in ["relevance", "technical", "understanding", "communication"]:
                scores[key] = float(scores.get(key, 0))

            # Calculate total score as average of all criteria
            scores["total_score"] = round(
                (
                    scores["relevance"]
                    + scores["technical"]
                    + scores["understanding"]
                    + scores["communication"]
                ) / 4,
                2
            )

            print(f"DEBUG: Final scores: {scores}")
            return scores

    except Exception as e:
        print("Evaluation parsing error:", e)
        return default_score()

    print("DEBUG: No JSON match found in LLM response")
    return default_score()


def llm_fallback_evaluation(question, answer):
    """
    LLM-based fallback evaluation when primary LLM fails
    """
    # Try a different LLM service or simpler prompt
    try:
        fallback_prompt = f"""
Quick evaluation of technical answer:

Question: {question}
Answer: {answer}

Give fair scores (0-5) for:
- Relevance: Does it answer the question?
- Technical: Is the information correct?
- Understanding: Does the candidate get it?
- Communication: Is it clear?

Be generous with good technical answers. Return JSON only:
{{
"relevance": [0-5],
"technical": [0-5],
"understanding": [0-5],
"communication": [0-5],
"total_score": [0-5]
}}
"""
        content = call_llm(fallback_prompt)
        
        if content:
            print(f"DEBUG: Fallback LLM response: {content}")
            match = re.search(r"\{.*\}", content, re.DOTALL)
            
            if match:
                scores = json.loads(match.group())
                # Ensure all keys exist
                for key in ["relevance", "technical", "understanding", "communication"]:
                    scores[key] = float(scores.get(key, 0))
                
                scores["total_score"] = round(
                    (scores["relevance"] + scores["technical"] + scores["understanding"] + scores["communication"]) / 4,
                    2
                )
                
                print(f"DEBUG: Fallback evaluation scores: {scores}")
                return scores
                
    except Exception as e:
        print(f"Fallback LLM evaluation failed: {e}")
    
    # If all LLM attempts fail, return a neutral score for good answers
    if answer and len(answer.split()) > 10:
        print("DEBUG: All LLM failed, giving neutral score for substantial answer")
        return {
            "relevance": 3,
            "technical": 3,
            "understanding": 3,
            "communication": 3,
            "total_score": 3.0
        }
    
    return default_score()


def default_score():
    return {
        "relevance": 0,
        "technical": 0,
        "understanding": 0,
        "communication": 0,
        "total_score": 0
    }


# -------------------------------
# FINAL INTERVIEW FEEDBACK
# -------------------------------

def generate_feedback(average_score, questions, answers):
    qa_text = ""

    for i in range(len(answers)):
        q = questions[i]["question"]
        a = answers[i]["answer"]
        score = answers[i]["score"]["total_score"]
        relevance = answers[i]["score"]["relevance"]
        clarity = answers[i]["score"]["clarity"]
        confidence = answers[i]["score"]["confidence"]

        qa_text += f"""
Question: {q}
Answer: {a}
Score: {score}/5
Relevance: {relevance}/5, Clarity: {clarity}/5, Confidence: {confidence}/5
"""

    prompt = f"""
You are an expert technical interviewer providing detailed feedback to a candidate.

Analyze the interview below and provide comprehensive feedback in the specified JSON format.

Average Score: {average_score}/5 ({(average_score/5)*100:.1f}%)

Interview Conversation:
{qa_text}

Provide detailed analysis covering:
1. Technical knowledge demonstrated
2. Communication skills (clarity, confidence)
3. Answer relevance and quality
4. Overall performance assessment

Return ONLY JSON format:
{{
"overall_feedback": "Detailed paragraph summarizing candidate's performance",
"strengths": [
    "Specific strength 1 with example",
    "Specific strength 2 with example"
],
"weaknesses": [
    "Specific weakness 1 with example", 
    "Specific weakness 2 with example"
],
"where_to_improve": [
    "Actionable improvement suggestion 1",
    "Actionable improvement suggestion 2",
    "Actionable improvement suggestion 3"
],
"suggestions": [
    "Specific learning recommendation 1",
    "Specific learning recommendation 2",
    "Career development suggestion 3"
],
"final_recommendation": "Strong Hire / Hire / Needs Improvement / Not Ready"
}}

Be specific and constructive in your feedback. Use examples from the interview where relevant.
"""

    content = call_llm(prompt, temperature=0.3)

    if not content:
        return default_feedback()

    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)

        if match:
            return json.loads(match.group())

    except Exception as e:
        print("Feedback parsing error:", e)

    return default_feedback()


def default_feedback():
    return {
        "overall_feedback": "Unable to generate detailed feedback",
        "strengths": ["Unable to analyze strengths"],
        "weaknesses": ["Unable to analyze weaknesses"],
        "where_to_improve": ["Unable to generate improvement suggestions"],
        "suggestions": ["Unable to provide specific suggestions"],
        "final_recommendation": "Unknown"
    }