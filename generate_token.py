from google_auth_oauthlib.flow import InstalledAppFlow
import os

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    if not os.path.exists('client_secret.json'):
        print("ERROR: client_secret.json not found in the current directory.")
        print("Please download your OAuth 2.0 Client ID from Google Cloud Console as client_secret.json")
        return
        
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("token.json generated successfully! You can now upload token.json to PythonAnywhere.")

if __name__ == '__main__':
    main()
