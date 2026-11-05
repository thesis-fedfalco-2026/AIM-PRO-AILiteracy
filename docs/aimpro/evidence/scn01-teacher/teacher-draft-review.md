# Complete original Teacher draft for human review

This is a readable rendering of the untouched typed output. Local findings are separate and do not edit any generated text.

## Activities

### unit-1-adviser-peer-demonstration / unit-1-item-1 — EXPLAIN

This is the demonstration phase of the workshop. The adviser will build a fictional payment-reminder prompt live, thinking aloud about every choice. You will see a weak version and an improved version displayed side by side, then one isolated change that makes the improved version worse, and finally a peer owner who presents her own fictional prompt and the failure it produced. All business names, customer names, invoice numbers and amounts used throughout this demonstration are entirely fictional instructional examples. They are not real customer records, not observed model outputs and not learner results.

What to watch for as the demonstration unfolds:
1. Notice what information is present or absent in each prompt version.
2. Listen to the adviser's reasoning for each addition or change.
3. Notice the single change that makes the improved prompt worse, and the adviser's explanation of its precise effect.
4. Notice what the peer owner's prompt contains and what the unsatisfactory result looked like.

After the demonstration you will be invited to annotate a transcript and then construct your own prompt. This demonstration does not ask you to submit anything; it is for observation and comparison only.

Materials: mat-explanation-prompt-structure, mat-transcript-adviser-demo, mat-example-weak-improved-worse, mat-example-peer-failure

```json
{
  "outcomes": [
    {
      "type": "LearningOutcome",
      "id": "aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:outcome:Pointer1792169221668_USER_96",
      "version": "1"
    }
  ],
  "citations": [
    {
      "resource_id": "wp3:32c2119d5504",
      "resource_version": "31057b5b35cfcfa5f31ee406f855477a",
      "document_ids": [
        "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:3",
        "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:4",
        "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:7"
      ],
      "supported_claim": "The corpus presents prompt construction as instruction plus primary content, worked basic, complex and instruction prompt examples, and best practices including being specific, clear and descriptive and using examples, supporting a live demonstration that shows weak and improved prompt variants side by side with thinking-aloud commentary."
    }
  ]
}
```

## mat-explanation-prompt-structure — EXPLANATION: How a prompt is constructed: instruction, primary content and best practices

FICTIONAL INSTRUCTIONAL EXAMPLE DECLARATION
All business names, customer names, invoice numbers, amounts and dates used in this explanation are entirely fictional. They are created for instructional illustration only and do not represent real customers, real transactions or observed model behaviour.

─────────────────────────────────────
SOURCE ATTRIBUTION NOTE
The concepts in this explanation are drawn from Prompt Engineering Fundamentals (wp3:32c2119d5504, version 31057b5b35cfcfa5f31ee406f855477a), specifically excerpts 3, 4 and 7. Direct quotations and close paraphrases are marked. The five-move label set used in this workshop (INSTRUCTION, PRIMARY CONTENT, EXAMPLE, CUE, TEMPLATE) is a new operator authoring adaptation for this workshop, not a taxonomy stated verbatim by the source. The best-practice recommendations cited below are drawn from excerpt 7 of the source.
─────────────────────────────────────

1. WHAT A PROMPT IS

A prompt is the text you send to an AI tool to tell it what to do. The AI uses your prompt as its only guide for what to produce. If the prompt is vague, the output will be vague. If the prompt is specific, the output is more likely to be useful.

The source states that with instruction prompts "we can use that text to specify a task in more detail, providing better guidance to the AI" (excerpt 3). It also shows that a basic prompt — a text input with no other context — produces a basic completion, while adding context and instructions changes the quality of the output significantly.

2. THE TWO CORE PARTS OF A PROMPT

The source describes a design pattern called primary content, in which "the input text is divided into two parts: an instruction (action) [and] relevant content (that influences action)" (excerpt 3/4). These two parts work together:

  INSTRUCTION: A direct statement telling the AI what action to perform. It specifies the task. Look for an imperative or directive sentence (write, summarise, translate, list).

  Example of an instruction (fictional): "Write a payment-reminder email."

  PRIMARY CONTENT: The specific information the AI should act on — the subject matter or data that the instruction applies to. Without primary content, the AI must guess which customer, which invoice and which amount you mean.

  Example of primary content (fictional): "The customer is Hartwell Catering Ltd (fictional). The invoice number is #4021 (fictional) and the amount is £340.00 (fictional), due 14 March (fictional)."

