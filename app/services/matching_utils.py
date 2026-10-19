import re

SKILL_ALIASES = {
    "python": ["python"],
    "java": ["java"],
    "sql": ["sql"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "git": ["git"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "django": ["django"],
    "fastapi": ["fastapi", "fast api"],
    "spring boot": ["spring boot", "springboot"],
    "react": ["react", "react.js", "reactjs"],
    "c#": ["c#", "c-sharp", "c sharp", "csharp"],
    "c++": ["c++", "cpp", "c plus plus"],
    ".net": [".net", "dotnet", "dot-net", ".net core"],
    "node.js": ["node.js", "nodejs", "node"],
    "next.js": ["next.js", "nextjs", "next"],
    "vue.js": ["vue.js", "vuejs", "vue"],
    "postgresql": ["postgresql", "postgres"],
    "typescript": ["typescript", "ts"],
    "javascript": ["javascript", "modern javascript", "javascript es6", "js"],
    "golang": ["go", "golang"],
    "firebase": ["firebase"],
    "firestore": ["firestore"],
    "gmail api": ["gmail api", "gmail"],
    "outlook api": ["outlook api", "outlook"],
    "redux": ["redux"],
    "redis": ["redis"],
    "kubernetes": ["kubernetes", "k8s"],
    "docker": ["docker"],
    "rest apis": ["rest api", "rest apis", "restful api", "restful apis"],
    "jwt": ["jwt", "json web token"]
}
SKILL_ALIASES.update({skill: [skill] for skill in ("mongodb", "jest", "graphql", "flutter")})


def extract_known_requirements(jd: str) -> dict:
    """Anchor known technologies to actual JD sentences and explicit priorities.

    This is a supplement to model extraction, not an exhaustive skill catalogue.
    Section labels outrank mentions in responsibility/background paragraphs.
    """
    result = {}
    scores = {}
    section = None
    for line in jd.splitlines():
        line = line.strip()
        heading = line.rstrip(':').lower()
        if heading in ('required technical skills', 'required skills', 'requirements'):
            section = 'required'
            continue
        if heading in ('preferred technical skills', 'preferred skills', 'nice to have'):
            section = 'preferred'
            continue
        if heading in ('additional information', 'responsibilities', 'about the role'):
            section = None
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', line):
            sentence = re.sub(r'^[-•]\s*', '', sentence).strip()
            for skill, aliases in SKILL_ALIASES.items():
                # Short shorthand can also be ordinary prose (e.g. "go", "next").
                aliases = [alias for alias in aliases if alias not in ('go', 'next', 'node', 'ts', 'js', 'gmail', 'outlook', 'vue')]
                if not any(re.search(r'(?<![a-zA-Z0-9])' + re.escape(alias) + r'(?![a-zA-Z0-9])', sentence, re.I) for alias in aliases):
                    continue
                priority, score = 'unspecified', 0
                if section:
                    priority, score = section, 2
                if re.search(r'\b(?:not required|not necessary)\b', sentence, re.I):
                    priority, score = 'not_required', 3
                elif re.search(r'\b(?:preferred|nice[- ]to[- ]have|optional)\b', sentence, re.I):
                    priority, score = 'preferred', 3
                elif re.search(r'\b(?:required|must have|essential)\b', sentence, re.I):
                    priority, score = 'required', 3
                if skill not in result or score > scores[skill]:
                    result[skill] = {'skill': skill, 'priority': priority, 'evidence': sentence}
                    scores[skill] = score
    return result

def normalize_skill(skill: str) -> str:
    s = re.sub(r"\s+", " ", skill.strip().lower())
    for canonical, aliases in SKILL_ALIASES.items():
        if s in aliases:
            return canonical
    return s

def find_skill_in_text(skill: str, text: str):
    canonical = normalize_skill(skill)
    aliases = SKILL_ALIASES.get(canonical, [canonical])
    text_lower = text.lower()
    
    for alias in aliases:
        escaped = re.escape(alias)
        pattern = r"(?<![a-zA-Z0-9])" + escaped + r"(?![a-zA-Z0-9])"
        match = re.search(pattern, text_lower)
        if match:
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            return text[start:end].replace('\n', ' ')
    return None
