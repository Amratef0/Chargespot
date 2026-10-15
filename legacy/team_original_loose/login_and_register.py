import re

users = [
    {
        "name": "ChargeSpot Admin",
        "email": "admin@chargespot.com",
        "password": "Admin1234",
        "role": "admin"
    }
]


def name_validation(name):
    return 3 <= len(name.strip()) <= 100


def email_validation(email):
    email = email.strip().lower()
    return 4 <= len(email) <= 100 and re.fullmatch(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", email) is not None


def phone_validation(phone):
    phone = phone.strip()
    return phone.isdigit() and 7 <= len(phone) <= 15


def age_validation(age):
    return age.isdigit() and 13 <= int(age) <= 100


def gender_validation(gender):
    return gender.strip().lower() in ["male", "female"]


def national_id_validation(national_id):
    return national_id.isdigit() and len(national_id) == 14


def password_validation(password, confirm_password):
    return len(password) >= 8 and password == confirm_password


def login():
    print("\n========== Login ==========")
    email = input("Email: ").strip().lower()
    password = input("Password: ")
    for user in users:
        if user["email"] == email and user["password"] == password:
            print("\nWelcome,", user["name"])
            return user
    print("Incorrect email or password.")
    return None


def register_user():
    print("\n========== Register ==========")
    name = input("Full name: ").strip()
    if not name_validation(name):
        print("Name must contain 3 to 100 characters.")
        return None
    email = input("Email: ").strip().lower()
    if not email_validation(email):
        print("Please enter a valid email address.")
        return None
    for user in users:
        if user["email"] == email:
            print("This email is already registered.")
            return None
    phone = input("Phone number: ").strip()
    if not phone_validation(phone):
        print("Phone number must contain 7 to 15 digits.")
        return None
    age = input("Age: ").strip()
    if not age_validation(age):
        print("Age must be a number between 13 and 100.")
        return None
    gender = input("Gender (male/female): ").strip().lower()
    if not gender_validation(gender):
        print("Please enter male or female.")
        return None
    governorate = input("Governorate: ").strip().upper()
    if len(governorate) == 0:
        print("Governorate cannot be empty.")
        return None
    national_id = input("National ID (14 digits): ").strip()
    if not national_id_validation(national_id):
        print("National ID must contain exactly 14 digits.")
        return None
    password = input("Password (at least 8 characters): ")
    confirm_password = input("Confirm password: ")
    if not password_validation(password, confirm_password):
        print("Passwords must match and contain at least 8 characters.")
        return None
    user = {"name": name, "email": email, "phone": phone, "age": int(age), "gender": gender,
            "governorate": governorate, "national_id": national_id, "password": password, "role": "user"}
    users.append(user)
    print("\nRegistration successful. You can now log in.")
    return user