When instruction and primary content are combined, the AI has both the task and the data it needs.

3. ADDITIONAL MOVES: EXAMPLES, CUES AND TEMPLATES

The source describes three further ways to shape a prompt using primary content (excerpt 4):

  EXAMPLE (one-shot or few-shot prompting): "instead of telling the model what to do with an explicit instruction, give it examples of what to do and let it infer the pattern." Supplying one example is called one-shot prompting; supplying more than one is called few-shot prompting. The source explicitly distinguishes zero-shot prompting — "where you give it an instruction (but no examples)" — from one-shot and few-shot approaches (excerpt 7). A discussion of examples without actually providing one does not enact this move.

  CUE: "follow the instruction with a 'cue' that primes the completion, guiding the model towards more relevant responses" (excerpt 4). A cue is a leading word, phrase or partial sentence placed at the end of the prompt to nudge the AI toward a desired format or opening. Example (fictional): ending a prompt with "Dear Hartwell Catering," so the AI continues from that opening.

  TEMPLATE: "repeatable 'recipes' for prompts with placeholders (variables) that can be customized with data for specific use cases" (excerpt 4). A template contains bracketed or labelled slots intended to be filled in, for example [CUSTOMER NAME], [INVOICE NUMBER], [AMOUNT DUE]. The source notes that templates allow creation of "a library of reusable prompts" (excerpt 6).

4. BEST PRACTICES FROM THE SOURCE

Excerpt 7 of the source lists best practices recommended by OpenAI and Azure OpenAI practitioners. The following are directly relevant to this workshop:

  "Be specific and clear — Give more details about the desired context, outcome, length, format, style etc. This will improve both the quality and consistency of responses. Capture recipes in reusable templates."

  "Be descriptive, use examples — Models may respond better to a 'show and tell' approach. Start with a zero-shot approach where you give it an instruction (but no examples) then try few-shot as a refinement, providing a few examples of the desired output. Use analogies."

  "Use cues to jumpstart completions — Nudge it towards a desired outcome by giving it some leading words or phrases that it can use as a starting point for the response."

  "Separate instructions and context — Check if your model/provider defines delimiters to distinguish instructions, primary and secondary content more clearly."

These best practices support the choices the adviser makes in the demonstration. The 150-word length constraint used in the improved fictional prompt below is a fictional operator illustration of the 'length' detail mentioned in 'be specific and clear'; it is not a learner response limit, a syllabus requirement or a passing threshold.

5. WHAT MAKES A PROMPT WEAK

A prompt is weak when it omits the information the AI needs. The source illustrates this with a basic prompt — a minimal text input with no context — which produces a generic output because the AI has nothing specific to act on (excerpt 3). In a payment-reminder context, a weak prompt might say only "Write an email to our customer about their invoice." The AI cannot determine which customer, which invoice, what amount, what tone or what action is required.

6. WHAT MAKES A PROMPT IMPROVED

An improved prompt adds the missing specifics. Based on the source's best practices (excerpt 7), an improved prompt for a payment reminder would include:
  - A role or context statement (who the AI is acting as)
  - A specific instruction (what to write)
  - Primary content (customer name, invoice number, amount, due date — all fictional in this workshop)
  - A tone instruction (friendly but firm)
  - An output constraint (payment deadline, length)

7. HOW ONE CHANGE CAN MAKE AN IMPROVED PROMPT WORSE

Removing a single specific element from an improved prompt can degrade the output. The source's best practice 'be specific and clear' recommends giving details about desired context, outcome, length, format and style (excerpt 7). If a length constraint is removed, the AI no longer has guidance on how concise the output should be, and may produce output that is too long or inconsistently sized for the intended use. The precise effect depends on the specific element removed; the demonstration shows one concrete example of this.

8. ADAPTATION AND GAPS

The five-move label set (INSTRUCTION, PRIMARY CONTENT, EXAMPLE, CUE, TEMPLATE) used in this workshop is a new operator authoring adaptation. It is not a validated taxonomy stated verbatim by the source. The source does not specify a formal assessment, rubric or passing threshold for this workshop; those remain unresolved gaps. The source's best-practice recommendations are drawn from OpenAI and Azure OpenAI practitioner guidance as cited in excerpt 7 and are not guaranteed to produce specific outputs for any given model or task.

