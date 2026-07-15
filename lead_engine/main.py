import os
import sys
import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
import pydantic

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from google import genai
from google.genai import types

# =====================================================================
# PYDANTIC MULTI-VERSION COMPATIBILITY SAFEGUARD
# =====================================================================
IS_PYDANTIC_V2 = pydantic.__version__.startswith("2")
lead_type_constraints = {"pattern": "^(B2C|B2B)$"} if IS_PYDANTIC_V2 else {"regex": "^(B2C|B2B)$"}

# =====================================================================
# PRODUCTION DATABASE CONFIGURATION
# =====================================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
USING_SQLITE_FALLBACK = False

if not DATABASE_URL:
    print("[WARNING] DATABASE_URL environment variable is missing. Falling back to local SQLite 'leads.db'.", file=sys.stderr)
    DATABASE_URL = "sqlite:///./leads.db"
    USING_SQLITE_FALLBACK = True
else:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(f"[INIT] Securely targeting PostgreSQL Engine.")

# Setup Database Engines
if USING_SQLITE_FALLBACK:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL, 
        pool_size=10, 
        max_overflow=20, 
        pool_recycle=1800,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =====================================================================
# DATABASE MODELS
# =====================================================================
class LeadRecord(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_type = Column(String(10), nullable=False, index=True)
    fullname = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False)
    state = Column(String(10), nullable=False, index=True)
    requested_amount = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    monthly_revenue = Column(Float, nullable=True, default=0.0)
    loan_purpose = Column(String(100), nullable=False)
    
    routing_verdict = Column(String(50), nullable=False)
    routing_destination = Column(String(100), nullable=False)
    retained_yield_range = Column(String(50), nullable=False)
    underwriting_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

# =====================================================================
# VALIDATION SCHEMAS (PYDANTIC)
# =====================================================================
class LeadCreateSchema(BaseModel):
    lead_type: str = Field(..., description="Loan Category Toggle State", **lead_type_constraints)
    fullname: str = Field(..., min_length=2, max_length=255, description="Borrower Full Name or Registered Company")
    email: EmailStr = Field(..., description="Secure Contact Email Address")
    phone: str = Field(..., min_length=7, max_length=50, description="Formatted Security Telephone String")
    state: str = Field(..., min_length=2, max_length=10, description="US State ID (TX, CA, FL, NY)")
    requested_amount: float = Field(..., gt=0, description="Requested Emergency Capital Amount")
    credit_score: int = Field(..., ge=300, le=850, description="Self-Reported FICO Range Check")
    monthly_revenue: Optional[float] = Field(0.0, description="Required verifiable parameters for B2B")
    loan_purpose: str = Field(..., description="Emergency Use Categorization")

class LeadResponseSchema(BaseModel):
    lead_id: int
    routing: str
    message: str
    retained_yield_range: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True
        orm_mode = True

# =====================================================================
# GEMINI AI CLIENT CONFIGURATION
# =====================================================================
try:
    ai_client = genai.Client()
except Exception:
    ai_client = None
    print("[WARNING] GEMINI_API_KEY not found. AI features will run in demo mode.")

# =====================================================================
# UNDERWRITING DECISION ENGINE
# =====================================================================
def evaluate_underwriting_and_route(lead: LeadCreateSchema) -> tuple:
    eligible_territories = {"CA", "TX", "FL"}
    state_upper = lead.state.strip().upper()
    
    if state_upper not in eligible_territories:
        return (
            "ARBITRAGE_MARKETPLACE",
            "Programmatic Marketplace (Affiliate Network)",
            "$120.00 - $350.00",
            f"Fallback routing triggered. Operational boundary exception for {state_upper} leads."
        )

    if lead.lead_type == "B2B":
        min_credit = 600
        min_revenue = 10000.00
        
        if lead.credit_score >= min_credit and lead.monthly_revenue >= min_revenue:
            return (
                "DIRECT_TO_CLIENT",
                "Internal Direct Portfolio Lending Desk",
                "Retained Yield: Premium (Commercial B2B Portfolio)",
                f"Qualified Commercial B2B Account with credit {lead.credit_score} and monthly revenue ${lead.monthly_revenue:,.2f}."
            )
        else:
            return (
                "ARBITRAGE_MARKETPLACE",
                "Fallback Programmatic Partner Net",
                "$120.00 - $350.00",
                f"Commercial criteria unfulfilled: Credit {lead.credit_score} (min: {min_credit}) or Revenue ${lead.monthly_revenue:,.2f} (min: ${min_revenue:,.2f})."
            )
            
    else:  # Consumer Personal Emergency B2C Portfolio
        max_amount = 10000.00
        min_credit = 640
        
        if lead.credit_score >= min_credit and lead.requested_amount <= max_amount:
            return (
                "DIRECT_TO_CLIENT",
                "Internal Direct Portfolio Lending Desk",
                "Retained Yield: Premium (Personal B2C Portfolio)",
                f"Qualified Personal B2C profile. Approved credit index score {lead.credit_score} with low-leverage request value."
            )
        else:
            return (
                "ARBITRAGE_MARKETPLACE",
                "Programmatic Marketplace (Consumer Arbitrage Group)",
                "$120.00 - $350.00",
                f"Consumer thresholds adjusted: Credit {lead.credit_score} (min: {min_credit}) or requested value limits exceeded."
            )

