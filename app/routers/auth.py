import jwt
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from app.core.security import create_jwt_token, get_current_user_from_cookie

router = APIRouter()

# Mock database
user_db = {"Raja": {"username": "Raja", "password": "r2a8j2a8"}}

@router.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires, token_type="access"
    )

    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_jwt_token(
        data={"sub": user["username"]}, expires_delta=refresh_token_expires, token_type="refresh"
    )
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    
    return {"message": "Login successful"}

@router.post("/refresh")
def refresh_token(response: Response, refresh_token: str | None = Cookie(default=None)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token.")
        
    try:
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
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_jwt_token(
        data={"sub": username}, expires_delta=access_token_expires, token_type="access"
    )
    
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    return {"message": "Access token refreshed successfully"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}

@router.get("/protected")
def protected_route(username: str = Depends(get_current_user_from_cookie)):
    return {"message": f"Welcome {username}, you are authenticated with a real JWT access token stored in a cookie!"}
