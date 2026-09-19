"""Email notifications for the thesis platform."""

import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import current_app


def send_project_completion_email(project):
    """Send a completion notification to the project's requester.

    Raises RuntimeError when the requester email or SMTP configuration is
    missing, allowing the caller to keep the project update while informing
    the manager that the notification could not be delivered.
    """
    recipient = (project.requester_email or "").strip()
    if not recipient:
        raise RuntimeError("No requester email is configured for this project.")

    host = current_app.config.get("SMTP_HOST")
    from_email = current_app.config.get("SMTP_FROM_EMAIL")
    if not host or not from_email:
        raise RuntimeError(
            "Project completion email is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL."
        )

    port = current_app.config.get("SMTP_PORT", 587)
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = current_app.config.get("SMTP_USE_TLS", True)

    completed_date = project.completed_at or datetime.utcnow()
    completed_label = completed_date.strftime("%B %d, %Y") if completed_date else "today"
    manager_name = project.manager.full_name if project.manager else "the project team"

    message = EmailMessage()
    message["Subject"] = f"Project Completed: {project.name}"
    message["From"] = from_email
    message["To"] = recipient
    message.set_content(
        f"Hello,\n\n"
        f"The project \"{project.name}\" has been completed as of {completed_label}.\n\n"
        f"Project Manager: {manager_name}\n"
        f"Project Priority: {project.priority or 'Medium'}\n\n"
        "This is an automated notification from the Smart Project Management and "
        "Employee Competency Development Platform.\n\n"
        "Regards,\n"
        "SPM&ECD Platform"
    )

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)
