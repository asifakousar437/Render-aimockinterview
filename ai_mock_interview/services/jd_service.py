import json
import re

# Use absolute imports for consistency
from ai_mock_interview.llm_service import call_llm

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,3}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}")

_SECTION_PATTERNS = {
    "skills": [r"\bskills\b", r"\btechnical\s+skills\b", r"\bcompetencies\b"],
    "projects": [r"\bprojects?\b", r"\bproject\s+experience\b"],
    "experience": [r"\bexperience\b", r"\bwork\s+experience\b", r"\bemployment\b"],
    "education": [r"\beducation\b", r"\bacademics\b"],
    "certifications": [r"\bcertifications?\b", r"\bcertificates?\b"],
    "contact": [r"\bcontact\b", r"\blinkedin\.com\b", r"\bportfolio\b"],
}


def _has_contact_info(text: str) -> bool:
    return bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text) or re.search(r"linkedin\.com", text, re.IGNORECASE))


def is_resume(text: str) -> bool:
    """
    Heuristic + (fallback) LLM classification to decide whether text resembles a resume.
    """
    t = text or ""
    t_l = t.lower()

    # Count how many major resume sections we can find.
    sections_hits = 0
    for key in ["skills", "projects", "experience", "education", "certifications"]:
        if any(re.search(pat, t_l, re.IGNORECASE) for pat in _SECTION_PATTERNS[key]):
            sections_hits += 1

    contact_hit = _has_contact_info(t)

    # Strong heuristic signal.
    if sections_hits >= 3:
        return True
    if sections_hits >= 2 and contact_hit:
        return True

    # Fallback: ask the LLM to decide.
    snippet = t[:3000]
    prompt = (
        "You are a document classifier.\n"
        "Decide whether the following text is a RESUME/CV.\n"
        "Resume indicators: Skills, Projects, Experience, Education, Certifications, Contact information (email/phone/LinkedIn).\n"
        "Answer with exactly YES or NO.\n\n"
        f"TEXT:\n{snippet}"
    )
    resp = call_llm(prompt) or ""
    resp = resp.strip().upper()
    return resp.startswith("YES")


def extract_candidate_name(resume_text: str) -> str:
    """
    Extract candidate name from the resume.
    Uses heuristics first; falls back to LLM if needed.
    """
    t = resume_text or ""
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    print(f"DEBUG: First 10 lines of resume: {lines[:10]}")
    
    # Common job titles to exclude
    job_titles = {
        'developer', 'engineer', 'manager', 'analyst', 'designer', 'consultant',
        'specialist', 'coordinator', 'administrator', 'director', 'lead',
        'senior', 'junior', 'full stack', 'backend', 'frontend', 'software',
        'web', 'mobile', 'data', 'system', 'network', 'security'
    }
    
    # Prefer top-of-document candidates - look for actual names first
    for ln in lines[:25]:
        if _EMAIL_RE.search(ln) or _PHONE_RE.search(ln):
            continue
            
        # Skip lines with job titles
        line_lower = ln.lower()
        if any(title in line_lower for title in job_titles):
            print(f"DEBUG: Skipping line with job title: '{ln}'")
            continue
            
        # Skip section headers
        if any(header in line_lower for header in ['contact', 'summary', 'objective', 'experience', 'education', 'skills']):
            print(f"DEBUG: Skipping section header: '{ln}'")
            continue
            
        # A more strict "name-ish" pattern: 2-4 words, letters/spaces/punctuation, no numbers
        # Look for ALL CAPS names first (common in resume headers)
        if len(ln) <= 60 and re.fullmatch(r"[A-Za-z][A-Za-z.\' -]*(?:\s+[A-Za-z][A-Za-z.\' -]*){1,3}", ln):
            if len(re.findall(r"[A-Za-z]", ln)) >= 3:  # Reduced from 6 to catch shorter names
                # Priority 1: ALL CAPS names (like "ASIFA")
                if ln.isupper() and len(ln.split()) <= 2:
                    print(f"DEBUG: Found ALL CAPS name: '{ln}'")
                    return ln
                # Priority 2: Proper case names (like "John Smith")
                elif any(c.isupper() for c in ln.split()[0] if ln.split()):
                    print(f"DEBUG: Found proper case name: '{ln}'")
                    return ln

    # Fallback to LLM.
    snippet = t[:4000]
    print(f"DEBUG: Using LLM fallback for name extraction")
    prompt = (
        "Extract the candidate's full name from the resume.\n"
        "Look for the person's actual name (like 'John Smith' or 'ASIFA'), NOT their job title.\n"
        "Names are usually at the top of the resume and may be in ALL CAPS.\n"
        "Return ONLY the name string (no quotes, no additional text).\n\n"
        f"RESUME:\n{snippet}"
    )
    resp = call_llm(prompt) or ""
    resp = resp.strip().splitlines()[0].strip()
    print(f"DEBUG: LLM response for name: '{resp}'")
    # Basic cleanup.
    resp = re.sub(r"[^A-Za-z.\' -]", "", resp).strip()
    result = resp[:60] if resp else ""
    print(f"DEBUG: Final extracted name: '{result}'")
    return result


