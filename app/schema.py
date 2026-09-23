from app.database import get_db_connection


def ensure_base_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                display_name VARCHAR(100),
                preferred_language VARCHAR(5) NOT NULL DEFAULT 'en'
                    CHECK (preferred_language IN ('en', 'ar')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_cycles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                cycle_name VARCHAR(120) NOT NULL DEFAULT 'Monthly Income',
                income_amount NUMERIC(14, 2) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subcategories (
                id SERIAL PRIMARY KEY,
                category_id INTEGER NOT NULL
                    REFERENCES categories(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE (category_id, name)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                amount NUMERIC(14, 2) NOT NULL,
                category_id INTEGER
                    REFERENCES categories(id),
                subcategory_id INTEGER
                    REFERENCES subcategories(id),
                cycle_id INTEGER NOT NULL
                    REFERENCES financial_cycles(id) ON DELETE CASCADE,
                description TEXT,
                expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                token TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_user_categories_schema():
    """Move legacy global categories to user-owned copies without data loss."""

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            ALTER TABLE categories
            ADD COLUMN IF NOT EXISTS user_id INTEGER
            """
        )
        cur.execute(
            """
            ALTER TABLE categories
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
        cur.execute(
            """
            ALTER TABLE subcategories
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
        cur.execute(
            """
            ALTER TABLE categories
            DROP CONSTRAINT IF EXISTS categories_name_key
            """
        )
        cur.execute(
            """
            DO $migration$
            DECLARE
                category_row RECORD;
                subcategory_row RECORD;
                new_category_id INTEGER;
                new_subcategory_id INTEGER;
            BEGIN
                FOR category_row IN
                    SELECT DISTINCT
                        transactions.user_id,
                        categories.id AS old_category_id,
                        categories.name,
                        categories.is_active
                    FROM transactions
                    JOIN categories
                        ON categories.id = transactions.category_id
                    WHERE categories.user_id IS NULL
                LOOP
                    SELECT id INTO new_category_id
                    FROM categories
                    WHERE user_id = category_row.user_id
                    AND LOWER(name) = LOWER(category_row.name)
                    LIMIT 1;

                    IF new_category_id IS NULL THEN
                        INSERT INTO categories (user_id, name, is_active)
                        VALUES (
                            category_row.user_id,
                            category_row.name,
                            category_row.is_active
                        )
                        RETURNING id INTO new_category_id;
                    END IF;

                    FOR subcategory_row IN
                        SELECT id, name, is_active
                        FROM subcategories
                        WHERE category_id = category_row.old_category_id
                    LOOP
                        SELECT id INTO new_subcategory_id
                        FROM subcategories
                        WHERE category_id = new_category_id
                        AND LOWER(name) = LOWER(subcategory_row.name)
                        LIMIT 1;

                        IF new_subcategory_id IS NULL THEN
                            INSERT INTO subcategories (
                                category_id,
                                name,
                                is_active
                            )
                            VALUES (
                                new_category_id,
                                subcategory_row.name,
                                subcategory_row.is_active
                            )
                            RETURNING id INTO new_subcategory_id;
                        END IF;

                        UPDATE transactions
                        SET subcategory_id = new_subcategory_id
                        WHERE user_id = category_row.user_id
                        AND category_id = category_row.old_category_id
                        AND subcategory_id = subcategory_row.id;
                    END LOOP;

                    UPDATE transactions
                    SET category_id = new_category_id
                    WHERE user_id = category_row.user_id
                    AND category_id = category_row.old_category_id;
                END LOOP;

                DELETE FROM categories WHERE user_id IS NULL;
            END
            $migration$;
            """
        )
        cur.execute(
            """
            ALTER TABLE categories
            ALTER COLUMN user_id SET NOT NULL
            """
        )
        cur.execute(
            """
            DO $constraint$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'categories_user_id_fkey'
                ) THEN
                    ALTER TABLE categories
                    ADD CONSTRAINT categories_user_id_fkey
                    FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE;
                END IF;
            END
            $constraint$;
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_categories_user_lower_name
            ON categories (user_id, LOWER(name))
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_subcategories_category_lower_name
            ON subcategories (category_id, LOWER(name))
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_ai_coach_schema():
    """Persist AI Coach exchanges and their provider token usage."""

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_coach_exchanges (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                cycle_id INTEGER NOT NULL
                    REFERENCES financial_cycles(id) ON DELETE CASCADE,
                question TEXT NOT NULL,
                headline VARCHAR(200) NOT NULL,
                explanation TEXT NOT NULL,
                recommended_action TEXT,
                response_source VARCHAR(40) NOT NULL,
                topics TEXT[] NOT NULL DEFAULT '{}',
                provider VARCHAR(100),
                model VARCHAR(120),
                input_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (input_tokens >= 0),
                output_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (output_tokens >= 0),
                used_fallback BOOLEAN NOT NULL DEFAULT FALSE,
                fallback_reason VARCHAR(100),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_coach_user_cycle_created
            ON ai_coach_exchanges (user_id, cycle_id, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_coach_created
            ON ai_coach_exchanges (created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_coach_user_created
            ON ai_coach_exchanges (user_id, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_usage_events (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                feature VARCHAR(80) NOT NULL,
                provider VARCHAR(100) NOT NULL,
                model VARCHAR(120) NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (input_tokens >= 0),
                output_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (output_tokens >= 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_usage_events_created
            ON ai_usage_events (created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_usage_events_user_created
            ON ai_usage_events (user_id, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS expense_categorization_feedback (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                expense_id INTEGER UNIQUE
                    REFERENCES transactions(id) ON DELETE CASCADE,
                source VARCHAR(40) NOT NULL,
                provider VARCHAR(100),
                model VARCHAR(120),
                prompt_version VARCHAR(80) NOT NULL,
                suggested_category_id INTEGER
                    REFERENCES categories(id) ON DELETE SET NULL,
                suggested_subcategory_id INTEGER
                    REFERENCES subcategories(id) ON DELETE SET NULL,
                proposed_category_name VARCHAR(100),
                proposed_subcategory_name VARCHAR(100),
                final_category_id INTEGER
                    REFERENCES categories(id) ON DELETE SET NULL,
                final_subcategory_id INTEGER
                    REFERENCES subcategories(id) ON DELETE SET NULL,
                confidence NUMERIC(5, 4) NOT NULL
                    CHECK (confidence >= 0 AND confidence <= 1),
                input_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (input_tokens >= 0),
                output_tokens INTEGER NOT NULL DEFAULT 0
                    CHECK (output_tokens >= 0),
                latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
                outcome VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (outcome IN ('pending', 'accepted', 'corrected')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_categorization_feedback_user_created
            ON expense_categorization_feedback (user_id, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_categorization_feedback_outcome
            ON expense_categorization_feedback (outcome, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS expense_categorization_memory (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                normalized_description VARCHAR(200) NOT NULL,
                category_id INTEGER NOT NULL
                    REFERENCES categories(id) ON DELETE CASCADE,
                subcategory_id INTEGER NOT NULL
                    REFERENCES subcategories(id) ON DELETE CASCADE,
                confirmation_count INTEGER NOT NULL DEFAULT 1
                    CHECK (confirmation_count > 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, normalized_description)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_categorization_memory_user_key
            ON expense_categorization_memory (
                user_id,
                normalized_description
            )
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_goals_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(120) NOT NULL,
                type VARCHAR(32) NOT NULL,
                target_amount NUMERIC(14, 2) NOT NULL,
                current_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                deadline_date DATE,
                priority VARCHAR(16) NOT NULL DEFAULT 'medium',
                auto_rule VARCHAR(80),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (target_amount > 0),
                CHECK (current_amount >= 0),
                CHECK (
                    type IN (
                        'required_bill',
                        'savings',
                        'charity',
                        'lifestyle',
                        'event',
                        'debt'
                    )
                ),
                CHECK (priority IN ('high', 'medium', 'low'))
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_goals_user_active
            ON goals (user_id, is_active, priority)
            """
        )
        cur.execute(
            """
            ALTER TABLE goals
            ADD COLUMN IF NOT EXISTS cycle_id INTEGER
            REFERENCES financial_cycles(id) ON DELETE CASCADE
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_goals_user_cycle_active
            ON goals (user_id, cycle_id, is_active, priority)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_goals_user_lifecycle
            ON goals (user_id, is_active, deadline_date, created_at)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_contributions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                cycle_id INTEGER REFERENCES financial_cycles(id) ON DELETE CASCADE,
                amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
                contribution_date DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_goal_contributions_cycle_date
            ON goal_contributions (cycle_id, user_id, contribution_date)
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_cycles_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            ALTER TABLE financial_cycles
            ADD COLUMN IF NOT EXISTS cycle_name VARCHAR(120)
            NOT NULL DEFAULT 'Monthly Income'
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_financial_cycles_user_dates
            ON financial_cycles (user_id, start_date, end_date, id)
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_payment_channel_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS payment_channel VARCHAR(20)
            NOT NULL DEFAULT 'cash'
            CHECK (payment_channel IN ('cash', 'credit_card'))
            """
        )
        cur.execute(
            """
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_cycle_payment_channel
            ON transactions (user_id, cycle_id, payment_channel, expense_date)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_cc_settlement
            ON transactions (user_id, cycle_id, settled_at)
            WHERE payment_channel = 'credit_card'
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_credit_cards_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_cards (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(80) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, name)
            )
            """
        )
        cur.execute(
            """
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS credit_card_id INTEGER
            REFERENCES credit_cards(id) ON DELETE SET NULL
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_credit_card
            ON transactions (user_id, credit_card_id, cycle_id, expense_date)
            WHERE payment_channel = 'credit_card'
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_budget_adjustments_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cycle_budget_adjustments (
                id SERIAL PRIMARY KEY,
                cycle_id INTEGER NOT NULL
                    REFERENCES financial_cycles(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
                note VARCHAR(160),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cycle_budget_adjustments_cycle
            ON cycle_budget_adjustments (user_id, cycle_id, created_at)
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_performance_indexes():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_user_cycle_date
            ON transactions (user_id, cycle_id, expense_date)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_user_cycle_category
            ON transactions (user_id, cycle_id, category_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_user_cycle_subcategory
            ON transactions (user_id, cycle_id, subcategory_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_goal_contributions_goal_user
            ON goal_contributions (goal_id, user_id)
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_user_profile_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)
            """
        )
        cur.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5)
            NOT NULL DEFAULT 'en'
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'users_preferred_language_check'
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT users_preferred_language_check
                    CHECK (preferred_language IN ('en', 'ar'));
                END IF;
            END
            $$
            """
        )
        cur.execute(
            """
            UPDATE users
            SET display_name = INITCAP(
                REPLACE(SPLIT_PART(email, '@', 1), '.', ' ')
            )
            WHERE display_name IS NULL OR BTRIM(display_name) = ''
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
