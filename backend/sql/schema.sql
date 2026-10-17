CREATE TABLE transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    lifecycle_id VARCHAR(50),
    account_id VARCHAR(50) NOT NULL,
    merchant_name VARCHAR(100) NOT NULL,
    transaction_date DATE NOT NULL,
    transaction_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(20) NOT NULL,
    settlement_status VARCHAR(20) DEFAULT 'PENDING',
    total_settled_amount DECIMAL(10,2) DEFAULT 0.00,
    last_settlement_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE settlement_history (
    settlement_id VARCHAR(50) PRIMARY KEY,
    transaction_id VARCHAR(50),
    lifecycle_id VARCHAR(50),
    settlement_date DATE NOT NULL,
    settlement_amount DECIMAL(10,2) NOT NULL,
    settlement_type VARCHAR(10) NOT NULL,  
    currency VARCHAR(3) NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE reconciliation_exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id VARCHAR(50),
    reason VARCHAR(100) NOT NULL,
    raw_row TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);