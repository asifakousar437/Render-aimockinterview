# Use absolute imports for consistency
from ai_mock_interview.llm_service import call_llm



# -----------------------------------
# INITIAL QUESTION (FIRST QUESTION)
# -----------------------------------

def generate_first_question(name, jd, resume):
    prompt = f"""
You are a professional technical interviewer.

Start the interview.

Candidate Name: {name}

Instructions:
- Welcome the candidate warmly
- Briefly introduce yourself
- Ask the candidate to introduce themselves and their background
- Keep it natural and human-like

Return only the question/message.
"""

    return call_llm(prompt)


# ------------------------------------------------------------
# STRICT JSON QUESTION GENERATION (REQUIRED CONTRACT)
# ------------------------------------------------------------
#
# Your system requirements require the LLM to output ONLY JSON:
# { "question": "...", "technology": "...", "difficulty": "EASY|MODERATE|HARD" }
#
# We keep the legacy string-based functions above for now, and add contract-based
# functions that backend code can call going forward.


def _extract_json_object(content: str) -> dict:
    if not content:
        return {}
    import re
    import json

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except Exception:
        return {}


def generate_first_question_json(name: str, technology: str, difficulty: str = "EASY") -> dict:
    """
    First question with strict JSON-only LLM contract with enhanced randomness.
    """
    safe_name = name.strip() if isinstance(name, str) and name.strip() else "Candidate"
    import random
    
    # Add random context to encourage variety
    random_context = random.choice([
        "Start with a technical concept",
        "Begin with a practical scenario", 
        "Ask about fundamental principles",
        "Focus on real-world application",
        "Include a problem-solving element"
    ])
    
    prompt = f"""
SYSTEM REQUIREMENTS FOR AI MOCK INTERVIEW PLATFORM

QUESTION GENERATION (STRICT JSON ONLY)
Return JSON only:
{{
  "question": "Generated interview question including greeting and acknowledgement",
  "technology": "{technology}",
  "difficulty": "{difficulty}"
}}

CRITICAL RULES (DO NOT CHANGE):
- Address candidate by name: {safe_name}
- For first question: warm greeting + brief introduction + ONE technical question
- Question must match EXACT technology: {technology}
- Difficulty must match EXACT level: {difficulty}
- Ask exactly ONE clear, specific question
- Avoid generic "go deeper into" or "tell me about" questions
- Make questions practical and scenario-based when possible
- NO markdown formatting, no extra keys, no explanations
- **IMPORTANT**: Generate a UNIQUE question each time - do not repeat the same question
- **NEW**: Focus on this context: {random_context}
- **NEW**: Ask about SPECIFIC technical concepts, not general topics

TECHNOLOGY FOCUS: {technology}
DIFFICULTY LEVEL: {difficulty}
- EASY: Basic concepts, definitions, "What is..." questions, simple scenarios
- MODERATE: Practical usage, "How would you..." questions, implementation scenarios  
- HARD: Deep concepts, system design, "Why..." questions, architectural decisions

EXAMPLES BY DIFFICULTY:
EASY: "Hello {safe_name}, what is [specific concept] in {technology} and when would you use it?"
MODERATE: "Hello {safe_name}, how would you implement [specific feature] using {technology}?"
HARD: "Hello {safe_name}, why would you choose [specific approach] over [alternative] in {technology}?"

IMPORTANT FOR {technology}:
- Ask about concrete technical concepts
- Use specific terminology related to {technology}
- Avoid generic "programming" or "technical concepts" language
- Focus on practical, real-world scenarios

Return JSON only.
"""
    content = call_llm(prompt)
    data = _extract_json_object(content)
    if data.get("question"):
        return {
            "question": data.get("question"),
            "technology": data.get("technology", technology),
            "difficulty": data.get("difficulty", difficulty),
        }
    # Generate varied fallback questions to avoid repetition
    fallback_questions = [
        f"Hello {safe_name}, let's begin with {technology}. Can you explain a key concept?",
        f"Hello {safe_name}, welcome to the interview. What's your understanding of {technology}?",
        f"Hello {safe_name}, let's start with {technology}. Can you describe a basic principle?",
        f"Hello {safe_name}, nice to meet you. What do you know about {technology}?",
        f"Hello {safe_name}, let's dive into {technology}. Can you explain an foundational concept?",
        f"Hello {safe_name}, let's discuss {technology}. What's your experience with it?",
        f"Hello {safe_name}, can you walk me through a simple {technology} example?",
        f"Hello {safe_name}, how would you approach a {technology} problem?",
    ]
    
    return {
        "question": random.choice(fallback_questions),
        "technology": technology,
        "difficulty": difficulty,
    }


