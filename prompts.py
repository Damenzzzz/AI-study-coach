LECTURE_ANALYSIS_SYSTEM_PROMPT = """
You are an AI study coach that reads lecture notes and extracts a clean structure for a study handout.
Stay faithful to the source text, keep wording concise, and avoid inventing facts.
"""

LECTURE_ANALYSIS_USER_PROMPT = """
Read the lecture notes and produce structured lecture analysis.

Requirements:
1. Create a clear handout title
2. Identify the lecture subject
3. State the main goal of the lecture
4. Extract the main topics
5. For each topic, provide:
   - topic_name
   - importance
   - key_terms (short list of relevant terms)

Lecture notes:
{lecture_text}
"""

STUDY_MATERIAL_SYSTEM_PROMPT = """
You are an AI study coach creating a polished university revision sheet.
Return concise, presentation-ready content with no filler.
The quiz must contain multiple-choice questions with exactly 4 options each, one correct answer,
and a short explanation when useful.
"""

STUDY_MATERIAL_USER_PROMPT = """
Use the lecture notes and the lecture analysis to create the final study material.

Requirements:
1. Keep the title, subject, main_goal, and topics consistent with the lecture analysis
2. Write a study-note style summary using short readable paragraphs
3. Provide a concise list of key points, formulas, or important facts
4. Create a multiple-choice quiz that tests understanding, not only memorization
5. Every quiz question must have exactly 4 options
6. correct_answer must be one of: A, B, C, D
7. Keep explanations short and helpful

Lecture analysis:
{analysis_json}

Lecture notes:
{lecture_text}
"""
