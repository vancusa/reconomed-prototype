# populate_test_patients.py
import sys
sys.path.append('/workspaces/reconomed-prototype')

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Patient, User
import uuid
from datetime import datetime, timedelta
import random

def clear_patients(db: Session):
    """Delete all patients from database"""
    db.query(Patient).delete()
    db.commit()
    print("✓ Cleared all patients")

def get_demo_clinic_id(db: Session):
    """Get the demo clinic ID"""
    demo_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not demo_user:
        raise Exception("Demo user not found - run initial setup first")
    return demo_user.clinic_id

def generate_cnp(birth_date, gender='M'):
    """Generate Romanian CNP"""
    year = birth_date.year
    month = birth_date.month
    day = birth_date.day
    
    # Gender digit (1=male 1900-1999, 2=female 1900-1999, 5=male 2000+, 6=female 2000+)
    if year >= 2000:
        gender_digit = '5' if gender == 'M' else '6'
    else:
        gender_digit = '1' if gender == 'M' else '2'
    
    # Format: SYYMMDDJJNNNC
    cnp = f"{gender_digit}{year%100:02d}{month:02d}{day:02d}01{random.randint(100,999)}"
    # Simplified - not calculating actual checksum
    cnp += str(random.randint(0,9))
    return cnp

def create_test_patients(db: Session, clinic_id: str):
    """Create 30 test patients with Romanian names"""
    
    # Romanian names with intentional similarities for search testing
    patients_data = [
        # Similar names for search testing
        ("Ion", "Ionescu", "M"),
        ("Maria", "Ionescu", "F"),
        ("Ion", "Ionașcu", "M"),
        ("Maria", "Mihalaș", "F"),
        ("Ioan", "Ionescu", "M"),
        ("Mariana", "Ionescu", "F"),
        
        # Common Romanian names
        ("Andrei", "Popescu", "M"),
        ("Elena", "Popescu", "F"),
        ("Mihai", "Georgescu", "M"),
        ("Ana", "Dumitrescu", "F"),
        ("Alexandru", "Popa", "M"),
        ("Ioana", "Stan", "F"),
        ("Gheorghe", "Radu", "M"),
        ("Carmen", "Marin", "F"),
        ("Vasile", "Constantinescu", "M"),
        ("Daniela", "Niculescu", "F"),
        ("Cristian", "Stoica", "M"),
        ("Gabriela", "Dinu", "F"),
        ("Florin", "Ungureanu", "M"),
        ("Simona", "Barbu", "F"),
        
        # More variety
        ("Stefan", "Moldovan", "M"),
        ("Roxana", "Matei", "F"),
        ("Adrian", "Tudor", "M"),
        ("Oana", "Luca", "F"),
        ("Bogdan", "Ciobanu", "M"),
        ("Andreea", "Nistor", "F"),
        ("Catalin", "Munteanu", "M"),
        ("Diana", "Olteanu", "F"),
        ("Razvan", "Ionita", "M"),
        ("Laura", "Dobre", "F"),
    ]
    
    phone_prefixes = ["0721", "0722", "0731", "0732", "0740", "0741", "0751"]
    
    for i, (given_name, family_name, gender) in enumerate(patients_data):
        # Random birth date between 1940 and 2010
        birth_year = random.randint(1940, 2010)
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birth_date = datetime(birth_year, birth_month, birth_day).date()
        
        # 80% have complete data, 20% have missing data
        has_complete_data = random.random() < 0.8
        
        patient = Patient(
            id=str(uuid.uuid4()),
            clinic_id=clinic_id,
            family_name=family_name,
            given_name=given_name,
            birth_date=birth_date,
            cnp=generate_cnp(birth_date, gender) if has_complete_data else None,
            insurance_number=f"INS{random.randint(100000, 999999)}" if has_complete_data else None,
            insurance_house="CNAS" if has_complete_data else None,
            phone=f"{random.choice(phone_prefixes)}{random.randint(100000, 999999)}" if has_complete_data else None,
            email=f"{given_name.lower()}.{family_name.lower()}@email.ro" if random.random() < 0.7 else None,
            address={"city": "București", "street": f"Strada Exemplu {i+1}"} if has_complete_data else {},
            gdpr_consents={
                "treatment": {
                    "granted": True,
                    "granted_at": datetime.utcnow().isoformat(),
                    "consent_type": "treatment",
                    "legal_basis": "consent"
                },
                "data_processing": {
                    "granted": True,
                    "granted_at": datetime.utcnow().isoformat(),
                    "consent_type": "data_processing",
                    "legal_basis": "consent"
                }
            }
        )
        db.add(patient)
    
    db.commit()
    print("✓ Created 30 test patients with Romanian names")
    print("  - Similar names for search testing: Ion Ionescu, Maria Ionescu, Ion Ionașcu, Maria Mihalaș")
    print("  - ~80% with complete data (CNP, phone, insurance)")
    print("  - ~20% with missing data for testing edge cases")

def main():
    db = SessionLocal()
    try:
        clinic_id = get_demo_clinic_id(db)
        print(f"Using clinic ID: {clinic_id}")
        
        clear_patients(db)
        create_test_patients(db, clinic_id)
        
        count = db.query(Patient).count()
        print(f"\n✓ Done! Total patients in database: {count}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()