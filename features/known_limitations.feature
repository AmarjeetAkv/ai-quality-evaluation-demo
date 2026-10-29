Feature: Limits of automated judging are documented, not hidden
  Word-overlap grounding is cheap and deterministic, but it is not
  semantic understanding. These scenarios pin down where it is wrong.

  Background:
    Given the evaluation dataset version "1.0.0"

  Scenario: A correct paraphrase is flagged (false positive)
    When the "baseline" build answers case "LIM-001"
    Then the "grounded" check fails
    And the outcome is recorded as "known_false_positive"

  Scenario: A wrong answer that reuses the source's words passes (false negative)
    When the "baseline" build answers case "LIM-002"
    Then the "grounded" check passes
    And the outcome is recorded as "known_false_negative"
