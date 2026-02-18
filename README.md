# Advanced RAG Chatbot

An intelligent, production-ready Retrieval-Augmented Generation (RAG) chatbot built with **FastAPI**, **LangChain**, and **Groq**. This project features advanced document processing, multi-persona interactions, and secure authentication flows.

---

## Key Features

- ** Smart Document Processing**: Upload and query PDF, TXT, and DOCX files.
- ** Advanced Retrieval Pipeline**: 
  - Vector-based search using **FAISS**.
  - High-precision re-ranking using **FlashRank**.
- ** Multi-Persona AI**: Seamlessly switch between specialized roles:
  - **Teacher**: Simplifies complex topics.
  - **Interviewer**: Conducts professional mock interviews.
  - **Researcher**: Provides detailed technical analysis.
  - **Debugger**: Helps identify and fix code issues.
- ** Secure Authentication**:
  - **OTP Email Login**: Passwordless secure access.
  - **Google OAuth**: One-click social authentication.
- ** Real-time Streaming**: Modern, glassmorphic UI with real-time response streaming.

---

##  Technology Stack

| Component | Technology |
|---|---|
| **Backend** | FastAPI, Python 3.10+ |
| **LLM Engine** | Groq (Llama-3 models) |
| **Orchestration** | LangChain |
| **Vector DB** | FAISS |
| **Database** | SQLite (SQLAlchemy) |
| **Frontend** | Vanilla JS, CSS3 (Modern Glassmorphism) |

---

##  Prerequisites

- Python 3.10 or higher
- Groq API Key
- Google Cloud Console credentials (for OAuth)

---

##  Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd RAG_Chatbot
   ```

2. **Set Up Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_groq_key
   SECRET_KEY=your_session_secret
   GOOGLE_CLIENT_ID=your_google_id
   GOOGLE_CLIENT_SECRET=your_google_secret
   ```

---

##  Running the Application

Start the development server:
```bash
python -m uvicorn app.main:app --reload
```
Open your browser and navigate to `http://127.0.0.1:8000`.

---

##  Project Structure

```text
RAG_Chatbot/
├── app/
│   ├── api/          # API Endpoints (Chat, Docs, Auth)
│   ├── core/         # Config & Security
│   ├── db/           # Database models & sessions
│   ├── services/     # RAG Core (Retrieval, Reranking)
│   ├── static/       # CSS & Frontend JS
│   └── templates/    # HTML Pages
├── data/             # Document uploads
├── db/               # Local SQLite & FAISS Index
└── requirements.txt  # Project dependencies
```

---

##  Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

