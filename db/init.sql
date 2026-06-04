-- ============================================================
--  DWH Assistant — Database Schema
--  Auto-loaded by PostgreSQL on first container start
-- ============================================================

-- Reference / lookup tables first (no FK dependencies)

CREATE TABLE IF NOT EXISTS countries (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    parent_category_id  INTEGER REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS shipping_carriers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    tracking_url    VARCHAR(512)
);

CREATE TABLE IF NOT EXISTS merchants (
    id              SERIAL PRIMARY KEY,
    country_code    INTEGER REFERENCES countries(id),
    status          VARCHAR(50),
    merchant_name   VARCHAR(255) NOT NULL,
    address         TEXT,
    website_url     VARCHAR(512),
    phone_number    VARCHAR(50),
    email           VARCHAR(255),
    logo_url        VARCHAR(512),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    username        VARCHAR(100),
    phone_number    VARCHAR(50),
    last_login_at   TIMESTAMP,
    avatar_url      VARCHAR(512),
    created_at      TIMESTAMP DEFAULT NOW(),
    country_code    INTEGER REFERENCES countries(id)
);

CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    brand           VARCHAR(255),
    color           VARCHAR(100),
    weight          DOUBLE PRECISION,
    dimensions      VARCHAR(100),
    rating          DOUBLE PRECISION,
    merchant_id     INTEGER REFERENCES merchants(id),
    price           DOUBLE PRECISION,
    created_at      TIMESTAMP DEFAULT NOW(),
    category_id     INTEGER REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id),
    status              VARCHAR(50),
    created_at          TIMESTAMP DEFAULT NOW(),
    total_sum           DOUBLE PRECISION,
    shipping_address    TEXT,
    billing_address     TEXT,
    payment_method      VARCHAR(50),
    payment_status      VARCHAR(50),
    shipping_carrier_id INTEGER REFERENCES shipping_carriers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id),
    product_id      INTEGER REFERENCES products(id),
    quantity        INTEGER,
    price           DOUBLE PRECISION,
    sum             DOUBLE PRECISION
);
