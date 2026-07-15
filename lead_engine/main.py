import os
import sys
import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# =====================================================================
# PRODUCTION DATABASE CONFIGURATION
# =====================================================================
# Read PostgreSQL Connection String from environment variables (provided by Render/Railway/Supabase).
# Falls back to a local PostgreSQL instance or SQLite strictly for local safe-fallback testing.
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("[WARNING] DATABASE_URL environment variable is missing. Falling back to local SQLite 'leads.db' for development safety.", file=sys.stderr)
    DATABASE_URL = "sqlite:///./leads.db"
else:
    # Production Safeguard: Cloud providers (like Render or Heroku) often provision database connection strings
    # starting with 'postgres://'. Modern SQLAlchemy strictly requires 'postgresql://' dialect specifiers.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(f"[INIT] Securely targeting PostgreSQL Engine at endpoint: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

# Setup Database Engines
# For SQLite fallback, we require 'check_same_thread=False'. PostgreSQL handles connection pools natively.
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL, 
        pool_size=10, 
        max_overflow=20, 
        pool_recycle=1800,
        pool_pre_ping=True  # Production robust practice: verifies connection health before execution
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Model matching lead schema precisely
class LeadRecord(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_type = Column(String(10), nullable=False, index=True)  # B2C or B2B
    fullname = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False)
    state = Column(String(10), nullable=False, index=True)      # Target: TX, CA, FL
    requested_amount = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    monthly_revenue = Column(Float, nullable=True, default=0.0)
    loan_purpose = Column(String(100), nullable=False)
    
    # Internal Engine Routing Verdicts
    routing_verdict = Column(String(50), nullable=False)        # DIRECT_TO_CLIENT or ARBITRAGE_MARKETPLACE
    routing_destination = Column(String(100), nullable=False)  # Internal Queue vs fallback
    retained_yield_range = Column(String(50), nullable=False)
    underwriting_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

# Request Validation schemas ensuring strict API ingestion security
class LeadCreateSchema(BaseModel):
    lead_type: str = Field(..., pattern="^(B2C|B2B)$", description="Loan Category Toggle State")
    fullname: str = Field(..., min_length=2, max_length=255, description="Borrower Full Name or Registered Company")
    email: EmailStr = Field(..., description="Secure Contact Email Address")
    phone: str = Field(..., min_length=7, max_length=50, description="Formatted Security Telephone String")
    state: str = Field(..., min_length=2, max_length=10, description="US State ID (TX, CA, FL, NY)")
    requested_amount: float = Field(..., gt=0, description="Requested Emergency Capital Amount")
    credit_score: int = Field(..., ge=300, le=850, description="Self-Reported FICO Range Check")
    monthly_revenue: Optional[float] = Field(0.0, description="Required verifiable parameters for B2B")
    loan_purpose: str = Field(..., description="Emergency Use Categorization")

# API Response schema aligning perfectly with UI Frontend elements
class LeadResponseSchema(BaseModel):
    import sys
    import datetime
    from typing import Optional
    from fastapi import FastAPI, Depends, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, EmailStr, Field
    from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, text
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session

    # =====================================================================
    # PYDANTIC MULTI-VERSION COMPATIBILITY SAFEGUARD
    # =====================================================================
    # Auto-detects whether the host system is running Pydantic V1 or V2
    # to prevent "unexpected keyword argument 'pattern'" validation crashes.
    import pydantic
    IS_PYDANTIC_V2 = pydantic.__version__.startswith("2")
    lead_type_constraints = {"pattern": "^(B2C|B2B)$"} if IS_PYDANTIC_V2 else {"regex": "^(B2C|B2B)$"}

    # =====================================================================
    # PRODUCTION DATABASE CONFIGURATION
    # =====================================================================
    DATABASE_URL = os.environ.get("DATABASE_URL")
    USING_SQLITE_FALLBACK = False

    if not DATABASE_URL:
        print("[WARNING] DATABASE_URL environment variable is missing. Falling back to local SQLite 'leads.db' for development safety.", file=sys.stderr)
        DATABASE_URL = "sqlite:///./leads.db"
        USING_SQLITE_FALLBACK = True
    else:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        print(f"[INIT] Securely targeting PostgreSQL Engine at endpoint: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    if "sqlite" in DATABASE_URL:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        USING_SQLITE_FALLBACK = True
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
    lead_type = Column(String(10), nullable=False, index=True)  # B2C or B2B
    fullname = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False)
    state = Column(String(10), nullable=False, index=True)      # Target: TX, CA, FL
    requested_amount = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    monthly_revenue = Column(Float, nullable=True, default=0.0)
    loan_purpose = Column(String(100), nullable=False)
    
    routing_verdict = Column(String(50), nullable=False)        # DIRECT_TO_CLIENT or ARBITRAGE_MARKETPLACE
    routing_destination = Column(String(100), nullable=False)  # Internal Queue vs fallback
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
        from_attributes = True  # Pydantic v2
        orm_mode = True         # Pydantic v1 fallback

