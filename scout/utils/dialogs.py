"""Centralised dialog helpers used throughout AppController.

Having a single module for dialogs makes error paths consistent and
simplifies testing (callers can be tested by patching show_error/show_warning).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal critical error dialog."""
    QMessageBox.critical(parent, title, message)


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal warning dialog."""
    QMessageBox.warning(parent, title, message)


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal informational dialog."""
    QMessageBox.information(parent, title, message)


def ask_yes_no(
    parent: QWidget | None,
    title: str,
    message: str,
    default_yes: bool = False,
) -> bool:
    """Show a Yes/No question dialog. Returns True if the user clicked Yes."""
    default = (
        QMessageBox.StandardButton.Yes
        if default_yes
        else QMessageBox.StandardButton.No
    )
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default,
    )
    return reply == QMessageBox.StandardButton.Yes
