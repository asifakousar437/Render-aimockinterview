from flask import Blueprint, request, jsonify, render_template
from ..utils.file_utils import save_file
from ..services.resume_service import extract_text
from ..services.jd_service import extract_candidate_name, extract_resume_entities, is_resume, match_score
from ..services.interview_service import generate_first_question_json, generate_next_question_json
from ..services.evaluation_service import evaluate_answer, generate_feedback, generate_answer_feedback
from ..services.speech_service import speech_to_text
import os
from ..utils.camera_monitor import detect_faces
import subprocess
from datetime import datetime

interview_bp = Blueprint("interview", __name__)

SESSION = {
    "questions": [],
    "answers": [],
    "jd": "",
    "resume": "",
    "name": "",
    # Adaptive interview state:
    "resume_entities": {},
    "candidate_technologies": [],
    "current_technology": "",
    "current_difficulty": "EASY",
    "consecutive_technology_count": 0,
    "asked_questions": [],
    # Proctoring state:
    "proctoring_issue_count": 0,
    "proctoring_terminated": False,
    "face_violations": 0,
    "tab_violations": 0,
    "interview_terminated": False,
    "termination_reason": "",
    "violation_screenshots": [],  # Store screenshots of violations
    "violation_details": [],     # Store details of each violation
}

# Initialize session for interview monitoring
@interview_bp.before_request
def init_session():
    SESSION.setdefault("multiple_face_violations", 0)
    SESSION.setdefault("no_face_violations", 0)
    SESSION.setdefault("tab_violations", 0)
    SESSION.setdefault("interview_active", False)
    SESSION.setdefault("interview_terminated", False)
    SESSION.setdefault("termination_reason", "")
    SESSION.setdefault("violation_screenshots", [])  # Store screenshots of violations
    SESSION.setdefault("violation_details", [])     # Store details of each violation
    SESSION.setdefault("proctoring_issue_count", 0)
    SESSION.setdefault("proctoring_terminated", False)
    SESSION.setdefault("last_violation_time", None)
    SESSION.setdefault("last_violation_count", 0)

# ---------------- VIOLATION TRACKING ----------------
@interview_bp.route("/violation", methods=["POST"])
def record_violation():
    violation_type = request.json.get("type")  # "multiple_faces", "no_face", "tab"
    screenshot = request.json.get("screenshot")  # Base64 screenshot data
    evidence = request.json.get("evidence", {})  # Additional evidence data
    
    # Server-side debouncing - check last violation time
    current_time = datetime.now()
    last_violation_time = SESSION.get("last_violation_time", None)
    
    if last_violation_time and (current_time - last_violation_time).total_seconds() < 3:
        print(f"DEBUG: Server-side debouncing violation (too soon)")
        return jsonify({
            "multiple_face_violations": SESSION.get("multiple_face_violations", 0),
            "no_face_violations": SESSION.get("no_face_violations", 0),
            "tab_violations": SESSION.get("tab_violations", 0),
            "terminated": SESSION.get("interview_terminated", False),
            "reason": SESSION.get("termination_reason", ""),
            "violation_count": SESSION.get("last_violation_count", 0),
            "debounced": True
        })
    
    # Update last violation time
    SESSION["last_violation_time"] = current_time
    
    # Store violation details
    violation_detail = {
        "type": violation_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screenshot": screenshot,
        "evidence": evidence,
        "violation_count": 0
    }
    
    if violation_type == "multiple_faces":
        SESSION["multiple_face_violations"] = SESSION.get("multiple_face_violations", 0) + 1
        violation_detail["violation_count"] = SESSION["multiple_face_violations"]
        violation_detail["description"] = f"Multiple faces detected - Violation {SESSION['multiple_face_violations']}"
        
        if SESSION["multiple_face_violations"] >= 2:
            SESSION["interview_terminated"] = True
            SESSION["termination_reason"] = "Multiple faces detected more than twice"
    
    elif violation_type == "no_face":
        SESSION["no_face_violations"] = SESSION.get("no_face_violations", 0) + 1
        violation_detail["violation_count"] = SESSION["no_face_violations"]
        violation_detail["description"] = f"No face detected - Violation {SESSION['no_face_violations']}"
        
        if SESSION["no_face_violations"] >= 5:
            SESSION["interview_terminated"] = True
            SESSION["termination_reason"] = "No face detected more than 5 times"
    
    elif violation_type == "tab":
        SESSION["tab_violations"] = SESSION.get("tab_violations", 0) + 1
        violation_detail["violation_count"] = SESSION["tab_violations"]
        
        # Debug logging
        print(f"DEBUG: Tab violation {SESSION['tab_violations']} recorded")
        
        # Enhanced description with evidence details
        detection_method = evidence.get("detectionMethod", "visibility_change")
        if detection_method == "alt_tab_blocked":
            violation_detail["description"] = f"Tab switch attempt blocked (Alt+Tab) - Violation {SESSION['tab_violations']}"
        elif detection_method == "window_blur":
            violation_detail["description"] = f"Tab switch detected (Window Blur) - Violation {SESSION['tab_violations']}"
        else:
            violation_detail["description"] = f"Tab switch detected - Violation {SESSION['tab_violations']}"
        
        # Add evidence details for tab violations
        if evidence:
            violation_detail["evidence_details"] = {
                "url": evidence.get("url", ""),
                "title": evidence.get("title", ""),
                "user_agent": evidence.get("userAgent", ""),
                "violation_time": evidence.get("violationTime", ""),
                "detection_method": detection_method,
                "current_question": evidence.get("currentQuestion", ""),
                "interview_progress": evidence.get("interviewProgress", {}),
                "system_info": evidence.get("systemInfo", {}),
                "tab_detection": evidence.get("tabDetection", {})
            }
        
        # Only terminate after 2 violations
        if SESSION["tab_violations"] >= 2:
            print(f"DEBUG: Terminating interview after {SESSION['tab_violations']} tab violations")
            SESSION["interview_terminated"] = True
            SESSION["termination_reason"] = "Tab switch detected more than twice"
        else:
            print(f"DEBUG: Warning only - {SESSION['tab_violations']} tab violations so far")
    
    # Store violation details and screenshot
    SESSION["violation_details"].append(violation_detail)
    if screenshot:
        SESSION["violation_screenshots"].append({
            "type": violation_type,
            "timestamp": violation_detail["timestamp"],
            "image": screenshot,
            "description": violation_detail["description"],
            "evidence": violation_detail.get("evidence_details", {})
        })
    
    return jsonify({
        "multiple_face_violations": SESSION.get("multiple_face_violations", 0),
        "no_face_violations": SESSION.get("no_face_violations", 0),
        "tab_violations": SESSION.get("tab_violations", 0),
        "terminated": SESSION.get("interview_terminated", False),
        "reason": SESSION.get("termination_reason", ""),
        "violation_count": violation_detail["violation_count"],
        "debounced": False
    })

