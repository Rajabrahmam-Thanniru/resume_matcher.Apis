import jwt
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, status, Depends, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm

SECRET_KEY = "your-secret-key-keep-it-secret"  # In a real application, use a securely generated key and load from env vars
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

app = FastAPI(title="resume api")

# Mock database from previous user dictionary
user_db = {"Raja": {"username": "Raja", "password": "r2a8j2a8"}}

def create_jwt_token(data: dict, expires_delta: timedelta, token_type: str):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "type": token_type})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency to verify token from cookies
def get_current_user_from_cookie(access_token: str | None = Cookie(default=None)):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")

        if username is None or token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
            
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired. Please refresh your token."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

@app.get("/")
def home():
    return {"message": 'oii server is up and running mr K'}

@app.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # Generate Access Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires, token_type="access"
    )

    # Generate Refresh Token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_jwt_token(
        data={"sub": user["username"]}, expires_delta=refresh_token_expires, token_type="refresh"
    )
    
    # Set tokens in HttpOnly cookies to protect against XSS
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    
    return {"message": "Login successful"}

@app.post("/refresh")
def refresh_token(response: Response, refresh_token: str | None = Cookie(default=None)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token.")
        
    try:
        # Verify the refresh token from cookie
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")

        if username is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
            
        user = user_db.get(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
        
    # Generate a NEW Access Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_jwt_token(
        data={"sub": username}, expires_delta=access_token_expires, token_type="access"
    )
    
    # Update the access token cookie
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    return {"message": "Access token refreshed successfully"}

@app.get("/protected")
def protected_route(username: str = Depends(get_current_user_from_cookie)):
    return {"message": f"Welcome {username}, you are authenticated with a real JWT access token stored in a cookie!"}

@app.post("/logout")
def logout(response: Response):
    # Clear both cookies to log the user out
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}