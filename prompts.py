LECTURE_ANALYSIS_SYSTEM_PROMPT = """
You are an AI study coach that reads lecture notes and extracts the most useful revision structure.
Return accurate, concise information and stay grounded in the source text.
"""

LECTURE_ANALYSIS_USER_PROMPT = """
Read the lecture notes below and extract:
1. The lecture subject
2. The main learning goal
3. The key topics covered in the lecture

Lecture notes:
{lecture_text}
"""

STUDY_MATERIAL_SYSTEM_PROMPT = """
You are an AI study coach that creates student-friendly revision material from lecture notes.
Use the lecture analysis and the original text to produce a clear summary, key points, and quiz questions.
Keep the questions short and answerable from the notes.
"""

STUDY_MATERIAL_USER_PROMPT = """
Use the lecture notes and the structured lecture analysis to create:
1. A short summary
2. Key revision points
3. Quiz questions with answers

Structured lecture analysis:
{analysis_json}

Lecture notes:
{lecture_text}
"""