Citations:
```json
[
  {
    "resource_id": "wp3:32c2119d5504",
    "resource_version": "31057b5b35cfcfa5f31ee406f855477a",
    "document_ids": [
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:3",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:4",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:7"
    ],
    "supported_claim": "The source defines prompt construction as instruction plus primary content, describes examples (zero-shot, one-shot, few-shot), cues and templates as distinct prompt moves, and provides best practices including being specific and clear about context, outcome, length, format and style, and using cues to jumpstart completions. These concepts directly support the explanation of prompt structure, the five-move operator adaptation and the adviser demonstration rationale."
  }
]
```

## mat-transcript-adviser-demo — TRANSCRIPT: Demonstration transcript: adviser builds a fictional payment-reminder prompt (unannotated, line-numbered)

FICTIONAL INSTRUCTIONAL EXAMPLE DECLARATION
All business names, customer names, invoice numbers, amounts and dates in this transcript are entirely fictional. This transcript is a newly authored instructional illustration. It does not record an actual workshop session, real model outputs or real learner results. It is provided unannotated so that a later separately approved Trainer activity could reuse it; teaching commentary appears in the explanation material, not here.

─────────────────────────────────────
1.  Adviser: Right, let's look at how we actually build a prompt. I'm going to start with the simplest possible version and show you what happens as we improve it.
2.  Adviser: Here's my first attempt — the weak version. I'll read it out: "Write an email to our customer about their invoice."
3.  Adviser: That's it. Nothing else. What do you think the AI will do with that?
4.  Participant: It won't know which customer or which invoice.
5.  Adviser: Exactly. So the first thing I need to add is the specific information — the customer name, the invoice number, the amount, the due date. That's what we call primary content: the data the AI needs to act on.
6.  Adviser: Watch what happens when I add it. New prompt: "Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, due 14 March."
7.  Participant: That's much clearer already.
8.  Adviser: Good. But I can do more. I'm also going to give it a role — tell it who it's supposed to be — and a tone instruction. So now: "You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler. Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, which was due on 14 March. The tone should be friendly but firm."
9.  Adviser: And I'll add a specific action: ask the customer to arrange payment within five business days, and include the invoice number and amount in the email body.
10. Adviser: Finally, I'll add a length constraint: keep the email under 150 words. That's my improved prompt.
11. Participant: So the improved prompt has a lot more in it.
12. Adviser: It does. Let me put the weak and improved versions side by side so you can see the difference clearly.
13. Adviser: Weak prompt body: "Write an email to our customer about their invoice."
14. Adviser: Improved prompt body: "You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler. Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, which was due on 14 March. The tone should be friendly but firm. Ask the customer to arrange payment within five business days and include the invoice number and amount in the email body. Keep the email under 150 words."
15. Adviser: Now I want to show you what happens when I take the improved prompt and make just one change — a change that makes it worse.
16. Adviser: I'm going to remove the sentence "Keep the email under 150 words." Everything else stays exactly the same.
17. Adviser: So the worse prompt body becomes: "You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler. Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, which was due on 14 March. The tone should be friendly but firm. Ask the customer to arrange payment within five business days and include the invoice number and amount in the email body."
18. Adviser: The precise effect of removing that sentence is this: the AI no longer has any guidance on how long the output should be. Without a length constraint, it may produce an email that is much longer than needed — perhaps several paragraphs — which would be too long to send as a short payment reminder. The constraint was doing real work, and removing it leaves that dimension of the output uncontrolled.
19. Participant: So one sentence made a real difference.
20. Adviser: Yes. And notice it's not a dramatic rewrite — it's one specific instruction removed. That's why being specific and clear matters: each element you include is doing a job.
21. Adviser: Now I'll hand over to my colleague. She's been using AI tools in her own fictional business for a few months and she's going to show you a prompt she tried and what went wrong.
22. Peer owner: Thanks. My fictional business is called Sunrise Bakery Supplies — a small wholesale bakery ingredient supplier. I was trying to send a payment reminder to a fictional customer called Moorfield Events Ltd about a fictional invoice, number B-077, for £215.00.
23. Peer owner: Here's the prompt I used: "Send a reminder about the unpaid bill."
24. Peer owner: And here's what the AI tool produced — I'll describe it: a very short, generic message. It didn't mention the customer's name, the invoice number, the amount owed or any payment deadline. I felt the output could not be sent to any customer without being completely rewritten.
25. Participant: So it was the same problem as the weak prompt at the start.
26. Peer owner: Exactly. I hadn't given the AI any primary content — no customer name, no invoice number, no amount, no deadline. The instruction was also vague: "send a reminder" doesn't tell the AI what kind of reminder, what tone or what action to request.
27. Adviser: So both the adviser's weak prompt and the peer's prompt share the same underlying issue: the instruction is too vague and there is no primary content. The AI has to guess, and it guesses generically.
28. Adviser: What you've seen today is: a weak prompt, an improved prompt, one change that made it worse and why, and a peer example of the same pattern. In the next part of the workshop you'll annotate a transcript to identify these moves, and then you'll construct your own prompt.
─────────────────────────────────────
END OF TRANSCRIPT
This transcript is unannotated. Teaching commentary, source attribution and concept explanations appear in the explanation material (mat-explanation-prompt-structure). No classification answers, annotation keys or assessment solutions are embedded here.

