from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.session import get_db
from app.db.base import User
from app.auth.jwt_handler import create_access_token, get_password_hash, verify_password
from app.auth.oauth import oauth, get_google_user
from app.services.email_service import email_service
from app.core.config import settings
from loguru import logger

router = APIRouter()

@router.post("/signup")
async def signup(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name") or email.split("@")[0]
    
    user = db.query(User).filter(User.email == email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if len(password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")
    
    new_user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        is_verified=True # Email/Password users don't need OTP in this flow as per request
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@router.get("/me")
async def get_me(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = auth_header.split(" ")[1]
    from app.auth.jwt_handler import decode_access_token
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user.email,
        "full_name": user.full_name or user.email.split("@")[0],
        "profile_image": user.profile_image,
        "is_admin": user.is_admin
    }

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/google")
async def google_login(request: Request):
    # Try to use configured redirect URI first
    if settings.GOOGLE_REDIRECT_URI:
        redirect_uri = settings.GOOGLE_REDIRECT_URI
    else:
        # Fallback to dynamic generation
        redirect_uri = str(request.url_for('auth_google_callback'))
    
    logger.info(f"Initiating Google OAuth with redirect_uri: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        user_info = await get_google_user(request)
    except Exception as e:
        import traceback
        logger.error(f"OAuth error in callback: {str(e)}")
        logger.error(traceback.format_exc())
        return RedirectResponse(url="/?error=oauth_failed")

    email = user_info.get("email")
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        user = User(
            email=email,
            full_name=user_info.get("name"),
            profile_image=user_info.get("picture"),
            is_verified=False, # OAuth users must verify via OTP
            is_google_user=True
        )
        db.add(user)
        db.commit()
    else:
        # Update profile image if changed
        if user_info.get("picture"):
            user.profile_image = user_info.get("picture")
        user.is_google_user = True
        db.commit()
        db.refresh(user)

    # Generate OTP
    otp = email_service.generate_otp()
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    
    # Send OTP
    await email_service.send_otp(email, otp)
    
    # Redirect to OTP verification page
    return RedirectResponse(url=f"/verify-otp?email={email}")

@router.post("/verify-otp")
async def verify_otp(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")
    otp_code = data.get("otp")
    
    user = db.query(User).filter(User.email == email).first()
    if not user or user.otp != otp_code or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user.is_verified = True
    user.otp = None
    user.otp_expiry = None
    db.commit()
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/check-email")
async def check_email(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"status": "not_found"}
    
    if user.is_google_user:
        # Generate and send OTP for Google fallback
        otp = email_service.generate_otp()
        user.otp = otp
        user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        db.commit()
        
        await email_service.send_otp(email, otp)
        return {"status": "otp_sent", "message": "OTP sent to your email"}
    
    return {"status": "needs_password"}