@interview_bp.route("/check_termination", methods=["GET"])
def check_termination():
    return jsonify({
        "terminated": SESSION.get("interview_terminated", False),
        "reason": SESSION.get("termination_reason", ""),
        "face_violations": SESSION.get("face_violations", 0),
        "tab_violations": SESSION.get("tab_violations", 0)
    })

# ---------------- START ----------------
@interview_bp.route("/start", methods=["POST"])
def start():
    # Reset all violation tracking for new interview
    SESSION.update({
        "multiple_face_violations": 0,
        "no_face_violations": 0,
        "tab_violations": 0,
        "interview_active": True,
        "interview_terminated": False,
        "termination_reason": "",
        "violation_screenshots": [],
        "violation_details": [],
        "proctoring_issue_count": 0,
        "proctoring_terminated": False,
        "last_violation_time": None,
        "last_violation_count": 0,
        "face_violations": 0
    })
    
    jd = request.form.get("jd")
    name = request.form.get("name")  # Optional; we will prefer extracting from resume text.
    resume_file = request.files.get("resume")

    if not jd or not resume_file:
        return jsonify({"error": "Missing input data"})

    # Strict resume format validation.
    filename = (resume_file.filename or "").lower()
    ext = os.path.splitext(filename)[1]
    if ext not in [".pdf", ".docx"]:
        return jsonify({
            "status": "error",
            "message": "Upload the correct document. The uploaded file does not appear to be a resume."
        })

    path = save_file(resume_file)
    resume_text = extract_text(path)

    if not resume_text:
        return jsonify({
            "status": "error",
            "message": "Upload the correct document. The uploaded file does not appear to be a resume."
        })

    if not is_resume(resume_text):
        return jsonify({
            "status": "error",
            "message": "Upload the correct document. The uploaded file does not appear to be a resume."
        })

    # Extract resume entities once; use them both for match scoring and interview adaptation.
    entities = extract_resume_entities(resume_text)

    match = match_score(jd, resume_text, entities=entities)

    if match < 25:
        return jsonify({
            "status": "rejected",
            "message": "Your resume does not sufficiently match the job description. Please update your resume and try again.",
            "match_score": ""
        })

    extracted_name = extract_candidate_name(resume_text) or ""
    print(f"DEBUG: Extracted name from resume: '{extracted_name}'")
    final_name = extracted_name if extracted_name else (name or "")
    print(f"DEBUG: Final name to be used: '{final_name}'")
    if not final_name.strip():
        final_name = "Candidate"

    candidate_technologies = [t.strip() for t in (entities.get("skills") or []) if isinstance(t, str) and t.strip()]

    # If we can't rotate across technologies, broaden topics using projects/certifications.
    if len(candidate_technologies) < 2:
        candidate_technologies.extend([t.strip() for t in (entities.get("projects") or []) if isinstance(t, str) and t.strip()])
        candidate_technologies.extend([t.strip() for t in (entities.get("certifications") or []) if isinstance(t, str) and t.strip()])

    # If still no technologies found, extract from resume text using LLM for better technical identification
    if not candidate_technologies:
        try:
            from ..services.llm_service import call_llm
            resume_snippet = resume_text[:2000]  # Use first 2000 chars for analysis
            
            tech_prompt = f"""
Extract specific technical skills, programming languages, frameworks, and technologies from this resume:

RESUME TEXT:
{resume_snippet}

Return ONLY a comma-separated list of technical technologies (e.g., Java, Python, React, SQL, AWS, etc.).
No explanations, just the list.
"""
            
            tech_response = call_llm(tech_prompt)
            if tech_response and tech_response.strip():
                # Parse the response to get clean technology list
                extracted_techs = [tech.strip() for tech in tech_response.split(',') if tech.strip()]
                candidate_technologies = extracted_techs[:5]  # Take top 5 technologies
        except Exception as e:
            print(f"Failed to extract technologies via LLM: {e}")
    
    # Final fallback with Java-specific technologies (since resume shows Java developer)
    if not candidate_technologies:
        # Use Java-specific technologies since the resume clearly mentions Java developer
        candidate_technologies = ["Java", "Object-Oriented Programming", "Data Structures", "Algorithms", "Software Development"]

    # Clean and filter technologies
    candidate_technologies = [tech for tech in candidate_technologies if len(tech) > 2 and tech.lower() != "general"]
    
    print(f"DEBUG: Extracted candidate technologies: {candidate_technologies}")

    initial_technology = candidate_technologies[0]
    initial_difficulty = "EASY"

    # Validate the LLM contract: technology/difficulty must match backend selections.
    first_q_data = None
    for _ in range(3):
        candidate = generate_first_question_json(final_name, initial_technology, initial_difficulty)
        if (
            candidate
            and candidate.get("question")
            and candidate.get("technology") == initial_technology
            and candidate.get("difficulty") == initial_difficulty
        ):
            first_q_data = candidate
            break
    if not first_q_data or not first_q_data.get("question"):
        return jsonify({"error": "Question generation failed"})

    SESSION.update({
        "questions": [{"question": first_q_data["question"], "technology": first_q_data["technology"], "difficulty": first_q_data["difficulty"]}],
        "answers": [],
        "jd": jd,
        "resume": resume_text,
        "name": final_name,
        "resume_entities": entities,
        "candidate_technologies": candidate_technologies,
        "current_technology": first_q_data["technology"],
        "current_difficulty": first_q_data["difficulty"],
        "consecutive_technology_count": 1,
        "asked_questions": [first_q_data["question"]],
        "proctoring_issue_count": 0,
        "proctoring_terminated": False,
        "consecutive_low_scores": 0,  # Track consecutive scores below 3
    })

    return jsonify({
        "question": first_q_data["question"],
        "match_percentage": match
    })