Citations:
```json
[
  {
    "resource_id": "wp3:32c2119d5504",
    "resource_version": "31057b5b35cfcfa5f31ee406f855477a",
    "document_ids": [
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:3",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:4",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:7"
    ],
    "supported_claim": "The transcript enacts the source concepts of basic prompt, instruction prompt, primary content, and best practices (be specific and clear about context, outcome, length, format and style) by showing a weak prompt built into an improved prompt and then degraded by removing a length constraint, consistent with the source's illustration that adding context and instructions changes output quality and that specificity matters."
  }
]
```

## mat-example-weak-improved-worse — EXAMPLE: Fictional worked example: weak, improved and worse prompt variants displayed side by side

FICTIONAL INSTRUCTIONAL EXAMPLE DECLARATION
All business names, customer names, invoice numbers, amounts and dates below are entirely fictional. These prompt variants are newly authored instructional illustrations. They are not source quotations, not observed model outputs and not learner results. The 150-word length constraint is a fictional operator illustration of the 'length' detail in the source's 'be specific and clear' best practice (excerpt 7); it is not a learner response limit, a syllabus requirement or a passing threshold.

─────────────────────────────────────
FICTIONAL CONTEXT (applies to all three variants)
Fictional business: Greenleaf Office Supplies (fictional), a small stationery wholesaler.
Fictional customer: Hartwell Catering Ltd (fictional).
Fictional invoice: Invoice #4021 (fictional), amount £340.00 (fictional), due date 14 March (fictional).
─────────────────────────────────────

VARIANT A — WEAK PROMPT

PROMPT TEXT
Write an email to our customer about their invoice.
END PROMPT TEXT

What is present: A minimal instruction.
What is absent: Role or context, customer name, invoice number, amount, due date, tone, payment deadline, length or format guidance.
Why it is weak: The source describes a basic prompt as "a text input sent to the model with no other context" (excerpt 3). Without primary content, the AI cannot determine which customer, which invoice, what amount or what action is required, and the output will be generic.

─────────────────────────────────────

VARIANT B — IMPROVED PROMPT

PROMPT TEXT
You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler. Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, which was due on 14 March. The tone should be friendly but firm. Ask the customer to arrange payment within five business days and include the invoice number and amount in the email body. Keep the email under 150 words.
END PROMPT TEXT

