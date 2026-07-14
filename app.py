import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from google import genai
from google.genai import types

app = FastAPI(title="AI-Powered Lead & Outreach Engine")

# Enable CORS so your Netlify frontend can safely communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Gemini Client (Make sure GEMINI_API_KEY is in your environment)
# For testing without a key, you can handle the exception gracefully
try:
    ai_client = genai.Client()
except Exception:
    ai_client = None
    print("Warning: GEMINI_API_KEY not found. AI features will run in demo mode.")

# --- DATA STRUCTURES ---
class LeadInput(BaseModel):
    lead_type: str        # "B2C" (Consumer) or "B2B" (Business)
    fullname: str
    email: EmailStr
    phone: str
    state: str           # "CA", "TX", "FL"
    requested_amount: float
    credit_score: int
    monthly_revenue: float = 0.0
    loan_purpose: str    # e.g., "car_repair", "home_repair", "medical", "working_capital"

# --- CORE ROUTING ENGINE ---
@app.post("/api/route-lead")
async def route_lead(lead: LeadInput):
    """
    Evaluates incoming leads from Netlify and decides whether to send them 
    directly to your client or monetize them via fallback affiliate networks.
    """
    state_upper = lead.state.upper()
    target_states = ["CA", "TX", "FL"]
    
    # Rule 1: Direct Geofencing
    if state_upper not in target_states:
        return {
            "status": "ARBITRAGE_FALLBACK",
            "destination": "Leadsmarket / Lead Stack Media",
            "reason": f"Target states are CA, TX, FL. Lead is from {state_upper}.",
            "estimated_payout": "$15.00 - $45.00"
        }
    
    # Rule 2: Underwriting for Consumer Emergency Loans (B2C)
    if lead.lead_type.upper() == "B2C":
        if lead.credit_score >= 600:
            return {
                "status": "CLIENT_DIRECT_FUNDING",
                "destination": "Client Internal Sales CRM",
                "reason": f"High-intent consumer emergency lead in {state_upper} with qualifying credit ({lead.credit_score}).",
                "estimated_value": f"High Margin (Interest from ${lead.requested_amount:,.2f} loan)"
            }
        else:
            return {
                "status": "ARBITRAGE_FALLBACK",
                "destination": "Payday / High-Risk Lending Network",
                "reason": f"Credit score ({lead.credit_score}) below client B2C minimum threshold of 600.",
                "estimated_payout": "$25.00"
            }
            
    # Rule 3: Underwriting for Commercial Business Funding (B2B)
    elif lead.lead_type.upper() == "B2B":
        if lead.credit_score >= 620 and lead.monthly_revenue >= 5000:
            return {
                "status": "CLIENT_DIRECT_FUNDING",
                "destination": "Client Commercial MCA Desk",
                "reason": f"Qualified B2B emergency lead. Revenue (${lead.monthly_revenue:,.2f}) and Credit ({lead.credit_score}) meet direct funding criteria.",
                "estimated_value": f"Premium Commercial Asset"
            }
        else:
            return {
                "status": "ARBITRAGE_FALLBACK",
                "destination": "Lendio / Alternative B2B Marketplaces",
                "reason": "Business revenue or credit score falls below primary direct underwriting standards.",
                "estimated_payout": "$120.00 - $350.00"
            }

    raise HTTPException(status_code=400, detail="Invalid lead type. Choose B2B or B2C.")

# --- AI MARKETING GENERATOR ---
@app.get("/api/generate-trigger-marketing")
async def generate_trigger_marketing(event_description: str, state: str):
    """
    Uses Gemini to instantly generate localized ad copy and outreach assets 
    based on real-time emergencies or local economic triggers.
    """
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