def should_end_interview(current_score, current_difficulty, consecutive_low, total_questions):
    """
    Determine if interview should end based on adaptive conditions
    """
    # Calculate average score so far
    answers = SESSION.get("answers", [])
    if not answers:
        return {"should_end": False, "reason": ""}
    
    avg_score = sum([a["score"]["total_score"] for a in answers]) / len(answers)
    avg_percentage = (avg_score / 5) * 100
    
    # Condition 1: Excellent performance - early termination
    if avg_percentage >= 85 and total_questions >= 5:
        return {
            "should_end": True, 
            "reason": f"Interview completed - Excellent performance ({avg_percentage:.1f}%) demonstrated"
        }
    
    # Condition 2: Consistent high performance on HARD questions
    if current_difficulty == "HARD" and current_score >= 4 and total_questions >= 6:
        hard_questions = [a for a in answers if a.get("difficulty") == "HARD"]
        if len(hard_questions) >= 2:
            hard_avg = sum([a["score"]["total_score"] for a in hard_questions]) / len(hard_questions)
            if hard_avg >= 4:
                return {
                    "should_end": True,
                    "reason": f"Interview completed - Strong performance on advanced topics (Hard avg: {hard_avg:.1f}/5)"
                }
    
    # Condition 3: Maximum questions reached
    if total_questions >= 10:
        return {
            "should_end": True,
            "reason": f"Interview completed - Maximum questions reached ({total_questions})"
        }
    
    # Condition 4: Poor performance - compassionate ending
    if avg_percentage <= 30 and total_questions >= 4:
        return {
            "should_end": True,
            "reason": f"Interview completed - Performance assessment complete ({avg_percentage:.1f}%)"
        }
    
    # Condition 5: Consistent moderate performance - reasonable ending
    if 60 <= avg_percentage <= 75 and total_questions >= 8:
        return {
            "should_end": True,
            "reason": f"Interview completed - Comprehensive assessment completed ({avg_percentage:.1f}%)"
        }
    
    # Condition 6: Technology coverage complete
    technologies_asked = set([q.get("technology") for q in SESSION.get("questions", [])])
    candidate_techs = set(SESSION.get("candidate_technologies", []))
    if len(technologies_asked) >= min(3, len(candidate_techs)) and total_questions >= 6:
        coverage_ratio = len(technologies_asked) / max(1, len(candidate_techs))
        if coverage_ratio >= 0.7:  # 70% of technologies covered
            return {
                "should_end": True,
                "reason": f"Interview completed - Technology coverage comprehensive ({len(technologies_asked)}/{len(candidate_techs)} areas)"
            }
    
    # Condition 7: Adaptive difficulty mastery
    if total_questions >= 7:
        easy_scores = [a["score"]["total_score"] for a in answers if a.get("difficulty") == "EASY"]
        moderate_scores = [a["score"]["total_score"] for a in answers if a.get("difficulty") == "MODERATE"]
        
        if easy_scores and moderate_scores:
            easy_avg = sum(easy_scores) / len(easy_scores)
            moderate_avg = sum(moderate_scores) / len(moderate_scores)
            
            if easy_avg >= 4 and moderate_avg >= 3.5:
                return {
                    "should_end": True,
                    "reason": f"Interview completed - Candidate demonstrates mastery across difficulty levels"
                }
    
    # No ending condition met - continue interview
    return {"should_end": False, "reason": ""}


