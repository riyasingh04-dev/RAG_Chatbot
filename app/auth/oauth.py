from authlib.integrations.starlette_client import OAuth
from app.core.config import settings

oauth = OAuth()

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

import logging
logger = logging.getLogger(__name__)

async def get_google_user(request):
    token = await oauth.google.authorize_access_token(request)
    logger.debug(f"OAuth Token keys: {list(token.keys())}")
    
    user_info = None
   
    if 'id_token' in token:
        try:
            user_info = await oauth.google.parse_id_token(request, token)
        except Exception as e:
            logger.warning(f"Failed to parse id_token: {e}")
    

    if not user_info:
        logger.info("Falling back to userinfo endpoint")
        resp = await oauth.google.get('https://www.googleapis.com/oauth2/v3/userinfo', token=token)
        user_info = resp.json()
        logger.debug(f"UserInfo from endpoint: {user_info}")
        
    return user_info
