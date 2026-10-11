# ============================================================================
# Imports
# ============================================================================
import json
import re
# ====================================================================================================
# ============================================================================
# load users from json
# ============================================================================
try:
    with open("users.json", 'r') as file:
        users = json.load(file)
except FileNotFoundError:
    users = []
except json.JSONDecodeError:
    users = []
# ====================================================================================================
# Validations
# ====================================================================================================
# ------------------------------------------------
# Name Validation
# ------------------------------------------------
def name_validation(name):
    register_attempts = 3
    while len(name) < 3 or len(name) > 100:
        if register_attempts > 0:
            print("name must be between 3 and 100 characters")
            name = input("Enter your name: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return name
# ------------------------------------------------
# Email Validation
# ------------------------------------------------
email_regex = re.compile(r"\w+@\w+\.\w+$")
def email_validation(email):
    match_email = re.match(email_regex, email)
    register_attempts = 3
    while len(email) < 4 or len(email) > 100 or match_email is None:
        if register_attempts > 0:
            print("Invalid email")
            email = input("Enter your email: ").lower()
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return email
# ------------------------------------------------
# Phone Validation
# ------------------------------------------------
def phone_validation(phone):
    register_attempts = 3
    while len(phone) < 4 or len(phone) > 100:
        if register_attempts > 0:
            print("Invalid phone number")
            phone = input("Enter your phone number: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return phone
# ------------------------------------------------
# Age Validation
# ------------------------------------------------
def age_validation(age):
    register_attempts = 3
    while age < 16 or age > 55:
        if register_attempts > 0:
            print("Invalid age")
            age = input("Enter your age: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return age
# ------------------------------------------------
# Gender Validation
# ------------------------------------------------
def gender_validation(gender):
    register_attempts = 3
    while gender not in ["male", "female"]:
        if register_attempts > 0:
            print("Invalid gender")
            gender = input("Enter your gender: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return gender
# ------------------------------------------------
# National ID Validation
# ------------------------------------------------
def national_id_validation(national_id):
    register_attempts = 3
    while len(national_id) != 14 or not national_id.isdigit():
        if register_attempts > 0:
            print("Invalid national id")
            national_id = input("Enter your national id: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return national_id
# ------------------------------------------------
# Password Validation
# ------------------------------------------------
def password_validation(password, confirm_password):
    register_attempts = 3
    while len(password) < 8 or len(password) > 100 or password != confirm_password:
        if register_attempts > 0:
            print("Invalid password")
            password = input("Enter your password: ")
            confirm_password = input("Confirm your password: ")
            register_attempts -= 1
            continue
        else:
            print("Too many invalid attempts. Returning.... to Home page.")
            return None
    return password
# ====================================================================================================
# ============================================================================
# Login
# ============================================================================
current_user = None
def login():
    global current_user
    login_email = input("Enter your email: ").lower()
    login_password = input("Enter your password: ")
    for user in users:
        if user['email'] == login_email and user['password'] == login_password:
            current_user = user
            if current_user['role'] == "admin":
                print(f"Login successful, Welcome MR.{current_user['name']}.")
            else:
                print(f"Login successful, Welcome Back {current_user['name']}.")
            return current_user
    print("Email or Password is not valid. Returning.... to Home page.")
    return None

# ============================================================================
# Register
# ============================================================================
def register_user():
    while True:
        try:
            entered_name = input("Enter your name: ")
            entered_email = input("Enter your email: ").lower()
            entered_phone = input("Enter your phone number: ")
            entered_age = int(input("Enter your age: "))
            entered_gender = input("Enter your gender: ").lower()
            entered_governorate = input("Enter your governorate: ").upper()
            entered_national_id = input("Enter your national id: ")
            entered_password = input("Enter your password: ")
            confirmed_password = input("Confirm your password: ")
            # ------------------ Validation of name ------------------
            valid_name = name_validation(entered_name)
            if valid_name is None:
                continue
            # ------------------ Validation of email ------------------
            valid_email = email_validation(entered_email)
            if valid_email is None:
                continue
            # ------------------ Validation of phone ------------------
            valid_phone = phone_validation(entered_phone)
            if valid_phone is None:
                continue
            # ------------------- Validation of age -------------------
            valid_age = age_validation(entered_age)
            if valid_age is None:
                continue
            # ------------------ Validation of gender ------------------
            valid_gender = gender_validation(entered_gender)
            if valid_gender is None:
                continue
            # ----------------- Validation of national id -----------------
            valid_national_id = national_id_validation(entered_national_id)
            if valid_national_id is None:
                continue
            # ----------------- Validation of password -----------------
            valid_password = password_validation(entered_password, confirmed_password)
            if valid_password is None:
                continue
            new_user ={
                    'name' : valid_name,
                    'email' : valid_email,
                    'phone' : valid_phone,
                    'age' : valid_age,
                    'gender' : valid_gender,
                    'governorate' : entered_governorate,
                    'national_id' : valid_national_id,
                    'password' : valid_password,
                    'role' : "user",
            }
            users.append(new_user)

            with open('users.json', 'w') as f:
                json.dump(users, f, indent=4)
            print("Registration successful.")
            break
        except ValueError:
            print("Invalid input. Returning.... to Home page.")