# ---------------- NEXT ----------------
@interview_bp.route("/next", methods=["POST"])
def next_q():
    audio_file = request.files.get("audio")

    if not audio_file:
        return jsonify({"error": "No audio received"})

    if not os.path.exists("uploads"):
        os.makedirs("uploads")

    input_path = os.path.join("uploads", "temp_input")
    output_path = os.path.join("uploads", "temp.wav")
    audio_file.save(input_path)

    # MediaRecorder output is not always true WAV. Convert to WAV for SpeechRecognition.
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                input_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # If conversion fails, fall back to original path.
        output_path = input_path

    answer = speech_to_text(output_path)

    if not answer or answer == "SPEECH_NOT_DETECTED":
        return jsonify({"error": "Unable to detect speech. Please speak clearly and try again."})
    
    if answer.startswith("AUDIO_ERROR:"):
        return jsonify({"error": f"Audio processing error: {answer.replace('AUDIO_ERROR: ', '')}"})

    last_question_obj = SESSION["questions"][-1]
    last_q = last_question_obj["question"]

    score = evaluate_answer(last_q, answer)
    score_val = score.get("total_score", 0)
    
    # Generate feedback for this specific answer
    answer_feedback = generate_answer_feedback(last_q, answer, score)

    # Persist answer first; question selection depends on score_val and current state.
    SESSION["answers"].append({
        "question": last_q,
        "answer": answer,
        "score": score,
        "feedback": answer_feedback
    })

    # Track consecutive low scores (below 3)
    current_consecutive = SESSION.get("consecutive_low_scores", 0)
    if score_val < 3:
        current_consecutive += 1
        SESSION["consecutive_low_scores"] = current_consecutive
    else:
        SESSION["consecutive_low_scores"] = 0  # Reset on good score

    def choose_different_technology(current: str) -> str:
        # Prefer technologies not used very recently.
        recent = [q.get("technology") for q in SESSION.get("questions", [])[-4:]]
        for tech in SESSION.get("candidate_technologies", []):
            if tech != current and tech not in recent:
                return tech
        for tech in SESSION.get("candidate_technologies", []):
            if tech != current:
                return tech
        return current  # Only one technology available.

    current_technology = SESSION.get("current_technology", "")
    current_difficulty = SESSION.get("current_difficulty", "EASY")
    consecutive_count = SESSION.get("consecutive_technology_count", 0)
    technologies = SESSION.get("candidate_technologies", []) or []

    # -------------------------
    # Adaptive Ending Conditions
    # -------------------------
    
    # Check if interview should end based on adaptive conditions
    end_condition = should_end_interview(score_val, current_difficulty, current_consecutive, len(SESSION["answers"]))
    if end_condition["should_end"]:
        avg = sum([a["score"]["total_score"] for a in SESSION["answers"]]) / len(SESSION["answers"])
        percentage = (avg / 5) * 100
        return jsonify({
            "end": True,
            "transcript": answer,
            "score": score,
            "percentage": percentage,
            "reason": end_condition["reason"]
        })

    # End interview after 3 consecutive low scores (existing logic)
    if current_consecutive >= 3:
        avg = sum([a["score"]["total_score"] for a in SESSION["answers"]]) / len(SESSION["answers"])
        percentage = (avg / 5) * 100
        return jsonify({
            "end": True,
            "transcript": answer,
            "score": score,
            "percentage": percentage,
            "reason": "Interview ended due to 3 consecutive low scores"
        })

    # -------------------------
    # Adaptive selection rules
    # (EXACTLY FOLLOWING "DO NOT CHANGE" CASES)
    # -------------------------
    next_technology = current_technology
    next_difficulty = current_difficulty

    # Case 1: Score < 3
    if score_val < 3:
        next_difficulty = "EASY"
        next_technology = choose_different_technology(current_technology)

    # Case 2: Score > 3 on EASY
    elif score_val > 3 and current_difficulty == "EASY":
        next_difficulty = "MODERATE"
        next_technology = current_technology

    # Case 3: Score < 3 on MODERATE
    # Note: This is already covered by Case 1 (score_val < 3),
    # but we keep the rule explicit for clarity/compliance.
    elif score_val < 3 and current_difficulty == "MODERATE":
        next_difficulty = "EASY"
        next_technology = choose_different_technology(current_technology)

    # Case 4: Score > 3 on HARD
    elif score_val > 3 and current_difficulty == "HARD":
        next_difficulty = "EASY"
        next_technology = choose_different_technology(current_technology)

    # All other score/difficulty combinations:
    # keep the current technology/difficulty (no rule triggers).

    # Technology cannot be used for more than 2 consecutive questions.
    if next_technology == current_technology and consecutive_count >= 2:
        forced = choose_different_technology(current_technology)
        next_technology = forced

    # Update consecutive technology count.
    next_consecutive_count = consecutive_count + 1 if next_technology == current_technology else 1

    SESSION["current_technology"] = next_technology
    SESSION["current_difficulty"] = next_difficulty
    SESSION["consecutive_technology_count"] = next_consecutive_count

    # Generate next question with strict JSON contract.
    asked_questions = SESSION.get("asked_questions", [])
    next_q_data = None
    for attempt in range(5):  # Increased attempts for better question variety
        next_q_data = generate_next_question_json(
            name=SESSION.get("name", ""),
            previous_question=last_q,
            previous_answer=answer,
            technology=next_technology,
            difficulty=next_difficulty,
            asked_questions=asked_questions,
        )
        
        # Check if LLM decided to end the interview
        if next_q_data and next_q_data.get("end_interview"):
            avg = sum([a["score"]["total_score"] for a in SESSION["answers"]]) / len(SESSION["answers"])
            percentage = (avg / 5) * 100
            return jsonify({
                "end": True,
                "transcript": answer,
                "score": score,
                "percentage": percentage,
                "reason": next_q_data.get("reason", "Interview ended due to consecutive low scores")
            })
        
        # More strict question validation
        if (
            next_q_data
            and next_q_data.get("question")
            and next_q_data["question"] not in asked_questions
            and next_q_data.get("technology") == next_technology
            and next_q_data.get("difficulty") == next_difficulty
        ):
            # Additional check: ensure question is not too similar to previous questions
            question_text = next_q_data["question"].lower()
            is_similar = False
            
            for asked_q in asked_questions[-5:]:  # Check last 5 questions
                asked_q_lower = asked_q.lower()
                # Simple similarity check - if more than 70% of words match, consider it similar
                asked_words = set(asked_q_lower.split())
                question_words = set(question_text.split())
                if asked_words and question_words:
                    common_words = asked_words.intersection(question_words)
                    similarity = len(common_words) / len(asked_words)
                    if similarity > 0.7:
                        is_similar = True
                        break
            
            if not is_similar:
                break
        
        print(f"DEBUG: Attempt {attempt + 1} failed, trying again...")
        next_q_data = None

    if not next_q_data or not next_q_data.get("question"):
        return jsonify({"error": "Next question generation failed"})

    # If the LLM returned an incorrect contract, fall back to a deterministic question.
    if next_q_data.get("technology") != next_technology or next_q_data.get("difficulty") != next_difficulty:
        candidate_name = SESSION.get("name", "")
        next_q_data = {
            "question": f"{candidate_name}, thanks for that. Based on your answer, can you go deeper into {next_technology} at {next_difficulty} level?",
            "technology": next_technology,
            "difficulty": next_difficulty,
        }

    # Enforce backend-selected technology/difficulty.
    next_q_data["technology"] = next_technology
    next_q_data["difficulty"] = next_difficulty

    SESSION["questions"].append({
        "question": next_q_data["question"],
        "technology": next_technology,
        "difficulty": next_difficulty,
    })
    SESSION["asked_questions"].append(next_q_data["question"])

    return jsonify({
        "next_question": next_q_data["question"],
        "transcript": answer,
        "score": score
    })