# =====================================================================
# FASTAPI APPLICATION LIFESPAN & SETUP
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup DB Schema Checks
    print("[STARTUP] Syncing target schemas with SQL Engine...")
    Base.metadata.create_all(bind=engine)
    print("[STARTUP] Schema sync check finalized successfully.")
    yield
    # Shutdown logic (if any) can go here

app = FastAPI(
    title="Emergency Funding Arbitrage Router API",
    version="1.0.0",
    description="Automated Underwriting Decision Matrix with PostgreSQL persistence.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# ENDPOINTS
# =====================================================================
@app.get("/", response_class=HTMLResponse)
def root_dashboard(db: Session = Depends(get_db)):
    db_status = "Connected"
    db_color = "emerald"
    db_driver = "PostgreSQL (Production Cloud)"
    db_error_section = ""
    
    if USING_SQLITE_FALLBACK:
        db_driver = "SQLite (Local Safety Fallback)"
        db_color = "amber"
    
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "Inaccessible / Disconnected"
        db_color = "red"
        db_error_section = f"""
        <div class="mt-4 p-4 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-200 font-mono text-left max-w-xl mx-auto overflow-x-auto">
            <strong>Database Connection Diagnostic Error:</strong><br/>
            {str(e)}
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arbitrage Underwriting Router Gateway</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Icons" rel="stylesheet">
        <style>
            body {{
                font-family: 'Google Sans', sans-serif;
                background: radial-gradient(circle at top, #0f172a, #020617);
            }}
        </style>
    </head>
    <body class="text-slate-100 min-h-screen flex flex-col justify-between">
        <div class="max-w-4xl mx-auto w-full px-4 py-16 flex-grow flex flex-col justify-center">
            <div class="text-center space-y-6">
                <div class="inline-flex items-center justify-center h-20 w-20 rounded-full bg-emerald-500/10 border border-emerald-500/30 animate-pulse">
                    <span class="material-icons text-emerald-400 text-4xl">bolt</span>
                </div>
                
                <h1 class="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-500 bg-clip-text text-transparent">
                    Emergency Funding Arbitrage API Gateway
                </h1>
                
                <p class="text-slate-400 text-lg max-w-xl mx-auto">
                    Your automated B2B/B2C loan underwriting decision engine is running successfully in production cloud environment.
                </p>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto pt-6">
                    <div class="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 backdrop-blur-md text-center">
                        <span class="text-xs font-semibold text-slate-500 uppercase tracking-widest block mb-1">API Engine Status</span>
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-950/50 rounded-lg border border-emerald-500/30 text-emerald-400 text-sm font-bold">
                            <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            ACTIVE
                        </span>
                    </div>

                    <div class="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 backdrop-blur-md text-center">
                        <span class="text-xs font-semibold text-slate-500 uppercase tracking-widest block mb-1">Database Engine</span>
                        <span class="text-slate-200 text-sm font-semibold truncate block">
                            {db_driver}
                        </span>
                    </div>

                    <div class="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 backdrop-blur-md text-center">
                        <span class="text-xs font-semibold text-slate-500 uppercase tracking-widest block mb-1">Database Status</span>
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-{db_color}-950/50 rounded-lg border border-{db_color}-500/30 text-{db_color}-400 text-sm font-bold">
                            {db_status}
                        </span>
                    </div>
                </div>

                {db_error_section}

                <div class="flex flex-col sm:flex-row justify-center items-center gap-4 pt-8">
                    <a href="/docs" target="_blank" class="w-full sm:w-auto bg-emerald-400 hover:bg-emerald-500 text-slate-950 font-bold py-3.5 px-6 rounded-xl transition-all duration-200 shadow-lg shadow-emerald-500/10 flex items-center justify-center gap-2 text-sm uppercase tracking-wider">
                        <span class="material-icons">api</span>
                        Explore Interactive API Docs
                    </a>
                </div>
            </div>
        </div>

        <footer class="border-t border-slate-900/60 bg-slate-950/40 py-6 text-center text-xs text-slate-500">
            <p>&copy; 2026 Emergency Loan Arbitrage Network. Live Cloud Production Pipeline.</p>
        </footer>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/admin/leads", response_class=HTMLResponse)
def view_leads_admin(db: Session = Depends(get_db)):
    """
    Renders a professional admin dashboard table of all leads.
    """
    leads = db.query(LeadRecord).order_by(LeadRecord.created_at.desc()).all()
    
    rows = ""
    for lead in leads:
        # Determine styling based on verdict
        status_color = "emerald" if lead.routing_verdict == "DIRECT_TO_CLIENT" else "amber"
        
        rows += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/50 transition">
            <td class="p-4 text-xs font-mono text-slate-500">#{lead.id}</td>
            <td class="p-4 text-sm font-bold text-slate-200">{lead.fullname}</td>
            <td class="p-4 text-sm text-slate-400">{lead.lead_type}</td>
            <td class="p-4 text-sm text-slate-400">{lead.state}</td>
            <td class="p-4 text-sm font-semibold text-emerald-400">${lead.requested_amount:,.2f}</td>
            <td class="p-4">
                <span class="px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-{status_color}-950 text-{status_color}-400 border border-{status_color}-500/30">
                    {lead.routing_verdict.replace('_', ' ')}
                </span>
            </td>
            <td class="p-4 text-xs text-slate-500">{lead.created_at.strftime('%Y-%m-%d %H:%M')}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Material+Icons" rel="stylesheet">
        <title>Lead Admin Dashboard</title>
    </head>
    <body class="bg-slate-950 text-slate-200 p-8">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-2xl font-bold text-white">Lead Pipeline Administration</h1>
                <!-- Refresh and Navigation Buttons -->
                <div class="flex gap-2">
                    <button onclick="window.location.reload()" class="text-xs bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-lg text-white font-bold flex items-center gap-1 shadow-lg shadow-emerald-900/20 transition">
                        <span class="material-icons text-sm">refresh</span> Refresh
                    </button>
                    <a href="/" class="text-xs bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg text-slate-300 font-bold transition">Back to Intake</a>
                </div>
            </div>
            
            <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-950 text-slate-500 uppercase text-[10px] tracking-widest">
                        <tr>
                            <th class="p-4">ID</th>
                            <th class="p-4">Borrower</th>
                            <th class="p-4">Type</th>
                            <th class="p-4">State</th>
                            <th class="p-4">Request</th>
                            <th class="p-4">Verdict</th>
                            <th class="p-4">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800">
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/api/v1/leads")
def get_all_leads(db: Session = Depends(get_db)):
    """
    Returns all leads stored in the database.
    Useful for verification and debugging.
    """
    leads = db.query(LeadRecord).all()
    return leads

@app.post("/api/v1/leads", response_model=LeadResponseSchema, status_code=status.HTTP_201_CREATED)
def intake_secure_lead(lead_in: LeadCreateSchema, db: Session = Depends(get_db)):
    try:
        verdict, destination, yield_range, notes = evaluate_underwriting_and_route(lead_in)
        
        new_lead = LeadRecord(
            lead_type=lead_in.lead_type,
            fullname=lead_in.fullname,
            email=lead_in.email,
            phone=lead_in.phone,
            state=lead_in.state.upper(),
            requested_amount=lead_in.requested_amount,
            credit_score=lead_in.credit_score,
            monthly_revenue=lead_in.monthly_revenue,
            loan_purpose=lead_in.loan_purpose,
            routing_verdict=verdict,
            routing_destination=destination,
            retained_yield_range=yield_range,
            underwriting_notes=notes
        )
        
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        
        return LeadResponseSchema(
            lead_id=new_lead.id,
            routing=new_lead.routing_verdict,
            message=new_lead.underwriting_notes,
            retained_yield_range=new_lead.retained_yield_range,
            created_at=new_lead.created_at
        )
        
    except Exception as e:
        db.rollback()
        print(f"[CRITICAL ERROR] Lead commit failure: {str(e)}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Secure ledger writing error: {str(e)}"
        )

# --- AI MARKETING GENERATOR ---
@app.get("/api/generate-trigger-marketing")
async def generate_trigger_marketing(event_description: str, state: str):
    if not ai_client:
        return {
            "headline": f"Need Emergency Funding in {state}?",
            "primary_text": f"Fast approval up to $50,000 for home, car, or business emergencies. Apply in 2 minutes.",
            "note": "Demo mode: Set GEMINI_API_KEY to see live AI variations."
        }
        
    prompt = f"""
    You are an elite conversion copywriter working for an instant emergency lending company.
    Analyze this localized trigger event: "{event_description}" happening in {state}.
    
    Generate two marketing assets:
    1. A short, high-intent Facebook/Instagram ad headline (under 40 characters).
    2. A matching primary text copy (under 3 sentences) driving users to check their eligibility instantly.
    
    Make it sound empathetic, fast, and local. Avoid generic sales hype. Wrap your answer in clean JSON keys: 'headline' and 'primary_text'.
    """
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))