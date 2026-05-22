# Misclassification Case Studies

## Case 1: REGN / EYLEA ROP

Source JSON: `data/history_runs/6df8a6a4aa29769e.json`

### Model Signal
STRONG_NEGATIVE

### Model Probability
15

### Model Confidence
90

### Key Concerns Extracted by Model
- Primary non-inferiority endpoint not met in either pivotal study
- High rate of important protocol deviations in Butterfleye (40% in aflibercept arm)
- Potential systemic safety risks in preterm infants (higher systemic exposure than adults, nonclinical nasal turbinate erosions)
- Safety database for pediatric ROP limited; long-term effects unknown

### Key Positives Extracted by Model
- Orphan drug designation shows recognition of unmet need
- Avoids retinal laser scarring, potentially preserving peripheral vision
- Single injection may reduce treatment burden compared to multiple laser sessions

### Why the Model Likely Overreacted
The local record suggests the model weighted FDA risk language more heavily than contextual approval factors. This should be validated against primary sources before treating it as a final lesson.

### Final Regulatory Outcome
- fda_final_decision: approved
- fda_decision_date: 2023-02-08
- outcome_source: FDA meeting page; public FDA approval history for aflibercept ROP
- notes: FDA approved aflibercept for retinopathy of prematurity in February 2023; advisory vote left blank pending primary-source minutes.; TODO_SOURCE_NEEDED

### Why Final Outcome Diverged from Harsh FDA Tone
Insufficient local data. TODO_SOURCE_NEEDED.

### Features That Should Have Helped
- document_type
- unmet_need_score
- regulatory_flexibility
- safety_manageability
- advisory_question_polarity
- likely_panel_vote_direction

### Proposed Prompt Fix
Require the model to separate FDA critical tone from endpoint success, safety manageability, unmet need, regulatory flexibility, likely panel vote, and final FDA approval probability.

### Proposed Signal Rule Fix
Apply FDA briefing de-noising and positive adjustments for high unmet need, high regulatory flexibility, and manageable safety risks before mapping to final signal.


## Case 2: Opill

Source JSON: `data/history_runs/2252b7c3b1118d54.json`

### Model Signal
STRONG_NEGATIVE

### Model Probability
30

### Model Confidence
90

### Key Concerns Extracted by Model
- Improbable dosing data undermines adherence reliability
- Inadequate deselection by breast cancer patients
- Low comprehension of abnormal bleeding warning
- Concomitant hormonal contraceptive use despite warnings
- Adolescent comprehension gaps
- Limited literacy underrepresentation
- Unknown efficacy in overweight/obese population

### Key Positives Extracted by Model
- Potential to increase access to more effective contraception
- Nonprescription availability may reduce unintended pregnancies

### Why the Model Likely Overreacted
The local record suggests the model weighted FDA risk language more heavily than contextual approval factors. This should be validated against primary sources before treating it as a final lesson.

### Final Regulatory Outcome
- adcom_vote: 17-0 favorable
- adcom_outcome: positive
- fda_final_decision: approved
- fda_decision_date: 2023-07-13
- outcome_source: FDA approval press release; public reports of 17-0 advisory committee vote
- notes: Committees voted unanimously in favor; FDA approved first OTC daily oral contraceptive on 2023-07-13.

### Why Final Outcome Diverged from Harsh FDA Tone
Insufficient local data. TODO_SOURCE_NEEDED.

### Features That Should Have Helped
- document_type
- unmet_need_score
- regulatory_flexibility
- safety_manageability
- advisory_question_polarity
- likely_panel_vote_direction

### Proposed Prompt Fix
Require the model to separate FDA critical tone from endpoint success, safety manageability, unmet need, regulatory flexibility, likely panel vote, and final FDA approval probability.

### Proposed Signal Rule Fix
Apply FDA briefing de-noising and positive adjustments for high unmet need, high regulatory flexibility, and manageable safety risks before mapping to final signal.


## General Lessons

- FDA briefing tone is structurally critical and risk-focused.
- Harsh FDA language does not automatically imply rejection.
- Risk can be acceptable if it is manageable through labeling, REMS, restricted use, or monitoring.
- High unmet need, rare disease context, public health value, and lack of alternatives can create regulatory flexibility.
- The model must distinguish AdCom vote direction from final FDA approval probability.
