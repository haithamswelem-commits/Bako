from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.database import get_db_connection
from app.dependencies import get_current_user


router = APIRouter()


class CategoryName(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Name must contain text")
        if not any(character.isalpha() for character in normalized):
            raise ValueError("Name must include at least one letter")
        return normalized


class CategoryPairProposal(BaseModel):
    category_name: str = Field(min_length=1, max_length=100)
    subcategory_name: str = Field(min_length=1, max_length=100)

    @field_validator("category_name", "subcategory_name")
    @classmethod
    def normalize_names(cls, value: str) -> str:
        return CategoryName(name=value).name


def _serialize(row):
    return {"id": row[0], "name": row[1]}


@router.get("/categories")
def get_categories(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name
            FROM categories
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY name
            """,
            (current_user["id"],),
        )
        return [_serialize(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.post("/categories")
def create_category(
    category: CategoryName,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name, is_active
            FROM categories
            WHERE user_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (current_user["id"], category.name),
        )
        existing = cur.fetchone()
        if existing and existing[2]:
            raise HTTPException(status_code=409, detail="Spending group exists")
        if existing:
            cur.execute(
                """
                UPDATE categories
                SET name = %s, is_active = TRUE
                WHERE id = %s
                RETURNING id, name
                """,
                (category.name, existing[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO categories (user_id, name)
                VALUES (%s, %s)
                RETURNING id, name
                """,
                (current_user["id"], category.name),
            )
        row = cur.fetchone()
        conn.commit()
        return _serialize(row)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.post("/category-pairs")
def create_category_pair(
    pair: CategoryPairProposal,
    current_user=Depends(get_current_user),
):
    """Create or reactivate one confirmed user-owned category pair."""

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM categories
            WHERE user_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (current_user["id"], pair.category_name),
        )
        category_row = cur.fetchone()
        if category_row:
            cur.execute(
                """
                UPDATE categories
                SET name = %s, is_active = TRUE
                WHERE id = %s
                RETURNING id, name
                """,
                (pair.category_name, category_row[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO categories (user_id, name)
                VALUES (%s, %s)
                RETURNING id, name
                """,
                (current_user["id"], pair.category_name),
            )
        category = cur.fetchone()

        cur.execute(
            """
            SELECT id
            FROM subcategories
            WHERE category_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (category[0], pair.subcategory_name),
        )
        subcategory_row = cur.fetchone()
        if subcategory_row:
            cur.execute(
                """
                UPDATE subcategories
                SET name = %s, is_active = TRUE
                WHERE id = %s
                RETURNING id, name
                """,
                (pair.subcategory_name, subcategory_row[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO subcategories (category_id, name)
                VALUES (%s, %s)
                RETURNING id, name
                """,
                (category[0], pair.subcategory_name),
            )
        subcategory = cur.fetchone()
        conn.commit()
        return {
            "category": _serialize(category),
            "subcategory": _serialize(subcategory),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    category: CategoryName,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM categories
            WHERE user_id = %s
            AND LOWER(name) = LOWER(%s)
            AND id <> %s
            """,
            (current_user["id"], category.name, category_id),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Spending group exists")
        cur.execute(
            """
            UPDATE categories
            SET name = %s
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            RETURNING id, name
            """,
            (category.name, category_id, current_user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Spending group not found")
        conn.commit()
        return _serialize(row)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.delete("/categories/{category_id}")
def archive_category(
    category_id: int,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE categories
            SET is_active = FALSE
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            RETURNING id
            """,
            (category_id, current_user["id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Spending group not found")
        cur.execute(
            """
            UPDATE subcategories
            SET is_active = FALSE
            WHERE category_id = %s
            """,
            (category_id,),
        )
        conn.commit()
        return {"message": "Spending group archived"}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.get("/subcategories")
def get_subcategories(
    category_id: int,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT subcategories.id, subcategories.name
            FROM subcategories
            JOIN categories ON categories.id = subcategories.category_id
            WHERE subcategories.category_id = %s
            AND categories.user_id = %s
            AND categories.is_active = TRUE
            AND subcategories.is_active = TRUE
            ORDER BY subcategories.name
            """,
            (category_id, current_user["id"]),
        )
        return [_serialize(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.post("/categories/{category_id}/subcategories")
def create_subcategory(
    category_id: int,
    subcategory: CategoryName,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM categories
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            """,
            (category_id, current_user["id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Spending group not found")
        cur.execute(
            """
            SELECT id, name, is_active
            FROM subcategories
            WHERE category_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (category_id, subcategory.name),
        )
        existing = cur.fetchone()
        if existing and existing[2]:
            raise HTTPException(status_code=409, detail="Expense type exists")
        if existing:
            cur.execute(
                """
                UPDATE subcategories
                SET name = %s, is_active = TRUE
                WHERE id = %s
                RETURNING id, name
                """,
                (subcategory.name, existing[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO subcategories (category_id, name)
                VALUES (%s, %s)
                RETURNING id, name
                """,
                (category_id, subcategory.name),
            )
        row = cur.fetchone()
        conn.commit()
        return _serialize(row)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.put("/subcategories/{subcategory_id}")
def update_subcategory(
    subcategory_id: int,
    subcategory: CategoryName,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT subcategories.category_id
            FROM subcategories
            JOIN categories ON categories.id = subcategories.category_id
            WHERE subcategories.id = %s
            AND categories.user_id = %s
            AND subcategories.is_active = TRUE
            """,
            (subcategory_id, current_user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Expense type not found")
        cur.execute(
            """
            SELECT id
            FROM subcategories
            WHERE category_id = %s
            AND LOWER(name) = LOWER(%s)
            AND id <> %s
            """,
            (row[0], subcategory.name, subcategory_id),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Expense type exists")
        cur.execute(
            """
            UPDATE subcategories
            SET name = %s
            WHERE id = %s
            RETURNING id, name
            """,
            (subcategory.name, subcategory_id),
        )
        updated = cur.fetchone()
        conn.commit()
        return _serialize(updated)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.delete("/subcategories/{subcategory_id}")
def archive_subcategory(
    subcategory_id: int,
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE subcategories
            SET is_active = FALSE
            FROM categories
            WHERE subcategories.id = %s
            AND categories.id = subcategories.category_id
            AND categories.user_id = %s
            AND subcategories.is_active = TRUE
            RETURNING subcategories.id
            """,
            (subcategory_id, current_user["id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Expense type not found")
        conn.commit()
        return {"message": "Expense type archived"}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
