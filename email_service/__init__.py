"""Email service package for MatchKit."""
from email_service.builder import EmailBuilder, email_builder
from email_service.sender import EmailSender, email_sender

__all__ = ["EmailBuilder", "email_builder", "EmailSender", "email_sender"]