def _extract_resume_entities(resume_text: str) -> dict:
    """
    Extract skills, projects, certifications from the resume.
    Returns a dict with keys: skills, projects, certifications.
    """
    text = resume_text or ""

    # ---------- Heuristic extraction (fast, offline, reliable) ----------
    # If the LLM call fails, we still want match_score to work.
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    lower_lines = [ln.lower() for ln in lines]

    section_header_indices = {k: [] for k in ["skills", "projects", "certifications", "experience", "education"]}

    def _looks_like_header(original_line: str, line_l: str) -> bool:
        # Header lines are typically short and have no sentence-like punctuation.
        if len(original_line) > 45:
            return False
        word_count = len(original_line.split())
        if word_count > 6:
            return False
        if line_l.endswith(":"):
            return True
        # e.g. "SKILLS", "EDUCATION"
        if original_line.isupper():
            return True
        # e.g. "PROJECT EXPERIENCE." / "CAREER SUMMARY."
        if re.fullmatch(r"[A-Za-z\\s]+\\.?[A-Za-z\\s]*\\.?", original_line):
            return True
        return False

    for idx, ln_l in enumerate(lower_lines):
        original_line = lines[idx]
        for key in section_header_indices.keys():
            if any(re.search(pat, ln_l, re.IGNORECASE) for pat in _SECTION_PATTERNS.get(key, [])) and _looks_like_header(
                original_line, ln_l
            ):
                section_header_indices[key].append(idx)

    # Union of known section headers: stop capturing when any of these appears.
    all_header_pats = []
    for pats in _SECTION_PATTERNS.values():
        all_header_pats.extend(pats)

    def _is_any_header(idx: int) -> bool:
        original_line = lines[idx]
        line_l = lower_lines[idx]
        if not _looks_like_header(original_line, line_l):
            return False
        return any(re.search(pat, line_l, re.IGNORECASE) for pat in all_header_pats)

    def _capture_section_lines(start_idx: int) -> list[str]:
        end_idx = len(lines)
        for j in range(start_idx + 1, len(lines)):
            if _is_any_header(j):
                end_idx = j
                break
        return lines[start_idx + 1 : end_idx]

    def _clean_bullet(s: str) -> str:
        s2 = s.strip()
        while s2 and s2[0] in ["-", "*", "•", "·"]:
            s2 = s2[1:].strip()
        return s2

    def _heuristic_extract_skills(section_lines: list[str]) -> list[str]:
        joined = " | ".join([ln.replace("•", "-") for ln in section_lines])
        # Split on common separators.
        parts = re.split(r"[,\u2022;|/]\s*|\s+\|\s+|\s+-\s+", joined)
        skills = []
        seen = set()
        for p in parts:
            item = _clean_bullet(p)
            item_l = item.lower()
            if not item or item_l in seen:
                continue
            # Keep only plausible short tech phrases.
            if len(item) < 2 or len(item) > 50:
                continue
            if not re.search(r"[a-zA-Z]", item):
                continue
            # Avoid catching long sentences.
            if len(item.split()) > 6:
                continue
            skills.append(item)
            seen.add(item_l)
            if len(skills) >= 15:
                break
        return skills

    def _heuristic_extract_projects(section_lines: list[str]) -> list[str]:
        projects = []
        for ln in section_lines:
            item = _clean_bullet(ln)
            if not item:
                continue
            if len(item) < 8:
                continue
            # Avoid swallowing whole paragraphs.
            if len(item) > 160:
                item = item[:160].strip()
            projects.append(item)
            if len(projects) >= 5:
                break
        return projects

    def _heuristic_extract_certs(section_lines: list[str]) -> list[str]:
        certs = []
        seen = set()
        for ln in section_lines:
            item = _clean_bullet(ln)
            if not item:
                continue
            if len(item) < 5:
                continue
            item_l = item.lower()
            if item_l in seen:
                continue
            # Split if a line contains multiple certs.
            subparts = re.split(r"[,;]\s*", item)
            for sp in subparts:
                sp2 = _clean_bullet(sp)
                if not sp2 or sp2.lower() in seen:
                    continue
                if len(certs) >= 8:
                    return certs
                certs.append(sp2)
                seen.add(sp2.lower())
        return certs

    skills_section = section_header_indices["skills"][0] if section_header_indices["skills"] else None
    projects_section = section_header_indices["projects"][0] if section_header_indices["projects"] else None
    certs_section = section_header_indices["certifications"][0] if section_header_indices["certifications"] else None

    skills = _heuristic_extract_skills(_capture_section_lines(skills_section)) if skills_section is not None else []
    projects = _heuristic_extract_projects(_capture_section_lines(projects_section)) if projects_section is not None else []
    certifications = _heuristic_extract_certs(_capture_section_lines(certs_section)) if certs_section is not None else []

    # If heuristics found anything, use it.
    if skills or projects or certifications:
        return {"skills": skills, "projects": projects, "certifications": certifications}

    # ---------- LLM fallback extraction ------
    # ----
    snippet = text[:8000]
    prompt = (
        "Extract the following from the resume text.\n"
        "- skills: short tech skill phrases (max 15)\n"
        "- projects: short project descriptions (max 5)\n"
        "- certifications: certification names (max 8)\n\n"
        "Return ONLY valid JSON with keys: skills, projects, certifications.\n"
        "If unknown, use empty arrays.\n\n"
        f"RESUME:\n{snippet}"
    )
    content = call_llm(prompt) or ""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {"skills": [], "projects": [], "certifications": []}

    try:
        data = json.loads(match.group())
        return {
            "skills": data.get("skills") or [],
            "projects": data.get("projects") or [],
            "certifications": data.get("certifications") or [],
        }
    except Exception:
        return {"skills": [], "projects": [], "certifications": []}