def generate_next_question_json(
    name: str,
    previous_question: str,
    previous_answer: str,
    technology: str,
    difficulty: str,
    asked_questions: list,
) -> dict:
    """
    Next question with strict JSON-only LLM contract with enhanced randomness and adaptive logic.
    """
    safe_name = name.strip() if isinstance(name, str) and name.strip() else "Candidate"
    asked_questions_text = "\n".join(asked_questions[-10:]) if asked_questions else ""
    import random
    
    # Add random elements to encourage variety
    random_approach = random.choice([
        "Build on previous answer",
        "Explore different aspect", 
        "Challenge with new scenario",
        "Focus on practical implementation",
        "Include system design element"
    ])
    
    # Get available technologies from session (simulate this for now)
    available_technologies = ["Java", "Object-Oriented Programming", "Data Structures", "Algorithms", "Software Development"]
    
    prompt = f"""
You are an expert AI technical interviewer with adaptive questioning capabilities.

----------------------------------------
CONTEXT
----------------------------------------

PREVIOUS QUESTION:
{previous_question}

CANDIDATE ANSWER:
{previous_answer}

CURRENT TECHNOLOGY: {technology}
CURRENT DIFFICULTY: {difficulty}

----------------------------------------
AVAILABLE TECHNOLOGIES:
{', '.join(available_technologies)}
----------------------------------------

QUESTIONS TO AVOID (DO NOT REPEAT):
{asked_questions_text}

----------------------------------------
RULES
----------------------------------------

1. PERFORMANCE-BASED ADAPTATION

- If Score < 3:
    • Switch to a DIFFERENT technology
    • Ask an EASY question
    • **CRITICAL**: If this is the 3rd consecutive score < 3 → END INTERVIEW

- If Score between 3 and 4:
    • Continue SAME technology
    • Ask EASY or MODERATE question
    • If already 2 questions asked in same tech → SWITCH

- If Score > 4:
    • Increase difficulty
    • Ask HARD question

2. INTERVIEW ENDING CONDITIONS

- **END INTERVIEW** if 3 consecutive scores < 3
- **END INTERVIEW** if candidate consistently struggles across technologies
- **END INTERVIEW** if assessment shows fundamental gaps

3. TECHNOLOGY RULE

- Do NOT ask more than 2 consecutive questions in same technology
- Rotate across available technologies

----------------------------------------

4. LOOP PREVENTION

- Do NOT repeat questions
- Do NOT ask similar variations
- Always ask a new concept

----------------------------------------

TASK:
Generate the next interview question following the adaptive rules above.

**IMPORTANT**: If this should be the 3rd consecutive low score, instead of a question, return:
{{
  "end_interview": true,
  "reason": "Interview ended due to 3 consecutive scores below 3.0"
}}

Otherwise, return:
{{
  "question": "Generated interview question including acknowledgement of previous answer",
  "technology": "Selected technology based on rules",
  "difficulty": "Selected difficulty based on rules"
}}

CRITICAL REQUIREMENTS:
- Address candidate by name: {safe_name}
- Follow the adaptive rules strictly
- Ask about SPECIFIC technical concepts in the chosen technology
- NO markdown formatting, no extra keys
- **NEW**: Use {random_approach} as inspiration
- **NEW**: Ask about concrete technical concepts, not general topics

Return JSON only.
"""
    content = call_llm(prompt)
    data = _extract_json_object(content)
    
    # Check if LLM decided to end the interview
    if data.get("end_interview"):
        return {
            "end_interview": True,
            "reason": data.get("reason", "Interview ended due to consecutive low scores")
        }
    
    # Return normal question if interview continues
    if data.get("question"):
        return {
            "question": data.get("question"),
            "technology": data.get("technology", technology),
            "difficulty": data.get("difficulty", difficulty),
        }
    
    # Fallback question - specific technical questions based on technology and difficulty
    fallback_questions = {
        "Java": {
            "EASY": [
                f"{safe_name}, thanks for that answer. What is the difference between a class and an object in Java?",
                f"{safe_name}, good explanation. Can you explain what inheritance means in Java programming?",
                f"{safe_name}, thanks for that. What is polymorphism in Java and when would you use it?"
            ],
            "MODERATE": [
                f"{safe_name}, thanks for that answer. How would you implement encapsulation in a Java class?",
                f"{safe_name}, good point. Can you explain the difference between abstract classes and interfaces in Java?",
                f"{safe_name}, thanks. How does garbage collection work in Java?"
            ],
            "HARD": [
                f"{safe_name}, excellent answer. Why would you choose composition over inheritance in Java?",
                f"{safe_name}, great explanation. How would you handle memory management in a Java application?",
                f"{safe_name}, thanks. What are the trade-offs between different Java collection types?"
            ]
        },
        "Python": {
            "EASY": [
                f"{safe_name}, thanks for that answer. What is a Python list and how is it different from a tuple?",
                f"{safe_name}, good explanation. Can you explain what a Python function is and how to create one?",
                f"{safe_name}, thanks. What is the difference between local and global variables in Python?"
            ],
            "MODERATE": [
                f"{safe_name}, thanks for that answer. How would you implement error handling in Python using try-except?",
                f"{safe_name}, good point. Can you explain list comprehensions in Python with an example?",
                f"{safe_name}, thanks. What are Python decorators and how would you use them?"
            ],
            "HARD": [
                f"{safe_name}, excellent answer. How does Python's GIL affect multi-threading in Python applications?",
                f"{safe_name}, great explanation. What are the differences between shallow copy and deep copy in Python?",
                f"{safe_name}, thanks. How would you optimize memory usage in a Python application?"
            ]
        },
        "Data Structures": {
            "EASY": [
                f"{safe_name}, thanks for that answer. What is an array and how does it differ from a linked list?",
                f"{safe_name}, good explanation. Can you explain what a stack data structure is and when to use it?",
                f"{safe_name}, thanks. What is the difference between a queue and a stack?"
            ],
            "MODERATE": [
                f"{safe_name}, thanks for that answer. How would you implement a binary search tree?",
                f"{safe_name}, good point. Can you explain the difference between BFS and DFS traversal?",
                f"{safe_name}, thanks. What is time complexity and why is it important for algorithms?"
            ],
            "HARD": [
                f"{safe_name}, excellent answer. How would you balance a binary search tree?",
                f"{safe_name}, great explanation. What are the trade-offs between different sorting algorithms?",
                f"{safe_name}, thanks. How would you optimize a hash table for better performance?"
            ]
        },
        "Object-Oriented Programming": {
            "EASY": [
                f"{safe_name}, thanks for that answer. What are the four main principles of object-oriented programming?",
                f"{safe_name}, good explanation. Can you explain what encapsulation means in OOP?",
                f"{safe_name}, thanks. What is inheritance and why is it useful in programming?"
            ],
            "MODERATE": [
                f"{safe_name}, thanks for that answer. How would you implement abstraction in an OOP design?",
                f"{safe_name}, good point. Can you explain the difference between composition and aggregation?",
                f"{safe_name}, thanks. What is the Liskov Substitution Principle and why does it matter?"
            ],
            "HARD": [
                f"{safe_name}, excellent answer. How would you design a class hierarchy using SOLID principles?",
                f"{safe_name}, great explanation. What are the pros and cons of multiple inheritance?",
                f"{safe_name}, thanks. How would you implement the observer pattern in an object-oriented system?"
            ]
        }
    }
    
    # Get fallback questions for the technology, or use generic if not found
    tech_fallbacks = fallback_questions.get(technology, {})
    difficulty_fallbacks = tech_fallbacks.get(difficulty, [
        f"{safe_name}, thanks for that answer. What is a key concept in {technology} you can explain?",
        f"{safe_name}, good explanation. How would you apply {technology} in a real-world scenario?",
        f"{safe_name}, thanks. What are the benefits of using {technology} in software development?"
    ])
    
    import random
    fallback_question = random.choice(difficulty_fallbacks)
    
    return {
        "question": fallback_question,
        "technology": technology,
        "difficulty": difficulty,
    }


