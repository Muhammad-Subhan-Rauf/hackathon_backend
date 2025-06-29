import requests
import json
import time
from datetime import datetime, timedelta, date, time as time_obj

# --- Configuration ---
BASE_URL = "http://127.0.0.1:5000"

# --- Test Data ---
DRIVER_DATA = { "email": "driver@formanite.fccollege.edu.pk", "fullName": "Dana Driver", "password": "SecurePassword123" }
RIDER_DATA = { "email": "rider@fccollege.edu.pk", "fullName": "Riley Rider", "password": "SafePassword456" }

# --- State Management ---
state = {}

# --- Helper Functions ---
def print_test_case(name): print(f"\n--- 🧪 TESTING: {name} ---\n")
def print_result(success, message): print(f"✅ PASS: {message}" if success else f"❌ FAIL: {message}")

def test_endpoint(description, method, url, expected_status, headers=None, data=None):
    try:
        response = requests.request(method, url, headers=headers, json=data)
        if response.status_code == expected_status:
            print_result(True, f"({method} {url}) - {description} [Status: {response.status_code}]")
            try: return response.json()
            except json.JSONDecodeError: return None
        else:
            error_details = ""
            try: error_details = response.json().get('error', response.text)
            except json.JSONDecodeError: error_details = response.text
            print_result(False, f"({method} {url}) - {description} [Expected: {expected_status}, Got: {response.status_code}] - Details: {error_details}")
            return None
    except requests.exceptions.RequestException as e:
        print_result(False, f"({method} {url}) - {description} [Request failed: {e}]")
        return None

# --- Test Suites ---
def test_auth_flow():
    print_test_case("User Registration and Login")
    driver_res = test_endpoint("Register a new driver", "POST", f"{BASE_URL}/auth/register", 201, data=DRIVER_DATA)
    if driver_res: state['driver_id'] = driver_res['user_id']
    rider_res = test_endpoint("Register a new rider", "POST", f"{BASE_URL}/auth/register", 201, data=RIDER_DATA)
    if rider_res: state['rider_id'] = rider_res['user_id']
    test_endpoint("Fail to register with non-university email", "POST", f"{BASE_URL}/auth/register", 400, data={**DRIVER_DATA, "email": "hacker@gmail.com"})
    login_res_driver = test_endpoint("Login as driver", "POST", f"{BASE_URL}/auth/login", 200, data={"email": DRIVER_DATA['email'], "password": DRIVER_DATA['password']})
    if login_res_driver: state['driver_tokens'] = login_res_driver
    login_res_rider = test_endpoint("Login as rider", "POST", f"{BASE_URL}/auth/login", 200, data={"email": RIDER_DATA['email'], "password": RIDER_DATA['password']})
    if login_res_rider: state['rider_tokens'] = login_res_rider

def test_profile_and_role_management():
    print_test_case("User Profile and Role Management")
    driver_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    test_endpoint("Update user role to 'driver'", "PUT", f"{BASE_URL}/users/me", 200, headers=driver_headers, data={"role": "driver"})

    # Test driver location update
    location_data = {"lat": 31.478, "lng": 74.39}
    test_endpoint("Update driver's current location", "PUT", f"{BASE_URL}/users/me/location", 200, headers=driver_headers, data=location_data)

    # Verify the location was set
    profile_res = test_endpoint("Get updated profile to verify location", "GET", f"{BASE_URL}/users/me", 200, headers=driver_headers)
    if profile_res:
        lat_ok = profile_res.get('current_lat') == location_data['lat']
        lng_ok = profile_res.get('current_lng') == location_data['lng']
        if lat_ok and lng_ok:
            print_result(True, "Driver location was successfully updated and verified.")
        else:
            print_result(False, f"Driver location verification failed. Got lat: {profile_res.get('current_lat')}, lng: {profile_res.get('current_lng')}")

def test_ride_management_and_booking():
    print_test_case("Ride Creation, Search, and Booking")
    driver_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    rider_headers = {"Authorization": f"Bearer {state['rider_tokens']['access_token']}"}
    ride_data = {"origin_name": "DHA Phase 5", "destination_name": "FCCU", "departure_time": (datetime.utcnow() + timedelta(days=1)).isoformat(), "total_seats": 3}
    ride_res = test_endpoint("Driver creates a ride", "POST", f"{BASE_URL}/rides", 201, headers=driver_headers, data=ride_data)
    if ride_res: state['ride_id'] = ride_res['ride_id']
    
    # Update status to 'in_progress' to test if search still finds it
    test_endpoint("Driver updates ride status to in_progress", "PUT", f"{BASE_URL}/rides/{state['ride_id']}", 200, headers=driver_headers, data={"status": "in_progress"})
    
    search_res = test_endpoint("Search for the ride", "GET", f"{BASE_URL}/rides?destination=FCCU", 200)
    if search_res and any(r['id'] == state['ride_id'] for r in search_res):
        print_result(True, "Ride was found in search results even with 'in_progress' status")
    else:
        print_result(False, "Ride was NOT found in search results")

    test_endpoint("Rider books a seat", "POST", f"{BASE_URL}/rides/{state['ride_id']}/bookings", 201, headers=rider_headers, data={"pickup_point_name": "Midway"})

