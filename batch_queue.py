import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class QueueItem:
    case_number: str = ""
    call_id: str = ""
    call_type: str = ""
    location: str = ""
    report_type: str = "Standard Incident Report"
    notes: str = ""
    narrative: str = ""
    status: str = "queued"
    officer_name: str = ""
    officer_id: str = ""
    error: str = ""
    created_at: str = ""


def get_queue() -> List[Dict[str, Any]]:
    return st.session_state.get('batch_queue', [])


def set_queue(queue: List[Dict[str, Any]]):
    st.session_state['batch_queue'] = queue


def add_to_queue(item: Dict[str, Any]):
    queue = get_queue()
    item.setdefault('status', 'queued')
    item.setdefault('created_at', datetime.now().isoformat())
    queue.append(item)
    set_queue(queue)


def remove_from_queue(index: int):
    queue = get_queue()
    if 0 <= index < len(queue):
        queue.pop(index)
        set_queue(queue)


def clear_queue():
    st.session_state['batch_queue'] = []


def update_item(index: int, updates: Dict[str, Any]):
    queue = get_queue()
    if 0 <= index < len(queue):
        queue[index].update(updates)
        set_queue(queue)


def queue_stats() -> Dict[str, int]:
    queue = get_queue()
    return {
        "total": len(queue),
        "queued": sum(1 for i in queue if i.get('status') == 'queued'),
        "done": sum(1 for i in queue if i.get('status') == 'done'),
        "error": sum(1 for i in queue if i.get('status') == 'error'),
    }