# =====================================================================
# AUTOMATED UNDERWRITING DECISION ENGINE
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
# FASTAPI APPLICATION SETUP
# =====================================================================
app = FastAPI(
    title="Emergency Funding Arbitrage Router API",
    version="1.0.0",
    description="Automated Underwriting Decision Matrix with PostgreSQL persistence."
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

@app.on_event("startup")
def startup_db_initialization():
    print("[STARTUP] Syncing target schemas with SQL Engine...")
    Base.metadata.create_all(bind=engine)
    print("[STARTUP] Schema sync check finalized successfully.")

# =====================================================================
# ENDPOINTS
# =====================================================================
@app.get("/", response_class=HTMLResponse)
def root_dashboard(db: Session = Depends(get_db)):
    """
    Renders a stunning interactive landing page for users clicking on their live Render link.
    Now utilizes explicitly declared SQLAlchemy text constructs to maintain compatibility.
    """
    db_status = "Connected"
    db_color = "emerald"
    db_driver = "PostgreSQL (Production Cloud)"
    db_error_section = ""
    
    if USING_SQLITE_FALLBACK:
        db_driver = "SQLite (Local Safety Fallback)"
        db_color = "amber"
    
    try:
        # Wrap raw SQL in text() to avoid SQLAlchemy 2.0 Textual SQL expression error
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
                <!-- Glowing Pulsing Header Icon -->
                <div class="inline-flex items-center justify-center h-20 w-20 rounded-full bg-emerald-500/10 border border-emerald-500/30 animate-pulse">
                    <span class="material-icons text-emerald-400 text-4xl">bolt</span>
                </div>
                
                <h1 class="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-500 bg-clip-text text-transparent">
                    Emergency Funding Arbitrage API Gateway
                </h1>
                
                <p class="text-slate-400 text-lg max-w-xl mx-auto">
                    Your automated B2B/B2C loan underwriting decision engine is running successfully in production cloud environment.
                </p>

                <!-- Core Health Diagnostics Dashboard Grid -->
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

                <!-- Actions and Navigation -->
                <div class="flex flex-col sm:flex-row justify-center items-center gap-4 pt-8">
                    <a href="/docs" target="_blank" class="w-full sm:w-auto bg-emerald-400 hover:bg-emerald-500 text-slate-950 font-bold py-3.5 px-6 rounded-xl transition-all duration-200 shadow-lg shadow-emerald-500/10 flex items-center justify-center gap-2 text-sm uppercase tracking-wider">
                        <span class="material-icons">api</span>
                        Explore Interactive API Docs
                    </a>
                    <a href="https://github.com" target="_blank" class="w-full sm:w-auto bg-slate-900/80 hover:bg-slate-800 text-slate-300 font-bold py-3.5 px-6 rounded-xl border border-slate-800 transition-all duration-200 flex items-center justify-center gap-2 text-sm uppercase tracking-wider">
                        <span class="material-icons">help_outline</span>
                        Developer Support
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

@app.post("/api/v1/leads", response_model=LeadResponseSchema, status_code=status.HTTP_201_CREATED)
def intake_secure_lead(lead_in: LeadCreateSchema, db: Session = Depends(get_db)):
    """
    Intakes lead payloads, evaluates underwriting matrices, persists the output directly 
    to database tables, and returns routing directives instantly.
    """
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
    routing: str
    message: str
    retained_yield_range: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

def evaluate_underwriting_and_route(lead: LeadCreateSchema) -> tuple:
    """
    Core Underwriting Decision Matrix.
    Routes high-intent qualified leads directly to internal portfolios ('DIRECT_TO_CLIENT')
    and liquidates marginal, low-qualified, or out-of-bounds leads to fallback programmatic marketplaces ('ARBITRAGE_MARKETPLACE').
    """
    eligible_territories = {"CA", "TX", "FL"}
    state_upper = lead.state.strip().upper()
    
    # Check physical state eligibility bounds first
    if state_upper not in eligible_territories:
        return (
            "ARBITRAGE_MARKETPLACE",
            "Programmatic Marketplace (Affiliate Network)",
            "$120.00 - $350.00",
            f"Fallback routing triggered. Operational boundary exception for {state_upper} leads."
        )

    if lead.lead_type == "B2B":
        # Commercial Underwriting Checklist: Checks state eligibility, minimum credit, and minimum monthly revenue
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
        # Consumer Underwriting Checklist: Checks state eligibility, credit threshold, and logical request caps
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

app = FastAPI(
    title="Emergency Funding Arbitrage Router API",
    version="1.0.0",
    description="Automated Underwriting Decision Matrix with PostgreSQL persistence."
)

# CORS configuration to enable local frontend files to cross-communicate securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific origins in highly-secure deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to cleanly yield database session per-request thread and clean up after completions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_db_initialization():
    """
    On Engine Startup, initialize tables if they don't already exist in PostgreSQL.
    """
    print("[STARTUP] Syncing target schemas with SQL Engine...")
    Base.metadata.create_all(bind=engine)
    print("[STARTUP] Schema sync check finalized successfully.")

@app.get("/")
def health_endpoint(db: Session = Depends(get_db)):
    """
    Engine health checks. Validates live runtime and database connectivity.
    """
    try:
        # Simple test to confirm DB can process commands
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "router_active": True,
            "database_connection": "PostgreSQL Live & Active",
            "server_timestamp": datetime.datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Healthy Server, but Database is inaccessible: {str(e)}"
        )

@app.post("/api/v1/leads", response_model=LeadResponseSchema, status_code=status.HTTP_201_CREATED)
def intake_secure_lead(lead_in: LeadCreateSchema, db: Session = Depends(get_db)):
    """
    Intakes lead payloads, evaluates underwriting matrices, persists the output directly 
    to PostgreSQL, and returns routing directives instantly to the frontend.
    """
    try:
        # 1. Execute Underwriting Matrix Calculation Rules
        verdict, destination, yield_range, notes = evaluate_underwriting_and_route(lead_in)
        
        # 2. Package and Prepare Schema records
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
        
        # 3. Securely commit to live PostgreSQL schema tables
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        
        # 4. Construct response payloads matching standard structure
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

# Command to execute locally:
# uvicorn main:app --reload --port 8000