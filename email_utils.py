import os
import base64
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from asyncio import run

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    creds = None

    # Load existing credentials from 'token.pickle'
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials are available, request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)  # Ensure the port matches the one in redirect_uri

        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw.decode()}

async def send_email(subject, body):
    service = get_gmail_service()
    message = create_message("ytchanneltinos@gmail.com", "testmailforphone03727@gmail.com", subject, body)
    send_message = (service.users().messages().send(userId="me", body=message).execute())
    return {"message": "Email sent successfully"}

if __name__ == "__main__":
    run(send_email('hello', 'whassup biaaaatch?'))
