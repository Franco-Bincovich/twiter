"""Prompts de los redactores IA, aislados del código de los services.

Cada prompt vive en su propio módulo como constante: separa el texto largo de la
lógica (respeta el límite de líneas de `services/`) y deja un único lugar donde
auditar lo que se le pide al modelo (SEGURIDAD-PENTEST.md 6.1).
"""
