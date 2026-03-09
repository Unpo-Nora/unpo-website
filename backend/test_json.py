from app.database import SessionLocal
from app import models, schemas
import json
from fastapi.encoders import jsonable_encoder

def test_serialization():
    db = SessionLocal()
    lead = db.query(models.Lead).first()
    if not lead:
        print("No leads found in DB")
        return
    
    print(f"Lead ID: {lead.id}")
    print(f"Lead status type: {type(lead.status)}")
    print(f"Lead status value: {lead.status}")
    
    # Simulate Pydantic validation
    pydantic_lead = schemas.LeadResponse.model_validate(lead)
    print(f"Pydantic status: {pydantic_lead.status}")
    
    # Simulate FastAPI JSON encoding
    encoded = jsonable_encoder(pydantic_lead)
    print(f"Encoded status: {encoded['status']}")
    print(f"Encoded JSON: {json.dumps(encoded, indent=2)}")

if __name__ == "__main__":
    test_serialization()