What was added compared to Variant A:
  1. A role statement: "You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler." — This gives the AI context about who it is acting as, consistent with the source's recommendation to define domain-specific personalities (excerpt 6).
  2. A specific instruction: "Write a payment-reminder email" rather than just "write an email" — more directive and task-specific.
  3. Primary content: customer name (Hartwell Catering Ltd, fictional), invoice number (#4021, fictional), amount (£340.00, fictional), due date (14 March, fictional).
  4. A tone instruction: "The tone should be friendly but firm."
  5. A specific action request: "Ask the customer to arrange payment within five business days and include the invoice number and amount in the email body."
  6. A length constraint: "Keep the email under 150 words."

Source support: The source's best practice states: "Be specific and clear — Give more details about the desired context, outcome, length, format, style etc. This will improve both the quality and consistency of responses" (excerpt 7). Each element added in Variant B corresponds to one of these dimensions.

─────────────────────────────────────

VARIANT C — WORSE PROMPT (one change from Variant B)

PROMPT TEXT
You are a polite and professional accounts assistant for Greenleaf Office Supplies, a small stationery wholesaler. Write a payment-reminder email to Hartwell Catering Ltd about Invoice #4021 for £340.00, which was due on 14 March. The tone should be friendly but firm. Ask the customer to arrange payment within five business days and include the invoice number and amount in the email body.
END PROMPT TEXT

What changed: The sentence "Keep the email under 150 words." has been removed from the end of Variant B. Every other character in the prompt body is identical to Variant B.

Precise effect of the removal: Without the length constraint, the AI no longer has guidance on how concise the output should be. The source recommends specifying desired length as part of being specific and clear (excerpt 7). Removing this instruction leaves the length dimension of the output uncontrolled: the AI may produce a much longer email than is appropriate for a short payment reminder, making the output less immediately usable without editing.

Note for instructional use: The diagnosis above is provided here as teaching commentary in this EXAMPLE material. It is not reproduced in the assessment stimuli, which ask learners to identify the change and explain its effect themselves.

─────────────────────────────────────

SIDE-BY-SIDE COMPARISON SUMMARY

| Element                  | Weak (A) | Improved (B) | Worse (C) |
|--------------------------|----------|--------------|-----------|
| Role/context statement   | Absent   | Present      | Present   |
| Specific instruction     | Vague    | Specific     | Specific  |
| Primary content          | Absent   | Present      | Present   |
| Tone instruction         | Absent   | Present      | Present   |
| Payment deadline         | Absent   | Present (five business days) | Present (five business days) |
| Length constraint        | Absent   | Present (under 150 words) | ABSENT (removed) |

The only difference between Variant B and Variant C is the presence or absence of the sentence "Keep the email under 150 words."

Citations:
```json
[
  {
    "resource_id": "wp3:32c2119d5504",
    "resource_version": "31057b5b35cfcfa5f31ee406f855477a",
    "document_ids": [
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:3",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:7"
    ],
    "supported_claim": "The source illustrates basic prompts as minimal text inputs without context, and recommends being specific and clear by giving details about desired context, outcome, length, format and style to improve quality and consistency. The weak, improved and worse variants directly illustrate these concepts: the weak prompt omits all specifics; the improved prompt adds role, primary content, tone, deadline and length; the worse prompt removes only the length constraint, leaving that dimension uncontrolled."
  }
]
```

## mat-example-peer-failure — EXAMPLE: Fictional peer example: prompt and unsatisfactory result (Sunrise Bakery Supplies scenario)

FICTIONAL INSTRUCTIONAL EXAMPLE DECLARATION
All business names, customer names, invoice numbers, amounts and details below are entirely fictional. This is a newly authored instructional illustration. It does not record an actual workshop event, a real model output or an observed learner submission. It is provided to make the peer owner's experience visible for instructional comparison.

─────────────────────────────────────
FICTIONAL CONTEXT
Fictional business: Sunrise Bakery Supplies (fictional), a small wholesale bakery ingredient supplier.
Fictional customer: Moorfield Events Ltd (fictional).
Fictional invoice: Invoice #B-077 (fictional), amount £215.00 (fictional).
Fictional peer owner: referred to as the peer owner; not a named real person.
─────────────────────────────────────

FICTIONAL PEER PROMPT USED
"Send a reminder about the unpaid bill."

FICTIONAL UNSATISFACTORY RESULT RECEIVED
The AI tool produced a very short, generic message that did not mention the customer's name, the invoice number, the amount owed or any payment deadline. The fictional business owner felt the output could not be sent to any customer without being completely rewritten, making the AI tool seem unhelpful for this task.

─────────────────────────────────────
TEACHING COMMENTARY (appears here in the EXAMPLE material; not reproduced in assessment stimuli)

The peer prompt shares the same structural problem as the adviser's weak prompt (Variant A): it contains only a vague instruction and no primary content. Specifically:

  - The instruction is vague: "Send a reminder" does not specify what kind of reminder, what tone, what action to request or what format to use.
  - Primary content is entirely absent: there is no customer name, no invoice number, no amount, no due date and no payment deadline.

The source states that without primary content the AI decides what part of its pre-trained dataset is relevant (excerpt 3), which in this case produced a generic output. The source's best practice 'be specific and clear' (excerpt 7) directly addresses this: giving details about the desired context, outcome and format would have allowed the AI to produce a usable message.

This peer example is presented alongside the adviser's demonstration to show that the same pattern — vague instruction, absent primary content — produces the same kind of failure regardless of the business context. Learners observe both examples before constructing their own prompt.

Note: The teaching commentary above is in this EXAMPLE material for instructional purposes. The assessment stimulus peer_failure does not supply a causal diagnosis; learners are asked to identify what they observe and explain what they think contributed to the problem.
─────────────────────────────────────

Citations:
```json
[
  {
    "resource_id": "wp3:32c2119d5504",
    "resource_version": "31057b5b35cfcfa5f31ee406f855477a",
    "document_ids": [
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:3",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:4",
      "wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:7"
    ],
    "supported_claim": "The source illustrates that basic prompts without context or instruction detail produce generic outputs because the AI decides what part of its pre-trained dataset is relevant; the best practice 'be specific and clear' recommends giving details about desired context, outcome, length, format and style. The peer failure illustration directly enacts this concept: a vague instruction with no primary content produces a generic, unusable output."
  }
]
```

## All original generated gaps

1. No formal assessment, rubric or passing threshold is specified in the source; this Teacher draft proposes unvalidated EXPLAIN content for unit-1-adviser-peer-demonstration only, for human review. No score, acquisition rule or completion claim is made.
2. No workshop duration beyond the source constraint 'One evening workshop' is invented; no timing is added to this unit.
3. Corpus resources wp3:12ce471a0269 (grades 6-12 critical AI literacy) and wp3:4868ba8731b3 (AI in educational measurement) are not used as unit citations because they do not validate transfer to adult SME business learners and do not supply a SCN01 rubric or thresholds.
4. Notebook/API setup and illustrative lengths from corpus excerpts are not SCN01 requirements and are not imported into any material.
5. Source competency values are preserved without normalization: category DIGITAL, heRelevance HIGH, smeRelevance HIGH, vetRelevance HIGH are flagged as ENUM_VALUE mismatches; ksa SKILL and proficiency FOUNDATION are flagged as UNTYPED_VOCABULARY_VALUE mismatches. These are not repaired.
6. The GENERATED_CONTRACT missing-resources cardinality finding on LearningTarget_0 (Pointer1792169221668_USER_96) is left unrepaired.
7. The five-move taxonomy (INSTRUCTION, PRIMARY CONTENT, EXAMPLE, CUE, TEMPLATE) used in this workshop is a new operator authoring adaptation, not a validated source instrument or source-prescribed taxonomy. It is not stated verbatim by the corpus.
8. The 150-word constraint in the improved fictional prompt variant is a fictional operator illustration of the 'length' detail in the source's 'be specific and clear' best practice; it is not a learner response limit, a syllabus requirement or a passing threshold.
9. The approved assessment still has a transcript classification hint, an incomplete EXAMPLE illustration, descriptor missing-reasoning and partial-declaration gaps and an attribution limitation. These were accepted by the owner and remain unresolved. This Teacher content does not claim to repair or validate them.
10. The INSTRUCTION, CONTEXT, CONSTRAINT, EXAMPLE and OUTPUT CUE taxonomy used in the approved assessment is an operator instructional and assessment adaptation, not a validated taxonomy stated verbatim by the corpus. This Teacher content explains supported concepts with precise attribution and declares this adaptation gap.
11. Whether customer or business details in any learner-submitted prompt are genuinely fictional cannot be determined from appearance alone; only the presence and scope of a required visible declaration or labelling is assessable. This limitation is retained explicitly.
12. Any within-package links to other units are descriptive references; the host allocates exact ALM identifiers separately. No future Trainer ids or shared refs are invented here.
13. The format/evidence choices for the approved assessment items (CASE_ANALYSIS/CASE_RESULT, SHORT_STRUCTURED/CRITERIA_BASED_PRODUCT, CRITERIA_BASED_PRODUCT/CRITERIA_BASED_PRODUCT, SHORT_STRUCTURED/REFLECTIVE_RECORD) are operator authoring requirements, not source-validated assessment standards.
14. This Teacher draft covers only unit-1-adviser-peer-demonstration as specified by the host target_units. Units 2, 3 and 4 are PRACTICE units assigned to Trainer and are not generated here.
