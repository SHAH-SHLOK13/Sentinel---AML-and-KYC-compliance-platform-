# Sentinel: Hybrid-Intelligence Compliance Platform

Sentinel is an advanced, enterprise-grade hybrid-intelligence compliance platform designed to combine deterministic rules, machine learning anomaly detection, graph-based structural analysis, and biometric KYC verification.

Designed around a **3-Layer Architecture** (Directives, Orchestration, and Execution), Sentinel minimizes false positives, ensures strict compliance with regulations (like India's PMLA 2002 and RBI KYC Directions 2025), and maintains a cryptographically secure, immutable audit trail.

---

## 🚀 Key Modules & Capabilities

### 1. Adaptive Identity Verification (KYC) Pipeline
Sentinel features an asynchronous, device-adaptive identity verification pipeline built to handle low-end devices and poor connectivity while remaining robust against spoofing:
* **Intelligent Document Intake & OCR:** Real-time client-side guidance (blur/glare check) using OpenCV.js. Two-pass OCR utilizes Google Cloud Vision API as primary, with a Pytesseract fallback. Fuzzy name/DOB matching handles South Asian spelling variations.
* **Biometric Verification:** Active liveness challenge-response (blink detection, head turn, smile) using MediaPipe Face Mesh. High-accuracy face match uses DeepFace with an ArcFace backend.
* **Anti-Injection Protection:** Analyzes frame timing jitter (metronomic timing of virtual cameras vs. real camera hardware jitter) and metadata to stop virtual camera injection attacks.
* **Zero-Knowledge Aadhaar Policy:** Strict privacy compliance. No Aadhaar numbers or hashes are stored. Deduplication uses provider-managed vault tokens.

### 2. Hybrid AML Engine
Sentinel utilizes a 3-layered detection engine to balance regulatory safety, machine-learning intelligence, and network-level graph insight:
* **Layer 1: Regulatory Compliance (Deterministic Rules):** Execution of binary legal mandates (Monthly CTR threshold checks, PEP screening, and fuzzy Sanctions matching via trigram similarity with a circuit breaker pattern).
* **Layer 2: Statistical Anomaly Detection (ML):** An Isolation Forest model trained on transaction profiles (amount, velocity, time-of-day, etc.) to detect "unknown unknowns" and structuring tricks. Explainability is handled via SHAP values (restricted to internal triage prioritization).
* **Layer 3: Graph Intelligence (NetworkX):** In-memory graph computation tracking transaction flows. Features cycle detection (e.g., circular fund loops within a 72-hour window), degree centrality analysis for mule account detection, and Louvain community detection.

### 3. Compliance Command Center
A rich dashboard interface tailored for compliance officers:
* **Overview Analytics:** Risk distribution, false positive rates, MTTR (Mean Time to Resolution), and alert velocity.
* **Interactive Money Map:** Force-directed transaction graph visualization (`react-force-graph-2d`) with pulsing threat nodes and cluster isolation filters.
* **Template-Based Narrative Generator:** Complies with regulatory filing safety guidelines by generating narratives through deterministic, logic-driven templates rather than LLM text generation to prevent hallucinations.
* **Restricted AI Copilot:** Generates redacted, watermarked internal investigation summaries for Critical (Tier 3) alerts only, with hallucination gates checking valid transaction IDs.

### 4. Immutable Cryptographic Audit Trail
* **Hash-Chained Records:** Every compliance action (approvals, overrides, filings) hashes its contents along with the hash of the preceding entry. Modifying any historical database row breaks the integrity of all subsequent logs.
* **External Anchoring:** Periodically pushes the latest block hash to an append-only external bucket (e.g., S3 Object Lock) to prevent internal system overrides.

---

## 🛠️ Technology Stack

* **Frontend:** Next.js (App Router, TS), Tailwind CSS, Framer Motion, Radix UI, `react-force-graph-2d`.
* **Backend:** FastAPI (Python), Supabase (PostgreSQL), NetworkX (Graph Engine), Scikit-Learn (ML / Isolation Forest), MediaPipe/OpenCV.
* **Asynchronous Jobs & Cache:** Celery, Redis.

---

## 📂 Project Structure

```
Sentinel/
├── backend/                       # FASTAPI Python Backend
│   ├── app/
│   │   ├── api/                   # REST Endpoints (kyc, aml, dashboard, audit, etc.)
│   │   ├── engine/                # AML Rules, Anomaly Forest, & NetworkX Graph Engine
│   │   ├── services/              # Core business services (Aadhaar Vault, Liveness, Sanctions)
│   │   └── utils/                 # Utility scripts (JWT, cryptographic checks)
│   ├── models/                    # Pickled ML models and seed caches
│   └── scripts/                   # Data seeding, model training, and traffic simulation
├── frontend/                      # NEXT.JS Web Application
│   ├── src/
│   │   ├── app/                   # App Router Pages (/kyc, /aml, /dashboard)
│   │   ├── components/            # Shared UI components and layout sections
│   │   └── lib/                   # Frontend hooks and API utilities
├── directives/                    # Layer 1: SOPs (Standard Operating Procedures)
├── execution/                     # Layer 3: Deterministic script actions
└── AGENTS.md                      # Agent architecture and operation principles
```

---

## 💻 Setup & Installation

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Setup environment variables (`.env` file in `backend/`):
   Create a `.env` file based on `.env.example` containing your Supabase, OpenAI/Gemini, and API configurations.
5. Initialize the database and train the initial anomaly model:
   ```bash
   python scripts/demo_setup.py
   python scripts/train_model.py
   ```
6. Run the FastAPI development server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the Next.js development server:
   ```bash
   npm run dev
   ```
4. Access the web interface at `http://localhost:3000`.

---

## 🧩 3-Layer Architecture Compliance

Sentinel strictly enforces the 3-Layer Architecture:
1. **Directives (`/directives`)**: Markdown guides (SOPs) specifying steps for compliance processing.
2. **Orchestration**: The agent parses directives, verifies inputs/outputs, and executes actions.
3. **Execution (`/execution`)**: Deterministic Python scripts that run API checks, audit hashing, and data pipelines without human intervention.
