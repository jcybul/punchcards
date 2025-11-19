import secrets

def generate_cron_token():
    return secrets.token_urlsafe(32)

# Use it like:
token = generate_cron_token()
print(token)