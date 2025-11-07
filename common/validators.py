from datetime import date
from rest_framework.exceptions import ValidationError

def validate_age(token_payload):
    birthdate_str = token_payload.get("birthdate")
    if not birthdate_str:
        raise ValidationError("Укажите дату рождения, чтобы создать продукт.")
    
    birthdate = date.fromisoformat(birthdate_str)
    today = date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    
    if age < 18:
        raise ValidationError("Вам должно быть 18 лет, чтобы создать продукт.")
