"""SOP-derived interwhen verifiers for the Handbook Gear tasks.

Runs inside the task container under the OpenHands runner venv (stdlib only).
Verifier logic is Python; the local SLM is used purely to extract facts from
conversation/tool-output text (see ``extract.py``).
"""
