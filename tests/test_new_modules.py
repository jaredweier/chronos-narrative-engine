import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test modules that only need stdlib
passed = 0
failed = 0

# 1. wi_statutes
import wi_statutes
r = wi_statutes.search_statutes("homicide", 3)
assert len(r) > 0
ji = wi_statutes.search_jury_instructions("battery", 2)
assert len(ji) > 0
cats = wi_statutes.all_categories()
assert len(cats) > 0
assert wi_statutes.get_statute("940.01") is not None
assert wi_statutes.get_jury_instruction("JI-350") is not None
passed += 1
print("OK: wi_statutes")

# 2. logger
import logger
log = logger.get_logger("test")
log.info("Test")
log2 = logger.get_chronos_logger("test2")
log2.info("Test2")
passed += 1
print("OK: logger")

# 3. providers.base (stdlib + abc only)
from providers.base import LLMProvider, TranscriberProvider, PDFParserProvider, LLMResponse
resp = LLMResponse("test", "model", 100)
assert resp.text == "test"
passed += 1
print("OK: providers.base")

# 4. providers.registry
from providers.registry import (
    register_llm, register_transcriber, register_pdf_parser,
    list_llm_providers, list_transcriber_providers, list_pdf_providers,
)

# Register mock providers
class MockLLM(LLMProvider):
    def complete(self, *a, **kw): return LLMResponse("mock")
register_llm("mock", MockLLM)
assert "mock" in list_llm_providers()
passed += 1
print("OK: providers.registry")

# 5. spell_check
from spell_check import check_text_spelling, auto_correct, highlight_issues
issues = check_text_spelling("The suspect recieved his rights.")
assert len(issues) > 0
corrected = auto_correct("The suspect recieved his rights.")
assert "received" in corrected
passed += 1
print("OK: spell_check")

# 6. case_similar
from case_similar import apply_similar_case_template
result = apply_similar_case_template("Incident Report\nNARRATIVE\nI observed the suspect...", "Officer Jones")
assert "I observed" in result
passed += 1
print("OK: case_similar")

print(f"\nAll {passed} module tests PASSED")
