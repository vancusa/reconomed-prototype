"""Romanian-specific validation utilities"""
import re
from datetime import datetime
from typing import Optional, Tuple

def validate_cnp(cnp: str) -> Tuple[bool, Optional[str]]:
    """Validate Romanian CNP (Cod Numeric Personal)"""
    if not cnp or len(cnp) != 13:
        return False, "CNP must be exactly 13 digits"
    
    if not cnp.isdigit():
        return False, "CNP must contain only digits"
    
    # Check birth date validity
    try:
        year_digits = int(cnp[1:3])
        month = int(cnp[3:5])
        day = int(cnp[5:7])
        
        # Determine century based on first digit
        first_digit = int(cnp[0])
        if first_digit in [1, 2]:  # 1900-1999
            year = 1900 + year_digits
        elif first_digit in [3, 4]:  # 1800-1899
            year = 1800 + year_digits
        elif first_digit in [5, 6]:  # 2000-2099
            year = 2000 + year_digits
        else:
            return False, "Invalid CNP first digit"
        
        # Validate date
        datetime(year, month, day)
        
        # Check if birth date is reasonable
        current_year = datetime.now().year
        if year > current_year or year < 1800:
            return False, "Invalid birth year in CNP"
            
    except ValueError:
        return False, "Invalid birth date in CNP"
    
    # CNP checksum validation
    weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
    checksum = sum(int(cnp[i]) * weights[i] for i in range(12)) % 11
    checksum = 1 if checksum == 10 else checksum
    
    if checksum != int(cnp[12]):
        return False, "Invalid CNP checksum"
    
    return True, None

def extract_birth_date_from_cnp(cnp: str) -> Optional[str]:
    """Extract birth date from valid CNP"""
    is_valid, _ = validate_cnp(cnp)
    if not is_valid:
        return None
    
    year_digits = int(cnp[1:3])
    month = int(cnp[3:5])
    day = int(cnp[5:7])
    
    # Determine century
    first_digit = int(cnp[0])
    if first_digit in [1, 2]:
        year = 1900 + year_digits
    elif first_digit in [3, 4]:
        year = 1800 + year_digits
    elif first_digit in [5, 6]:
        year = 2000 + year_digits
    
    return f"{year:04d}-{month:02d}-{day:02d}"

def extract_gender_from_cnp(cnp: str) -> Optional[str]:
    """Extract gender from valid CNP"""
    is_valid, _ = validate_cnp(cnp)
    if not is_valid:
        return None
    
    first_digit = int(cnp[0])
    return "M" if first_digit in [1, 3, 5] else "F"

def validate_romanian_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate Romanian phone number"""
    if not phone:
        return True, None  # Optional field

    # Basic sanity check - just ensure it's not obviously wrong
    if len(phone.strip()) < 5:
        return False, "Phone number too short"

    return True, None  # Accept everything else

def validate_insurance_number(insurance_number: str) -> Tuple[bool, Optional[str]]:
    """Validate Romanian insurance number"""
    if not insurance_number:
        return True, None  # Optional field
    
    # Remove spaces
    clean_number = insurance_number.replace(' ', '')
    
    # Basic format validation (adjust based on actual CNAS format)
    if len(clean_number) < 8 or len(clean_number) > 15:
        return False, "Insurance number must be 8-15 characters"
    
    if not clean_number.isalnum():
        return False, "Insurance number must contain only letters and numbers"
    
    return True, None

def normalize_romanian_address(address_data: dict) -> dict:
    """Normalize Romanian address format"""
    if not address_data:
        return {}
    
    normalized = {
        "street": address_data.get("street", "").strip(),
        "number": address_data.get("number", "").strip(),
        "apartment": address_data.get("apartment", "").strip(),
        "city": address_data.get("city", "").strip(),
        "county": address_data.get("county", "").strip(),
        "postal_code": address_data.get("postal_code", "").strip(),
        "country": address_data.get("country", "Romania")
    }
    
    return {k: v for k, v in normalized.items() if v}

def normalize_phone_for_search(phone: str) -> str:
    """Normalize phone number for search matching"""
    #-------------VERSION 1, for next versions, let's revisit this ------------------
    if not phone:
        return ""
    
    # Remove all non-digits
    digits_only = re.sub(r'\D', '', phone)
    
    # Handle Romanian country code variations
    if digits_only.startswith('40'):
        digits_only = digits_only[2:]  # Remove country code
    
    # Handle leading zero
    if digits_only.startswith('0'):
        digits_only = digits_only[1:]  # Remove leading zero
    
    return digits_only

