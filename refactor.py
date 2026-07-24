import re

with open('pages/generate_report.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
if 'from state_manager import StateManager' not in content:
    content = content.replace('import streamlit as st', 'import streamlit as st\nfrom state_manager import StateManager')

replacements = [
    (r"st\.session_state\.get\('cad_data_list',\s*\[\]\)", "StateManager.get_cad_data_list()"),
    (r"st\.session_state\['cad_data_list'\]", "StateManager.get_cad_data_list()"),
    (r"if 'cad_data_list' not in st\.session_state:\n\s*st\.session_state\['cad_data_list'\] = \[\]\n", ""),

    (r"st\.session_state\.get\('transcripts',\s*\[\]\)", "StateManager.get_transcripts()"),
    (r"st\.session_state\['transcripts'\]", "StateManager.get_transcripts()"),
    (r"if 'transcripts' not in st\.session_state:\n\s*st\.session_state\['transcripts'\] = \[\]\n", ""),

    (r"st\.session_state\.get\('generated_report',\s*''\)", "StateManager.get_generated_report()"),
    (r"st\.session_state\.get\('generated_report'\)", "StateManager.get_generated_report()"),
    (r"st\.session_state\['generated_report'\]\s*=\s*(.*?)\n", r"StateManager.set_generated_report(\1)\n"),
    (r"st\.session_state\['generated_report'\]", "StateManager.get_generated_report()"),

    (r"st\.session_state\.get\('original_ai_draft',\s*''\)", "StateManager.get_original_ai_draft()"),
    (r"st\.session_state\.get\('original_ai_draft'\)", "StateManager.get_original_ai_draft()"),
    (r"st\.session_state\['original_ai_draft'\]\s*=\s*(.*?)\n", r"StateManager.set_original_ai_draft(\1)\n"),
    (r"st\.session_state\['original_ai_draft'\]", "StateManager.get_original_ai_draft()"),

    (r"st\.session_state\.get\('authenticated_officer',\s*''\)", "StateManager.get_authenticated_officer()"),
    (r"st\.session_state\.get\('authenticated_officer'\)", "StateManager.get_authenticated_officer()"),
    (r"st\.session_state\['authenticated_officer'\]", "StateManager.get_authenticated_officer()"),

    (r"st\.session_state\.get\('officer_id',\s*''\)", "StateManager.get_officer_id()"),
    (r"st\.session_state\.get\('officer_id'\)", "StateManager.get_officer_id()"),
    (r"st\.session_state\['officer_id'\]", "StateManager.get_officer_id()"),

    (r"st\.session_state\.get\('case_number',\s*'INC-UNKNOWN'\)", "StateManager.get_case_number() or 'INC-UNKNOWN'"),
    (r"st\.session_state\.get\('case_number',\s*''\)", "StateManager.get_case_number()"),
    (r"st\.session_state\.get\('case_number'\)", "StateManager.get_case_number()"),
    (r"st\.session_state\['case_number'\]\s*=\s*(.*?)\n", r"StateManager.set_case_number(\1)\n"),
    (r"st\.session_state\['case_number'\]", "StateManager.get_case_number()"),
]

for pat, repl in replacements:
    content = re.sub(pat, repl, content)

# Clean up any `StateManager.get_cad_data_list().append(...)` to just `StateManager.add_cad_data(...)` if needed, but append() on a list is fine too.

with open('pages/generate_report.py', 'w', encoding='utf-8') as f:
    f.write(content)