def _item_matches_jd(jd_lower: str, item: str) -> bool:
    if not item:
        return False
    s = item.strip().lower()
    if not s:
        return False

    # Direct substring match first
    if s in jd_lower:
        return True

    # Token overlap as a fallback with more lenient matching
    tokens = [tok for tok in re.split(r"[\W_]+", s) if len(tok) >= 2]
    if not tokens:
        return False

    # Check if any token appears in JD
    for token in tokens:
        if token in jd_lower:
            return True
    
    # Partial matching for multi-word terms
    if len(tokens) >= 2:
        # Check if consecutive tokens appear together in JD
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i+1]}"
            if bigram in jd_lower:
                return True
    
    # Fallback: check if at least 35% of tokens match (reduced from 0.35 to 0.25)
    hit_count = sum(1 for tok in tokens if tok in jd_lower)
    ratio = hit_count / max(1, len(tokens))
    return ratio >= 0.25  # Reduced threshold for better matching


def extract_resume_entities(resume_text: str) -> dict:
    return _extract_resume_entities(resume_text)


def match_score(jd: str, resume: str, entities: dict | None = None) -> int:
    """
    Compute match percentage (0-100) using Grok LLM for intelligent matching.
    """
    jd_text = jd or ""
    resume_text = resume or ""
    
    print(f"DEBUG: Using Grok LLM for JD-Resume matching")
    print(f"DEBUG: JD text length: {len(jd_text)}")
    print(f"DEBUG: Resume text length: {len(resume_text)}")

    # Use Grok LLM to evaluate match
    prompt = f"""
You are an expert HR recruiter evaluating how well a candidate's resume matches a job description.

JOB DESCRIPTION:
{jd_text[:2000]}

RESUME:
{resume_text[:2000]}

TASK:
Evaluate the match between this job description and resume on a scale of 0-100%.

Consider:
1. **Skills Match**: How many required skills are present in resume
2. **Experience Alignment**: Does experience level match job requirements
3. **Project Relevance**: Are projects relevant to job role
4. **Certifications**: Are certifications relevant and current
5. **Overall Fit**: General suitability for the position

SCORING GUIDELINES:
- 90-100: Excellent match - strong candidate
- 75-89: Good match - qualified candidate  
- 50-74: Moderate match - some gaps
- 25-49: Poor match - significant gaps
- 0-24: Very poor match - not suitable

Return ONLY a single number (0-100) representing the match percentage.
No explanations, no text, just the number.
"""

    try:
    from ai_mock_interview.llm_service import call_llm
