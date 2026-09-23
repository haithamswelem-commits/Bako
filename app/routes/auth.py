from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from fastapi import Depends
from app.dependencies import get_current_user

from app.database import get_db_connection
from app.metrics import LOGIN_FAILURE_TOTAL, LOGIN_SUCCESS_TOTAL
from app.security import hash_password, verify_password, create_access_token

import secrets
from datetime import datetime, timedelta


router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    preferred_language: Literal["en", "ar"]


def default_display_name(email: str) -> str:
    local_part = email.split("@", 1)[0]
    return " ".join(local_part.replace(".", " ").split()).title()


@router.post("/register")
def register_user(user: RegisterRequest):
    conn = get_db_connection()
    cur = conn.cursor()

    email = user.email.strip().lower()

    try:
        cur.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        existing_user = cur.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        hashed_password = hash_password(user.password)

        display_name = (
            user.display_name.strip()
            if user.display_name and user.display_name.strip()
            else default_display_name(email)
        )

        cur.execute(
            """
            INSERT INTO users (email, hashed_password, display_name)
            VALUES (%s, %s, %s)
            RETURNING id, email, display_name, preferred_language
            """,
            (email, hashed_password, display_name)
        )

        new_user = cur.fetchone()
        conn.commit()

        return {
            "message": "User registered successfully",
            "user": {
                "id": new_user[0],
                "email": new_user[1],
                "display_name": new_user[2],
                "preferred_language": new_user[3]
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        conn.rollback()
        print(error)
        raise HTTPException(
            status_code=500,
            detail="Failed to register user"
        )

    finally:
        cur.close()
        conn.close()


@router.post("/login")
def login_user(user: LoginRequest):
    conn = get_db_connection()
    cur = conn.cursor()

    email = user.email.strip().lower()

    try:
        cur.execute(
            """
            SELECT id, email, hashed_password, display_name, preferred_language
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        db_user = cur.fetchone()

        if not db_user:
            LOGIN_FAILURE_TOTAL.inc()
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        user_id = db_user[0]
        user_email = db_user[1]
        hashed_password = db_user[2]

        if not verify_password(user.password, hashed_password):
            LOGIN_FAILURE_TOTAL.inc()
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        token = create_access_token({
            "sub": str(user_id),
            "email": user_email
        })
        LOGIN_SUCCESS_TOTAL.inc()

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user_email,
                "display_name": db_user[3],
                "preferred_language": db_user[4]
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        LOGIN_FAILURE_TOTAL.inc()
        print(error)
        raise HTTPException(
            status_code=500,
            detail="Failed to login"
        )

    finally:
        cur.close()
        conn.close()

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    conn = get_db_connection()
    cur = conn.cursor()

    email = request.email.strip().lower()

    try:
        cur.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cur.fetchone()

        if not user:
            return {
                "message": "If the email exists, a reset token has been generated"
            }

        user_id = user[0]

        token = secrets.token_urlsafe(32)

        expires_at = datetime.utcnow() + timedelta(hours=1)

        cur.execute(
            """
            INSERT INTO password_reset_tokens
            (
                user_id,
                token,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user_id,
                token,
                expires_at
            )
        )

        conn.commit()

        return {
            "message": "Reset token generated",
            "reset_token": token
        }

    except Exception as error:
        conn.rollback()
        print(error)

        raise HTTPException(
            status_code=500,
            detail="Failed to generate reset token"
        )

    finally:
        cur.close()
        conn.close()

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT user_id
            FROM password_reset_tokens
            WHERE token = %s
            AND used = FALSE
            AND expires_at > NOW()
            """,
            (request.token,)
        )

        token_row = cur.fetchone()

        if not token_row:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired token"
            )

        user_id = token_row[0]

        hashed_password = hash_password(
            request.new_password
        )

        cur.execute(
            """
            UPDATE users
            SET hashed_password = %s
            WHERE id = %s
            """,
            (
                hashed_password,
                user_id
            )
        )

        cur.execute(
            """
            UPDATE password_reset_tokens
            SET used = TRUE
            WHERE token = %s
            """,
            (request.token,)
        )

        conn.commit()

        return {
            "message": "Password reset successfully"
        }

    except HTTPException:
        raise

    except Exception as error:
        conn.rollback()
        print(error)

        raise HTTPException(
            status_code=500,
            detail="Failed to reset password"
        )

    finally:
        cur.close()
        conn.close()


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, email, display_name, preferred_language
            FROM users
            WHERE id = %s
            """,
            (current_user["id"],),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "message": "Authenticated user",
            "user": {
                "id": user[0],
                "email": user[1],
                "display_name": user[2] or default_display_name(user[1]),
                "preferred_language": user[3] or "en",
            },
        }
    finally:
        cur.close()
        conn.close()


@router.put("/me")
def update_me(
    profile: ProfileUpdateRequest,
    current_user=Depends(get_current_user),
):
    display_name = " ".join(profile.display_name.split())
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE users
            SET display_name = %s,
                preferred_language = %s
            WHERE id = %s
            RETURNING id, email, display_name, preferred_language
            """,
            (
                display_name,
                profile.preferred_language,
                current_user["id"],
            ),
        )
        user = cur.fetchone()
        conn.commit()
        return {
            "user": {
                "id": user[0],
                "email": user[1],
                "display_name": user[2],
                "preferred_language": user[3],
            }
        }
    finally:
        cur.close()
        conn.close()
