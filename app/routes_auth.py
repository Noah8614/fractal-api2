from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


from auth import cognito, calculate_secret_hash, verify_jwt_token, CLIENT_ID

router = APIRouter()

class RegisterModel(BaseModel):
    username: str
    password: str
    email: str

class ConfirmModel(BaseModel):
    username: str
    code: str

class LoginModel(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(payload: RegisterModel):
    try:
        extra = {}
        sh = calculate_secret_hash(payload.username)
        if sh:
            extra["SecretHash"] = sh

        cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=payload.username,
            Password=payload.password,
            UserAttributes=[{"Name": "email", "Value": payload.email}],
            **extra,
        )
        return {"message": "User created. Check email for confirmation."}
    except cognito.exceptions.UsernameExistsException:
        raise HTTPException(400, "Username already exists")
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/confirm")
def confirm(payload: ConfirmModel):
    try:
        extra = {}
        sh = calculate_secret_hash(payload.username)
        if sh:
            extra["SecretHash"] = sh

        cognito.confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=payload.username,
            ConfirmationCode=payload.code,
            **extra
        )
        return {"message": "User confirmed. You can now log in."}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/login")
def login(payload: LoginModel):
    # Dev login bypass - MUST be at the beginning of the function
    if payload.username == "dev" and payload.password == "dev":
        fake_jwt = "dev-token-1234567890"
        return {
            "AccessToken": fake_jwt,
            "IdToken": fake_jwt,
            "RefreshToken": fake_jwt,
            "ExpiresIn": 3600,
            "TokenType": "Bearer",
        }
    
    try:
        auth_params = {"USERNAME": payload.username, "PASSWORD": payload.password}
        sh = calculate_secret_hash(payload.username)
        if sh:
            auth_params["SECRET_HASH"] = sh

        resp = cognito.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
        )
        result = resp.get("AuthenticationResult")
        if not result:
            return JSONResponse({"detail": "Authentication failed"}, status_code=400)
        return result
    except cognito.exceptions.NotAuthorizedException:
        raise HTTPException(401, "Incorrect username or password")
    except cognito.exceptions.UserNotConfirmedException:
        raise HTTPException(403, "User not confirmed")
    except Exception as e:
        raise HTTPException(400, str(e))

@router.get("/protected")
def protected(request: Request):
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing/invalid Authorization header")
    token = auth.split(" ", 1)[1]
    payload = verify_jwt_token(token)
    return {"message": f"Hello {payload.get('cognito:username')}", "claims": payload}