# -----------------------------------
# NEXT QUESTION (ADAPTIVE)
# -----------------------------------

def generate_next_question(previous_q, answer, score, skills, name):
    prompt = f"""
You are an expert AI technical interviewer.

Conduct a natural, conversational interview.
Act like a real engineer speaking to a candidate.

Candidate Name: {name}

----------------------------------------
AVAILABLE TECHNOLOGIES:
{skills}
----------------------------------------

PREVIOUS QUESTION:
{previous_q}

CANDIDATE ANSWER:
{answer}

SCORE:
{score}

----------------------------------------
RULES
----------------------------------------

1. PERFORMANCE-BASED ADAPTATION

- If Score < 3:
    • Switch to a DIFFERENT technology
    • Ask an EASY question

- If Score between 3 and 4:
    • Continue SAME technology
    • Ask EASY or MODERATE question
    • If already 2 questions asked in same tech → SWITCH

- If Score > 4:
    • Increase difficulty
    • Ask HARD question

----------------------------------------

2. TECHNOLOGY RULE

- Do NOT ask more than 2 consecutive questions in same technology
- Rotate across skills list

----------------------------------------

3. LOOP PREVENTION

- Do NOT repeat questions
- Do NOT ask similar variations
- Always ask a new concept

----------------------------------------

4. DIFFICULTY LEVELS

EASY → basic definitions  
MODERATE → practical usage  
HARD → deep concepts / system design  

----------------------------------------

5. STYLE

- Appreciate candidate using their name
- Keep it conversational
- No robotic tone
- No long paragraphs
- Ask ONLY ONE question

----------------------------------------

Return ONLY the next question.
"""

    return call_llm(prompt)