def test_policies_and_safety():
    print_test_case("Policies, Penalties, and Safety")
    driver_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    ride_to_cancel = test_endpoint("Create a ride to be cancelled", "POST", f"{BASE_URL}/rides", 201, headers=driver_headers, data={"origin_name": "Test", "destination_name": "Test", "departure_time": (datetime.utcnow() + timedelta(days=2)).isoformat(), "total_seats": 1})
    if ride_to_cancel:
        test_endpoint("Driver cancels ride, triggering penalty", "DELETE", f"{BASE_URL}/rides/{ride_to_cancel['ride_id']}", 200, headers=driver_headers)

def test_recurring_rides_and_advanced_search():
    print_test_case("Recurring Rides and Advanced Search")
    driver_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    weekdays = [0, 1, 2, 3, 4]  # Mon-Fri
    recurring_data = {"origin_name": "Recurring Origin", "destination_name": "Recurring Destination", "departure_time_of_day": "09:30:00", "days_of_week": weekdays, "total_seats": 2}
    res = test_endpoint("Create a recurring ride", "POST", f"{BASE_URL}/rides/recurring", 201, headers=driver_headers, data=recurring_data)
    assert res and res.get('generated_rides_count', 0) > 0, "No ride instances were generated"

    # --- FIX: Find the next valid weekday to make the test robust ---
    first_valid_date = None
    today = date.today()
    for i in range(8):
        future_date = today + timedelta(days=i)
        # Check if the day is in our list and if the time hasn't already passed for today
        if future_date.weekday() in weekdays:
            if future_date == today and datetime.now().time() > time_obj(9, 30):
                continue # Skip today if it's too late
            first_valid_date = future_date
            break
    
    assert first_valid_date is not None, "Could not find a valid upcoming weekday for the test"
    
    search_dt = datetime.combine(first_valid_date, time_obj(9, 30))
    search_time_iso = search_dt.isoformat()
    
    search_res = test_endpoint(f"Search with time window on {search_time_iso}", "GET", f"{BASE_URL}/rides?time={search_time_iso}&destination=Recurring Destination", 200)
    assert search_res is not None and len(search_res) > 0, "Time-window search failed"

def test_pattern_recognition_and_recommendations():
    print_test_case("Pattern Recognition and AI Recommendations")
    driver_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    rider_headers = {"Authorization": f"Bearer {state['rider_tokens']['access_token']}"}
    pattern_ride_data = {"origin_name": "Home Base", "destination_name": "Work HQ", "departure_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(), "total_seats": 1}
    ride = test_endpoint("Create ride for pattern tracking", "POST", f"{BASE_URL}/rides", 201, headers=driver_headers, data=pattern_ride_data)
    ride_id = ride['ride_id']
    test_endpoint("Rider books pattern ride", "POST", f"{BASE_URL}/rides/{ride_id}/bookings", 201, headers=rider_headers, data={"pickup_point_name": "Midway"})
    test_endpoint("Driver completes ride to trigger pattern update", "PUT", f"{BASE_URL}/rides/{ride_id}", 200, headers=driver_headers, data={"status": "completed"})
    
    time.sleep(1) 
    test_endpoint("Driver posts another ride on same route", "POST", f"{BASE_URL}/rides", 201, headers=driver_headers, data=pattern_ride_data)
    reco_res = test_endpoint("Rider gets pattern-based recommendations", "GET", f"{BASE_URL}/ai/recommendations/patterns", 200, headers=rider_headers)
    assert reco_res is not None and len(reco_res) > 0, "No pattern-based recommendations found"

def test_token_revocation():
    print_test_case("Token Refresh and Logout")
    refresh_headers = {"Authorization": f"Bearer {state['driver_tokens']['refresh_token']}"}
    refresh_res = test_endpoint("Use refresh token", "POST", f"{BASE_URL}/auth/refresh", 200, headers=refresh_headers)
    if refresh_res: state['driver_tokens']['access_token'] = refresh_res['access_token']
    logout_headers = {"Authorization": f"Bearer {state['driver_tokens']['access_token']}"}
    test_endpoint("Logout (revoke token)", "POST", f"{BASE_URL}/auth/logout", 200, headers=logout_headers)
    test_endpoint("Fail to use revoked token", "GET", f"{BASE_URL}/users/me", 401, headers=logout_headers)

if __name__ == "__main__":
    print("🚀 Starting API Integration Test Suite 🚀")
    test_auth_flow()
    if 'driver_tokens' in state and 'rider_tokens' in state:
        test_profile_and_role_management()
        test_ride_management_and_booking()
        test_policies_and_safety()
        test_recurring_rides_and_advanced_search()
        test_pattern_recognition_and_recommendations()
        test_token_revocation()
    else:
        print("\n❌ Critical failure during authentication flow. Halting tests.")
    print("\n🏁 Test Suite Finished 🏁")