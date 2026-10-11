# ============================================================================
# Imports
# ============================================================================
from login_and_register import login, register_user
# ====================================================================================================
while True:
    print("Welcome to our project") # Will be changed :)
    print("[1] Login")
    print("[2] Register")
    print("[3] Quit")
    try:
            choice1 = int(input("-> "))
            if choice1 == 1:
                current_user = login()
            elif choice1 == 2:
                register_user()
                break
            elif choice1 == 3:
                print("Closing")
                break
            else:
                print("Please enter a number between 1 and 3.")
    except ValueError:
            print("Invalid choice! Please enter a number between 1 and 3.")
            continue