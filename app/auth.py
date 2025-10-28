import hmac, hashlib, base64, time, json, requests
import jwt
from typing import Dict, Any, Optional
from fastapi import HTTPException
import boto3

# Initialize SSM client
ssm = boto3.client('ssm', region_name='ap-southeast-2')

def get_parameter(name):
    """Get parameter from Parameter Store"""
    try:
        response = ssm.get_parameter(Name=name)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"❌ Error getting parameter {name}: {e}")
        # Fallback values if Parameter Store fails
        fallback_values = {
            '/fractal-app/region': 'ap-southeast-2',
            '/fractal-app/user-pool-id': 'ap-southeast-2_JfylTCgME',
            '/fractal-app/client-id': '270ss412pj3mm2u3251df1c19b'
        }
        return fallback_values.get(name, '')

# Get configuration from Parameter Store
try:
    REGION = get_parameter('/fractal-app/region')
    USER_POOL_ID = get_parameter('/fractal-app/user-pool-id')
    CLIENT_ID = get_parameter('/fractal-app/client-id')
    CLIENT_SECRET = "70qkssn9kbv51eknvobu1ishpe8aqlutnj151a6q4orcrnt8g74"  # We'll move this later
    print(f"✅ Loaded configuration from Parameter Store: Region={REGION}")
except Exception as e:
    print(f"⚠️ Using fallback configuration: {e}")
    REGION = "ap-southeast-2"
    USER_POOL_ID = "ap-southeast-2_JfylTCgME"
    CLIENT_ID = "270ss412pj3mm2u3251df1c19b"
    CLIENT_SECRET = "70qkssn9kbv51eknvobu1ishpe8aqlutnj151a6q4orcrnt8g74"

cognito = boto3.client("cognito-idp", region_name=REGION)

# === Secret hash helper ===
def calculate_secret_hash(username: str) -> str:
    if not CLIENT_SECRET:
        return ""
    msg = username + CLIENT_ID
    dig = hmac.new(CLIENT_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

# === JWKS cache ===
_JWKS: Optional[Dict[str, Any]] = None
_JWKS_LAST_FETCH = 0
_JWKS_TTL = 3600

def get_jwks():
    global _JWKS, _JWKS_LAST_FETCH
    now = time.time()
    if _JWKS is None or now - _JWKS_LAST_FETCH > _JWKS_TTL:
        url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        _JWKS = resp.json()
        _JWKS_LAST_FETCH = now
    return _JWKS

def verify_jwt_token(token: str) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(401, "Invalid token header")

    kid = header.get("kid")
    keys = get_jwks().get("keys", [])
    key_data = next((k for k in keys if k.get("kid") == kid), None)
    if not key_data:
        raise HTTPException(401, "Key not found")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

    try:
        # Try to decode without audience verification first
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Disable audience verification
                "verify_exp": True,   # But still verify expiration
            }
        )
        
        # Manual audience verification for ID tokens if they have aud claim
        if "aud" in payload and payload["aud"] != CLIENT_ID:
            raise HTTPException(401, "Invalid audience")
            
        # Verify token_use if present
        if "token_use" in payload:
            if payload["token_use"] not in ["access", "id"]:
                raise HTTPException(401, "Invalid token use")
                
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")