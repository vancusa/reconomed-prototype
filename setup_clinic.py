"""Setup script for initial clinic and admin user"""
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal, create_tables
from app.models import Clinic, User
from app.auth import get_password_hash

def setup_initial_data():
    """Create initial clinic and admin user"""
    create_tables()
    db = SessionLocal()
    
    try:
        # Check if setup already done
        existing_clinic = db.query(Clinic).first()
        if existing_clinic:
            print("Setup already completed!")
            return
        
        # Create initial clinic
        clinic = Clinic(
            name="Demo Clinic",
            country="RO",
            gdpr_templates={
                "consent_types": [
                    {"id": "treatment", "name_ro": "Îngrijire medicală", "name_en": "Medical treatment"},
                    {"id": "data_processing", "name_ro": "Prelucrare date", "name_en": "Data processing"}
                ]
            }
        )
        db.add(clinic)
        db.commit()
        db.refresh(clinic)
        
        # Create admin user
        admin_user = User(
            email="admin@reconomed.ro",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            role="admin",
            clinic_id=clinic.id,
            specialties=[]
        )
        db.add(admin_user)
        
        # Create demo doctor
        doctor_user = User(
            email="doctor@reconomed.ro",
            hashed_password=get_password_hash("doctor123"),
            full_name="Dr. Ionescu",
            role="doctor",
            clinic_id=clinic.id,
            specialties=["internal_medicine", "cardiology"]
        )
        db.add(doctor_user)
        
        db.commit()
        
        print(f"Setup completed!")
        print(f"Clinic ID: {clinic.id}")
        print(f"Admin login: admin@reconomed.ro / admin123")
        print(f"Doctor login: doctor@reconomed.ro / doctor123")
        
    except Exception as e:
        print(f"Setup failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    setup_initial_data()