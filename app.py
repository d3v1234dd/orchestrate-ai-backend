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
CLIENT_ID = "950227819866-f1tv7vd3u2eils74s2k3an7gru5pvbfe.apps.googleusercontent.com"
CLIENT_SECRET = "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"
GEMINI_API_KEY = "AIzaSyAqKenzaNi4udgTtEhofXLR99KqPt05BmM"
SUPABASE_URL = "https://gwanvqkoiwhiquithzxf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3YW52cWtvaXdoaXF1aXRoenhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgyMDg2NTUsImV4cCI6MjA3Mzc4NDY1NX0.5RSl2YuG0x7DCeqdHq_edrZVzu9CN0BDH69ZovEdAKY"
FLASK_SECRET_KEY = "5466fb330c42cb6d76d3fe3fc2b4bbaa", os.urandom(24))

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- App Setup ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Scopes ---
SCOPES = [
    '[https://www.googleapis.com/auth/userinfo.email](https://www.googleapis.com/auth/userinfo.email)', '[https://www.googleapis.com/auth/userinfo.profile](https://www.googleapis.com/auth/userinfo.profile)',
    '[https://www.googleapis.com/auth/calendar.readonly](https://www.googleapis.com/auth/calendar.readonly)', '[https://www.googleapis.com/auth/gmail.readonly](https://www.googleapis.com/auth/gmail.readonly)'
]

# --- Routes ---
@app.route('/login')
def login():
    google = OAuth2Session(CLIENT_ID, scope=SCOPES, redirect_uri=REDIRECT_URI)
    authorization_url, state = google.authorization_url('[https://accounts.google.com/o/oauth2/v2/auth](https://accounts.google.com/o/oauth2/v2/auth)', access_type='offline', prompt='select_account')
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=session.get('oauth_state'))
    token = google.fetch_token('[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)', client_secret=CLIENT_SECRET, authorization_response=request.url)
    session['oauth_token'] = token
    
    user_info = google.get('[https://www.googleapis.com/oauth2/v1/userinfo').json](https://www.googleapis.com/oauth2/v1/userinfo').json)()
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
    user_info = google.get('[https://www.googleapis.com/oauth2/v1/userinfo').json](https://www.googleapis.com/oauth2/v1/userinfo').json)()
    email = user_info.get('email', 'User')

    # Fetch Calendar Events
    timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(timezone)
    time_min_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max_dt = time_min_dt + datetime.timedelta(days=1)
    time_min_iso = time_min_dt.isoformat()
    time_max_iso = time_max_dt.isoformat()
    calendar_api_url = f"[https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=](https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=){quote(time_min_iso)}&timeMax={quote(time_max_iso)}&singleEvents=true&orderBy=startTime"
    calendar_response = google.get(calendar_api_url).json()
    events = calendar_response.get('items', [])
    
    event_details = []
    if not events:
        event_text = "No events scheduled."
    else:
        for event in events:
            summary = event.get('summary', 'No Title')
            start_info = event.get('start', {})
            if 'dateTime' in start_info:
                dt_object = datetime.datetime.fromisoformat(start_info['dateTime'])
                display_time = dt_object.strftime('%I:%M %p')
                event_details.append(f"- {summary} at {display_time}")
            else:
                event_details.append(f"- {summary} (All day)")
        event_text = "\n".join(event_details)

    # Fetch Important Emails
    gmail_api_url = "[https://www.googleapis.com/gmail/v1/users/me/messages](https://www.googleapis.com/gmail/v1/users/me/messages)"
    query = "in:inbox category:primary newer_than:1d {subject:booking OR subject:confirmation OR subject:flight OR subject:order}"
    params = {"q": query, "maxResults": 5}
    gmail_response = google.get(gmail_api_url, params=params).json()
    messages = gmail_response.get('messages', [])
    
    email_subjects = []
    if messages:
        for message in messages:
            msg_data = google.get(f"{gmail_api_url}/{message['id']}?format=metadata&metadataHeaders=subject").json()
            subject_header = next((header for header in msg_data['payload']['headers'] if header['name'].lower() == 'subject'), None)
            if subject_header:
                email_subjects.append(f"- {subject_header['value']}")
    
    email_text = "\n".join(email_subjects) if email_subjects else "No important emails found in the last 24 hours."

    # Create the AI Prompt
    prompt = f"""You are Orchestrate AI, a helpful and friendly personal assistant for {email}. Your task is to provide a short, conversational summary of their day. Combine information from their calendar and important emails into a single, helpful briefing. Start with a friendly greeting.

Here are today's calendar events:
{event_text}

Here are the subjects of important emails from the last 24 hours:
{email_text}"""
    
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