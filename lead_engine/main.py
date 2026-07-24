import os
import re
import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ==========================================
# DATABASE CONFIGURATION
# ==========================================
# Replace with your actual PostgreSQL URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/leaddb")

# SQLAlchemy requires "postgresql://" but some providers use "postgres://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
# SQLAlchemy Model
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_type = Column(String(10), index=True)
    fullname = Column(String(150))
    email = Column(String(150))
    phone = Column(String(20))
    state = Column(String(5))
    requested_amount = Column(Float)
    credit_score = Column(Integer)
    monthly_revenue = Column(Float)
    loan_purpose = Column(String(100))
    routing_status = Column(String(50))
    routing_destination = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ==========================================
# PYDANTIC SCHEMAS (WITH STRICT VALIDATION)
# ==========================================
class LeadCreateSchema(BaseModel):
    lead_type: str
    fullname: str
    email: EmailStr  # Automatically enforces standard email protocol validation
    phone: str
    state: str
    requested_amount: float
    credit_score: int
    monthly_revenue: float
    loan_purpose: str

    @field_validator('phone')
    @classmethod
    def validate_and_format_phone(cls, value):
        clean_phone = re.sub(r'\D', '', value)
        
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]
            
        if len(clean_phone) != 10:
            raise ValueError('Must be a valid 10-digit US phone number')
            
        return f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}"

class LeadResponseSchema(BaseModel):
    id: int
    routing_status: str
    message: str

    class Config:
        from_attributes = True

# ==========================================
# ROUTING LOGIC (ALL 50 STATES)
# ==========================================
def evaluate_underwriting_and_route(lead: LeadCreateSchema) -> tuple:
    state_upper = lead.state.strip().upper()
    
    if lead.lead_type == "B2B":
        min_credit = 600
        min_revenue = 10000.00
        
        if lead.credit_score >= min_credit and lead.monthly_revenue >= min_revenue:
            return (
                "DIRECT_TO_CLIENT",
                "Internal Direct Portfolio Lending Desk",
                f"Qualified Commercial B2B Account in {state_upper}."
            )
        else:
            return (
                "HELD_IN_DATABASE", 
                "Pending Client Review",
                f"Commercial criteria unfulfilled in {state_upper}: Pending Review."
            )
            
    else:  # Consumer Personal Emergency B2C Portfolio
        max_amount = 10000.00
        min_credit = 640
        
        if lead.credit_score >= min_credit and lead.requested_amount <= max_amount:
            return (
                "DIRECT_TO_CLIENT",
                "Internal Direct Portfolio Lending Desk",
                f"Qualified Personal B2C profile in {state_upper}."
            )
        else:
            return (
                "HELD_IN_DATABASE",
                "Pending Client Review",
                f"Consumer thresholds adjusted in {state_upper}: Pending Review."
            )

# ==========================================
# FASTAPI APP SETUP & ENDPOINTS
# ==========================================
app = FastAPI(title="Secure Lead Routing Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to your Netlify/Vercel URL in production
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

@app.post("/api/v1/leads", status_code=status.HTTP_201_CREATED, response_model=LeadResponseSchema)
def submit_lead(lead: LeadCreateSchema, db: Session = Depends(get_db)):
    
    # 1. Process Logic
    routing_status, routing_dest, routing_message = evaluate_underwriting_and_route(lead)
    
    # 2. Database Insertion
    new_lead = Lead(
        lead_type=lead.lead_type,
        fullname=lead.fullname,
        email=lead.email,
        phone=lead.phone,
        state=lead.state.upper(),
        requested_amount=lead.requested_amount,
        credit_score=lead.credit_score,
        monthly_revenue=lead.monthly_revenue,
        loan_purpose=lead.loan_purpose,
        routing_status=routing_status,
        routing_destination=routing_dest
    )
    
    try:
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database save failed.")
    
    # 3. Return Success (Which triggers Google Ads Tracking)
    return LeadResponseSchema(
        id=new_lead.id,
        routing_status=routing_status,
        message=routing_message
    )