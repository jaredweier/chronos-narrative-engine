import streamlit as st
from typing import Any, List, Optional

class StateManager:
    @staticmethod
    def get_cad_data_list() -> List[Any]:
        if 'cad_data_list' not in st.session_state:
            st.session_state['cad_data_list'] = []
        return st.session_state['cad_data_list']

    @staticmethod
    def add_cad_data(cad: Any):
        StateManager.get_cad_data_list().append(cad)

    @staticmethod
    def get_transcripts() -> List[str]:
        if 'transcripts' not in st.session_state:
            st.session_state['transcripts'] = []
        return st.session_state['transcripts']

    @staticmethod
    def add_transcript(t: str):
        StateManager.get_transcripts().append(t)

    @staticmethod
    def get_generated_report() -> str:
        return st.session_state.get('generated_report', '')

    @staticmethod
    def set_generated_report(val: str):
        st.session_state['generated_report'] = val

    @staticmethod
    def get_original_ai_draft() -> str:
        return st.session_state.get('original_ai_draft', '')

    @staticmethod
    def set_original_ai_draft(val: str):
        st.session_state['original_ai_draft'] = val

    @staticmethod
    def get_authenticated_officer() -> str:
        return st.session_state.get('authenticated_officer', '')

    @staticmethod
    def get_officer_id() -> str:
        return st.session_state.get('officer_id', '')

    @staticmethod
    def get_case_number() -> str:
        return st.session_state.get('case_number', '')

    @staticmethod
    def set_case_number(val: str):
        st.session_state['case_number'] = val
