-- MySQL version
CREATE TABLE IF NOT EXISTS provisioning (
    id INT AUTO_INCREMENT PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    mac_address VARCHAR(17) NOT NULL UNIQUE,
    status BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_mac_address (mac_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- SQLite version
-- CREATE TABLE IF NOT EXISTS provisioning (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     endpoint VARCHAR(255) NOT NULL,
--     make VARCHAR(50) NOT NULL,
--     model VARCHAR(50) NOT NULL,
--     mac_address VARCHAR(17) NOT NULL UNIQUE,
--     status BOOLEAN DEFAULT 1,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );
-- 
-- CREATE INDEX IF NOT EXISTS idx_mac_address ON provisioning(mac_address); 