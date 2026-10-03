import json
import os
import re
from datetime import datetime

import fitz
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

st.set_page_config(page_title="EduMind AI", page_icon="🎓", layout="wide")

MAX_CONTEXT_CHARS = 30000
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def get_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        st.error("Gemini API key not found. Add GEMINI_API_KEY to your local .env file.")
        st.stop()
    return genai.Client(api_key=api_key)


def extract_pdf_text(uploaded_file):
    try:
        document = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
        pages = [page.get_text("text") for page in document]
        return "\n\n".join(
            f"--- Page {index + 1} ---\n{page_text}"
            for index, page_text in enumerate(pages)
            if page_text.strip()
        ).strip()
    except Exception as exc:
        st.error(f"Could not read this PDF: {exc}")
        return ""


def call_gemini(prompt, model=DEFAULT_MODEL, json_mode=False):
    client = get_client()
    config = {}
    if json_mode:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config if json_mode else None,
    )
    return (response.text or "").strip()


def clean_json_response(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def validate_questions(data):
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError("The generated quiz did not contain a questions list.")

    cleaned = []
    for item in data["questions"]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        answer = item.get("answer_index")
        explanation = str(item.get("explanation", "")).strip()
        topic = str(item.get("topic", "General")).strip() or "General"

        if (
            not question
            or not isinstance(options, list)
            or len(options) != 4
            or not all(str(option).strip() for option in options)
            or not isinstance(answer, int)
            or answer not in range(4)
        ):
            continue

        cleaned.append({
            "question": question,
            "options": [str(option).strip() for option in options],
            "answer_index": answer,
            "explanation": explanation or "Review the related material to understand this answer.",
            "topic": topic,
        })

    if not cleaned:
        raise ValueError("No valid multiple-choice questions were generated.")
    return cleaned


def generate_quiz(material, count, difficulty, focus):
    focus_text = focus.strip() if focus.strip() else "Cover the key ideas across the material."
    prompt = f"""
You are an educational assessment designer. Create exactly {count} multiple-choice
questions based only on the learning material below.
Difficulty: {difficulty}
Focus: {focus_text}

Return valid JSON only, using this exact schema:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer_index": 0,
      "explanation": "Brief explanation grounded in the material",
      "topic": "Short topic name"
    }}
  ]
}}

Rules:
- Every question must have exactly four distinct options.
- answer_index must be an integer from 0 to 3.
- Only one option should be correct.
- Avoid ambiguous, duplicate, or trick questions.
- Do not include answers in the question text.
- Base all answers and explanations on the supplied material.
- Return exactly {count} questions if the material allows.

LEARNING MATERIAL:
{material[:MAX_CONTEXT_CHARS]}
"""
    raw = call_gemini(prompt, json_mode=True)
    return validate_questions(clean_json_response(raw))


def reset_quiz_state():
    for key in ("quiz_questions", "quiz_answers", "quiz_submitted", "quiz_score"):
        st.session_state.pop(key, None)


st.title("🎓 EduMind AI")
st.caption("Learn smarter with an AI tutor that understands your materials, evaluates your progress, and personalizes your learning journey.")

with st.sidebar:
    st.header("📚 Learning material")
    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    st.caption("Text-based PDFs are supported. Scanned PDFs may need OCR, which is not included yet.")
    st.divider()
    model_name = st.text_input("Gemini model", value=DEFAULT_MODEL)

if "quiz_history" not in st.session_state:
    st.session_state.quiz_history = []
if "document_text" not in st.session_state:
    st.session_state.document_text = ""
if "document_key" not in st.session_state:
    st.session_state.document_key = None

if uploaded_pdf is not None:
    document_key = f"{uploaded_pdf.name}:{uploaded_pdf.size}"
    if document_key != st.session_state.document_key:
        st.session_state.document_text = extract_pdf_text(uploaded_pdf)
        st.session_state.document_key = document_key
        reset_quiz_state()
        st.session_state.quiz_history = []

material = st.session_state.document_text

if uploaded_pdf is None:
    st.info("Upload a learning-material PDF from the sidebar to start.")
elif not material:
    st.warning("No selectable text was found in this PDF. Try a text-based PDF.")

if material:
    st.success(f"Loaded **{uploaded_pdf.name}** · {len(material):,} characters extracted")

    tutor_tab, quiz_tab, progress_tab = st.tabs(["💬 AI Tutor", "📝 Quiz Generator", "📊 Progress"])

    with tutor_tab:
        st.subheader("Ask your learning material")
        st.write("Ask questions, request explanations, or get a summary based on the uploaded PDF.")
        question = st.text_area(
            "Your question",
            placeholder="Explain the main concept in simple terms...",
            key="tutor_question",
        )
        if st.button("Ask EduMind", type="primary", key="ask_tutor"):
            if not question.strip():
                st.warning("Enter a question first.")
            else:
                prompt = f"""You are EduMind AI, a supportive personal tutor.
Answer the student's question using the learning material provided.
Explain clearly, define important terms, and use a small example when useful.
If the material does not contain the answer, say so and distinguish general
knowledge from information found in the PDF.

LEARNING MATERIAL:
{material[:MAX_CONTEXT_CHARS]}

STUDENT QUESTION:
{question.strip()}
"""
                with st.spinner("EduMind is preparing an explanation..."):
                    try:
                        answer = call_gemini(prompt, model=model_name)
                        st.markdown(answer or "No response was returned.")
                    except Exception as exc:
                        st.error(f"Could not get a response from Gemini: {exc}")

        if st.button("Summarize this PDF", key="summarize"):
            prompt = f"""Summarize the following learning material for a student.
Use headings, concise bullet points, key terms, and a short recap.
Do not invent facts not supported by the text.

LEARNING MATERIAL:
{material[:MAX_CONTEXT_CHARS]}
"""
            with st.spinner("Creating your summary..."):
                try:
                    st.markdown(call_gemini(prompt, model=model_name))
                except Exception as exc:
                    st.error(f"Could not create the summary: {exc}")

    with quiz_tab:
        st.subheader("Create an adaptive practice quiz")
        left, right = st.columns(2)
        with left:
            question_count = st.selectbox("Number of questions", [5, 10, 15], index=0)
            difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
        with right:
            focus = st.text_input("Topic focus (optional)", placeholder="e.g., graph theory, definitions")
            st.write("")
            st.write("")
            make_quiz = st.button("✨ Generate quiz", type="primary", use_container_width=True)

        if make_quiz:
            with st.spinner("Generating questions from your PDF..."):
                try:
                    st.session_state.quiz_questions = generate_quiz(
                        material, question_count, difficulty, focus
                    )
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_score = None
                except Exception as exc:
                    st.error(f"Quiz generation failed: {exc}")

        questions = st.session_state.get("quiz_questions", [])
        if questions:
            st.caption(f"{len(questions)} questions · {difficulty} difficulty")
            with st.form("quiz_form"):
                selected_answers = {}
                for idx, item in enumerate(questions):
                    st.markdown(f"**Q{idx + 1}. {item['question']}**")
                    selected = st.radio(
                        "Choose one answer",
                        options=list(range(4)),
                        format_func=lambda option, opts=item["options"]: f"{chr(65 + option)}. {opts[option]}",
                        key=f"quiz_answer_{idx}",
                        index=None,
                        label_visibility="collapsed",
                    )
                    selected_answers[idx] = selected
                    st.caption(f"Topic: {item['topic']}")
                    if idx < len(questions) - 1:
                        st.divider()
                submitted = st.form_submit_button("Submit answers", type="primary")

            if submitted:
                score = sum(
                    selected_answers.get(i) == item["answer_index"]
                    for i, item in enumerate(questions)
                )
                st.session_state.quiz_answers = selected_answers
                st.session_state.quiz_score = score
                st.session_state.quiz_submitted = True
                st.session_state.quiz_history.append({
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "score": score,
                    "total": len(questions),
                    "difficulty": difficulty,
                    "topics": [item["topic"] for item in questions],
                    "correct": [
                        selected_answers.get(i) == item["answer_index"]
                        for i, item in enumerate(questions)
                    ],
                })

            if st.session_state.get("quiz_submitted"):
                score = st.session_state.quiz_score
                total = len(questions)
                st.metric("Your score", f"{score}/{total}", f"{score / total * 100:.1f}%")
                st.progress(score / total if total else 0)
                st.markdown("### Answer review")
                for idx, item in enumerate(questions):
                    chosen = st.session_state.quiz_answers.get(idx)
                    correct = chosen == item["answer_index"]
                    st.markdown(f"**Q{idx + 1}. {item['question']}**")
                    if chosen is None:
                        st.warning(f"Not answered. Correct answer: {chr(65 + item['answer_index'])}. {item['options'][item['answer_index']]}")
                    elif correct:
                        st.success(f"Correct: {chr(65 + item['answer_index'])}. {item['options'][item['answer_index']]}")
                    else:
                        st.error(
                            f"Your answer: {chr(65 + chosen)}. {item['options'][chosen]}  \n"
                            f"Correct answer: {chr(65 + item['answer_index'])}. {item['options'][item['answer_index']]}"
                        )
                    st.write(f"**Explanation:** {item['explanation']}")
                    st.caption(f"Topic: {item['topic']}")
                    st.divider()

                if st.button("Generate another quiz", key="new_quiz"):
                    reset_quiz_state()
                    st.rerun()

    with progress_tab:
        st.subheader("Your learning progress")
        history = st.session_state.quiz_history
        if not history:
            st.info("Complete a quiz to see your progress here.")
        else:
            attempts = len(history)
            total_questions = sum(entry["total"] for entry in history)
            total_correct = sum(entry["score"] for entry in history)
            accuracy = total_correct / total_questions * 100 if total_questions else 0
            best = max(entry["score"] / entry["total"] * 100 for entry in history if entry["total"])

            c1, c2, c3 = st.columns(3)
            c1.metric("Quiz attempts", attempts)
            c2.metric("Overall accuracy", f"{accuracy:.1f}%")
            c3.metric("Best quiz accuracy", f"{best:.1f}%")

            st.markdown("### Quiz history")
            for index, entry in enumerate(reversed(history), start=1):
                st.write(
                    f"{index}. **{entry['date']}** — {entry['score']}/{entry['total']} "
                    f"({entry['score'] / entry['total'] * 100:.1f}%) · {entry['difficulty']}"
                )

            topic_totals = {}
            for entry in history:
                for topic, is_correct in zip(entry["topics"], entry["correct"]):
                    stats = topic_totals.setdefault(topic, {"correct": 0, "total": 0})
                    stats["total"] += 1
                    stats["correct"] += int(is_correct)

            st.markdown("### Topic-wise performance")
            topic_rows = []
            for topic, stats in sorted(topic_totals.items()):
                topic_accuracy = stats["correct"] / stats["total"] * 100
                topic_rows.append({
                    "Topic": topic,
                    "Correct": stats["correct"],
                    "Questions": stats["total"],
                    "Accuracy": f"{topic_accuracy:.1f}%",
                })
            st.dataframe(topic_rows, use_container_width=True, hide_index=True)

            weakest = min(
                topic_totals.items(),
                key=lambda pair: pair[1]["correct"] / pair[1]["total"]
            )
            st.info(
                f"**Revision suggestion:** Review **{weakest[0]}**. "
                "Generate a focused quiz on this topic to practise it further."
            )

st.divider()
st.caption("EduMind AI · Quiz history is stored in the current Streamlit session only and may reset when the app restarts.")
