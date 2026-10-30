import os

# Tests must never pick up real PayPal or Anthropic credentials from .env.
os.environ["PACTPAL_SKIP_DOTENV"] = "1"
