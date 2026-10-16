import copy

import pytest

from app.agent.llm import LlmError, LlmReply
from app.agent.orchestrator import FALLBACK_REPLY, MAX_REPAIRS, fit_reply, run_turn
from app.agent.tools import MAX_REPLY_CHARS
from app.services import signing
from tests.agent.conftest import SIGNING_KEY, ScriptedLlm, propose, tool

USER = [{"role": "user", "content": "Make it 240 cm wide"}]


def turn(llm, design, catalog, messages=USER, revision=3):
    return run_turn(messages=messages, design=design, revision=revision, catalog=catalog, llm=llm,
                    signing_key=SIGNING_KEY)


def test_valid_proposal_is_signed_and_bound_to_the_design(design, catalog):
    result = turn(ScriptedLlm(propose([{"op": "update_dimensions", "width": 2400}])), design, catalog)
    proposal = result["proposal"]
    assert result["reply"] == "Wider wardrobe."
    assert proposal["ops"] == [{"op": "update_dimensions", "width": 2400}]
    assert proposal["baseRevision"] == 3
    assert proposal["baseHash"] == signing.design_hash(design)
    assert signing.verify(SIGNING_KEY, proposal["signature"], proposal["proposalId"], proposal["ops"], 3,
                          proposal["baseHash"])
    assert proposal["changes"] == [{"title": "Dimensions", "detail": "Width 200 cm → 240 cm"}]


def test_the_turn_never_mutates_the_design(design, catalog):
    before = copy.deepcopy(design)
    turn(ScriptedLlm(propose([{"op": "update_dimensions", "width": 2400}])), design, catalog)
    assert design == before


def test_signed_ops_are_the_canonical_parsed_form(design, catalog):
    # Explicit nulls and defaults from the model are normalised before signing.
    raw = [{"op": "add_shelf", "compartmentId": "cmp_left", "y": 1800, "thickness": None, "id": None}]
    proposal = turn(ScriptedLlm(propose(raw)), design, catalog)["proposal"]
    assert proposal["ops"] == [{"op": "add_shelf", "compartmentId": "cmp_left", "y": 1800}]


def test_invalid_op_is_fed_back_and_the_repaired_proposal_wins(design, catalog):
    llm = ScriptedLlm(
        propose([{"op": "add_shelf", "compartmentId": "cmp_missing", "y": 100}], call_id="bad"),
        propose([{"op": "add_shelf", "compartmentId": "cmp_left", "y": 100}], call_id="good"),
    )
    result = turn(llm, design, catalog)
    assert result["proposal"]["ops"][0]["compartmentId"] == "cmp_left"
    feedback = llm.calls[1][-1]
    assert feedback["role"] == "tool" and feedback["tool_call_id"] == "bad"
    assert "NOT_FOUND" in feedback["content"]
    assert llm.calls[1][-2]["tool_calls"][0]["id"] == "bad"


def test_gives_up_after_the_repair_budget(design, catalog):
    bad = [propose([{"op": "update_dimensions", "width": 99}], call_id=f"c{i}") for i in range(MAX_REPAIRS + 1)]
    llm = ScriptedLlm(*bad)
    result = turn(llm, design, catalog)
    assert result == {"reply": FALLBACK_REPLY, "proposal": None}
    assert len(llm.calls) == MAX_REPAIRS + 1


@pytest.mark.parametrize("arguments", ["not json", "[1, 2]", {"summary": "x", "ops": []}, {"summary": "x", "ops": "nope"}])
def test_malformed_tool_arguments_are_rejected_not_raised(design, catalog, arguments):
    llm = ScriptedLlm(tool("propose_changes", arguments), propose([{"op": "update_dimensions", "depth": 650}]))
    assert turn(llm, design, catalog)["proposal"]["ops"] == [{"op": "update_dimensions", "depth": 650}]


def test_unknown_tool_is_rejected(design, catalog):
    llm = ScriptedLlm(tool("delete_everything", {}), tool("ask_clarification", {"question": "Which side?"}))
    assert turn(llm, design, catalog) == {"reply": "Which side?", "proposal": None}


def test_clarification_returns_a_question_without_a_proposal(design, catalog):
    result = turn(ScriptedLlm(tool("ask_clarification", {"question": "How tall should it be?"})), design, catalog)
    assert result == {"reply": "How tall should it be?", "proposal": None}


def test_unsafe_characters_are_stripped_from_model_text(design, catalog):
    question = "Which‮ side​?\x07" + "\U000e0041"
    result = turn(ScriptedLlm(tool("ask_clarification", {"question": question})), design, catalog)
    assert result["reply"] == "Which side?"


def test_long_summary_is_capped_to_three_bubble_lines(design, catalog):
    reply = propose([{"op": "update_dimensions", "depth": 650}], summary="x" * 5000)
    assert len(turn(ScriptedLlm(reply), design, catalog)["reply"]) <= MAX_REPLY_CHARS


def test_long_reply_keeps_whole_sentences_that_fit():
    text = "I'll widen it to 240 cm. " + "This extra sentence is far too long to fit into the chat bubble together with the first one. " * 3
    assert fit_reply(text.strip(), MAX_REPLY_CHARS) == "I'll widen it to 240 cm."


def test_one_long_sentence_is_cut_at_a_word_with_an_ellipsis():
    text = "I will " + "really " * 30 + "widen it."
    fitted = fit_reply(text, MAX_REPLY_CHARS)
    assert len(fitted) <= MAX_REPLY_CHARS and fitted.endswith("really…")


def test_newlines_are_collapsed_into_one_paragraph(design, catalog):
    result = turn(ScriptedLlm(tool("ask_clarification", {"question": "Which\n\n\nside?"})), design, catalog)
    assert result["reply"] == "Which side?"


def test_plain_text_reply_is_accepted(design, catalog):
    assert turn(ScriptedLlm(LlmReply(content="Hello!")), design, catalog) == {"reply": "Hello!", "proposal": None}


def test_empty_reply_is_an_llm_error(design, catalog):
    with pytest.raises(LlmError):
        turn(ScriptedLlm(LlmReply(content=None)), design, catalog)


def test_design_is_sent_as_data_after_the_system_prompt(design, catalog):
    llm = ScriptedLlm(tool("ask_clarification", {"question": "?"}))
    turn(llm, design, catalog, messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello"},
                                         {"role": "user", "content": "wider"}])
    sent = llm.calls[0]
    assert sent[0]["role"] == "system" and "currentDesign" not in sent[0]["content"]
    assert sent[1]["role"] == "user" and '"currentDesign"' in sent[1]["content"]
    assert [m["content"] for m in sent[2:]] == ["hi", "Hello", "wider"]


def test_hebrew_message_gets_an_explicit_reply_language_hint_last(design, catalog):
    llm = ScriptedLlm(tool("ask_clarification", {"question": "?"}))
    turn(llm, design, catalog, messages=[{"role": "user", "content": "תעשה אותו רחב יותר"}])
    assert llm.calls[0][-1] == {"role": "system", "content": "The customer wrote in Hebrew. Reply in Hebrew."}


def test_latin_message_gets_no_language_hint(design, catalog):
    llm = ScriptedLlm(tool("ask_clarification", {"question": "?"}))
    turn(llm, design, catalog)
    assert llm.calls[0][-1]["role"] == "user"
