CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    product_id TEXT NOT NULL,
    variant_id TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS product_variants (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    color TEXT,
    size TEXT,
    price REAL NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gift_cards (
    id TEXT PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0.0,
    customer_id TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    kyc_status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    type TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    type TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    name TEXT NOT NULL,
    value REAL DEFAULT 0.0,
    stage TEXT NOT NULL DEFAULT 'prospect'
);

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    department TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    pto_balance REAL DEFAULT 0.0,
    pto_accrual_rate REAL DEFAULT 1.25
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    employee_id TEXT REFERENCES employees(id),
    type TEXT NOT NULL,
    serial_number TEXT,
    status TEXT NOT NULL DEFAULT 'assigned'
);

CREATE TABLE IF NOT EXISTS access_records (
    id TEXT PRIMARY KEY,
    employee_id TEXT REFERENCES employees(id),
    system TEXT NOT NULL,
    access_level TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'pending',
    invoice_date TEXT,
    due_date TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    invoice_id TEXT REFERENCES invoices(id),
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credit_notes (
    id TEXT PRIMARY KEY,
    invoice_id TEXT REFERENCES invoices(id),
    amount REAL NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_requests (
    id TEXT PRIMARY KEY,
    requester_id TEXT NOT NULL,
    department TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approval_chains (
    id TEXT PRIMARY KEY,
    request_id TEXT REFERENCES purchase_requests(id),
    approver_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    limit_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    excluded_from_sla INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    deployed_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS sla_configs (
    id TEXT PRIMARY KEY,
    severity TEXT NOT NULL UNIQUE,
    response_minutes INTEGER NOT NULL,
    resolution_hours INTEGER NOT NULL,
    quiet_hours_start INTEGER DEFAULT 22,
    quiet_hours_end INTEGER DEFAULT 8
);

CREATE TABLE IF NOT EXISTS session_tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    params TEXT NOT NULL,
    result TEXT,
    called_at TEXT NOT NULL DEFAULT (datetime('now'))
);
