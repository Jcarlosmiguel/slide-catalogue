CREATE TABLE contact_messages (
  message_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'Primary key.',
  name VARCHAR(255) NOT NULL COMMENT 'Name provided by the visitor.',
  email VARCHAR(255) NOT NULL COMMENT 'Email provided by the visitor, used as Reply-To on the notification email.',
  message_text TEXT NOT NULL COMMENT 'The submitted message content.',
  remote_addr VARCHAR(100) NULL DEFAULT NULL COMMENT 'Submitter''s IP address, captured for abuse/audit purposes.',
  user_agent VARCHAR(500) NULL DEFAULT NULL COMMENT 'Submitter''s browser user-agent string.',
  email_sent_at DATETIME NULL DEFAULT NULL COMMENT 'When the admin notification email was confirmed sent; NULL if it failed or was never attempted (e.g. CONTACT_NOTIFICATION_EMAIL not configured) - lets a query distinguish delivered messages from ones needing manual follow-up.',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When the message was submitted.'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Public contact-form submissions - persisted independently of the admin notification email, so a mail-relay failure cannot silently lose a message.';