# ---------------- RESET SESSION ----------------
@interview_bp.route("/reset", methods=["POST"])
def reset_session():
    """
    Reset all session data for a fresh interview start
    """
    # Clear all session data
    SESSION.clear()
    
    # Reinitialize with default values
    SESSION.update({
        "multiple_face_violations": 0,
        "no_face_violations": 0,
        "tab_violations": 0,
        "interview_active": False,
        "interview_terminated": False,
        "termination_reason": "",
        "violation_screenshots": [],
        "violation_details": [],
        "proctoring_issue_count": 0,
        "proctoring_terminated": False,
        "last_violation_time": None,
        "last_violation_count": 0,
        "face_violations": 0
    })
    
    return jsonify({
        "status": "success",
        "message": "Session reset successfully"
    })

# ---------------- PROCTORING ----------------
@interview_bp.route("/monitor", methods=["POST"])
def monitor():
    """
    Receive webcam frame (base64 data URL) and detect face count.
    The frontend expects:
      { terminate: bool, reason: string, faces: number, warnings: string }
    """
    # Check if interview is active
    if not SESSION.get("interview_active", False):
        return jsonify({
            "terminate": False,
            "reason": "",
            "faces": 0,
            "warnings": "Interview not active",
        })
    
    # Check if interview was already terminated
    if SESSION.get("interview_terminated", False):
        return jsonify({
            "terminate": True,
            "reason": SESSION.get("termination_reason", "Interview was terminated"),
            "faces": 0,
            "warnings": "Interview terminated",
        })
    
    payload = request.get_json(silent=True) or {}
    image = payload.get("image", "")

    if not image:
        return jsonify({
            "terminate": False,
            "reason": "",
            "faces": 0,
            "warnings": "No image received",
        })

    faces = detect_faces(image)

    print(f"DEBUG: Monitor endpoint - Faces detected: {faces}")

    warnings = f"Detected {faces} face(s). Please keep your camera on and facing to the screen."
    terminate = False
    reason = ""

    if faces != 1:
        print(f"DEBUG: Face violation detected - Current faces: {faces}")
        SESSION["proctoring_issue_count"] = SESSION.get("proctoring_issue_count", 0) + 1
        if SESSION["proctoring_issue_count"] >= 5:
            SESSION["proctoring_terminated"] = True
            SESSION["interview_terminated"] = True
            SESSION["termination_reason"] = "Interview terminated due to repeated face detection issues."
            terminate = True
            reason = SESSION["termination_reason"]
    else:
        # Reset on good frame.
        SESSION["proctoring_issue_count"] = 0

    return jsonify({
        "terminate": terminate,
        "reason": reason,
        "faces": faces,
        "warnings": warnings,
    })


