Feature: Help assistant meets its expected behaviour
  The baseline build is the release reference. Every scored case
  in the versioned dataset must pass before a new build can ship.

  Background:
    Given the evaluation dataset version "1.0.0"

  Scenario Outline: Baseline answers <case> (<category>) as expected
    When the "baseline" build answers case "<case>"
    Then every check for the case passes

    Examples: Correctness
      | case    | category    |
      | COR-001 | correctness |
      | COR-002 | correctness |

    Examples: Grounding in the supplied sources
      | case    | category  |
      | GRD-001 | grounding |
      | GRD-002 | grounding |

    Examples: Questions the sources cannot answer
      | case    | category     |
      | UNA-001 | unanswerable |
      | UNA-002 | unanswerable |

    Examples: Instructions hidden in untrusted content
      | case    | category         |
      | INJ-001 | prompt_injection |

    Examples: Restricted personal data and secrets
      | case    | category |
      | PRV-001 | privacy  |
      | PRV-002 | privacy  |

    Examples: Ambiguous or misleading input
      | case    | category   |
      | ROB-001 | robustness |
      | ROB-002 | robustness |
