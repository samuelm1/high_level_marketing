import os
import logging
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from google import genai
from google.genai import types

# 1. Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("production_lead_engine")

# 2. Database Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./leads.db")  # Defaults to local SQLite, swaps to PostgreSQL in production
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Database Schema (Lead Table)
class LeadTable(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_type = Column(String, nullable=False)  # B2B or B2C
    fullname = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    state = Column(String, nullable=False)
    requested_amount = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    monthly_revenue = Column(Float, default=0.0)
    loan_purpose = Column(String, nullable=False)
    routing_status = Column(String, nullable=False)  # CLIENT_DIRECT or ARBITRAGE_FALLBACK
    routing_reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# FastAPI Initialization
app = FastAPI(title="Production Lead Routing Engine")

# CORS Setup for Netlify Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Swap this with your actual Netlify URL in production for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY environment variable is missing. AI generation will fail.")
ai_client = genai.Client() if GEMINI_API_KEY else None

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Schemas for API Requests ---
class LeadCreate(BaseModel):
    lead_type: str
    fullname: str
    email: EmailStr
    phone: str
    state: str
    requested_amount: float
    credit_score: int
    monthly_revenue: float = 0.0
    loan_purpose: str

# --- Background Task: Notify Client of New Direct Lead ---
def notify_client_of_lead(lead_id: int, lead_name: str, lead_phone: str):
    """
    Background task to notify your client via email, webhook, or SMS.
    Ensures the user gets a fast response without slowing down the form submission.
    """
    logger.info(f"Notification triggered for lead #{lead_id} ({lead_name}). Send email/SMS alert to client.")
    # Implement actual email/SMS API call here (e.g., SendGrid, Twilio)

# --- Live Routing API ---
@app.post("/api/v1/leads")
async def process_and_save_lead(
    lead_data: LeadCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    state_upper = lead_data.state.upper()
    target_states = ["CA", "TX", "FL"]
    
    # 1. Routing & Underwriting Logic
    routing_status = "ARBITRAGE_FALLBACK"
    routing_reason = ""
    
    if state_upper not in target_states:
        routing_reason = f"State {state_upper} is outside the client's direct lending territory."
    elif lead_data.lead_type.upper() == "B2C":
        if lead_data.credit_score >= 600:
            routing_status = "CLIENT_DIRECT"
            routing_reason = f"Qualified consumer lead in {state_upper} with credit score of {lead_data.credit_score}."
        else:
            routing_reason = f"B2C credit score ({lead_data.credit_score}) is below the client's minimum 600 threshold."
    elif lead_data.lead_type.upper() == "B2B":
        if lead_data.credit_score >= 620 and lead_data.monthly_revenue >= 5000:
            routing_status = "CLIENT_DIRECT"
            routing_reason = f"Qualified B2B lead in {state_upper}. Revenue is ${lead_data.monthly_revenue:,.2f}."
        else:
            routing_reason = f"B2B lead does not meet the minimum credit (620) or revenue ($5,000) threshold."
            
    # 2. Save Lead securely to Database
    db_lead = LeadTable(
        lead_type=lead_data.lead_type.upper(),
        fullname=lead_data.fullname,
        email=lead_data.email,
        phone=lead_data.phone,
        state=state_upper,
        requested_amount=lead_data.requested_amount,
        credit_score=lead_data.credit_score,
        monthly_revenue=lead_data.monthly_revenue,
        loan_purpose=lead_data.loan_purpose,
        routing_status=routing_status,
        routing_reason=routing_reason
    )
    
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    
    # 3. Handle Notification or External Posting
    if routing_status == "CLIENT_DIRECT":
        background_tasks.add_task(notify_client_of_lead, db_lead.id, db_lead.fullname, db_lead.phone)
        return {
            "status": "success",
            "routing": "DIRECT_TO_CLIENT",
            "message": "Lead saved and client underwriting team notified.",
            "lead_id": db_lead.id
        }
    else:
        # Future-proof: This is where your code will automatically sell the lead to Lendio/Leadsmarket APIs
        logger.info(f"Lead #{db_lead.id} marked for external sale to maximize profit.")
        return {
            "status": "success",
            "routing": "FALLBACK_MARKETPLACE",
            "message": "Lead processed. Sent to secondary underwriting networks.",
            "lead_id": db_lead.id
        }