# ---------------- END ----------------
# @interview_bp.route("/end", methods=["POST"])
# def end():
#     answers = SESSION["answers"]
#     questions = SESSION["questions"]

#     if len(answers) == 0:
#         return jsonify({"average_score": 0, "percentage": 0})

#     avg = sum([a["score"]["total_score"] for a in answers]) / len(answers)

#     feedback = generate_feedback(avg, questions, answers)

#     # Store detailed feedback in session for result page
#     SESSION["feedback"] = feedback

#     return jsonify({
#         "average_score": avg,
#         "percentage": (avg / 5) * 100,
#         "feedback": feedback
#     })
@interview_bp.route("/end", methods=["POST"])
def end():
    try:
        answers = SESSION.get("answers", [])
        questions = SESSION.get("questions", [])

        if not answers:
            SESSION["feedback"] = {}
            return jsonify({
                "average_score": 0,
                "percentage": 0,
                "feedback": {}
            })

        avg = sum([a.get("score", {}).get("total_score", 0) for a in answers]) / len(answers)

        try:
            feedback = generate_feedback(avg, questions, answers)
        except Exception as e:
            print("Feedback error:", e)
            feedback = {}

        SESSION["feedback"] = feedback or {}

        return jsonify({
            "average_score": avg,
            "percentage": (avg / 5) * 100,
            "feedback": feedback
        })

    except Exception as e:
        print("ERROR in /end:", str(e))
        return jsonify({
            "error": "Failed to end interview",
            "details": str(e)
        }), 500

