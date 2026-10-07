from fastapi import APIRouter, HTTPException, status, Depends
from app.models.admin import LoginRequest, TokenResponse, AdminResponse
from app.repositories.admin_repo import find_admin_by_email, find_admin_by_id
from app.auth import verify_password, create_access_token, get_current_admin
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    db = get_db()
    admin = await find_admin_by_email(db, body.email)
    if not admin or not verify_password(body.password, admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": admin["id"], "role": admin["role"]})
    return TokenResponse(
        access_token=token,
        admin=AdminResponse(
            id=admin["id"],
            email=admin["email"],
            role=admin["role"],
            name=admin["name"],
            created_at=admin["created_at"],
            updated_at=admin["updated_at"],
        ),
    )


@router.post("/logout")
async def logout(_: dict = Depends(get_current_admin)):
    # JWT is stateless; logout handled client-side by discarding token
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AdminResponse)
async def me(admin: dict = Depends(get_current_admin)):
    return AdminResponse(
        id=admin["id"],
        email=admin["email"],
        role=admin["role"],
        name=admin["name"],
        created_at=admin["created_at"],
        updated_at=admin["updated_at"],
    )
