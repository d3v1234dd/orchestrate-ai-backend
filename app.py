import os
import datetime
import pytz
from urllib.parse import quote
import google.generativeai as genai
from flask import Flask, request, redirect, session, url_for
from flask_cors import CORS
from requests_oauthlib import OAuth2Session
from supabase import create_client, Client

# --- Configuration (Now read securely from Environment Variables) ---
CLIENT_ID = os.getenv("950227819866-f1tv7vd3u2eils74s2k3an7gru5pvbfe.apps.googleusercontent.com")
CLIENT_SECRET = os.getenv("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")
REDIRECT_URI = os.getenv("http://localhost:5000/callback")
GEMINI_API_KEY = os.getenv("AIzaSyAqKenzaNi4udgTtEhofXLR99KqPt05BmM")
FRONTEND_URL = os.getenv("http://localhost:5173")
SUPABASE_URL = os.getenv("https://gwanvqkoiwhiquithzxf.supabase.co")
SUPABASE_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3YW52cWtvaXdoaXF1aXRoenhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgyMDg2NTUsImV4cCI6MjA3Mzc4NDY1NX0.5RSl2YuG0x7DCeqdHq_edrZVzu9CN0BDH69ZovEdAKY")
FLASK_SECRET_KEY = os.getenv("5466fb330c42cb6d76d3fe3fc2b4bbaa", os.urandom(24)) # Use Render's key, or a random one for local

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- App Setup ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Scopes ---
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/gmail.readonly'
]

# --- Routes (The logic inside is identical) ---
@app.route('/login')
def login():
    google = OAuth2Session(CLIENT_ID, scope=SCOPES, redirect_uri=REDIRECT_URI)
    authorization_url, state = google.authorization_url('https://accounts.google.com/o/oauth2/v2/auth', access_type='offline', prompt='select_account')
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=session.get('oauth_state'))
    token = google.fetch_token('https://oauth2.googleapis.com/token', client_secret=CLIENT_SECRET, authorization_response=request.url)
    session['oauth_token'] = token
    
    user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
    user_email = user_info.get('email')

    response = supabase.table('users').select('id').eq('email', user_email).execute()
    if not response.data:
        insert_response = supabase.table('users').insert({'email': user_email, 'subscription_status': 'free'}).execute()
        session['user_id'] = insert_response.data[0]['id']
    else:
        session['user_id'] = response.data[0]['id']
        
    return redirect(FRONTEND_URL)

@app.route('/profile')
def profile():
    if 'oauth_token' not in session:
        return {"error": "Not authenticated"}, 401

    google = OAuth2Session(CLIENT_ID, token=session['oauth_token'])
    user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
    email = user_info.get('email', 'User')

    # ... (The rest of the logic for fetching data and calling the AI is exactly the same)
    timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(timezone)
    time_min_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max_dt = time_min_dt + datetime.timedelta(days=1)
    time_min_iso = time_min_dt.isoformat()
    time_max_iso = time_max_dt.isoformat()
    calendar_api_url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={quote(time_min_iso)}&timeMax={quote(time_max_iso)}&singleEvents=true&orderBy=startTime"
    calendar_response = google.get(calendar_api_url).json()
    events = calendar_response.get('items', [])
    
    event_details = []
    if not events:
        event_text = "No events scheduled."
    else:
        # ... processing logic ...
        event_text = "\n".join(event_details)

    gmail_api_url = "https://www.googleapis.com/gmail/v1/users/me/messages"
    # ... processing logic ...
    email_text = "\n".join(email_subjects) if email_subjects else "No important emails found in the last 24 hours."

    prompt = f"""
    You are Orchestrate AI...
    Here are today's calendar events:
    {event_text}
    Here are the subjects of important emails from the last 24 hours:
    {email_text}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        ai_summary = response.text
    except Exception as e:
        return {"error": "Could not generate AI summary.", "details": str(e)}, 500

    return {
        "email": email,
        "briefing": ai_summary
    }


After you've updated `app.py`, pushed it to GitHub, and added all the environment variables on Render, you are ready to click **`Create Web Service`**.