# EduMind AI 🎓

An AI-powered personalized learning platform that helps students understand educational material through interactive AI tutoring.

## Current features

- Upload text-based educational PDFs
- Extract PDF text with page markers
- Ask questions about uploaded material
- Receive AI-generated explanations through the Gemini API
- Maintain chat history for the current document
- Clear the conversation

> This starter version does not yet include OCR for scanned PDFs, retrieval-augmented chunk search, quizzes, mastery tracking, or a progress dashboard. These can be added as future features.

## Requirements

- Python 3.10 or newer
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Run locally

1. Extract or clone this repository and open the folder in VS Code.
2. Create and activate a virtual environment (recommended):

   **Windows**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and add your API key:

   ```env
   GEMINI_API_KEY=your_actual_key
   GEMINI_MODEL=gemini-2.5-flash
   ```

   Keep `.env` private. Do not commit it to GitHub.

5. Start the app:

   ```bash
   streamlit run app.py
   ```

6. Open the local URL shown in the terminal, upload a text-based PDF, and ask a question.

## Troubleshooting

- **API key missing:** Confirm `.env` is in the same folder as `app.py` and the variable is named `GEMINI_API_KEY`.
- **Model unavailable:** Set `GEMINI_MODEL` to a text-generation model currently available to your API key.
- **No PDF text:** The current version extracts selectable text. Scanned/image-only PDFs need OCR, which is not included.
- **Large document:** The starter app caps the included document context. Large PDFs may need chunking and retrieval for better coverage.

## Planned improvements

- Chunked retrieval and source-grounded citations
- Quiz generation and evaluation
- Bayesian Knowledge Tracing for topic mastery
- Personalized revision recommendations
- Student learning dashboard
- OCR and multimodal material support