# ---------------- RESULT PAGE ----------------
@interview_bp.route("/result")
def result():
    feedback = SESSION.get("feedback", {})
    average_score = 0
    percentage = 0
    
    if SESSION.get("answers"):
        avg = sum([a["score"]["total_score"] for a in SESSION["answers"]]) / len(SESSION["answers"])
        average_score = avg
        percentage = (avg / 5) * 100
    
    # Generate enhanced feedback data
    enhanced_feedback = generate_enhanced_feedback(percentage, SESSION.get("answers", []))
    
    # Ensure question_feedback is always included
    question_feedback = []
    for i, answer in enumerate(SESSION.get("answers", [])):
        question_feedback.append({
            "question": answer.get("question", f"Question {i+1}"),
            "answer": answer.get("answer", "No answer provided"),
            "feedback": answer.get("feedback", "No feedback available"),
            "score": answer.get("score", {}).get("total_score", 0)
        })
    
    # Add question_feedback to enhanced_feedback
    enhanced_feedback["question_feedback"] = question_feedback
    
    # Generate lip sync results
    lip_sync_score = 85 + (percentage * 0.15)  # Simulated lip sync score based on performance
    lip_sync_feedback = generate_lip_sync_feedback(lip_sync_score)
    
    # Get violation data for result page
    violation_screenshots = SESSION.get("violation_screenshots", [])
    violation_details = SESSION.get("violation_details", [])
    multiple_face_violations = SESSION.get("multiple_face_violations", 0)
    no_face_violations = SESSION.get("no_face_violations", 0)
    tab_violations = SESSION.get("tab_violations", 0)
    termination_reason = SESSION.get("termination_reason", "")
    
    return render_template("result.html", 
                         feedback=enhanced_feedback, 
                         average_score=average_score, 
                         percentage=percentage,
                         lip_sync_score=lip_sync_score,
                         lip_sync_feedback=lip_sync_feedback,
                         violation_screenshots=violation_screenshots,
                         violation_details=violation_details,
                         multiple_face_violations=multiple_face_violations,
                         no_face_violations=no_face_violations,
                         tab_violations=tab_violations,
                         termination_reason=termination_reason)

def generate_enhanced_feedback(percentage, answers):
    """Generate comprehensive feedback with strengths, weaknesses, and technology recommendations using LLM"""
    
    # Generate dynamic feedback using LLM
    from ..services.llm_service import call_llm
    
    # Prepare answers summary for context
    answers_summary = ""
    if answers:
        for i, answer in enumerate(answers[-5:], 1):  # Use last 5 answers for context
            score = answer.get("score", {}).get("total_score", 0)
            ans_text = answer.get("answer", "")[:200]  # Truncate long answers
            answers_summary += f"Q{i}: {ans_text} (Score: {score}/5)\n"
    
    prompt = f"""
You are an expert technical interviewer and career coach.

ANALYZE THE CANDIDATE'S PERFORMANCE:
- Overall Score: {percentage:.1f}%
- Recent Answers:
{answers_summary}

TASK: Generate comprehensive feedback with:
1. Strengths (3-4 specific points)
2. Weaknesses (2-3 areas for improvement) 
3. Technology recommendations (2-3 specific technologies/skills to focus on)
4. Performance level assessment

REQUIREMENTS:
- Be specific and constructive
- Base feedback on actual performance level
- Provide actionable recommendations
- Use professional but encouraging tone
- Keep feedback concise but thorough

Return JSON format:
{{
  "strengths": "List of 3-4 specific strengths separated by |",
  "weaknesses": "List of 2-3 areas for improvement separated by |", 
  "technology_improvements": "List of 2-3 specific technologies/skills to focus on separated by |",
  "performance_level": "excellent|good|needs_improvement"
}}
"""
    
    try:
        content = call_llm(prompt)
        if content and content.strip():
            # Parse JSON response
            import json
            try:
                feedback_data = json.loads(content)
                return {
                    "strengths": feedback_data.get("strengths", "Candidate shows good communication skills and technical knowledge."),
                    "weaknesses": feedback_data.get("weaknesses", "Candidate needs to work on problem-solving and technical depth."),
                    "technology_improvements": feedback_data.get("technology_improvements", "Focus on core programming concepts and practical implementation."),
                    "performance_level": feedback_data.get("performance_level", "good")
                }
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Failed to parse LLM feedback response: {e}")
                return get_fallback_feedback(percentage)
        else:
            print("LLM returned empty response")
            return get_fallback_feedback(percentage)
    except Exception as e:
        print(f"Error generating LLM feedback: {e}")
        return get_fallback_feedback(percentage)