except ImportError:
    from llm_service import call_llm
    
    llm_response = call_llm(prompt)
    
    if llm_response:
        # Extract number from response
        import re
        numbers = re.findall(r'\b(\d{1,3})\b', llm_response)
        if numbers:
            score = int(numbers[0])
            # Ensure score is within valid range
            score = max(0, min(100, score))
            print(f"DEBUG: Grok LLM match score: {score}%")
            return score
    
    print("DEBUG: Grok LLM matching failed, using fallback")
    
except Exception as e:
    print(f"DEBUG: LLM matching error: {e}")

# Fallback to heuristic matching if LLM fails
print("DEBUG: Falling back to heuristic matching")
return _heuristic_match_score(jd_text, resume_text, entities)


def _heuristic_match_score(jd: str, resume: str, entities: dict | None = None) -> int:
    """
    Enhanced fallback heuristic matching if LLM fails.
    """
    jd_lower = jd.lower()
    
    entities = entities if entities is not None else _extract_resume_entities(resume or "")
    skills = [s for s in (entities.get("skills") or []) if isinstance(s, str) and s.strip()]
    projects = [p for p in (entities.get("projects") or []) if isinstance(p, str) and p.strip()]
    certifications = [c for c in (entities.get("certifications") or []) if isinstance(c, str) and c.strip()]

    parts = []
    weights = {"skills": 0.5, "projects": 0.3, "certifications": 0.2}  # Adjusted weights for better balance

    def ratio(items):
        if not items:
            return None
        matched = sum(1 for it in items if _item_matches_jd(jd_lower, it))
        return matched / max(1, len(items))

    r_skills = ratio(skills)
    r_projects = ratio(projects)
    r_certs = ratio(certifications)

    # Add bonus points for exact matches
    def exact_match_bonus(items):
        if not items:
            return 0
        exact_matches = sum(1 for it in items if it.lower() in jd_lower)
        return (exact_matches / max(1, len(items))) * 0.1  # 10% bonus for exact matches

    if r_skills is not None:
        skill_bonus = exact_match_bonus(skills)
        parts.append(r_skills * weights["skills"] + skill_bonus)
    if r_projects is not None:
        project_bonus = exact_match_bonus(projects)
        parts.append(r_projects * weights["projects"] + project_bonus)
    if r_certs is not None:
        cert_bonus = exact_match_bonus(certifications)
        parts.append(r_certs * weights["certifications"] + cert_bonus)

    # Add overall text similarity bonus
    def text_similarity_bonus():
        jd_words = set(re.findall(r'\b\w+\b', jd_lower))
        resume_words = set(re.findall(r'\b\w+\b', resume.lower()))
        if not jd_words or not resume_words:
            return 0
        common_words = jd_words.intersection(resume_words)
        similarity = len(common_words) / len(jd_words)
        return similarity * 0.05  # 5% bonus for text similarity

    parts.append(text_similarity_bonus())

    included_weight = 0.0
    if skills:
        included_weight += weights["skills"]
    if projects:
        included_weight += weights["projects"]
    if certifications:
        included_weight += weights["certifications"]
    
    # Always include text similarity in weight
    included_weight += 0.05

    if included_weight <= 0:
        return 0

    score_01 = sum(parts) / included_weight  # 0..1
    score = int(round(max(0.0, min(1.0, score_01)) * 100))
    print(f"DEBUG: Enhanced heuristic fallback score: {score}%")
    
    # Safe debug logging without formatting None values
    skills_str = f"{r_skills:.2f}" if r_skills is not None else "N/A"
    projects_str = f"{r_projects:.2f}" if r_projects is not None else "N/A"
    certs_str = f"{r_certs:.2f}" if r_certs is not None else "N/A"
    print(f"DEBUG: Skills match: {skills_str}, Projects match: {projects_str}, Certs match: {certs_str}")
    
    return score