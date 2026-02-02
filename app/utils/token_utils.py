from typing import Dict, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TokenPayload:
    def __init__(self, tenant_id: str, plan_id: Optional[str] = None, user_id: Optional[str] = None, **kwargs):
        self.tenant_id = tenant_id
        self.plan_id = plan_id
        self.user_id = user_id
        self.extra_data = kwargs

    def to_dict(self) -> Dict:
        return {
            "tenant_id": self.tenant_id,
            "plan_id": self.plan_id,
            "user_id": self.user_id,
            **self.extra_data
        }


async def decrypt_token(encrypted_token: str) -> TokenPayload:
    """
    Decrypt encrypted token and extract user information.
    
    This is a placeholder for future implementation.
    The encrypted token will contain:
    - tenant_id: Tenant identifier
    - plan_id: User's plan identifier (optional)
    - user_id: User identifier (optional)
    - Other relevant user context
    
    Args:
        encrypted_token: Encrypted token string from client
        
    Returns:
        TokenPayload object containing decrypted user information
        
    Raises:
        ValueError: If token is invalid or cannot be decrypted
    """
    await logger.warning(
        "decrypt_token called but not yet implemented. "
        "This is a placeholder for future encrypted token support."
    )
    
    raise NotImplementedError(
        "Token decryption not yet implemented. "
        "This will be implemented to decrypt encrypted tokens and extract "
        "tenant_id, plan_id, user_id, and other relevant user context."
    )


async def extract_user_context(encrypted_token: str) -> Dict[str, Optional[str]]:
    """
    Returns:
        Dictionary with tenant_id, plan_id, user_id, etc.
    """
    payload = await decrypt_token(encrypted_token)
    return payload.to_dict()