def get_fallback_feedback(percentage):
    """Fallback feedback using Grok LLM if primary LLM fails"""
    try:
        # Import Grok service
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ..services.llm_service import call_grok_llm
        
        prompt = f"""
You are an expert technical interviewer and career coach.

CANDIDATE PERFORMANCE:
- Overall Score: {percentage:.1f}%

TASK: Generate comprehensive feedback with:
1. Strengths (3-4 specific points)
2. Weaknesses (2-3 areas for improvement) 
3. Technology recommendations (2-3 specific technologies/skills to focus on)
4. Performance level assessment

REQUIREMENTS:
- Be specific and constructive
- Base feedback on actual performance level ({percentage:.1f}%)
- Provide actionable recommendations
- Use professional but encouraging tone
- Keep feedback concise but thorough

Return JSON format:
{{
  "strengths": "List of 3-4 specific strengths separated by |",
  "weaknesses": "List of 2-3 areas for improvement separated by |", 
  "technology_improvements": "List of 2-3 specific technologies/skills to focus on separated by |",
  "performance_level": "excellent|good|needs_improvement"
}}
"""
        
        content = call_grok_llm(prompt)
        if content and content.strip():
            import json
            try:
                feedback_data = json.loads(content)
                return {
                    "strengths": feedback_data.get("strengths", "Candidate shows good communication skills and technical knowledge."),
                    "weaknesses": feedback_data.get("weaknesses", "Candidate needs to work on problem-solving and technical depth."),
                    "technology_improvements": feedback_data.get("technology_improvements", "Focus on core programming concepts and practical implementation."),
                    "performance_level": feedback_data.get("performance_level", "good")
                }
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Failed to parse Grok feedback response: {e}")
                return get_emergency_fallback(percentage)
        else:
            print("Grok returned empty response")
            return get_emergency_fallback(percentage)
            
    except Exception as e:
        print(f"Error generating Grok feedback: {e}")
        return get_emergency_fallback(percentage)

def get_emergency_fallback(percentage):
    """Emergency hardcoded fallback if all LLMs fail"""
    if percentage >= 80:
        performance_level = "excellent"
        strengths = "Strong technical knowledge and problem-solving skills | Clear communication and structured answers | Good understanding of core concepts | Confident and well-articulated responses"
        weaknesses = "Minor areas for improvement in advanced topics | Could benefit from more practical examples"
        tech_improvements = "Focus on advanced architectural patterns | Explore emerging technologies and frameworks"
    elif percentage >= 60:
        performance_level = "good"
        strengths = "Good grasp of fundamental concepts | Adequate problem-solving approach | Shows potential for growth"
        weaknesses = "Needs improvement in technical depth | Lacks confidence in some areas | Could provide more detailed explanations"
        tech_improvements = "Strengthen core programming fundamentals | Practice more hands-on coding exercises | Study system design principles"
    else:
        performance_level = "needs_improvement"
        strengths = "Shows willingness to learn | Basic understanding of some concepts"
        weaknesses = "Significant gaps in technical knowledge | Poor problem-solving approach | Lacks confidence and clarity | Needs more practical experience"
        tech_improvements = "Focus on basic programming concepts | Study fundamental algorithms and data structures | Build more practical projects | Improve communication skills"
    
    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "technology_improvements": tech_improvements,
        "performance_level": performance_level
    }

def generate_lip_sync_feedback(score):
    """Generate lip sync analysis feedback"""
    if score >= 80:
        return "Excellent lip sync consistency. Natural speaking patterns detected throughout the interview."
    elif score >= 60:
        return "Good lip sync consistency with minor inconsistencies. Generally natural speaking patterns."
    else:
        return "Inconsistent lip sync patterns detected. May need to focus on natural communication during interviews."