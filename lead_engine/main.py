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
    lead_id: int
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