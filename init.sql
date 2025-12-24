CREATE DATABASE IF NOT EXISTS shortener_db;
GRANT SELECT, INSERT, UPDATE, DELETE ON shortener_db.* TO 'web_user'@'%';

USE shortener_db;

CREATE TABLE IF NOT EXISTS urls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    original_url TEXT NOT NULL,
    short_code VARCHAR(10) NOT NULL UNIQUE, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    visit_count INT DEFAULT 0 
);

CREATE TABLE IF NOT EXISTS clicks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url_id INT NOT NULL,
    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),  
    browser VARCHAR(50),     
    os VARCHAR(50),          
    referer VARCHAR(255),    
    FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE
);
